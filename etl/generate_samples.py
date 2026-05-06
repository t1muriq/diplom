"""
Генератор тестовых файлов-источников для демонстрации импорта.

Запускается один раз: создаёт CSV / XLSX / JSON в etl/samples/.
Файлы используются и в pytest-тестах, и для ручной демонстрации на защите.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


# --- Импорт учеников: XLSX ---------------------------------------------------

students_data = [
    ("Иванова",  "Мария",   "Алексеевна",   "2010-03-12", 1, 2022, "active"),
    ("Сидоров",  "Артур",   "Денисович",    "2009-07-04", 2, 2021, "active"),
    ("Беляев",   "Кирилл",  "Сергеевич",    "2008-11-23", 3, 2020, "active"),
    ("Гусева",   "Полина",  "Игоревна",     "2011-02-19", 4, 2023, "active"),
    ("Котов",    "Тимофей", "Александрович","2012-06-08", 5, 2024, "active"),
    ("Романова", "Алиса",   "Антоновна",    "2013-12-30", 6, 2025, "active"),
    ("Орлов",    "Глеб",    "Викторович",   "2010-09-15", 1, 2022, "active"),
    ("Шарова",   "Виктория","Романовна",    "2009-05-27", 2, 2021, "active"),
]
df_students = pd.DataFrame(students_data, columns=[
    "last_name", "first_name", "middle_name",
    "birth_date", "class_id", "admission_year", "student_status",
])
df_students.to_excel(SAMPLES_DIR / "students_import.xlsx", index=False)


# --- Импорт оценок: CSV ------------------------------------------------------

grades_data = [
    (1, 1, 1, 4, "2026-04-10", "Контрольная работа"),
    (2, 2, 2, 5, "2026-04-10", "Изложение"),
    (3, 3, 3, 5, "2026-04-11", "Самостоятельная"),
    (4, 4, 4, 4, "2026-04-11", "Тест по теме"),
    (5, 5, 7, 3, "2026-04-12", "Лабораторная"),
    (6, 6, 6, 5, "2026-04-12", "Грамматика"),
    (7, 5, 5, 4, "2026-04-13", "Решение задач"),
    (8, 1, 1, 5, "2026-04-13", "Устный ответ"),
    (9, 6, 6, 4, "2026-04-14", "Аудирование"),
    (10, 8, 4, 4, "2026-04-14", "Контурная карта"),
]
df_grades = pd.DataFrame(grades_data, columns=[
    "student_id", "subject_id", "teacher_id",
    "grade_value", "grade_date", "grade_comment",
])
df_grades.to_csv(SAMPLES_DIR / "grades_import.csv", index=False, encoding="utf-8")


# --- Импорт расписания: JSON -------------------------------------------------

schedule_data = [
    {"class_id": 1, "subject_id": 2, "teacher_id": 2, "classroom_id": 1,
     "lesson_date": "2026-04-15", "lesson_number": 1},
    {"class_id": 1, "subject_id": 1, "teacher_id": 1, "classroom_id": 1,
     "lesson_date": "2026-04-15", "lesson_number": 2},
    {"class_id": 2, "subject_id": 3, "teacher_id": 3, "classroom_id": 3,
     "lesson_date": "2026-04-15", "lesson_number": 3},
    {"class_id": 3, "subject_id": 6, "teacher_id": 6, "classroom_id": 2,
     "lesson_date": "2026-04-15", "lesson_number": 4},
    {"class_id": 4, "subject_id": 4, "teacher_id": 4, "classroom_id": 4,
     "lesson_date": "2026-04-15", "lesson_number": 5},
    {"class_id": 5, "subject_id": 7, "teacher_id": 7, "classroom_id": 5,
     "lesson_date": "2026-04-15", "lesson_number": 6},
]
with open(SAMPLES_DIR / "schedule_import.json", "w", encoding="utf-8") as f:
    json.dump({"data": schedule_data}, f, ensure_ascii=False, indent=2)


# --- "Сломанный" файл для демонстрации обработки ошибок ---------------------

bad_data = [
    ("Тестов", "Ошибка", "Пустой", "2010-01-01", 1, 1999, "active"),  # год < 2015
]
df_bad = pd.DataFrame(bad_data, columns=[
    "last_name", "first_name", "middle_name",
    "birth_date", "class_id", "admission_year", "student_status",
])
df_bad.to_csv(SAMPLES_DIR / "students_invalid.csv", index=False, encoding="utf-8")


print("Сгенерированы файлы в", SAMPLES_DIR)
for f in sorted(SAMPLES_DIR.iterdir()):
    print(" ", f.name, f.stat().st_size, "байт")
