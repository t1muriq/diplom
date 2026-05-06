-- Представления для упрощения типовых запросов
-- Используются веб-приложением и при работе через DBeaver

-- v_student_grades: оценки ученика с расшифровкой ФИО, предмета и педагога
CREATE OR REPLACE VIEW v_student_grades AS
SELECT
    g.grade_id,
    g.grade_date,
    g.grade_value,
    g.grade_comment,
    s.student_id,
    s.last_name  || ' ' || s.first_name  || ' ' || COALESCE(s.middle_name, '') AS student_full_name,
    c.class_name,
    sub.subject_name,
    t.last_name  || ' ' || LEFT(t.first_name, 1) || '.' ||
    COALESCE(LEFT(t.middle_name, 1) || '.', '') AS teacher_short_name
FROM grades g
JOIN students s  ON s.student_id = g.student_id
JOIN classes  c  ON c.class_id   = s.class_id
JOIN subjects sub ON sub.subject_id = g.subject_id
JOIN teachers t  ON t.teacher_id = g.teacher_id;

-- v_class_schedule: расписание класса с расшифровкой
CREATE OR REPLACE VIEW v_class_schedule AS
SELECT
    sch.schedule_id,
    sch.lesson_date,
    sch.lesson_number,
    c.class_id,
    c.class_name,
    sub.subject_name,
    t.last_name  || ' ' || LEFT(t.first_name, 1) || '.' ||
    COALESCE(LEFT(t.middle_name, 1) || '.', '') AS teacher_short_name,
    cr.room_number,
    cr.building
FROM schedule sch
JOIN classes    c   ON c.class_id     = sch.class_id
JOIN subjects   sub ON sub.subject_id = sch.subject_id
JOIN teachers   t   ON t.teacher_id   = sch.teacher_id
JOIN classrooms cr  ON cr.classroom_id = sch.classroom_id;

-- v_attendance_summary: сводка посещаемости по ученикам
CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT
    s.student_id,
    s.last_name  || ' ' || s.first_name AS student_full_name,
    c.class_name,
    COUNT(*) FILTER (WHERE a.attendance_status = 'present') AS lessons_present,
    COUNT(*) FILTER (WHERE a.attendance_status = 'late')    AS lessons_late,
    COUNT(*) FILTER (WHERE a.attendance_status = 'absent')  AS lessons_absent,
    COUNT(*)                                                AS lessons_total
FROM students s
JOIN classes  c ON c.class_id = s.class_id
LEFT JOIN attendance a ON a.student_id = s.student_id
GROUP BY s.student_id, s.last_name, s.first_name, c.class_name;

-- v_recent_imports: последние записи журнала импорта (для дашборда)
CREATE OR REPLACE VIEW v_recent_imports AS
SELECT
    import_id,
    source_name,
    import_time,
    rows_loaded,
    status
FROM import_log
ORDER BY import_time DESC
LIMIT 20;

-- v_recent_monitoring: последние события мониторинга (для дашборда)
CREATE OR REPLACE VIEW v_recent_monitoring AS
SELECT
    log_id,
    event_time,
    event_type,
    description
FROM monitoring_log
ORDER BY event_time DESC
LIMIT 20;

-- Раздаём права на представления уже существующим ролям
GRANT SELECT ON v_student_grades, v_class_schedule, v_attendance_summary,
                v_recent_imports, v_recent_monitoring
    TO admin_db, operator_user, auditor_user;
