import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def submission_upload_path(instance, filename):
    """Store under media/assignments/YYYY/MM/assignment_<id>/<roll_number>/"""
    safe_name = os.path.basename(filename)
    due = instance.assignment.created_at
    return (
        f'assignments/{due:%Y/%m}/assignment_{instance.assignment_id}/'
        f'{instance.student.roll_number}/{uuid.uuid4().hex}_{safe_name}'
    )


class Assignment(models.Model):
    """An assignment posted to a specific class and section."""

    title = models.CharField(max_length=200)
    description = models.TextField()
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignments_posted',
    )
    class_name = models.CharField(max_length=100)
    section = models.CharField(max_length=50)
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return self.title

    @property
    def is_past_due(self):
        return timezone.now() > self.due_date

    def matches_student(self, student) -> bool:
        return (
            student.class_name == self.class_name
            and student.section == self.section
        )


class AssignmentSubmission(models.Model):
    """A student's file submission for an assignment."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
    )
    submitted_file = models.FileField(upload_to=submission_upload_path)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_late = models.BooleanField(default=False)

    class Meta:
        unique_together = [('assignment', 'student')]
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.student.roll_number} — {self.assignment.title}'

    @staticmethod
    def compute_is_late(assignment, at_time=None):
        """Return True if submission time is after the assignment due date."""
        at_time = at_time or timezone.now()
        return at_time > assignment.due_date
