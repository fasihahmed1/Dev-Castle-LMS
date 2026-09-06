"""
CSV upload validation and preprocessing for performance data.

Expected CSV schema (header row required, exact column names):
    roll_number          — str, must match an existing Student.roll_number (whitespace stripped)
    subject              — str, non-empty subject name
    marks_obtained       — numeric, >= 0 and <= total_marks
    total_marks          — numeric, > 0
    attendance_percentage — numeric, 0–100 inclusive

Assumptions:
    - One row represents one student–subject record for the uploaded class batch.
    - Duplicate (roll_number, subject) pairs within the same file are rejected (second occurrence skipped).
    - Rows with unknown roll_number are skipped with a row-level error; valid rows still import.
    - Structural problems (missing columns, empty file, unreadable CSV) abort before any DB write.
    - class_name is provided via the upload form, not the CSV (one class per upload batch).

Input shape:  file-like object or bytes → pandas DataFrame with REQUIRED_COLUMNS.
Output shape: ParseOutcome with valid_rows list[dict], row_errors list[RowError], optional stats dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import BinaryIO

import pandas as pd
from django.db import transaction

from analytics.models import PerformanceRecord, UploadBatch
from students.models import Student

REQUIRED_COLUMNS = [
    'roll_number',
    'subject',
    'marks_obtained',
    'total_marks',
    'attendance_percentage',
]

NUMERIC_COLUMNS = ['marks_obtained', 'total_marks', 'attendance_percentage']


@dataclass
class RowError:
    """A single row-level validation failure."""

    row_number: int
    message: str

    def as_text(self) -> str:
        return f'Row {self.row_number}: {self.message}'


@dataclass
class ParseOutcome:
    """Result of in-memory CSV parsing and validation (no DB writes)."""

    structural_errors: list[str] = field(default_factory=list)
    row_errors: list[RowError] = field(default_factory=list)
    valid_rows: list[dict] = field(default_factory=list)
    stats: dict | None = None

    @property
    def is_structurally_valid(self) -> bool:
        return not self.structural_errors

    @property
    def processed_count(self) -> int:
        return len(self.valid_rows)

    @property
    def skipped_count(self) -> int:
        return len(self.row_errors)


def _read_csv(file_obj: BinaryIO) -> tuple[pd.DataFrame | None, list[str]]:
    """
    Read uploaded file into a DataFrame.

    Returns:
        (DataFrame, errors) — DataFrame is None when reading fails.
    """
    errors: list[str] = []
    try:
        raw = file_obj.read()
        if not raw.strip():
            return None, ['The uploaded file is empty.']
        df = pd.read_csv(BytesIO(raw))
    except Exception as exc:
        return None, [f'Could not read CSV file: {exc}']

    if df.empty:
        return None, ['The CSV file contains no data rows.']

    return df, errors


def _validate_structure(df: pd.DataFrame) -> list[str]:
    """Check required columns are present (case-insensitive header match)."""
    errors: list[str] = []
    normalized = {col.strip().lower(): col for col in df.columns}
    missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
    if missing:
        errors.append(
            'Missing required column(s): '
            + ', '.join(missing)
            + f'. Expected columns: {", ".join(REQUIRED_COLUMNS)}.'
        )
        return errors

    rename_map = {normalized[col]: col for col in REQUIRED_COLUMNS}
    df.rename(columns=rename_map, inplace=True)
    return errors


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip whitespace from string columns and coerce numeric columns.

    Input shape:  DataFrame with REQUIRED_COLUMNS.
    Output shape: Same columns; blanks in strings become NaN; numerics coerced.
    """
    cleaned = df[REQUIRED_COLUMNS].copy()
    cleaned['roll_number'] = cleaned['roll_number'].astype(str).str.strip()
    cleaned['subject'] = cleaned['subject'].astype(str).str.strip()
    cleaned.loc[cleaned['roll_number'].isin(['', 'nan', 'None']), 'roll_number'] = pd.NA
    cleaned.loc[cleaned['subject'].isin(['', 'nan', 'None']), 'subject'] = pd.NA

    for col in NUMERIC_COLUMNS:
        cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')

    return cleaned


