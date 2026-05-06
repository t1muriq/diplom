"""
Модуль автоматизированного импорта данных в БД school_1416_db.

Поддерживает форматы CSV, XLSX, JSON. Универсален: одна функция import_file()
определяет формат по расширению, читает источник через pandas, валидирует
структуру и загружает в указанную таблицу через psycopg2.

Импорт идёт в одной транзакции. При ошибке выполняется ROLLBACK
и в import_log пишется status='failed'. Для существующих ключей применяется
INSERT ... ON CONFLICT DO UPDATE (UPSERT), что делает импорт идемпотентным.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from validators import VALIDATORS, ValidationError

# Конфигурация подключения. По умолчанию — учётка admin из docker-compose.
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "school_1416_db"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", "Admin123!"),
}

# Описание целевых таблиц: список колонок, естественный ключ для UPSERT,
# и валидатор. Естественный ключ — это набор колонок, по которым выполняется
# поиск дубликатов при повторном импорте.
TABLE_SPECS = {
    "students": {
        "columns":     ["last_name", "first_name", "middle_name",
                        "birth_date", "class_id", "admission_year",
                        "student_status"],
        "conflict_on": ["last_name", "first_name", "birth_date"],
        "update_cols": ["middle_name", "class_id", "admission_year",
                        "student_status"],
    },
    "teachers": {
        "columns":     ["last_name", "first_name", "middle_name",
                        "position_title"],
        "conflict_on": ["last_name", "first_name", "middle_name"],
        "update_cols": ["position_title"],
    },
    "subjects": {
        "columns":     ["subject_name", "weekly_hours"],
        "conflict_on": ["subject_name"],
        "update_cols": ["weekly_hours"],
    },
    "classrooms": {
        "columns":     ["room_number", "building", "capacity"],
        "conflict_on": ["room_number", "building"],
        "update_cols": ["capacity"],
    },
    "schedule": {
        "columns":     ["class_id", "subject_id", "teacher_id",
                        "classroom_id", "lesson_date", "lesson_number"],
        "conflict_on": ["class_id", "lesson_date", "lesson_number"],
        "update_cols": ["subject_id", "teacher_id", "classroom_id"],
    },
    "grades": {
        "columns":     ["student_id", "subject_id", "teacher_id",
                        "grade_value", "grade_date", "grade_comment"],
        "conflict_on": None,  # оценок может быть много — UPSERT не нужен
        "update_cols": [],
    },
}


# --- Чтение исходных файлов --------------------------------------------------

def read_source(file_path: str | Path) -> pd.DataFrame:
    """Читает файл-источник в DataFrame по расширению."""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext == ".csv":
        return pd.read_csv(file_path, encoding="utf-8")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    if ext == ".json":
        with open(file_path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        return pd.DataFrame(payload)
    raise ValueError(f"Неподдерживаемый формат файла: {ext}")


# --- Подготовка строк для вставки -------------------------------------------

def _prepare_rows(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    """Приводит DataFrame к списку кортежей в порядке колонок таблицы.

    NaN заменяется на None, чтобы корректно записывались NULL.
    """
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValidationError(
            f"В файле отсутствуют обязательные колонки: {sorted(missing)}"
        )

    df = df[columns].where(pd.notna(df[columns]), None)
    return [tuple(row) for row in df.itertuples(index=False, name=None)]


def _build_upsert_sql(table: str, spec: Mapping) -> str:
    """Строит SQL вида INSERT ... ON CONFLICT DO UPDATE."""
    cols     = spec["columns"]
    conflict = spec["conflict_on"]
    updates  = spec["update_cols"]

    cols_sql   = ", ".join(cols)
    base       = f"INSERT INTO {table} ({cols_sql}) VALUES %s"

    if not conflict:
        return base
    conflict_sql = ", ".join(conflict)
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates) or \
              f"{conflict[0]} = EXCLUDED.{conflict[0]}"
    return (
        f"{base} ON CONFLICT ({conflict_sql}) "
        f"DO UPDATE SET {set_sql}"
    )


# --- Журналирование ----------------------------------------------------------

def _start_log(cur, source_name: str) -> int:
    cur.execute(
        "INSERT INTO import_log (source_name, status) "
        "VALUES (%s, 'in_progress') RETURNING import_id",
        (source_name,),
    )
    return cur.fetchone()[0]


def _finish_log(cur, import_id: int, rows_loaded: int, status: str) -> None:
    cur.execute(
        "UPDATE import_log SET rows_loaded = %s, status = %s "
        "WHERE import_id = %s",
        (rows_loaded, status, import_id),
    )


# --- Главная функция ---------------------------------------------------------

def import_file(file_path: str | Path, table: str,
                db_config: Mapping | None = None) -> dict:
    """Импортирует файл в указанную таблицу.

    Возвращает словарь с результатами: import_id, rows_loaded, status, error.
    """
    if table not in TABLE_SPECS:
        raise ValueError(
            f"Неизвестная таблица '{table}'. "
            f"Доступны: {list(TABLE_SPECS)}"
        )

    file_path = Path(file_path)
    spec = TABLE_SPECS[table]
    cfg = dict(db_config or DB_CONFIG)

    # 1. Читаем файл
    df = read_source(file_path)

    # 2. Валидируем содержимое (типы, диапазоны)
    if table in VALIDATORS:
        VALIDATORS[table](df)

    # 3. Готовим кортежи и SQL
    rows = _prepare_rows(df, spec["columns"])
    sql  = _build_upsert_sql(table, spec)

    result = {
        "import_id":   None,
        "rows_loaded": 0,
        "status":      "failed",
        "error":       None,
    }

    # Шаг A. Пишем "in_progress" в отдельной транзакции и сразу коммитим.
    # Это нужно, чтобы запись об операции пережила возможный ROLLBACK
    # самих данных и обеспечила аудит даже неудачных попыток импорта.
    log_conn = psycopg2.connect(**cfg)
    log_conn.autocommit = True
    try:
        with log_conn.cursor() as cur:
            import_id = _start_log(cur, file_path.name)
            result["import_id"] = import_id
    finally:
        log_conn.close()

    # Шаг B. Загружаем сами данные в основной транзакции.
    data_conn = psycopg2.connect(**cfg)
    try:
        with data_conn:
            with data_conn.cursor() as cur:
                execute_values(cur, sql, rows, page_size=500)
                rows_loaded = len(rows)
        # При выходе из `with data_conn:` без исключения — COMMIT.
        result["rows_loaded"] = rows_loaded
        result["status"]      = "completed"
    except Exception as exc:
        # При исключении внутри `with data_conn:` — автоматический ROLLBACK.
        result["error"] = str(exc)
    finally:
        data_conn.close()

    # Шаг C. В отдельной транзакции обновляем import_log финальным статусом.
    finish_conn = psycopg2.connect(**cfg)
    finish_conn.autocommit = True
    try:
        with finish_conn.cursor() as cur:
            _finish_log(
                cur, result["import_id"],
                result["rows_loaded"], result["status"],
            )
    finally:
        finish_conn.close()

    return result


# --- CLI --------------------------------------------------------------------

def _main() -> int:
    parser = argparse.ArgumentParser(
        description="ETL-импорт файлов в БД school_1416_db"
    )
    parser.add_argument("file",  help="Путь к файлу (CSV / XLSX / JSON)")
    parser.add_argument("table", help="Целевая таблица",
                        choices=list(TABLE_SPECS))
    args = parser.parse_args()

    print(f"[{datetime.now():%H:%M:%S}] Начат импорт: "
          f"{args.file} → {args.table}")
    result = import_file(args.file, args.table)

    if result["status"] == "completed":
        print(f"[{datetime.now():%H:%M:%S}] Готово. "
              f"Загружено строк: {result['rows_loaded']} "
              f"(import_id={result['import_id']})")
        return 0
    print(f"[{datetime.now():%H:%M:%S}] ОШИБКА: {result['error']}",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_main())
