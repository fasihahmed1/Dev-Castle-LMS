from django import forms
from django.contrib.auth.models import User

from .models import Student


class StudentCreateForm(forms.ModelForm):
    """Creates a User (STUDENT role) and linked Student in one submission."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Login password for the student account.',
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Student
        fields = [
            'roll_number',
            'full_name',
            'class_name',
            'section',
            'date_of_birth',
            'contact_number',
            'guardian_name',
        ]
        widgets = {
            'roll_number': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'class_name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_roll_number(self):
        roll_number = self.cleaned_data['roll_number'].strip()
        if Student.objects.filter(roll_number=roll_number).exists():
            raise forms.ValidationError('A student with this roll number already exists.')
        return roll_number

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class StudentEditForm(forms.ModelForm):
    """Edit student details and optional linked user email."""

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Student
        fields = [
            'roll_number',
            'full_name',
            'class_name',
            'section',
            'date_of_birth',
            'contact_number',
            'guardian_name',
        ]
        widgets = {
            'roll_number': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'class_name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['email'].initial = self.instance.user.email

    def clean_roll_number(self):
        roll_number = self.cleaned_data['roll_number'].strip()
        qs = Student.objects.filter(roll_number=roll_number).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A student with this roll number already exists.')
        return roll_number


class StudentFilterForm(forms.Form):
    """Search and filter controls for the student list."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search name or roll number…',
        }),
    )
    class_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Class',
        }),
    )
    section = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Section',
        }),
    )
