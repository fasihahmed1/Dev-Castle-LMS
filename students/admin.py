from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'roll_number',
        'full_name',
        'class_name',
        'section',
        'user',
        'created_at',
    )
    list_filter = ('class_name', 'section')
    search_fields = ('roll_number', 'full_name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('roll_number',)
