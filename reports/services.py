from __future__ import annotations

from io import BytesIO
from typing import Any

from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from accounts.models import Profile
from analytics.chart import (
    attendance_by_subject_chart,
    grade_distribution_chart,
    performance_by_subject_chart,
    quiz_score_distribution_chart,
)
from analytics.models import PerformanceRecord
from quizzes.models import Quiz, QuizAttempt
from students.models import Student

PASS_PERCENTAGE = 50


def get_student_for_report(user, pk: int) -> Student:
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk)
    role = user.profile.role

    if role in (Profile.Role.ADMIN, Profile.Role.TEACHER):
        return student
    if role == Profile.Role.STUDENT and hasattr(user, "student_profile") and user.student_profile.pk == student.pk:
        return student

    raise Http404


def get_manageable_quiz(user, pk: int) -> Quiz:
    quiz = get_object_or_404(Quiz.objects.select_related("created_by").prefetch_related("questions"), pk=pk)
    role = user.profile.role

    if role == Profile.Role.ADMIN:
        return quiz
    if role == Profile.Role.TEACHER and quiz.created_by_id == user.pk:
        return quiz

    raise Http404


def percentage(record: PerformanceRecord) -> float:
    total = float(record.total_marks or 0)
    if total <= 0:
        return 0.0
    return round((float(record.marks_obtained) / total) * 100, 2)


def grade_for_percentage(value: float) -> str:
    if value >= 80:
        return "A"
    if value >= 70:
        return "B"
    if value >= 60:
        return "C"
    if value >= 50:
        return "D"
    return "F"


def student_report_context(user, pk: int) -> dict[str, Any]:
    student = get_student_for_report(user, pk)
    performance_records = list(
        PerformanceRecord.objects
        .filter(student=student)
        .select_related("upload_batch")
        .order_by("-created_at", "subject")
    )
    attempts = list(
        QuizAttempt.objects
        .filter(student=student)
        .select_related("quiz")
        .order_by("-started_at")
    )

    performance_rows = [
        {
            "record": record,
            "percentage": percentage(record),
            "grade": grade_for_percentage(percentage(record)),
        }
        for record in performance_records
    ]

    average_percentage = None
    average_attendance = None
    if performance_records:
        percentages = [row["percentage"] for row in performance_rows]
        average_percentage = round(sum(percentages) / len(percentages), 2)
        average_attendance = round(
            sum(float(record.attendance_percentage) for record in performance_records) / len(performance_records),
            2,
        )

    return {
        "student": student,
        "performance_rows": performance_rows,
        "quiz_attempts": attempts,
        "summary": {
            "record_count": len(performance_records),
            "average_percentage": average_percentage,
            "average_attendance": average_attendance,
            "quiz_attempt_count": len(attempts),
        },
        "charts": {
            "performance_by_subject": performance_by_subject_chart(performance_records),
            "attendance_by_subject": attendance_by_subject_chart(performance_records),
        },
    }


def class_report_context(class_name: str, section: str) -> dict[str, Any]:
    students = Student.objects.filter(class_name=class_name, section=section).order_by("roll_number")
    records = list(
        PerformanceRecord.objects
        .filter(student__class_name=class_name, student__section=section)
        .select_related("student", "upload_batch")
        .order_by("student__roll_number", "subject")
    )

    percentages = [percentage(record) for record in records]
    pass_count = sum(1 for value in percentages if value >= PASS_PERCENTAGE)
    fail_count = len(percentages) - pass_count

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for value in percentages:
        grade_counts[grade_for_percentage(value)] += 1

    average_marks = round(sum(percentages) / len(percentages), 2) if percentages else None
    average_attendance = (
        round(sum(float(record.attendance_percentage) for record in records) / len(records), 2)
        if records else None
    )

    subject_rows = []
    for subject in sorted({record.subject for record in records}):
        subject_records = [record for record in records if record.subject == subject]
        subject_percentages = [percentage(record) for record in subject_records]
        subject_rows.append({
            "subject": subject,
            "records": len(subject_records),
            "average_percentage": round(sum(subject_percentages) / len(subject_percentages), 2),
            "average_attendance": round(
                sum(float(record.attendance_percentage) for record in subject_records) / len(subject_records),
                2,
            ),
        })

    return {
        "class_name": class_name,
        "section": section,
        "students": students,
        "records": records,
        "subject_rows": subject_rows,
        "summary": {
            "student_count": students.count(),
            "record_count": len(records),
            "average_marks": average_marks,
            "average_attendance": average_attendance,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "grade_counts": grade_counts,
        },
        "charts": {
            "performance_by_subject": performance_by_subject_chart(records),
            "attendance_by_subject": attendance_by_subject_chart(records),
            "grade_distribution": grade_distribution_chart(records),
        },
    }


def quiz_report_context(user, pk: int) -> dict[str, Any]:
    quiz = get_manageable_quiz(user, pk)
    attempts = list(
        QuizAttempt.objects
        .filter(quiz=quiz, submitted_at__isnull=False)
        .select_related("student")
        .order_by("-submitted_at")
    )
    scores = [float(attempt.score) for attempt in attempts if attempt.score is not None]
    total_marks = quiz.questions.aggregate(total=Sum("marks"))["total"] or 0

    return {
        "quiz": quiz,
        "attempts": attempts,
        "summary": {
            "attempt_count": len(attempts),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "highest_score": max(scores) if scores else None,
            "lowest_score": min(scores) if scores else None,
            "total_marks": total_marks,
        },
        "charts": {
            "score_distribution": quiz_score_distribution_chart(attempts, float(total_marks) if total_marks else None),
        },
    }


def class_choices() -> list[dict[str, str]]:
    return list(
        Student.objects
        .values("class_name", "section")
        .annotate(student_count=Count("id"))
        .order_by("class_name", "section")
    )


def quiz_choices(user):
    quizzes = Quiz.objects.select_related("created_by").order_by("-created_at")
    if user.profile.role == Profile.Role.TEACHER:
        quizzes = quizzes.filter(created_by=user)
    return quizzes


def render_pdf_response(request, template_name: str, context: dict[str, Any], filename: str) -> HttpResponse:
    html = render_to_string(template_name, context, request=request)
    pdf_bytes = _html_to_pdf(html, request)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _html_to_pdf(html: str, request) -> bytes:
    base_url = request.build_absolute_uri("/")
    try:
        from weasyprint import HTML
    except ImportError:
        HTML = None

    if HTML is not None:
        return HTML(string=html, base_url=base_url).write_pdf()

    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise RuntimeError("Install WeasyPrint or xhtml2pdf to enable PDF export.") from exc

    output = BytesIO()
    result = pisa.CreatePDF(src=html, dest=output, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF generation failed.")
    return output.getvalue()
