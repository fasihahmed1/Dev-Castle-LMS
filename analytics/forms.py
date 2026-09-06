from django import forms


class CSVUploadForm(forms.Form):
    """Form for uploading a performance CSV file."""

    class_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. CS-2024-A',
        }),
        help_text='Class or section label for this upload batch.',
    )
    csv_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,text/csv',
        }),
        help_text='CSV with columns: roll_number, subject, marks_obtained, total_marks, attendance_percentage.',
    )

    def clean_csv_file(self):
        uploaded = self.cleaned_data['csv_file']
        if not uploaded.name.lower().endswith('.csv'):
            raise forms.ValidationError('Only .csv files are accepted.')
        if uploaded.size == 0:
            raise forms.ValidationError('The uploaded file is empty.')
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File size must not exceed 5 MB.')
        return uploaded
