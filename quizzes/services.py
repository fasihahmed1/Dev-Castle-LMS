"""
CSV validation and import for bulk quiz question upload.

Expected CSV schema (header row required, exact column names):
    question_text    — str, non-empty
    option_a         — str, non-empty
    option_b         — str, non-empty
    option_c         — str, non-empty
    option_d         — str, non-empty
    correct_option   — str, one of A/B/C/D (case-insensitive)
    marks            — numeric, >= 1 (optional, defaults to 1)

Structural validation failures abort before any DB write.
Row-level errors are collected; if any row fails, the entire upload is rejected
(no partial question save).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import BinaryIO

import pandas as pd
from django.db import transaction

from .models import Question, Quiz

REQUIRED_COLUMNS = [
    'question_text',
    'option_a',
    'option_b',
    'option_c',
    'option_d',
    'correct_option',
]

OPTIONAL_COLUMNS = ['marks']
VALID_CORRECT_OPTIONS = {'A', 'B', 'C', 'D'}


@dataclass
class RowError:
    row_number: int
    message: str

    def as_text(self) -> str:
        return f'Row {self.row_number}: {self.message}'


@dataclass
class QuestionImportOutcome:
    structural_errors: list[str] = field(default_factory=list)
    row_errors: list[RowError] = field(default_factory=list)
    valid_rows: list[dict] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.structural_errors and not self.row_errors and bool(self.valid_rows)


def _read_csv(file_obj: BinaryIO) -> tuple[pd.DataFrame | None, list[str]]:
    try:
        raw = file_obj.read()
        if not raw.strip():
            return None, ['The uploaded file is empty.']
        df = pd.read_csv(BytesIO(raw))
    except Exception as exc:
        return None, [f'Could not read CSV file: {exc}']

    if df.empty:
        return None, ['The CSV file contains no data rows.']

    return df, []


def _validate_structure(df: pd.DataFrame) -> list[str]:
    normalized = {col.strip().lower(): col for col in df.columns}
    missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
    if missing:
        return [
            'Missing required column(s): '
            + ', '.join(missing)
            + f'. Expected: {", ".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)}.'
        ]

    rename_map = {normalized[col]: col for col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS if col in normalized}
    df.rename(columns=rename_map, inplace=True)
    return []


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cols = REQUIRED_COLUMNS.copy()
    if 'marks' in df.columns:
        cols.append('marks')

    cleaned = df[cols].copy()
    for col in ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']:
        cleaned[col] = cleaned[col].astype(str).str.strip()
        cleaned.loc[cleaned[col].isin(['', 'nan', 'None']), col] = pd.NA

    if 'marks' in cleaned.columns:
        cleaned['marks'] = pd.to_numeric(cleaned['marks'], errors='coerce')

    return cleaned


def _validate_rows(df: pd.DataFrame) -> tuple[list[dict], list[RowError]]:
    valid_rows: list[dict] = []
    row_errors: list[RowError] = []

    for idx, row in df.iterrows():
        row_number = int(idx) + 2

        if pd.isna(row['question_text']):
            row_errors.append(RowError(row_number, 'question_text is missing or blank.'))
            continue

        for opt_col in ['option_a', 'option_b', 'option_c', 'option_d']:
            if pd.isna(row[opt_col]):
                row_errors.append(RowError(row_number, f'{opt_col} is missing or blank.'))
                break
        else:
            correct = str(row['correct_option']).upper().strip()
            if correct not in VALID_CORRECT_OPTIONS:
                row_errors.append(
                    RowError(row_number, f"correct_option must be A, B, C, or D (got '{row['correct_option']}').")
                )
                continue

            marks = 1
            if 'marks' in df.columns and not pd.isna(row.get('marks')):
                marks = int(row['marks'])
                if marks < 1:
                    row_errors.append(RowError(row_number, 'marks must be at least 1.'))
                    continue

            valid_rows.append({
                'question_text': str(row['question_text']),
                'option_a': str(row['option_a']),
                'option_b': str(row['option_b']),
                'option_c': str(row['option_c']),
                'option_d': str(row['option_d']),
                'correct_option': correct,
                'marks': marks,
            })

    return valid_rows, row_errors


def parse_questions_csv(file_obj: BinaryIO) -> QuestionImportOutcome:
    """Parse and validate a questions CSV entirely in memory (no DB writes)."""
    outcome = QuestionImportOutcome()

    df, read_errors = _read_csv(file_obj)
    if read_errors:
        outcome.structural_errors.extend(read_errors)
        return outcome

    structure_errors = _validate_structure(df)
    if structure_errors:
        outcome.structural_errors.extend(structure_errors)
        return outcome

    cleaned = _clean_dataframe(df)
    valid_rows, row_errors = _validate_rows(cleaned)

    outcome.valid_rows = valid_rows
    outcome.row_errors = row_errors

    if not valid_rows and not row_errors:
        outcome.structural_errors.append('The CSV file contains no valid question rows.')

    return outcome


@transaction.atomic
def create_quiz_from_csv(*, quiz_fields: dict, file_obj: BinaryIO, created_by) -> tuple[Quiz | None, QuestionImportOutcome]:
    """
    Validate CSV and atomically create Quiz + Questions.

    Returns (Quiz, outcome). Quiz is None if validation failed.
    """
    outcome = parse_questions_csv(file_obj)

    if outcome.structural_errors or outcome.row_errors or not outcome.valid_rows:
        return None, outcome

    quiz = Quiz.objects.create(created_by=created_by, **quiz_fields)
    Question.objects.bulk_create([
        Question(quiz=quiz, **row) for row in outcome.valid_rows
    ])

    return quiz, outcome
