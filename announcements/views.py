from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import AnnouncementForm
from .models import Announcement


def _can_manage_announcement(user, announcement):
    role = user.profile.role
    if role == Profile.Role.ADMIN:
        return True
    if role == Profile.Role.TEACHER:
        return announcement.posted_by_id == user.pk
    return False


def _get_student_profile(request):
    if hasattr(request.user, 'student_profile'):
        return request.user.student_profile
    return None


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def manage_list(request):
    """List announcements for Teacher/Admin management."""
    announcements = Announcement.objects.select_related('posted_by')
    if request.user.profile.role == Profile.Role.TEACHER:
        announcements = announcements.filter(posted_by=request.user)

    is_admin = request.user.profile.role == Profile.Role.ADMIN

    return render(request, 'announcements/manage_list.html', {
        'announcements': announcements,
        'is_admin': is_admin,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def announcement_create(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.posted_by = request.user
            announcement.save()
            messages.success(request, 'Announcement posted.')
            return redirect('announcements:manage')
    else:
        form = AnnouncementForm()

    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'form_title': 'New Announcement',
        'submit_label': 'Post Announcement',
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def announcement_edit(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if not _can_manage_announcement(request.user, announcement):
        messages.error(request, 'You can only edit your own announcements.')
        return redirect('announcements:manage')

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Announcement updated.')
            return redirect('announcements:manage')
    else:
        form = AnnouncementForm(instance=announcement)

    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'form_title': 'Edit Announcement',
        'submit_label': 'Save Changes',
        'announcement': announcement,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if not _can_manage_announcement(request.user, announcement):
        messages.error(request, 'You can only delete your own announcements.')
        return redirect('announcements:manage')

    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f'Announcement "{title}" deleted.')
        return redirect('announcements:manage')

    return render(request, 'announcements/announcement_confirm_delete.html', {
        'announcement': announcement,
    })


@role_required(Profile.Role.STUDENT)
def student_feed(request):
    """Read-only announcement list for students."""
    student = _get_student_profile(request)
    if not student:
        messages.error(request, 'No student profile linked to your account.')
        return redirect('accounts:dashboard_student')

    announcements = Announcement.objects.filter(is_active=True).select_related('posted_by')

    visible = [
        a for a in announcements
        if a.is_visible_to_student(student)
    ]

    return render(request, 'announcements/student_feed.html', {
        'announcements': visible,
    })
