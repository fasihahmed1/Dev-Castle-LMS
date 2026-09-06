from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'posted_by', 'audience_label', 'is_active', 'created_at')
    list_filter = ('is_active', 'class_name')
    search_fields = ('title', 'body')
    readonly_fields = ('created_at', 'updated_at')
