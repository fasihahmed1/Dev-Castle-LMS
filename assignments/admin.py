from django.contrib import admin

from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'class_name', 'section', 'due_date', 'posted_by', 'created_at')
    list_filter = ('class_name', 'section')
    search_fields = ('title',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at', 'is_late')
    list_filter = ('is_late',)
