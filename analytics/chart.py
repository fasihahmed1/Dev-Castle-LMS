from __future__ import annotations

import base64
from io import BytesIO
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _figure_to_data_uri(fig) -> str:
    buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _record_percentage(record) -> float:
    total = float(record.total_marks or 0)
    if total <= 0:
        return 0.0
    return (float(record.marks_obtained) / total) * 100


def performance_by_subject_chart(records: Iterable) -> str | None:
    rows = list(records)
    if not rows:
        return None

    subject_totals: dict[str, list[float]] = {}
    for record in rows:
        subject_totals.setdefault(record.subject, []).append(_record_percentage(record))

    subjects = sorted(subject_totals)
    averages = [sum(subject_totals[subject]) / len(subject_totals[subject]) for subject in subjects]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(subjects, averages, color="#0d6efd")
    ax.set_title("Average marks by subject")
    ax.set_ylabel("Average %")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    return _figure_to_data_uri(fig)


def attendance_by_subject_chart(records: Iterable) -> str | None:
    rows = list(records)
    if not rows:
        return None

    subject_totals: dict[str, list[float]] = {}
    for record in rows:
        subject_totals.setdefault(record.subject, []).append(float(record.attendance_percentage))

    subjects = sorted(subject_totals)
    averages = [sum(subject_totals[subject]) / len(subject_totals[subject]) for subject in subjects]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(subjects, averages, marker="o", color="#198754", linewidth=2)
    ax.set_title("Attendance by subject")
    ax.set_ylabel("Attendance %")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    return _figure_to_data_uri(fig)


def grade_distribution_chart(records: Iterable) -> str | None:
    rows = list(records)
    if not rows:
        return None

    buckets = {"A (80-100)": 0, "B (70-79)": 0, "C (60-69)": 0, "D (50-59)": 0, "F (<50)": 0}
    for record in rows:
        pct = _record_percentage(record)
        if pct >= 80:
            buckets["A (80-100)"] += 1
        elif pct >= 70:
            buckets["B (70-79)"] += 1
        elif pct >= 60:
            buckets["C (60-69)"] += 1
        elif pct >= 50:
            buckets["D (50-59)"] += 1
        else:
            buckets["F (<50)"] += 1

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(buckets.keys(), buckets.values(), color="#6f42c1")
    ax.set_title("Grade distribution")
    ax.set_ylabel("Record count")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    return _figure_to_data_uri(fig)


def quiz_score_distribution_chart(attempts: Iterable, total_marks: float | None = None) -> str | None:
    rows = [attempt for attempt in attempts if attempt.score is not None]
    if not rows:
        return None

    labels = [attempt.student.roll_number for attempt in rows]
    scores = [float(attempt.score) for attempt in rows]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(labels, scores, color="#fd7e14")
    ax.set_title("Quiz scores")
    ax.set_ylabel("Score")
    if total_marks:
        ax.set_ylim(0, max(total_marks, max(scores)))
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    return _figure_to_data_uri(fig)