def _validate_rows(df: pd.DataFrame, students_by_roll: dict[str, Student]) -> tuple[list[dict], list[RowError]]:
    """
    Validate each row and return importable records plus row errors.

    Input shape:  cleaned DataFrame (REQUIRED_COLUMNS).
    Output shape: valid_rows list of dicts with keys matching PerformanceRecord fields;
                  row_errors list of RowError (1-based CSV line numbers, header = row 1).
    """
    valid_rows: list[dict] = []
    row_errors: list[RowError] = []
    seen_pairs: set[tuple[str, str]] = set()

    for idx, row in df.iterrows():
        row_number = int(idx) + 2  # pandas 0-index + header row

        roll = row['roll_number']
        subject = row['subject']

        if pd.isna(roll) or not str(roll).strip():
            row_errors.append(RowError(row_number, 'roll_number is missing or blank.'))
            continue

        roll_key = str(roll).strip()
        if pd.isna(subject) or not str(subject).strip():
            row_errors.append(RowError(row_number, f"roll_number '{roll_key}': subject is missing or blank."))
            continue

        subject_key = str(subject).strip()

        pair = (roll_key, subject_key)
        if pair in seen_pairs:
            row_errors.append(
                RowError(
                    row_number,
                    f"duplicate entry for roll_number '{roll_key}' and subject '{subject_key}'.",
                )
            )
            continue
        seen_pairs.add(pair)

        if roll_key not in students_by_roll:
            row_errors.append(
                RowError(row_number, f"roll_number '{roll_key}' not found in Student records.")
            )
            continue

        if any(pd.isna(row[col]) for col in NUMERIC_COLUMNS):
            row_errors.append(
                RowError(
                    row_number,
                    f"roll_number '{roll_key}': invalid or missing numeric value(s) "
                    f"({', '.join(NUMERIC_COLUMNS)}).",
                )
            )
            continue

        marks_obtained = float(row['marks_obtained'])
        total_marks = float(row['total_marks'])
        attendance = float(row['attendance_percentage'])

        if total_marks <= 0:
            row_errors.append(
                RowError(row_number, f"roll_number '{roll_key}': total_marks must be greater than 0.")
            )
            continue

        if marks_obtained < 0:
            row_errors.append(
                RowError(row_number, f"roll_number '{roll_key}': marks_obtained cannot be negative.")
            )
            continue

        if marks_obtained > total_marks:
            row_errors.append(
                RowError(
                    row_number,
                    f"roll_number '{roll_key}': marks_obtained ({marks_obtained}) "
                    f"exceeds total_marks ({total_marks}).",
                )
            )
            continue

        if attendance < 0 or attendance > 100:
            row_errors.append(
                RowError(
                    row_number,
                    f"roll_number '{roll_key}': attendance_percentage must be between 0 and 100.",
                )
            )
            continue

        valid_rows.append({
            'student': students_by_roll[roll_key],
            'subject': subject_key,
            'marks_obtained': marks_obtained,
            'total_marks': total_marks,
            'attendance_percentage': attendance,
        })

    return valid_rows, row_errors


