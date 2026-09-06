from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import CSVUploadForm
from .models import UploadBatch
from .services import (
    parse_csv_upload,
    parse_skipped_rows,
    persist_upload_batch,
    recompute_stats_for_batch,
)


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def upload_performance_csv(request):
    """Upload and preprocess a performance CSV (Teacher & Admin only)."""
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            outcome = parse_csv_upload(form.cleaned_data['csv_file'])

            if not outcome.is_structurally_valid:
                return render(request, 'analytics/upload.html', {
                    'form': form,
                    'structural_errors': outcome.structural_errors,
                })

            batch = persist_upload_batch(
                uploaded_by=request.user,
                class_name=form.cleaned_data['class_name'].strip(),
                outcome=outcome,
            )

            if batch.status == UploadBatch.Status.FAILED:
                messages.warning(
                    request,
                    'Upload completed with no valid rows. Review skipped rows below.',
                )
            else:
                messages.success(
                    request,
                    f'Successfully imported {batch.row_count} record(s).',
                )

            return redirect('analytics:upload_summary', batch_id=batch.pk)
    else:
        form = CSVUploadForm()

    return render(request, 'analytics/upload.html', {'form': form})


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def upload_summary(request, batch_id):
    """Show processing summary for a single upload batch."""
    batch = get_object_or_404(
        UploadBatch.objects.select_related('uploaded_by'),
        pk=batch_id,
    )
    skipped = parse_skipped_rows(batch.error_log)
    stats = recompute_stats_for_batch(batch)

    return render(request, 'analytics/upload_summary.html', {
        'batch': batch,
        'processed_count': batch.row_count,
        'skipped_count': len(skipped),
        'skipped_rows': skipped,
        'stats': stats,
    })


@role_required(Profile.Role.ADMIN, Profile.Role.TEACHER)
def upload_history(request):
    """List past upload batches (Teacher & Admin only)."""
    batches = UploadBatch.objects.select_related('uploaded_by').all()
    if request.user.profile.role == Profile.Role.TEACHER:
        batches = batches.filter(uploaded_by=request.user)

    return render(request, 'analytics/upload_history.html', {
        'batches': batches,
    })
