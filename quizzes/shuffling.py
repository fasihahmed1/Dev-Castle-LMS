"""
Quiz shuffling and grading utilities.

Shuffling is generated once per QuizAttempt and persisted in the database.
It must never be recomputed on page load — always read from the attempt record.

Option mapping:
    shuffled_option_map[str(question_id)] = ['C', 'A', 'D', 'B']
    means the student sees display A → stored C, display B → stored A, etc.
    selected_option on StudentAnswer is the DISPLAY letter (A–D) the student clicked.
"""

from __future__ import annotations

import random
from decimal import Decimal

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Question, Quiz, QuizAttempt, StudentAnswer

OPTION_LETTERS = ['A', 'B', 'C', 'D']


def generate_shuffle_state(quiz: Quiz, seed: int) -> tuple[list[int], dict[str, list[str]]]:
    """
    Generate shuffled question order and per-question option order.

    Input shape:  Quiz with questions; integer seed for reproducibility.
    Output shape: (question_id_list, option_map_dict)
        question_id_list — e.g. [3, 1, 5]
        option_map_dict  — e.g. {'3': ['C','A','D','B'], '1': ['B','D','A','C']}
    """
    rng = random.Random(seed)
    question_ids = list(quiz.questions.values_list('pk', flat=True))
    rng.shuffle(question_ids)

    option_map: dict[str, list[str]] = {}
    for qid in question_ids:
        letters = OPTION_LETTERS.copy()
        rng.shuffle(letters)
        option_map[str(qid)] = letters

    return question_ids, option_map


@transaction.atomic
def create_quiz_attempt(*, quiz: Quiz, student) -> QuizAttempt:
    """
    Create a QuizAttempt with persisted shuffle state.

    Uses attempt PK as shuffle seed after initial insert (single transaction).
    Raises ValueError if quiz has no questions or student already submitted.
    """
    if not quiz.questions.exists():
        raise ValueError('This quiz has no questions yet.')

    existing = QuizAttempt.objects.filter(quiz=quiz, student=student).first()
    if existing:
        if existing.is_submitted:
            raise ValueError('You have already completed this quiz.')
        return existing

    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=student,
        shuffled_question_order=[],
        shuffled_option_map={},
    )

    seed = attempt.pk * 1_000_003 + student.pk * 9_173 + quiz.pk
    question_order, option_map = generate_shuffle_state(quiz, seed=seed)
    attempt.shuffled_question_order = question_order
    attempt.shuffled_option_map = option_map

    if quiz.timer_enabled and quiz.duration_minutes:
        now = timezone.now()
        attempt.started_at = now
        attempt.time_expires = now + timedelta(minutes=quiz.duration_minutes)

    attempt.save(update_fields=[
        'shuffled_question_order',
        'shuffled_option_map',
        'started_at',
        'time_expires',
    ])

    return attempt


def get_display_options(question: Question, shuffled_letters: list[str]) -> list[dict]:
    """
    Build display-ready options for a question using persisted shuffle order.

    Output shape: list of {'display': 'A', 'text': '...'} in shuffled order.
    """
    return [
        {
            'display': display_letter,
            'text': question.get_option_text(stored_letter),
        }
        for display_letter, stored_letter in zip(OPTION_LETTERS, shuffled_letters)
    ]


def display_to_stored_option(display_letter: str, shuffled_letters: list[str]) -> str:
    """Map a display letter (what the student selected) back to the stored A–D option."""
    index = OPTION_LETTERS.index(display_letter.upper())
    return shuffled_letters[index]


