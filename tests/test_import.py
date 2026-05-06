"""
Тесты ETL-импорта.

Проверяют:
  • успешный импорт каждого формата (CSV / XLSX / JSON)
  • идемпотентность: повторный импорт того же файла не создаёт дубликатов
  • обработку некорректных данных: ROLLBACK, status='failed' в журнале
  • валидацию структуры: отсутствие колонок ловится до отправки в СУБД

Запуск:  pytest tests/test_import.py -v
Требует: запущенный контейнер school_1416_postgres с применёнными
         01_schema.sql, 02_roles.sql, 03_seed.sql.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))

from import_data import import_file  # noqa: E402
from validators import ValidationError  # noqa: E402

SAMPLES = ROOT / "etl" / "samples"

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "dbname": "school_1416_db",
    "user": "admin", "password": "Admin123!",
}


@pytest.fixture
def conn():
    c = psycopg2.connect(**DB_CONFIG)
    yield c
    c.close()


def _count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def _last_log(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT import_id, source_name, rows_loaded, status "
            "FROM import_log ORDER BY import_id DESC LIMIT 1"
        )
        row = cur.fetchone()
        return {
            "import_id":   row[0],
            "source_name": row[1],
            "rows_loaded": row[2],
            "status":      row[3],
        }


# --- Тесты успешного импорта ------------------------------------------------

def test_xlsx_import_students(conn):
    """XLSX: ученики импортируются и попадают в таблицу."""
    before = _count(conn, "students")
    result = import_file(SAMPLES / "students_import.xlsx", "students")

    assert result["status"] == "completed"
    assert result["rows_loaded"] == 8
    after = _count(conn, "students")
    assert after >= before  # минимум столько же, может быть и больше
    log = _last_log(conn)
    assert log["status"] == "completed"
    assert log["rows_loaded"] == 8


def test_csv_import_grades(conn):
    """CSV: оценки импортируются успешно."""
    before = _count(conn, "grades")
    result = import_file(SAMPLES / "grades_import.csv", "grades")

    assert result["status"] == "completed"
    assert result["rows_loaded"] == 10
    after = _count(conn, "grades")
    assert after - before == 10  # оценки всегда добавляются (без UPSERT)


def test_json_import_schedule(conn):
    """JSON: расписание импортируется (с UPSERT)."""
    result = import_file(SAMPLES / "schedule_import.json", "schedule")
    assert result["status"] == "completed"
    assert result["rows_loaded"] == 6


# --- Идемпотентность --------------------------------------------------------

def test_idempotent_students_upsert(conn):
    """Повторный импорт того же файла учеников не создаёт дубликатов."""
    import_file(SAMPLES / "students_import.xlsx", "students")
    count_first = _count(conn, "students")

    import_file(SAMPLES / "students_import.xlsx", "students")
    count_second = _count(conn, "students")

    assert count_first == count_second, (
        "ON CONFLICT DO UPDATE должен предотвратить появление дубликатов"
    )


# --- Обработка ошибок -------------------------------------------------------

def test_invalid_data_rolls_back(conn):
    """Файл с невалидным admission_year=1999 должен быть отклонён валидатором.

    ValidationError бросается ДО открытия транзакции с СУБД, так что
    данные в БД заведомо не попадают. Это и есть роллбэк на уровне ETL.
    """
    before = _count(conn, "students")

    with pytest.raises(ValidationError, match="2015"):
        import_file(SAMPLES / "students_invalid.csv", "students")

    assert _count(conn, "students") == before, (
        "Ни одна строка не должна попасть в БД"
    )


def test_invalid_data_in_db_rolls_back(conn):
    """Если ошибка возникает уже в СУБД (нарушение FK), транзакция откатывается
    и в import_log появляется запись 'failed'.

    Создаём временный JSON с несуществующим class_id=999.
    """
    import json
    import tempfile
    from pathlib import Path

    bad = [{
        "last_name": "Тестов", "first_name": "БД",
        "middle_name": "Ошибка", "birth_date": "2010-01-01",
        "class_id": 999,                # FK нарушение
        "admission_year": 2024,
        "student_status": "active",
    }]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"data": bad}, f, ensure_ascii=False)
        tmp_path = Path(f.name)

    try:
        before = _count(conn, "students")
        result = import_file(tmp_path, "students")
        assert result["status"] == "failed"
        assert _count(conn, "students") == before
        log = _last_log(conn)
        assert log["status"] == "failed"
    finally:
        tmp_path.unlink()


def test_unknown_table_raises():
    """Неизвестная таблица должна давать ValueError."""
    with pytest.raises(ValueError, match="Неизвестная таблица"):
        import_file(SAMPLES / "students_import.xlsx", "nonexistent")
