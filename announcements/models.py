from django.conf import settings
from django.db import models


class Announcement(models.Model):
    """One-way broadcast from Teacher/Admin to students."""

    title = models.CharField(max_length=200)
    body = models.TextField()
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='announcements',
    )
    class_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Leave blank to broadcast to all students.',
    )
    section = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Optional section filter when class_name is set.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

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
        """Return True if this active announcement applies to the given student."""
        if not self.is_active:
            return False
        if self.is_global:
            return True
        if student.class_name != self.class_name:
            return False
        if self.section and student.section != self.section:
            return False
        return True
