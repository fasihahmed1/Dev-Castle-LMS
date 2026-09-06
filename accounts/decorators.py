from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Profile


def role_required(*allowed_roles):
    """
    Restrict a view to users whose profile.role is in allowed_roles.
    Must be applied below @login_required (or used with LoginRequiredMixin).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            try:
                user_role = request.user.profile.role
            except Profile.DoesNotExist:
                raise PermissionDenied('User profile not found.')

            if user_role not in allowed_roles:
                return redirect('accounts:dashboard_redirect')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
