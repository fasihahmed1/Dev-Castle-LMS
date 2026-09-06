from django.contrib import messages
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import Profile
from students.models import Student

from .forms import AssignmentForm, SubmissionUploadForm
from .models import Assignment, AssignmentSubmission
from .services import save_submission


def _can_manage_assignment(user, assignment):
    role = user.profile.role
    if role == Profile.Role.ADMIN:
        return True
    if role == Profile.Role.TEACHER:
        return assignment.posted_by_id == user.pk
    return False


def _get_student_profile(request):
    if hasattr(request.user, 'student_profile'):
        return request.user.student_profile
    return None


def _assignment_stats(assignment):
    """Return (submitted_count, total_students) for an assignment."""
    total = Student.objects.filter(
        class_name=assignment.class_name,
        section=assignment.section,
    ).count()
    submitted = assignment.submissions.count()
    return submitted, total


# ── Teacher / Admin ───────────────────────────────────────────────────────────

@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def manage_list(request):
    assignments = Assignment.objects.select_related('posted_by').annotate(
        submission_count=Count('submissions'),
    )
    if request.user.profile.role == Profile.Role.TEACHER:
        assignments = assignments.filter(posted_by=request.user)

    rows = []
    for assignment in assignments:
        submitted, total = _assignment_stats(assignment)
        rows.append({
            'assignment': assignment,
            'submitted': submitted,
            'total': total,
        })

    return render(request, 'assignments/manage_list.html', {
        'rows': rows,
        'is_admin': request.user.profile.role == Profile.Role.ADMIN,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def assignment_create(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.posted_by = request.user
            assignment.save()
            messages.success(request, f'Assignment "{assignment.title}" created.')
            return redirect('assignments:manage')
    else:
        form = AssignmentForm(initial={
            'due_date': timezone.now().replace(hour=23, minute=59, second=0, microsecond=0),
        })

    return render(request, 'assignments/assignment_form.html', {
        'form': form,
        'form_title': 'New Assignment',
        'submit_label': 'Create Assignment',
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def assignment_edit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not _can_manage_assignment(request.user, assignment):
        messages.error(request, 'You can only edit your own assignments.')
        return redirect('assignments:manage')

    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Assignment updated.')
            return redirect('assignments:manage')
    else:
        form = AssignmentForm(instance=assignment)

    return render(request, 'assignments/assignment_form.html', {
        'form': form,
        'form_title': 'Edit Assignment',
        'submit_label': 'Save Changes',
        'assignment': assignment,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def assignment_delete(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not _can_manage_assignment(request.user, assignment):
        messages.error(request, 'You can only delete your own assignments.')
        return redirect('assignments:manage')

    if request.method == 'POST':
        title = assignment.title
        assignment.delete()
        messages.success(request, f'Assignment "{title}" deleted.')
        return redirect('assignments:manage')

    return render(request, 'assignments/assignment_confirm_delete.html', {
        'assignment': assignment,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related('posted_by'), pk=pk)
    if not _can_manage_assignment(request.user, assignment):
        return redirect('assignments:manage')

    students = Student.objects.filter(
        class_name=assignment.class_name,
        section=assignment.section,
    ).order_by('roll_number')

    submissions = {
        s.student_id: s
        for s in assignment.submissions.select_related('student')
    }

    roster = []
    for student in students:
        sub = submissions.get(student.pk)
        roster.append({'student': student, 'submission': sub})

    submitted, total = _assignment_stats(assignment)

    return render(request, 'assignments/assignment_detail.html', {
        'assignment': assignment,
        'roster': roster,
        'submitted': submitted,
        'total': total,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER, Profile.Role.STUDENT)
def submission_download(request, pk):
    """Download a submission file — teachers/admins for their assignments; students own only."""
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related('assignment', 'student'),
        pk=pk,
    )
    role = request.user.profile.role

    if role == Profile.Role.STUDENT:
        student = _get_student_profile(request)
        if not student or submission.student_id != student.pk:
            raise Http404
    elif role == Profile.Role.TEACHER:
        if not _can_manage_assignment(request.user, submission.assignment):
            raise Http404
    elif role != Profile.Role.ADMIN:
        raise Http404

    if not submission.submitted_file:
        raise Http404

    return FileResponse(
        submission.submitted_file.open('rb'),
        as_attachment=True,
        filename=submission.submitted_file.name.split('/')[-1],
    )


# ── Student ───────────────────────────────────────────────────────────────────

@role_required(Profile.Role.STUDENT)
def student_list(request):
    student = _get_student_profile(request)
    if not student:
        messages.error(request, 'No student profile linked to your account.')
        return redirect('accounts:dashboard_student')

    assignments = Assignment.objects.filter(
        class_name=student.class_name,
        section=student.section,
    ).order_by('due_date')

    submissions = {
        s.assignment_id: s
        for s in AssignmentSubmission.objects.filter(student=student)
    }

    rows = []
    for assignment in assignments:
        sub = submissions.get(assignment.pk)
        if sub:
            status = 'late' if sub.is_late else 'on_time'
        else:
            status = 'not_submitted'
        rows.append({
            'assignment': assignment,
            'submission': sub,
            'status': status,
        })

    return render(request, 'assignments/student_list.html', {'rows': rows})


@role_required(Profile.Role.STUDENT)
def student_submit(request, pk):
    student = _get_student_profile(request)
    if not student:
        return redirect('accounts:dashboard_student')

    assignment = get_object_or_404(Assignment, pk=pk)
    if not assignment.matches_student(student):
        raise Http404

    existing = AssignmentSubmission.objects.filter(
        assignment=assignment,
        student=student,
    ).first()

    if request.method == 'POST':
        form = SubmissionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            submission = save_submission(
                assignment=assignment,
                student=student,
                uploaded_file=form.cleaned_data['submitted_file'],
            )
            if submission.is_late:
                messages.warning(request, 'Submitted after the due date — marked as late.')
            else:
                messages.success(request, 'Assignment submitted successfully.')
            return redirect('assignments:student_list')
    else:
        form = SubmissionUploadForm()

    return render(request, 'assignments/student_submit.html', {
        'assignment': assignment,
        'form': form,
        'existing': existing,
    })
