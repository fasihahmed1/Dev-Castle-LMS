import os

from django import forms
from django.core.exceptions import ValidationError

from .models import Assignment

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.zip'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_submission_file(uploaded_file):
    """Server-side validation for assignment submission files."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f'File type "{ext}" is not allowed. '
            f'Accepted types: {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
        )
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError('File size must not exceed 10 MB.')
    if uploaded_file.size == 0:
        raise ValidationError('The uploaded file is empty.')


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'class_name', 'section', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'class_name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control'}),
            'due_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['due_date'].input_formats = ['%Y-%m-%dT%H:%M']


class SubmissionUploadForm(forms.Form):
    submitted_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.zip',
        }),
        help_text='Allowed: PDF, DOC, DOCX, ZIP — max 10 MB.',
    )

    def clean_submitted_file(self):
        uploaded = self.cleaned_data['submitted_file']
        validate_submission_file(uploaded)
        return uploaded
