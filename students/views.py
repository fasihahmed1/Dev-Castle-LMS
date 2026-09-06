from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import StudentCreateForm, StudentEditForm, StudentFilterForm
from .models import Student
from .services import create_student_with_user, delete_student_with_user, update_student_with_user

STUDENTS_PER_PAGE = 15


def _filter_students(queryset, filter_form):
    if not filter_form.is_valid():
        return queryset

    q = filter_form.cleaned_data.get('q', '').strip()
    class_name = filter_form.cleaned_data.get('class_name', '').strip()
    section = filter_form.cleaned_data.get('section', '').strip()

    if q:
        queryset = queryset.filter(
            Q(full_name__icontains=q) | Q(roll_number__icontains=q),
        )
    if class_name:
        queryset = queryset.filter(class_name__icontains=class_name)
    if section:
        queryset = queryset.filter(section__icontains=section)

    return queryset


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def student_list(request):
    """Paginated student list with search and filters (Admin & Teacher)."""
    filter_form = StudentFilterForm(request.GET or None)
    queryset = Student.objects.select_related('user').all()
    queryset = _filter_students(queryset, filter_form)

    paginator = Paginator(queryset, STUDENTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'students/student_list.html', {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'is_admin': request.user.profile.role == Profile.Role.ADMIN,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def student_create(request):
    """Create User + Student together (Admin & Teacher)."""
    if request.method == 'POST':
        form = StudentCreateForm(request.POST)
        if form.is_valid():
            student_fields = {
                field: form.cleaned_data[field]
                for field in form.Meta.fields
            }
            student = create_student_with_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                email=form.cleaned_data.get('email', ''),
                student_fields=student_fields,
            )
            messages.success(request, f'Student {student.full_name} created successfully.')
            return redirect('students:detail', pk=student.pk)
    else:
        form = StudentCreateForm()

    return render(request, 'students/student_form.html', {
        'form': form,
        'form_title': 'Add Student',
        'submit_label': 'Create Student',
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def student_edit(request, pk):
    """Edit student details (Admin & Teacher)."""
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)

    if request.method == 'POST':
        form = StudentEditForm(request.POST, instance=student)
        if form.is_valid():
            student_fields = {
                field: form.cleaned_data[field]
                for field in form.Meta.fields
            }
            update_student_with_user(
                student=student,
                student_fields=student_fields,
                email=form.cleaned_data.get('email', ''),
            )
            messages.success(request, f'Student {student.full_name} updated successfully.')
            return redirect('students:detail', pk=student.pk)
    else:
        form = StudentEditForm(instance=student)

    return render(request, 'students/student_form.html', {
        'form': form,
        'form_title': f'Edit {student.full_name}',
        'submit_label': 'Save Changes',
        'student': student,
    })


@role_required(Profile.Role.ADMIN)
def student_delete(request, pk):
    """Delete student and linked User (Admin only)."""
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)

    if request.method == 'POST':
        name = student.full_name
        delete_student_with_user(student)
        messages.success(request, f'Student {name} deleted successfully.')
        return redirect('students:list')

    return render(request, 'students/student_confirm_delete.html', {
        'student': student,
    })


def _can_view_student(request, student):
    role = request.user.profile.role
    if role in (Profile.Role.ADMIN, Profile.Role.TEACHER):
        return True
    if role == Profile.Role.STUDENT:
        return (
            hasattr(request.user, 'student_profile')
            and request.user.student_profile.pk == student.pk
        )
    return False


@role_required(
    Profile.Role.ADMIN,
    Profile.Role.TEACHER,
    Profile.Role.STUDENT,
)
def student_detail(request, pk):
    """View student profile — own record only for Student role."""
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)

    if not _can_view_student(request, student):
        return redirect('accounts:dashboard_redirect')

    is_admin = request.user.profile.role == Profile.Role.ADMIN
    can_edit = request.user.profile.role in (Profile.Role.ADMIN, Profile.Role.TEACHER)

    return render(request, 'students/student_detail.html', {
        'student': student,
        'is_admin': is_admin,
        'can_edit': can_edit,
    })


@role_required(Profile.Role.STUDENT)
def my_profile(request):
    """Redirect a logged-in student to their own profile page."""
    if not hasattr(request.user, 'student_profile'):
        messages.error(request, 'No student profile is linked to your account.')
        return redirect('accounts:dashboard_student')

    return redirect('students:detail', pk=request.user.student_profile.pk)
