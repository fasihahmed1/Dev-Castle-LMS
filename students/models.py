from django.conf import settings
from django.db import models


class Student(models.Model):
    """Student profile linked to a STUDENT-role User account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
    )
    roll_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    class_name = models.CharField(max_length=100)
    section = models.CharField(max_length=50)
    date_of_birth = models.DateField(null=True, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    guardian_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['roll_number']

    def __str__(self):
        return f'{self.roll_number} — {self.full_name}'
