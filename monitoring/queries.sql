-- Готовые SQL-запросы мониторинга для использования в DBeaver или psql.
-- Эти же запросы программно вызываются модулем monitoring.py.

-- ============================================================
-- 1. Cache hit ratio. Целевое значение > 0.99 (99% чтений из кэша).
-- ============================================================
SELECT
    datname,
    ROUND(SUM(blks_hit)::numeric
          / NULLIF(SUM(blks_hit) + SUM(blks_read), 0), 4) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname = current_database()
GROUP BY datname;


-- ============================================================
-- 2. Размер базы данных в человекочитаемом виде.
-- ============================================================
SELECT
    current_database()                         AS database,
    pg_size_pretty(pg_database_size(current_database())) AS pretty_size,
    pg_database_size(current_database())       AS bytes;


-- ============================================================
-- 3. Размер каждой таблицы (включая индексы) — для оценки роста.
-- ============================================================
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) AS total_size,
    pg_total_relation_size(quote_ident(tablename))                 AS bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(quote_ident(tablename)) DESC;


-- ============================================================
-- 4. Активные соединения и их состояние.
-- ============================================================
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    LEFT(query, 100) AS query_preview
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY query_start NULLS LAST;


-- ============================================================
-- 5. Счётчики транзакций и взаимоблокировок.
-- ============================================================
SELECT
    datname,
    xact_commit,
    xact_rollback,
    deadlocks,
    conflicts,
    temp_files,
    pg_size_pretty(temp_bytes) AS temp_bytes_pretty
FROM pg_stat_database
WHERE datname = current_database();


-- ============================================================
-- 6. Долгие активные запросы (более 5 секунд).
-- ============================================================
SELECT
    pid,
    usename,
    NOW() - query_start AS duration,
    state,
    LEFT(query, 200) AS query_preview
FROM pg_stat_activity
WHERE state = 'active'
  AND NOW() - query_start > INTERVAL '5 seconds'
  AND pid <> pg_backend_pid();


-- ============================================================
-- 7. Использование индексов: поиск неиспользуемых индексов
-- (idx_scan = 0 — кандидат на удаление).
-- ============================================================
SELECT
    schemaname,
    relname  AS table_name,
    indexrelname AS index_name,
    idx_scan AS scans,
    idx_tup_read AS tuples_read,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC;


-- ============================================================
-- 8. Свежие записи журнала импорта.
-- ============================================================
SELECT * FROM v_recent_imports;


-- ============================================================
-- 9. Свежие записи журнала мониторинга.
-- ============================================================
SELECT * FROM v_recent_monitoring;
