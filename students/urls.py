from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='list'),
    path('add/', views.student_create, name='create'),
    path('profile/', views.my_profile, name='my_profile'),
    path('<int:pk>/', views.student_detail, name='detail'),
    path('<int:pk>/edit/', views.student_edit, name='edit'),
    path('<int:pk>/delete/', views.student_delete, name='delete'),
]
