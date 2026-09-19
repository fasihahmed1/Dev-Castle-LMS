from django import forms
from django.forms import inlineformset_factory

from .models import Question, Quiz


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = [
            'title', 'subject', 'class_name', 'section', 'is_active',
            'timer_enabled', 'duration_minutes',
            'anti_cheat_enabled', 'max_violations_allowed',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'class_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leave blank for all students',
            }),
            'section': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional — requires class name',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_active'}),
            'timer_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_timer_enabled'}),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'id': 'id_duration_minutes',
            }),
            'anti_cheat_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_anti_cheat_enabled',
            }),
            'max_violations_allowed': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'id': 'id_max_violations_allowed',
            }),
        }
        labels = {
            'duration_minutes': 'Duration (minutes)',
            'max_violations_allowed': 'Disqualify after N violations',
        }
        help_texts = {
            'class_name': 'Leave blank to make this quiz available to all students.',
            'section': 'Optional. Only used when a class name is set.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duration_minutes'].required = False
        self.fields['max_violations_allowed'].required = False
        self.fields['class_name'].required = False
        self.fields['section'].required = False

    def clean(self):
        cleaned = super().clean()
        timer_enabled = cleaned.get('timer_enabled')
        duration = cleaned.get('duration_minutes')
        anti_cheat = cleaned.get('anti_cheat_enabled')
        max_violations = cleaned.get('max_violations_allowed')

        class_name = (cleaned.get('class_name') or '').strip() or None
        section = (cleaned.get('section') or '').strip() or None
        cleaned['class_name'] = class_name
        cleaned['section'] = section

        if section and not class_name:
            raise forms.ValidationError(
                'Section cannot be set without a class name. Leave both blank for all students.'
            )

        if timer_enabled:
            if not duration or duration < 1:
                self.add_error('duration_minutes', 'Duration is required when the timer is enabled.')
        else:
            cleaned['duration_minutes'] = None

        if anti_cheat:
            if not max_violations or max_violations < 1:
                self.add_error(
                    'max_violations_allowed',
                    'Max violations is required when anti-cheat is enabled.',
                )
        else:
            cleaned['max_violations_allowed'] = None

        return cleaned


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'marks',
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'option_a': forms.TextInput(attrs={'class': 'form-control'}),
            'option_b': forms.TextInput(attrs={'class': 'form-control'}),
            'option_c': forms.TextInput(attrs={'class': 'form-control'}),
            'option_d': forms.TextInput(attrs={'class': 'form-control'}),
            'correct_option': forms.Select(attrs={'class': 'form-select'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


QuestionFormSet = inlineformset_factory(
    Quiz,
    Question,
    form=QuestionForm,
    extra=3,
    can_delete=True,
)


class QuizBulkUploadForm(forms.Form):
    """Create a quiz and populate questions from a CSV file."""

    title = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    subject = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    class_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank for all students'}),
        help_text='Leave blank to make this quiz available to all students.',
    )
    section = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional — requires class name'}),
    )
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    csv_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
        help_text='Columns: question_text, option_a–d, correct_option, marks (optional).',
    )

    def clean(self):
        cleaned = super().clean()
        class_name = (cleaned.get('class_name') or '').strip() or None
        section = (cleaned.get('section') or '').strip() or None
        cleaned['class_name'] = class_name
        cleaned['section'] = section
        if section and not class_name:
            raise forms.ValidationError(
                'Section cannot be set without a class name. Leave both blank for all students.'
            )
        return cleaned

    def clean_csv_file(self):
        uploaded = self.cleaned_data['csv_file']
        if not uploaded.name.lower().endswith('.csv'):
            raise forms.ValidationError('Only .csv files are accepted.')
        if uploaded.size == 0:
            raise forms.ValidationError('The uploaded file is empty.')
        return uploaded


class AttemptFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search student name or roll #…'}),
    )
    sort = forms.ChoiceField(
        required=False,
        label='Sort by',
        choices=[
            ('-submitted_at', 'Newest first'),
            ('submitted_at', 'Oldest first'),
            ('-score', 'Highest score'),
            ('score', 'Lowest score'),
            ('student__full_name', 'Name A–Z'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
