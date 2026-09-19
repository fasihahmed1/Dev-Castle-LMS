import json

from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import AttemptFilterForm, QuestionFormSet, QuizBulkUploadForm, QuizForm
from .models import Quiz, QuizAttempt
from .services import create_quiz_from_csv
from .shuffling import (
    auto_submit_on_timer,
    create_quiz_attempt,
    get_display_options,
    grade_attempt,
    record_violation,
)


def _get_student_profile(request):
    if not hasattr(request.user, 'student_profile'):
        return None
    return request.user.student_profile


def _can_manage_quiz(user, quiz):
    role = user.profile.role
    if role == Profile.Role.ADMIN:
        return True
    if role == Profile.Role.TEACHER:
        return quiz.created_by_id == user.pk
    return False


def _get_owned_attempt(request, attempt_id):
    """Return attempt only if the current student owns it."""
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz', 'student'),
        pk=attempt_id,
    )
    student = _get_student_profile(request)
    if not student or attempt.student_id != student.pk:
        raise Http404
    return attempt


def _parse_answers(request):
    return {
        key.replace('question_', ''): value
        for key, value in request.POST.items()
        if key.startswith('question_')
    }


def _build_take_context(attempt, display_questions):
    quiz = attempt.quiz
    return {
        'attempt': attempt,
        'display_questions': display_questions,
        'timer_enabled': quiz.timer_enabled,
        'time_expires_iso': attempt.time_expires.isoformat() if attempt.time_expires else '',
        'anti_cheat_enabled': quiz.anti_cheat_enabled,
        'max_violations': quiz.max_violations_allowed or 3,
        'violation_count': attempt.violation_count,
    }


def _get_display_questions(attempt):
    questions_by_id = {q.pk: q for q in attempt.quiz.questions.all()}
    display_questions = []
    for qid in attempt.shuffled_question_order:
        question = questions_by_id.get(qid)
        if not question:
            continue
        shuffled = attempt.shuffled_option_map.get(str(qid), ['A', 'B', 'C', 'D'])
        display_questions.append({
            'question': question,
            'options': get_display_options(question, shuffled),
        })
    return display_questions


def _handle_attempt_finalization(request, attempt):
    """Redirect if attempt is disqualified, submitted, or timer-expired."""
    attempt.refresh_from_db()

    if attempt.disqualified:
        return redirect('quizzes:disqualified', attempt_id=attempt.pk)

    if attempt.is_submitted:
        return redirect('quizzes:result', attempt_id=attempt.pk)

    if attempt.quiz.timer_enabled and attempt.is_timer_expired:
        auto_submit_on_timer(attempt, _parse_answers(request) if request.method == 'POST' else {})
        messages.info(request, 'Time is up — your quiz was auto-submitted.')
        return redirect('quizzes:result', attempt_id=attempt.pk)

    return None


# ── Teacher / Admin views ─────────────────────────────────────────────────────

