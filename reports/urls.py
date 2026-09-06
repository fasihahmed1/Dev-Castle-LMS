from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),
    path("students/<int:pk>/", views.student_report, name="student"),
    path("students/<int:pk>/pdf/", views.student_report_pdf, name="student_pdf"),
    path("class/", views.class_report, name="class"),
    path("class/pdf/", views.class_report_pdf, name="class_pdf"),
    path("quizzes/<int:pk>/", views.quiz_report, name="quiz"),
    path("quizzes/<int:pk>/pdf/", views.quiz_report_pdf, name="quiz_pdf"),
]
