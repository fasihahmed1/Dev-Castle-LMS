from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect

from .models import Profile


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin for class-based views that require specific profile roles."""

    allowed_roles = ()

    def test_func(self):
        try:
            return self.request.user.profile.role in self.allowed_roles
        except Profile.DoesNotExist:
            return False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('accounts:dashboard_redirect')
        return super().handle_no_permission()
