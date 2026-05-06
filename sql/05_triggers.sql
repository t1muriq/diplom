-- Триггеры базы данных school_1416_db

-- Триггер 1: при появлении записи об импорте автоматически создаётся
-- соответствующая запись в monitoring_log. Это гарантирует, что любая
-- ETL-операция отражается в журнале мониторинга, даже если её выполнил
-- администратор напрямую через psql, минуя Python-скрипт.

CREATE OR REPLACE FUNCTION log_import_to_monitoring()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' THEN
        INSERT INTO monitoring_log (event_type, description)
        VALUES (
            'import_completed',
            format('Импорт из источника "%s" завершён, загружено строк: %s',
                   NEW.source_name, NEW.rows_loaded)
        );
    ELSIF NEW.status = 'failed' THEN
        INSERT INTO monitoring_log (event_type, description)
        VALUES (
            'error',
            format('Импорт из источника "%s" завершился с ошибкой',
                   NEW.source_name)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_import_to_monitoring ON import_log;

CREATE TRIGGER trg_import_to_monitoring
AFTER INSERT OR UPDATE OF status ON import_log
FOR EACH ROW
EXECUTE FUNCTION log_import_to_monitoring();


-- Триггер 2: запрет на выставление оценок ученикам со статусом 'expelled'.
-- Демонстрирует контроль бизнес-правил на уровне СУБД.

CREATE OR REPLACE FUNCTION check_grade_for_active_student()
RETURNS TRIGGER AS $$
DECLARE
    s_status VARCHAR(20);
BEGIN
    SELECT student_status INTO s_status
      FROM students
     WHERE student_id = NEW.student_id;

    IF s_status = 'expelled' THEN
        RAISE EXCEPTION 'Невозможно выставить оценку отчисленному ученику (student_id=%)',
            NEW.student_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_grade_active ON grades;

CREATE TRIGGER trg_check_grade_active
BEFORE INSERT OR UPDATE ON grades
FOR EACH ROW
EXECUTE FUNCTION check_grade_for_active_student();
