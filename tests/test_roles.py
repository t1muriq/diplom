"""
Тесты ролевой модели PostgreSQL.

Проверяют, что матрица доступа из главы 2 диплома действительно
реализована на уровне СУБД:

  • admin_db    — может всё
  • operator_user — SELECT/INSERT/UPDATE на всех таблицах,
                    но не DELETE и не доступ к confidential_data
  • auditor_user  — только SELECT

Запуск: pytest tests/test_roles.py -v
"""

from __future__ import annotations

import psycopg2
import pytest

ROLE_CONFIGS = {
    "admin_db":      {"user": "admin_db",      "password": "Admin123!"},
    "operator_user": {"user": "operator_user", "password": "Operator123!"},
    "auditor_user":  {"user": "auditor_user",  "password": "Auditor123!"},
}

BASE = {"host": "localhost", "port": 5432, "dbname": "school_1416_db"}


def _conn(role: str):
    return psycopg2.connect(**BASE, **ROLE_CONFIGS[role])


@pytest.mark.parametrize("role", list(ROLE_CONFIGS))
def test_login_works(role):
    """Все три роли должны успешно подключаться."""
    c = _conn(role)
    c.close()


@pytest.mark.parametrize("role", list(ROLE_CONFIGS))
def test_select_students_works_for_all(role):
    """Чтение students доступно всем трём ролям."""
    with _conn(role) as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM students")
        assert cur.fetchone()[0] >= 0


def test_auditor_cannot_insert():
    """auditor_user не должен иметь права на INSERT."""
    with _conn("auditor_user") as c, c.cursor() as cur:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO subjects (subject_name, weekly_hours) "
                "VALUES ('тест', 1)"
            )


def test_auditor_cannot_update():
    """auditor_user не должен иметь права на UPDATE."""
    with _conn("auditor_user") as c, c.cursor() as cur:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("UPDATE subjects SET weekly_hours = 99")


def test_operator_can_insert_grade():
    """operator_user должен иметь право выставлять оценки."""
    with _conn("operator_user") as c, c.cursor() as cur:
        # Только проверяем, что INSERT не запрещён правами,
        # потом откатываем транзакцию
        cur.execute(
            "INSERT INTO grades "
            "(student_id, subject_id, teacher_id, grade_value, grade_date) "
            "VALUES (1, 1, 1, 5, CURRENT_DATE) RETURNING grade_id"
        )
        new_id = cur.fetchone()[0]
        assert new_id is not None
        c.rollback()


def test_operator_cannot_delete():
    """operator_user не должен иметь права на DELETE."""
    with _conn("operator_user") as c, c.cursor() as cur:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM students WHERE student_id = 1")
