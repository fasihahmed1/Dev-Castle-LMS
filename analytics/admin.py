from django.contrib import admin

from .models import PerformanceRecord, UploadBatch


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'class_name', 'uploaded_by', 'status', 'row_count', 'uploaded_at')
    list_filter = ('status', 'class_name')
    search_fields = ('class_name', 'uploaded_by__username')
    readonly_fields = ('uploaded_at',)


@admin.register(PerformanceRecord)
class PerformanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'subject',
        'marks_obtained',
        'total_marks',
        'attendance_percentage',
        'upload_batch',
        'created_at',
    )
    list_filter = ('subject', 'upload_batch')
    search_fields = ('student__roll_number', 'subject')
