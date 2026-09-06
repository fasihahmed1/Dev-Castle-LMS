from django.urls import path

from . import views

app_name = 'quizzes'

urlpatterns = [
    # Teacher / Admin
    path('', views.quiz_list, name='list'),
    path('create/', views.quiz_create, name='create'),
    path('upload/', views.quiz_bulk_upload, name='bulk_upload'),
    path('<int:pk>/', views.quiz_detail, name='detail'),
    path('<int:pk>/edit/', views.quiz_edit, name='edit'),
    path('<int:pk>/questions/', views.quiz_edit_questions, name='edit_questions'),
    path('<int:pk>/attempts/', views.quiz_attempts, name='attempts'),

    # Student
    path('my/', views.student_quiz_list, name='student_list'),
    path('<int:pk>/start/', views.quiz_start, name='start'),
    path('<int:pk>/notice/', views.quiz_notice, name='notice'),
    path('<int:pk>/begin/', views.quiz_begin, name='begin'),
    path('attempt/<int:attempt_id>/take/', views.quiz_take, name='take'),
    path('attempt/<int:attempt_id>/submit/', views.quiz_submit, name='submit'),
    path('attempt/<int:attempt_id>/violation/', views.record_violation_view, name='record_violation'),
    path('attempt/<int:attempt_id>/disqualified/', views.quiz_disqualified, name='disqualified'),
    path('attempt/<int:attempt_id>/result/', views.quiz_result, name='result'),
]
