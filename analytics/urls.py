from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('upload/', views.upload_performance_csv, name='upload'),
    path('upload/history/', views.upload_history, name='upload_history'),
    path('upload/<int:batch_id>/summary/', views.upload_summary, name='upload_summary'),
]
