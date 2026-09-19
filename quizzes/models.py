from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Quiz(models.Model):
    """A quiz for all students or a specific class (and optional section)."""

    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    class_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Leave blank to make this quiz available to all students.',
    )
    section = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Optional section filter when class_name is set.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quizzes_created',
    )
    is_active = models.BooleanField(default=False)
    timer_enabled = models.BooleanField(default=False)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    anti_cheat_enabled = models.BooleanField(default=False)
    max_violations_allowed = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'quizzes'

    def __str__(self):
        return self.title

    @property
    def requires_pre_quiz_notice(self):
        return self.timer_enabled or self.anti_cheat_enabled

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def is_global(self):
        return not self.class_name

    @property
    def audience_label(self):
        if self.is_global:
            return 'All students'
        if self.section:
            return f'{self.class_name} / Section {self.section}'
        return f'{self.class_name} (all sections)'

    def is_visible_to_student(self, student) -> bool:
        if not self.is_active:
            return False
        if self.is_global:
            return True
        if student.class_name != self.class_name:
            return False
        if self.section and student.section != self.section:
            return False
        return True


class Question(models.Model):
    """A single multiple-choice question belonging to a quiz."""

    class OptionChoice(models.TextChoices):
        A = 'A', 'A'
        B = 'B', 'B'
        C = 'C', 'C'
        D = 'D', 'D'

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(max_length=1, choices=OptionChoice.choices)
    marks = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return self.question_text[:60]

    def get_option_text(self, letter):
        """Return option text for a stored option letter (A–D)."""
        return getattr(self, f'option_{letter.lower()}', '')


class QuizAttempt(models.Model):
    """One student's attempt at a quiz with persisted shuffle state."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    shuffled_question_order = models.JSONField(
        help_text='List of question IDs in the order shown to this student.',
    )
    shuffled_option_map = models.JSONField(
        help_text='Dict mapping question ID (str) to shuffled option letter order.',
    )
    time_expires = models.DateTimeField(null=True, blank=True)
    violation_count = models.PositiveIntegerField(default=0)
    violation_log = models.JSONField(default=list, blank=True)
    disqualified = models.BooleanField(default=False)
    auto_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']
        unique_together = [('quiz', 'student')]

    def __str__(self):
        return f'{self.student.roll_number} — {self.quiz.title}'

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    @property
    def is_in_progress(self):
        return self.submitted_at is None and not self.disqualified

    @property
    def is_timer_expired(self):
        if not self.time_expires:
            return False
        from django.utils import timezone
        return timezone.now() >= self.time_expires


class StudentAnswer(models.Model):
    """A single answer within a quiz attempt."""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers',
    )
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField(null=True, blank=True)

    class Meta:
        unique_together = [('attempt', 'question')]

    def __str__(self):
        return f'{self.attempt_id} — Q{self.question_id}: {self.selected_option}'
