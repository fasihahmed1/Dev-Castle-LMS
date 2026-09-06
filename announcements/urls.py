from django.urls import path

from . import views

app_name = 'announcements'

urlpatterns = [
    path('', views.manage_list, name='manage'),
    path('feed/', views.student_feed, name='feed'),
    path('create/', views.announcement_create, name='create'),
    path('<int:pk>/edit/', views.announcement_edit, name='edit'),
    path('<int:pk>/delete/', views.announcement_delete, name='delete'),
]
