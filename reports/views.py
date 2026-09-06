from django.contrib import messages
from django.http import Http404, HttpResponseServerError
from django.shortcuts import redirect, render

from accounts.decorators import role_required
from accounts.models import Profile

from .services import (
    class_choices,
    class_report_context,
    quiz_choices,
    quiz_report_context,
    render_pdf_response,
    student_report_context,
)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER, Profile.Role.STUDENT)
def report_index(request):
    role = request.user.profile.role
    context = {
        "role": role,
        "class_choices": [],
        "quiz_choices": [],
    }

    if role in (Profile.Role.ADMIN, Profile.Role.TEACHER):
        context["class_choices"] = class_choices()
        context["quiz_choices"] = quiz_choices(request.user)
    elif hasattr(request.user, "student_profile"):
        context["student"] = request.user.student_profile

    return render(request, "reports/index.html", context)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER, Profile.Role.STUDENT)
def student_report(request, pk):
    context = student_report_context(request.user, pk)
    return render(request, "reports/student_report.html", context)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER, Profile.Role.STUDENT)
def student_report_pdf(request, pk):
    context = student_report_context(request.user, pk)
    return _pdf_or_error(
        request,
        "reports/pdf/student_report.html",
        context,
        f"student-report-{context['student'].roll_number}.pdf",
    )


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def class_report(request):
    class_name = request.GET.get("class_name", "").strip()
    section = request.GET.get("section", "").strip()

    if not class_name or not section:
        messages.info(request, "Choose a class and section to view a class report.")
        return redirect("reports:index")

    context = class_report_context(class_name, section)
    return render(request, "reports/class_report.html", context)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def class_report_pdf(request):
    class_name = request.GET.get("class_name", "").strip()
    section = request.GET.get("section", "").strip()
    if not class_name or not section:
        raise Http404

    context = class_report_context(class_name, section)
    return _pdf_or_error(
        request,
        "reports/pdf/class_report.html",
        context,
        f"class-report-{class_name}-{section}.pdf",
    )


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_report(request, pk):
    context = quiz_report_context(request.user, pk)
    return render(request, "reports/quiz_report.html", context)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def quiz_report_pdf(request, pk):
    context = quiz_report_context(request.user, pk)
    return _pdf_or_error(
        request,
        "reports/pdf/quiz_report.html",
        context,
        f"quiz-report-{context['quiz'].pk}.pdf",
    )


def _pdf_or_error(request, template_name, context, filename):
    try:
        return render_pdf_response(request, template_name, context, filename)
    except RuntimeError as exc:
        return HttpResponseServerError(str(exc))
