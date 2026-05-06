"""
Валидаторы данных перед загрузкой в БД.

Каждая функция принимает DataFrame и бросает ValidationError при нарушениях.
Цель — поймать заведомо некорректные данные до отправки в СУБД, чтобы
получить осмысленное сообщение об ошибке вместо невнятной ошибки PostgreSQL.
"""

from __future__ import annotations

import pandas as pd


class ValidationError(Exception):
    """Ошибка валидации входных данных."""


# --- Утилиты ----------------------------------------------------------------

def _require_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = set(required) - set(df.columns)
    if missing:
        raise ValidationError(
            f"Отсутствуют обязательные колонки: {sorted(missing)}"
        )


def _require_no_nulls(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if df[c].isna().any():
            raise ValidationError(
                f"В колонке '{c}' встречаются пустые значения"
            )


# --- Конкретные валидаторы --------------------------------------------------

def validate_students(df: pd.DataFrame) -> None:
    required = ["last_name", "first_name", "birth_date",
                "class_id", "admission_year", "student_status"]
    _require_columns(df, required)
    _require_no_nulls(df, required)

    if not df["admission_year"].between(2015, 2100).all():
        raise ValidationError(
            "Год поступления должен быть в диапазоне 2015..2100"
        )
    allowed = {"active", "graduated", "expelled"}
    bad = set(df["student_status"]) - allowed
    if bad:
        raise ValidationError(
            f"Недопустимые значения student_status: {bad}. "
            f"Разрешены: {allowed}"
        )


def validate_teachers(df: pd.DataFrame) -> None:
    required = ["last_name", "first_name", "position_title"]
    _require_columns(df, required)
    _require_no_nulls(df, required)


def validate_subjects(df: pd.DataFrame) -> None:
    required = ["subject_name", "weekly_hours"]
    _require_columns(df, required)
    _require_no_nulls(df, required)
    if not (df["weekly_hours"] > 0).all():
        raise ValidationError("weekly_hours должно быть положительным")


def validate_classrooms(df: pd.DataFrame) -> None:
    required = ["room_number", "building", "capacity"]
    _require_columns(df, required)
    _require_no_nulls(df, required)
    if not (df["capacity"] > 0).all():
        raise ValidationError("capacity должно быть положительным")


def validate_schedule(df: pd.DataFrame) -> None:
    required = ["class_id", "subject_id", "teacher_id", "classroom_id",
                "lesson_date", "lesson_number"]
    _require_columns(df, required)
    _require_no_nulls(df, required)
    if not df["lesson_number"].between(1, 8).all():
        raise ValidationError("lesson_number должно быть от 1 до 8")


def validate_grades(df: pd.DataFrame) -> None:
    required = ["student_id", "subject_id", "teacher_id",
                "grade_value", "grade_date"]
    _require_columns(df, required)
    _require_no_nulls(df, required)
    if not df["grade_value"].between(2, 5).all():
        raise ValidationError(
            "grade_value должно быть в диапазоне 2..5 (пятибалльная шкала)"
        )


VALIDATORS = {
    "students":   validate_students,
    "teachers":   validate_teachers,
    "subjects":   validate_subjects,
    "classrooms": validate_classrooms,
    "schedule":   validate_schedule,
    "grades":     validate_grades,
}
