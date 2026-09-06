from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .decorators import role_required
from .models import Profile

ROLE_DASHBOARD_URLS = {
    Profile.Role.ADMIN: 'accounts:dashboard_admin',
    Profile.Role.TEACHER: 'accounts:dashboard_teacher',
    Profile.Role.STUDENT: 'accounts:dashboard_student',
}


class RoleLoginView(LoginView):
    """Login view that redirects users to their role-specific dashboard."""

    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        role = self.request.user.profile.role
        return reverse(ROLE_DASHBOARD_URLS.get(role, 'accounts:dashboard_student'))


def logout_view(request):
    """Log out the current user and redirect to login."""
    logout(request)
    return redirect('accounts:login')


def dashboard_redirect(request):
    """Send authenticated users to the dashboard matching their role."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    try:
        role = request.user.profile.role
    except Profile.DoesNotExist:
        logout(request)
        return redirect('accounts:login')

    return redirect(ROLE_DASHBOARD_URLS.get(role, 'accounts:dashboard_student'))


@role_required(Profile.Role.ADMIN)
def dashboard_admin(request):
    return render(request, 'accounts/dashboard_admin.html', {
        'role_display': Profile.Role.ADMIN.label,
    })


@role_required(Profile.Role.TEACHER)
def dashboard_teacher(request):
    return render(request, 'accounts/dashboard_teacher.html', {
        'role_display': Profile.Role.TEACHER.label,
    })


@role_required(Profile.Role.STUDENT)
def dashboard_student(request):
    return render(request, 'accounts/dashboard_student.html', {
        'role_display': Profile.Role.STUDENT.label,
    })