def compute_batch_stats(valid_rows: list[dict]) -> dict | None:
    """
    Compute summary statistics from validated rows using Pandas.

    Input shape:  list of dicts with marks_obtained, total_marks, attendance_percentage, subject.
    Output shape: dict with class_average_pct, attendance stats, per-subject averages, min/max marks.
    """
    if not valid_rows:
        return None

    df = pd.DataFrame(valid_rows)
    df['percentage'] = (df['marks_obtained'] / df['total_marks']) * 100

    subject_stats = (
        df.groupby('subject')['percentage']
        .agg(['mean', 'count'])
        .reset_index()
        .rename(columns={'mean': 'average_pct', 'count': 'record_count'})
    )
    per_subject = [
        {
            'subject': row['subject'],
            'average_pct': round(float(row['average_pct']), 2),
            'record_count': int(row['record_count']),
        }
        for _, row in subject_stats.iterrows()
    ]

    return {
        'class_average_pct': round(float(df['percentage'].mean()), 2),
        'attendance_average': round(float(df['attendance_percentage'].mean()), 2),
        'attendance_min': round(float(df['attendance_percentage'].min()), 2),
        'attendance_max': round(float(df['attendance_percentage'].max()), 2),
        'marks_min': round(float(df['marks_obtained'].min()), 2),
        'marks_max': round(float(df['marks_obtained'].max()), 2),
        'per_subject': per_subject,
    }


def parse_csv_upload(file_obj: BinaryIO) -> ParseOutcome:
    """
    Parse and validate a CSV upload entirely in memory.

    No database writes occur in this function.
    """
    outcome = ParseOutcome()

    df, read_errors = _read_csv(file_obj)
    if read_errors:
        outcome.structural_errors.extend(read_errors)
        return outcome

    structure_errors = _validate_structure(df)
    if structure_errors:
        outcome.structural_errors.extend(structure_errors)
        return outcome

    cleaned = _clean_dataframe(df)
    students_by_roll = {
        s.roll_number: s for s in Student.objects.all()
    }
    valid_rows, row_errors = _validate_rows(cleaned, students_by_roll)

    outcome.valid_rows = valid_rows
    outcome.row_errors = row_errors
    if valid_rows:
        outcome.stats = compute_batch_stats(valid_rows)

    return outcome


def _format_error_log(row_errors: list[RowError]) -> str | None:
    if not row_errors:
        return None
    return '\n'.join(err.as_text() for err in row_errors)


@transaction.atomic
def persist_upload_batch(
    *,
    uploaded_by,
    class_name: str,
    outcome: ParseOutcome,
) -> UploadBatch:
    """
    Persist an upload batch and its performance records in a single transaction.

    Input shape:  ParseOutcome from parse_csv_upload with valid_rows populated.
    Output shape: UploadBatch instance (PROCESSED if rows saved, FAILED if none).
    """
    error_log = _format_error_log(outcome.row_errors)
    status = (
        UploadBatch.Status.PROCESSED
        if outcome.valid_rows
        else UploadBatch.Status.FAILED
    )

    batch = UploadBatch.objects.create(
        uploaded_by=uploaded_by,
        class_name=class_name,
        status=status,
        row_count=len(outcome.valid_rows),
        error_log=error_log,
    )

    if outcome.valid_rows:
        records = [
            PerformanceRecord(
                student=row['student'],
                subject=row['subject'],
                marks_obtained=Decimal(str(row['marks_obtained'])),
                total_marks=Decimal(str(row['total_marks'])),
                attendance_percentage=Decimal(str(row['attendance_percentage'])),
                upload_batch=batch,
            )
            for row in outcome.valid_rows
        ]
        PerformanceRecord.objects.bulk_create(records)

    return batch


def recompute_stats_for_batch(batch: UploadBatch) -> dict | None:
    """Recompute summary stats from stored PerformanceRecord rows for a batch."""
    records = batch.performance_records.select_related('student').all()
    if not records:
        return None

    valid_rows = [
        {
            'subject': r.subject,
            'marks_obtained': float(r.marks_obtained),
            'total_marks': float(r.total_marks),
            'attendance_percentage': float(r.attendance_percentage),
        }
        for r in records
    ]
    return compute_batch_stats(valid_rows)


def parse_skipped_rows(error_log: str | None) -> list[str]:
    """Split stored error_log into individual row messages for template display."""
    if not error_log:
        return []
    return [line for line in error_log.splitlines() if line.strip()]
