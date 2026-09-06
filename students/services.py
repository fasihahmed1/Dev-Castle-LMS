from django.contrib.auth.models import User
from django.db import transaction

from accounts.models import Profile

from .models import Student


@transaction.atomic
def create_student_with_user(*, username, password, email, student_fields):
    """
    Create a User (role=STUDENT) and linked Student record atomically.

    Input shape:  username/password/email strings; student_fields dict for Student model.
    Output shape: Student instance.
    """
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email or '',
    )
    user.profile.role = Profile.Role.STUDENT
    user.profile.save(update_fields=['role', 'updated_at'])

    return Student.objects.create(user=user, **student_fields)


@transaction.atomic
def update_student_with_user(*, student, student_fields, email):
    """Update Student fields and linked User email atomically."""
    for field, value in student_fields.items():
        setattr(student, field, value)
    student.save()

    if email is not None:
        student.user.email = email
        student.user.save(update_fields=['email'])

    return student


@transaction.atomic
def delete_student_with_user(student):
    """Delete Student and linked User (cascades Profile)."""
    user = student.user
    student.delete()
    user.delete()