def grade_attempt(
    attempt: QuizAttempt,
    answers: dict[str, str],
    *,
    auto_submitted: bool = False,
) -> Decimal:
    """
    Grade a quiz attempt and persist StudentAnswer rows and score.

    Input shape:  answers dict mapping question_id (str) → display letter (A–D).
    Output shape: Decimal total score awarded.
    """
    if attempt.is_submitted or attempt.disqualified:
        raise ValueError('This attempt has already been finalized.')

    if attempt.quiz.timer_enabled and attempt.is_timer_expired and not auto_submitted:
        auto_submitted = True

    total_score = Decimal('0')
    questions_by_id = {
        str(q.pk): q for q in attempt.quiz.questions.all()
    }

    answer_objects = []
    for qid_str in attempt.shuffled_question_order:
        qid_str = str(qid_str)
        question = questions_by_id.get(qid_str)
        if not question:
            continue

        selected_display = (answers.get(qid_str) or '').upper()
        shuffled = attempt.shuffled_option_map.get(qid_str, OPTION_LETTERS)

        if selected_display in OPTION_LETTERS:
            stored_option = display_to_stored_option(selected_display, shuffled)
            is_correct = stored_option == question.correct_option
            if is_correct:
                total_score += Decimal(str(question.marks))
        else:
            is_correct = False

        answer_objects.append(StudentAnswer(
            attempt=attempt,
            question=question,
            selected_option=selected_display or '',
            is_correct=is_correct,
        ))

    StudentAnswer.objects.bulk_create(answer_objects)

    attempt.score = total_score
    attempt.submitted_at = timezone.now()
    attempt.auto_submitted = auto_submitted
    attempt.save(update_fields=['score', 'submitted_at', 'auto_submitted'])

    return total_score


@transaction.atomic
def disqualify_attempt(attempt: QuizAttempt) -> QuizAttempt:
    """Disqualify an attempt — score zero, no further access."""
    attempt = QuizAttempt.objects.select_for_update().select_related('quiz').get(pk=attempt.pk)

    if attempt.disqualified or attempt.is_submitted:
        return attempt

    attempt.disqualified = True
    attempt.auto_submitted = True
    attempt.score = Decimal('0')
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=['disqualified', 'auto_submitted', 'score', 'submitted_at'])
    return attempt


def auto_submit_on_timer(attempt: QuizAttempt, answers: dict[str, str] | None = None) -> Decimal:
    """Auto-submit when the server-side timer expires — graded normally, not disqualified."""
    answers = answers or {}
    return grade_attempt(attempt, answers, auto_submitted=True)


VALID_VIOLATION_TYPES = {'tab_switch', 'window_blur'}


@transaction.atomic
def record_violation(attempt: QuizAttempt, violation_type: str) -> dict:
    """
    Record a tab-switch or window-blur violation server-side.

    Returns dict with violation_count, max_allowed, disqualified, message.
    """
    if violation_type not in VALID_VIOLATION_TYPES:
        raise ValueError(f'Invalid violation type: {violation_type}')

    attempt = QuizAttempt.objects.select_for_update().select_related('quiz').get(pk=attempt.pk)

    if not attempt.quiz.anti_cheat_enabled:
        return {
            'violation_count': attempt.violation_count,
            'max_allowed': attempt.quiz.max_violations_allowed,
            'disqualified': False,
            'message': '',
        }

    if attempt.disqualified or attempt.is_submitted:
        return {
            'violation_count': attempt.violation_count,
            'max_allowed': attempt.quiz.max_violations_allowed,
            'disqualified': attempt.disqualified,
            'message': 'Attempt already finalized.',
        }

    log = list(attempt.violation_log or [])
    log.append({
        'type': violation_type,
        'timestamp': timezone.now().isoformat(),
    })
    attempt.violation_log = log
    attempt.violation_count += 1

    max_allowed = attempt.quiz.max_violations_allowed or 3
    disqualified = attempt.violation_count >= max_allowed

    if disqualified:
        attempt.disqualified = True
        attempt.auto_submitted = True
        attempt.score = Decimal('0')
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=[
            'violation_log', 'violation_count', 'disqualified',
            'auto_submitted', 'score', 'submitted_at',
        ])
        return {
            'violation_count': attempt.violation_count,
            'max_allowed': max_allowed,
            'disqualified': True,
            'message': 'Disqualified due to repeated tab/window switching.',
        }

    attempt.save(update_fields=['violation_log', 'violation_count'])
    remaining = max_allowed - attempt.violation_count
    return {
        'violation_count': attempt.violation_count,
        'max_allowed': max_allowed,
        'disqualified': False,
        'message': (
            f'Tab switch detected ({attempt.violation_count}/{max_allowed}). '
            f'{remaining} more will disqualify this attempt.'
        ),
    }