@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_list(request):
    quizzes = Quiz.objects.select_related('created_by').prefetch_related('questions')
    if request.user.profile.role == Profile.Role.TEACHER:
        quizzes = quizzes.filter(created_by=request.user)
    return render(request, 'quizzes/quiz_list.html', {'quizzes': quizzes})


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_create(request):
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.created_by = request.user
            quiz.save()
            messages.success(request, f'Quiz "{quiz.title}" created. Now add questions.')
            return redirect('quizzes:edit_questions', pk=quiz.pk)
    else:
        form = QuizForm(initial={'max_violations_allowed': 3})

    return render(request, 'quizzes/quiz_form.html', {
        'form': form,
        'form_title': 'Create Quiz',
        'submit_label': 'Create & Add Questions',
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_bulk_upload(request):
    if request.method == 'POST':
        form = QuizBulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            quiz_fields = {
                'title': form.cleaned_data['title'],
                'subject': form.cleaned_data['subject'],
                'class_name': form.cleaned_data['class_name'],
                'section': form.cleaned_data['section'],
                'is_active': form.cleaned_data.get('is_active', False),
            }
            quiz, outcome = create_quiz_from_csv(
                quiz_fields=quiz_fields,
                file_obj=form.cleaned_data['csv_file'],
                created_by=request.user,
            )
            if quiz:
                messages.success(
                    request,
                    f'Quiz "{quiz.title}" created with {quiz.question_count} question(s).',
                )
                return redirect('quizzes:detail', pk=quiz.pk)

            return render(request, 'quizzes/quiz_bulk_upload.html', {
                'form': form,
                'structural_errors': outcome.structural_errors,
                'row_errors': [e.as_text() for e in outcome.row_errors],
            })
    else:
        form = QuizBulkUploadForm()

    return render(request, 'quizzes/quiz_bulk_upload.html', {'form': form})


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_detail(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related('created_by'), pk=pk)
    if not _can_manage_quiz(request.user, quiz):
        return redirect('quizzes:list')

    return render(request, 'quizzes/quiz_detail.html', {
        'quiz': quiz,
        'is_admin': request.user.profile.role == Profile.Role.ADMIN,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_edit(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not _can_manage_quiz(request.user, quiz):
        return redirect('quizzes:list')

    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, 'Quiz updated.')
            return redirect('quizzes:detail', pk=quiz.pk)
    else:
        form = QuizForm(instance=quiz)

    return render(request, 'quizzes/quiz_form.html', {
        'form': form,
        'form_title': f'Edit {quiz.title}',
        'submit_label': 'Save Changes',
        'quiz': quiz,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_edit_questions(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not _can_manage_quiz(request.user, quiz):
        return redirect('quizzes:list')

    if request.method == 'POST':
        formset = QuestionFormSet(request.POST, instance=quiz)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Questions saved.')
            return redirect('quizzes:detail', pk=quiz.pk)
    else:
        formset = QuestionFormSet(instance=quiz)

    return render(request, 'quizzes/quiz_questions_formset.html', {
        'quiz': quiz,
        'formset': formset,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_attempts(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not _can_manage_quiz(request.user, quiz):
        return redirect('quizzes:list')

    filter_form = AttemptFilterForm(request.GET or None)
    attempts = (
        QuizAttempt.objects
        .filter(quiz=quiz, submitted_at__isnull=False)
        .select_related('student')
    )

    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q', '').strip()
        sort = filter_form.cleaned_data.get('sort') or '-submitted_at'
        if q:
            attempts = attempts.filter(
                Q(student__full_name__icontains=q) | Q(student__roll_number__icontains=q),
            )
        attempts = attempts.order_by(sort)
    else:
        attempts = attempts.order_by('-submitted_at')

    return render(request, 'quizzes/quiz_attempts.html', {
        'quiz': quiz,
        'attempts': attempts,
        'filter_form': filter_form,
    })


# ── Student views ─────────────────────────────────────────────────────────────

@role_required(Profile.Role.STUDENT)
def student_quiz_list(request):
    student = _get_student_profile(request)
    if not student:
        messages.error(request, 'No student profile linked to your account.')
        return redirect('accounts:dashboard_student')

    completed_ids = QuizAttempt.objects.filter(
        student=student,
        submitted_at__isnull=False,
    ).values_list('quiz_id', flat=True)

    available = Quiz.objects.filter(is_active=True).filter(
        Q(class_name__isnull=True)
        | Q(class_name='')
        | (
            Q(class_name=student.class_name)
            & (Q(section__isnull=True) | Q(section='') | Q(section=student.section))
        ),
    ).exclude(pk__in=completed_ids).prefetch_related('questions')

    in_progress = QuizAttempt.objects.filter(
        student=student,
        submitted_at__isnull=True,
        disqualified=False,
    ).select_related('quiz')

    return render(request, 'quizzes/student_quiz_list.html', {
        'available_quizzes': available,
        'in_progress': in_progress,
    })


@role_required(Profile.Role.STUDENT)
def quiz_notice(request, pk):
    """Pre-quiz notice screen when timer or anti-cheat is enabled."""
    student = _get_student_profile(request)
    if not student:
        return redirect('accounts:dashboard_student')

    quiz = get_object_or_404(Quiz, pk=pk, is_active=True)
    if not quiz.is_visible_to_student(student):
        raise Http404

    if not quiz.requires_pre_quiz_notice:
        return redirect('quizzes:begin', pk=quiz.pk)

    existing = QuizAttempt.objects.filter(quiz=quiz, student=student).first()
    if existing:
        if existing.disqualified:
            return redirect('quizzes:disqualified', attempt_id=existing.pk)
        if existing.is_submitted:
            return redirect('quizzes:result', attempt_id=existing.pk)
        return redirect('quizzes:take', attempt_id=existing.pk)

    return render(request, 'quizzes/quiz_notice.html', {'quiz': quiz})


@role_required(Profile.Role.STUDENT)
def quiz_begin(request, pk):
    """POST only — start the attempt after the pre-quiz notice."""
    if request.method != 'POST':
        return redirect('quizzes:student_list')

    student = _get_student_profile(request)
    if not student:
        return redirect('accounts:dashboard_student')

    quiz = get_object_or_404(Quiz, pk=pk, is_active=True)
    if not quiz.is_visible_to_student(student):
        raise Http404

    try:
        attempt = create_quiz_attempt(quiz=quiz, student=student)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('quizzes:student_list')

    return redirect('quizzes:take', attempt_id=attempt.pk)


@role_required(Profile.Role.STUDENT)
def quiz_start(request, pk):
    """Direct start for quizzes without timer/anti-cheat notice."""
    if request.method != 'POST':
        return redirect('quizzes:student_list')

    student = _get_student_profile(request)
    if not student:
        return redirect('accounts:dashboard_student')

    quiz = get_object_or_404(Quiz, pk=pk, is_active=True)
    if not quiz.is_visible_to_student(student):
        raise Http404

    if quiz.requires_pre_quiz_notice:
        return redirect('quizzes:notice', pk=quiz.pk)

    try:
        attempt = create_quiz_attempt(quiz=quiz, student=student)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('quizzes:student_list')

    return redirect('quizzes:take', attempt_id=attempt.pk)


@role_required(Profile.Role.STUDENT)
def quiz_take(request, attempt_id):
    attempt = _get_owned_attempt(request, attempt_id)

    redirect_response = _handle_attempt_finalization(request, attempt)
    if redirect_response:
        return redirect_response

    display_questions = _get_display_questions(attempt)
    return render(request, 'quizzes/quiz_take.html', _build_take_context(attempt, display_questions))


@role_required(Profile.Role.STUDENT)
def quiz_submit(request, attempt_id):
    if request.method != 'POST':
        return redirect('quizzes:take', attempt_id=attempt_id)

    attempt = _get_owned_attempt(request, attempt_id)

    if attempt.disqualified:
        return redirect('quizzes:disqualified', attempt_id=attempt.pk)

    if attempt.is_submitted:
        return redirect('quizzes:result', attempt_id=attempt.pk)

    if attempt.quiz.timer_enabled and attempt.is_timer_expired:
        auto_submit_on_timer(attempt, _parse_answers(request))
        messages.info(request, 'Time is up — your quiz was auto-submitted.')
        return redirect('quizzes:result', attempt_id=attempt.pk)

    grade_attempt(attempt, _parse_answers(request))
    messages.success(request, f'Quiz submitted! Your score: {attempt.score}')
    return redirect('quizzes:result', attempt_id=attempt.pk)


@role_required(Profile.Role.STUDENT)
@require_POST
def record_violation_view(request, attempt_id):
    """Server-side violation recording for anti-cheat."""
    attempt = _get_owned_attempt(request, attempt_id)

    if not attempt.quiz.anti_cheat_enabled:
        return JsonResponse({'error': 'Anti-cheat not enabled.'}, status=400)

    if attempt.disqualified or attempt.is_submitted:
        return JsonResponse({
            'violation_count': attempt.violation_count,
            'max_allowed': attempt.quiz.max_violations_allowed,
            'disqualified': attempt.disqualified,
            'message': 'Attempt already finalized.',
        })

    try:
        body = json.loads(request.body)
        violation_type = body.get('type', '')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    result = record_violation(attempt, violation_type)
    return JsonResponse(result)


@role_required(Profile.Role.STUDENT)
def quiz_disqualified(request, attempt_id):
    attempt = _get_owned_attempt(request, attempt_id)
    if not attempt.disqualified:
        return redirect('quizzes:take', attempt_id=attempt.pk)
    return render(request, 'quizzes/quiz_disqualified.html', {'attempt': attempt})


@role_required(Profile.Role.STUDENT)
def quiz_result(request, attempt_id):
    attempt = _get_owned_attempt(request, attempt_id)

    if attempt.disqualified:
        return redirect('quizzes:disqualified', attempt_id=attempt.pk)

    if not attempt.is_submitted:
        return redirect('quizzes:take', attempt_id=attempt.pk)

    answers = attempt.answers.select_related('question').all()
    return render(request, 'quizzes/quiz_result.html', {
        'attempt': attempt,
        'answers': answers,
    })
