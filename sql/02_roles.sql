-- Ролевая модель школы №1416.
-- Четыре роли: технические (admin_db, operator_user, auditor_user)
-- и бизнес-роль teacher_user для входа учителей в личный кабинет.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_db') THEN
        CREATE ROLE admin_db WITH LOGIN PASSWORD 'Admin123!';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'operator_user') THEN
        CREATE ROLE operator_user WITH LOGIN PASSWORD 'Operator123!';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auditor_user') THEN
        CREATE ROLE auditor_user WITH LOGIN PASSWORD 'Auditor123!';
    END IF;

    -- Роль teacher_user — используется веб-приложением для подключения
    -- от имени учителей. Конкретный учитель идентифицируется параметром
    -- сессии app.current_teacher_id, который читается RLS-политиками.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'teacher_user') THEN
        CREATE ROLE teacher_user WITH LOGIN PASSWORD 'Teacher123!';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE school_1416_db
    TO admin_db, operator_user, auditor_user, teacher_user;

GRANT USAGE ON SCHEMA public
    TO admin_db, operator_user, auditor_user, teacher_user;
GRANT CREATE ON SCHEMA public TO admin_db;

-- admin_db — полный доступ
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin_db;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin_db;

-- operator_user — SELECT/INSERT/UPDATE на всех таблицах кроме confidential_data
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO operator_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO operator_user;
REVOKE ALL ON confidential_data FROM operator_user;

-- auditor_user — только чтение
GRANT SELECT ON ALL TABLES IN SCHEMA public TO auditor_user;
REVOKE ALL ON confidential_data FROM auditor_user;

-- teacher_user — может читать справочники (нужно для интерфейса)
-- и читать/писать только свои данные в schedule и grades.
-- Реальное ограничение «только своё» обеспечивается RLS-политиками
-- в файле 06_rls.sql.
GRANT SELECT ON classes, subjects, classrooms, teachers, students TO teacher_user;
GRANT SELECT, INSERT, UPDATE ON schedule, grades TO teacher_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO teacher_user;
REVOKE ALL ON confidential_data           FROM teacher_user;
REVOKE ALL ON import_log, monitoring_log  FROM teacher_user;
REVOKE ALL ON teacher_accounts            FROM teacher_user;

-- Default privileges — для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO admin_db;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO admin_db;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO operator_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO operator_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO auditor_user;
