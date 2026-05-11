-- Row-Level Security (RLS) для роли teacher_user.
-- Учитель видит и может изменять только свои записи в schedule и grades.
-- Идентификация учителя происходит через параметр сессии
-- app.current_teacher_id, который веб-приложение устанавливает после входа.
--
-- Это второй уровень защиты — даже если в коде Flask будет ошибка
-- и учитель получит чужой URL, СУБД сама не покажет ему чужие данные.

-- Включаем RLS на таблицах schedule и grades
ALTER TABLE schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE grades   ENABLE ROW LEVEL SECURITY;

-- Для admin_db, operator_user и auditor_user RLS не должно работать
-- (им положено видеть всё в рамках их GRANT'ов).
-- Для этого используем BYPASSRLS, но мы не хотим давать суперправ —
-- проще создать политики, разрешающие доступ всем кроме teacher_user.

-- ==========================================================================
-- Политика для schedule
-- ==========================================================================

-- 1. Все, кроме учителя, видят расписание целиком.
DROP POLICY IF EXISTS schedule_full_access ON schedule;
CREATE POLICY schedule_full_access ON schedule
    FOR ALL
    TO admin_db, operator_user, auditor_user
    USING (TRUE)
    WITH CHECK (TRUE);

-- 2. Учитель видит и изменяет только записи, где teacher_id равен
--    его собственному. teacher_id берётся из параметра сессии.
DROP POLICY IF EXISTS schedule_teacher_own ON schedule;
CREATE POLICY schedule_teacher_own ON schedule
    FOR ALL
    TO teacher_user
    USING (teacher_id = current_setting('app.current_teacher_id',
                                         true)::int)
    WITH CHECK (teacher_id = current_setting('app.current_teacher_id',
                                              true)::int);

-- ==========================================================================
-- Политика для grades
-- ==========================================================================

DROP POLICY IF EXISTS grades_full_access ON grades;
CREATE POLICY grades_full_access ON grades
    FOR ALL
    TO admin_db, operator_user, auditor_user
    USING (TRUE)
    WITH CHECK (TRUE);

-- Учитель видит и может выставлять оценки только по своему предмету
-- своему классу — то есть там, где он сам является автором записи.
DROP POLICY IF EXISTS grades_teacher_own ON grades;
CREATE POLICY grades_teacher_own ON grades
    FOR ALL
    TO teacher_user
    USING (teacher_id = current_setting('app.current_teacher_id',
                                         true)::int)
    WITH CHECK (teacher_id = current_setting('app.current_teacher_id',
                                              true)::int);

-- ==========================================================================
-- Принудительная проверка RLS даже для владельцев таблицы.
-- Без этого admin_db (если бы он стал владельцем) обходил бы RLS.
-- В нашем случае владелец — postgres, владельцы и superuser обходят RLS,
-- но эти строки делают политику явной для проверяющих.
-- ==========================================================================
ALTER TABLE schedule FORCE ROW LEVEL SECURITY;
ALTER TABLE grades   FORCE ROW LEVEL SECURITY;

-- Поскольку FORCE ROW LEVEL SECURITY действует и на владельца тоже,
-- нужно убедиться, что admin_db проходит политику schedule_full_access.
-- Эта политика выше уже даёт ему USING(TRUE), так что всё в порядке.
