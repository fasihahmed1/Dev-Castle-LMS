from django.conf import settings
from django.db import models

from students.models import Student


class UploadBatch(models.Model):
    """Tracks a single CSV upload event and its processing outcome."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSED = 'processed', 'Processed'
        FAILED = 'failed', 'Failed'

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='upload_batches',
    )
    class_name = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    row_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.class_name} — {self.uploaded_at:%Y-%m-%d %H:%M} ({self.get_status_display()})'


class PerformanceRecord(models.Model):
    """Structured performance row imported from a validated CSV upload."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='performance_records',
    )
    subject = models.CharField(max_length=100)
    marks_obtained = models.DecimalField(max_digits=7, decimal_places=2)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    upload_batch = models.ForeignKey(
        UploadBatch,
        on_delete=models.CASCADE,
        related_name='performance_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student__roll_number', 'subject']

    def __str__(self):
        return f'{self.student.roll_number} — {self.subject}'
