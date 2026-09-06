"""
URL configuration for devcastle project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import dashboard_redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('analytics/', include('analytics.urls')),
    path('quizzes/', include('quizzes.urls')),
    path('reports/', include('reports.urls')),
    path('announcements/', include('announcements.urls')),
    path('assignments/', include('assignments.urls')),
    path('', dashboard_redirect, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)