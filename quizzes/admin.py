from django.contrib import admin

from .models import Question, Quiz, QuizAttempt, StudentAnswer


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_name', 'section', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'class_name', 'subject')
    search_fields = ('title', 'subject')
    inlines = [QuestionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student', 'score', 'started_at', 'submitted_at')
    list_filter = ('quiz',)
    readonly_fields = ('shuffled_question_order', 'shuffled_option_map')


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_option', 'is_correct')
