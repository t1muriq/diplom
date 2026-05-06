"""
Скрипт мониторинга PostgreSQL для БД school_1416_db.

Собирает шесть ключевых метрик СУБД и записывает их в monitoring_log:

  1. cache_hit_ratio       — доля чтений из кэша (целевое значение > 0.99)
  2. database_size          — размер БД в байтах
  3. active_connections     — число активных соединений
  4. deadlocks_count        — счётчик взаимоблокировок
  5. longest_running_query  — длительность самого долгого активного запроса
  6. disk_free_space        — свободное место на диске контейнера

Может запускаться разово (по умолчанию) или в режиме демона
(--daemon с интервалом --interval секунд).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from datetime import datetime
from typing import Any

import psycopg2

# Конфигурация подключения. Используется суперпользователь admin,
# потому что часть метрик требует доступа к pg_stat_database и др.
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "school_1416_db"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", "Admin123!"),
}


# --- SQL для каждой метрики --------------------------------------------------

SQL_CACHE_HIT = """
SELECT ROUND(
    SUM(blks_hit)::numeric
    / NULLIF(SUM(blks_hit) + SUM(blks_read), 0),
    4
) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname = current_database();
"""

SQL_DB_SIZE = """
SELECT pg_database_size(current_database()) AS db_size_bytes;
"""

SQL_ACTIVE_CONN = """
SELECT COUNT(*) AS active_connections
FROM pg_stat_activity
WHERE state = 'active';
"""

SQL_DEADLOCKS = """
SELECT deadlocks
FROM pg_stat_database
WHERE datname = current_database();
"""

SQL_LONGEST_QUERY = """
SELECT COALESCE(
    EXTRACT(EPOCH FROM MAX(NOW() - query_start)),
    0
)::int AS longest_seconds
FROM pg_stat_activity
WHERE state = 'active'
  AND pid <> pg_backend_pid();
"""


# --- Сбор метрик ------------------------------------------------------------

def _scalar(cur, sql: str) -> Any:
    cur.execute(sql)
    row = cur.fetchone()
    return None if row is None else row[0]


def collect_metrics(cfg: dict | None = None) -> dict:
    """Собирает все шесть метрик одним подключением."""
    cfg = cfg or DB_CONFIG
    metrics: dict[str, Any] = {}

    with psycopg2.connect(**cfg) as conn:
        with conn.cursor() as cur:
            metrics["cache_hit_ratio"]      = _scalar(cur, SQL_CACHE_HIT)
            metrics["database_size_bytes"]  = _scalar(cur, SQL_DB_SIZE)
            metrics["active_connections"]   = _scalar(cur, SQL_ACTIVE_CONN)
            metrics["deadlocks_count"]      = _scalar(cur, SQL_DEADLOCKS)
            metrics["longest_query_seconds"] = _scalar(cur, SQL_LONGEST_QUERY)

    # Дисковое пространство берётся из ОС: если скрипт запущен в контейнере,
    # это пространство контейнера; если на хосте — пространство хоста.
    usage = shutil.disk_usage("/")
    metrics["disk_free_bytes"]  = usage.free
    metrics["disk_total_bytes"] = usage.total

    return metrics


# --- Запись в журнал --------------------------------------------------------

def write_to_log(metrics: dict, cfg: dict | None = None) -> None:
    """Сохраняет одну строку в monitoring_log с типом 'metric_check'."""
    cfg = cfg or DB_CONFIG
    description = (
        f"cache_hit={metrics['cache_hit_ratio']}, "
        f"db_size={metrics['database_size_bytes']} B, "
        f"active_conn={metrics['active_connections']}, "
        f"deadlocks={metrics['deadlocks_count']}, "
        f"longest_query={metrics['longest_query_seconds']} s, "
        f"disk_free={metrics['disk_free_bytes']} B"
    )
    with psycopg2.connect(**cfg) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO monitoring_log (event_type, description) "
            "VALUES ('metric_check', %s)",
            (description,),
        )


# --- Форматирование для вывода ----------------------------------------------

def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def print_report(metrics: dict) -> None:
    print(f"=== Снимок метрик {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    print(f"  Cache hit ratio       : {metrics['cache_hit_ratio']}")
    print(f"  Database size         : {_fmt_bytes(metrics['database_size_bytes'])}")
    print(f"  Active connections    : {metrics['active_connections']}")
    print(f"  Deadlocks (cumulative): {metrics['deadlocks_count']}")
    print(f"  Longest active query  : {metrics['longest_query_seconds']} с")
    print(f"  Disk free / total     : "
          f"{_fmt_bytes(metrics['disk_free_bytes'])} / "
          f"{_fmt_bytes(metrics['disk_total_bytes'])}")


# --- CLI --------------------------------------------------------------------

def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Сбор метрик мониторинга PostgreSQL"
    )
    parser.add_argument("--daemon", action="store_true",
                        help="Запуск в режиме демона")
    parser.add_argument("--interval", type=int, default=60,
                        help="Интервал между сборами в секундах (для daemon)")
    parser.add_argument("--no-log", action="store_true",
                        help="Не писать в monitoring_log, только в stdout")
    args = parser.parse_args()

    def _tick() -> None:
        try:
            metrics = collect_metrics()
            print_report(metrics)
            if not args.no_log:
                write_to_log(metrics)
                print("  → Записано в monitoring_log")
        except Exception as exc:
            print(f"ОШИБКА сбора метрик: {exc}", file=sys.stderr)

    if not args.daemon:
        _tick()
        return 0

    print(f"Демон запущен, интервал {args.interval} с. Ctrl+C для остановки.")
    try:
        while True:
            _tick()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Остановлен по запросу пользователя.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
