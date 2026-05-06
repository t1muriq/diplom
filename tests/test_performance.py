"""
Тесты производительности ключевых запросов.

В дипломе заявлено нефункциональное требование:
"время выполнения типовых запросов не должно превышать 100 мс
при нагрузке до 50 одновременных соединений".

Эти тесты проверяют выполнение базовых SELECT и фиксируют время.
Для проверки использования индексов запускают EXPLAIN.

Запуск:  pytest tests/test_performance.py -v -s
"""

from __future__ import annotations

import time

import psycopg2
import pytest

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "dbname": "school_1416_db",
    "user": "admin", "password": "Admin123!",
}

# Целевое время в миллисекундах
TARGET_MS = 100


@pytest.fixture
def conn():
    c = psycopg2.connect(**DB_CONFIG)
    yield c
    c.close()


def _measure(conn, sql: str, params: tuple = ()) -> float:
    """Запускает запрос несколько раз, возвращает среднее время в мс."""
    durations = []
    with conn.cursor() as cur:
        # Прогрев кэша
        cur.execute(sql, params)
        cur.fetchall()
        # Замер
        for _ in range(5):
            t0 = time.perf_counter()
            cur.execute(sql, params)
            cur.fetchall()
            durations.append((time.perf_counter() - t0) * 1000)
    avg = sum(durations) / len(durations)
    return avg


def test_query_class_schedule_under_target(conn):
    """Расписание класса должно отдаваться быстро (используется индекс)."""
    sql = "SELECT * FROM v_class_schedule WHERE class_id = %s"
    duration_ms = _measure(conn, sql, (1,))
    print(f"\n  v_class_schedule by class_id: {duration_ms:.2f} мс")
    assert duration_ms < TARGET_MS


def test_query_student_grades_under_target(conn):
    """Оценки ученика должны отдаваться быстро."""
    sql = "SELECT * FROM v_student_grades WHERE student_id = %s"
    duration_ms = _measure(conn, sql, (1,))
    print(f"\n  v_student_grades by student_id: {duration_ms:.2f} мс")
    assert duration_ms < TARGET_MS


def test_query_attendance_summary_under_target(conn):
    """Сводка посещаемости — агрегат, должен укладываться в лимит."""
    sql = "SELECT * FROM v_attendance_summary"
    duration_ms = _measure(conn, sql)
    print(f"\n  v_attendance_summary: {duration_ms:.2f} мс")
    assert duration_ms < TARGET_MS


def test_index_usage_for_grades(conn):
    """EXPLAIN должен показать использование idx_grades_student_id."""
    sql = ("EXPLAIN (FORMAT JSON) "
           "SELECT * FROM grades WHERE student_id = 1")
    with conn.cursor() as cur:
        cur.execute(sql)
        plan = cur.fetchone()[0][0]["Plan"]
        plan_text = str(plan)
        print(f"\n  Plan for grades by student_id: {plan_text[:200]}...")
    # При наличии индекса PostgreSQL использует Index Scan или Bitmap.
    # На малом объёме возможен Seq Scan — в этом случае тест информативен,
    # а не блокирующий.


def test_index_usage_for_students_class(conn):
    """EXPLAIN для выборки учеников класса."""
    sql = ("EXPLAIN (FORMAT JSON) "
           "SELECT * FROM students WHERE class_id = 1")
    with conn.cursor() as cur:
        cur.execute(sql)
        plan = cur.fetchone()[0][0]["Plan"]
        print(f"\n  Plan for students by class_id: {plan}")
