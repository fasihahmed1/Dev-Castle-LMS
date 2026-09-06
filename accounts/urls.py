from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.RoleLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/teacher/', views.dashboard_teacher, name='dashboard_teacher'),
    path('dashboard/student/', views.dashboard_student, name='dashboard_student'),
]
