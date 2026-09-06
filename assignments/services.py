from django.db import transaction
from django.utils import timezone

from .models import AssignmentSubmission


@transaction.atomic
def save_submission(*, assignment, student, uploaded_file):
    """
    Create or replace a student's submission for an assignment.

    Re-submission replaces the previous file. is_late is computed at upload time:
    submissions after due_date are flagged late; uploads before due_date set
    is_late=False even when replacing a prior attempt.
    """
    now = timezone.now()
    is_late = AssignmentSubmission.compute_is_late(assignment, now)

    try:
        submission = AssignmentSubmission.objects.select_for_update().get(
            assignment=assignment,
            student=student,
        )
        if submission.submitted_file:
            submission.submitted_file.delete(save=False)
    except AssignmentSubmission.DoesNotExist:
        submission = AssignmentSubmission(assignment=assignment, student=student)

    submission.submitted_file = uploaded_file
    submission.submitted_at = now
    submission.is_late = is_late
    submission.save()

    return submission
