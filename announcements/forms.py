from django import forms

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'class_name', 'section', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'class_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leave blank for all students',
            }),
            'section': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional — requires class name',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'class_name': 'Leave blank to broadcast to every student.',
            'section': 'Optional. Only used when a class name is set.',
        }

    def clean(self):
        cleaned = super().clean()
        class_name = (cleaned.get('class_name') or '').strip() or None
        section = (cleaned.get('section') or '').strip() or None

        cleaned['class_name'] = class_name
        cleaned['section'] = section

        if section and not class_name:
            raise forms.ValidationError(
                'Section cannot be set without a class name. Leave both blank for a global announcement.'
            )

        return cleaned
