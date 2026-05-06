INSERT INTO classes (class_id, class_name, grade_level, academic_year, profile_name)
VALUES
    (1, '9А', 9, '2025/2026', 'общеобразовательный'),
    (2, '10А', 10, '2025/2026', 'математический'),
    (3, '11Б', 11, '2025/2026', 'информационно-технологический'),
    (4, '8В', 8, '2025/2026', 'гуманитарный'),
    (5, '7Б', 7, '2025/2026', 'естественно-научный'),
    (6, '6Г', 6, '2025/2026', 'общеобразовательный');

INSERT INTO teachers (teacher_id, last_name, first_name, middle_name, position_title)
VALUES
    (1, 'Сидоров', 'Алексей', 'Викторович', 'Учитель математики'),
    (2, 'Смирнова', 'Елена', 'Сергеевна', 'Учитель русского языка'),
    (3, 'Кузнецов', 'Дмитрий', 'Игоревич', 'Учитель информатики'),
    (4, 'Орлова', 'Марина', 'Павловна', 'Учитель истории'),
    (5, 'Никитин', 'Павел', 'Андреевич', 'Учитель физики'),
    (6, 'Федорова', 'Ольга', 'Михайловна', 'Учитель английского языка'),
    (7, 'Морозов', 'Илья', 'Романович', 'Учитель биологии');

INSERT INTO subjects (subject_id, subject_name, weekly_hours)
VALUES
    (1, 'Математика', 5),
    (2, 'Русский язык', 4),
    (3, 'Информатика', 3),
    (4, 'История', 2),
    (5, 'Физика', 3),
    (6, 'Английский язык', 4),
    (7, 'Биология', 2),
    (8, 'География', 2);

INSERT INTO classrooms (classroom_id, room_number, building, capacity)
VALUES
    (1, '101', 'Основной корпус', 30),
    (2, '204', 'Основной корпус', 28),
    (3, '305', 'Корпус STEM', 25),
    (4, '112', 'Основной корпус', 32),
    (5, '210', 'Основной корпус', 30),
    (6, '401', 'Корпус STEM', 24),
    (7, '15', 'Спортивный корпус', 26);

INSERT INTO students (student_id, last_name, first_name, middle_name, birth_date, class_id, admission_year, student_status)
VALUES
    (1, 'Иванов', 'Иван', 'Иванович', DATE '2010-05-17', 1, 2022, 'active'),
    (2, 'Петрова', 'Анна', 'Сергеевна', DATE '2009-11-02', 2, 2021, 'active'),
    (3, 'Волков', 'Максим', 'Олегович', DATE '2008-03-29', 3, 2020, 'active'),
    (4, 'Соколова', 'Дарья', 'Алексеевна', DATE '2011-07-14', 4, 2023, 'active'),
    (5, 'Михайлов', 'Артем', 'Денисович', DATE '2012-01-08', 5, 2024, 'active'),
    (6, 'Новикова', 'Ксения', 'Ильинична', DATE '2013-09-21', 6, 2025, 'active'),
    (7, 'Козлов', 'Егор', 'Павлович', DATE '2010-12-03', 1, 2022, 'active'),
    (8, 'Лебедева', 'София', 'Андреевна', DATE '2009-04-18', 2, 2021, 'active'),
    (9, 'Зайцев', 'Марк', 'Русланович', DATE '2008-10-27', 3, 2020, 'active'),
    (10, 'Павлова', 'Алина', 'Владимировна', DATE '2011-02-11', 4, 2023, 'active'),
    (11, 'Семенов', 'Никита', 'Олегович', DATE '2012-06-30', 5, 2024, 'active'),
    (12, 'Егорова', 'Вера', 'Максимовна', DATE '2013-08-05', 6, 2025, 'active');

INSERT INTO schedule (schedule_id, class_id, subject_id, teacher_id, classroom_id, lesson_date, lesson_number)
VALUES
    (1, 1, 1, 1, 1, DATE '2026-03-23', 1),
    (2, 2, 2, 2, 2, DATE '2026-03-23', 2),
    (3, 3, 3, 3, 3, DATE '2026-03-23', 3),
    (4, 4, 4, 4, 4, DATE '2026-03-23', 4),
    (5, 5, 7, 7, 5, DATE '2026-03-23', 5),
    (6, 6, 6, 6, 6, DATE '2026-03-23', 6),
    (7, 1, 5, 5, 3, DATE '2026-03-24', 1),
    (8, 2, 1, 1, 1, DATE '2026-03-24', 2),
    (9, 3, 6, 6, 2, DATE '2026-03-24', 3),
    (10, 4, 8, 4, 4, DATE '2026-03-24', 4),
    (11, 5, 2, 2, 5, DATE '2026-03-24', 5),
    (12, 6, 3, 3, 6, DATE '2026-03-24', 6);

INSERT INTO grades (grade_id, student_id, subject_id, teacher_id, grade_value, grade_date, grade_comment)
VALUES
    (1, 1, 1, 1, 5, DATE '2026-03-20', 'Контрольная работа'),
    (2, 2, 2, 2, 4, DATE '2026-03-20', 'Сочинение'),
    (3, 3, 3, 3, 5, DATE '2026-03-20', 'Практическая работа'),
    (4, 4, 4, 4, 4, DATE '2026-03-21', 'Устный ответ'),
    (5, 5, 7, 7, 5, DATE '2026-03-21', 'Лабораторная работа'),
    (6, 6, 6, 6, 4, DATE '2026-03-21', 'Словарный диктант'),
    (7, 7, 5, 5, 3, DATE '2026-03-24', 'Решение задач'),
    (8, 8, 1, 1, 5, DATE '2026-03-24', 'Самостоятельная работа'),
    (9, 9, 6, 6, 4, DATE '2026-03-24', 'Диалогическая речь'),
    (10, 10, 8, 4, 5, DATE '2026-03-24', 'Работа с картой'),
    (11, 11, 2, 2, 4, DATE '2026-03-24', 'Изложение'),
    (12, 12, 3, 3, 5, DATE '2026-03-24', 'Проектная работа'),
    (13, 1, 5, 5, 4, DATE '2026-03-25', 'Лабораторная работа'),
    (14, 2, 1, 1, 5, DATE '2026-03-25', 'Контрольная работа'),
    (15, 3, 6, 6, 4, DATE '2026-03-25', 'Аудирование');

INSERT INTO attendance (attendance_id, student_id, schedule_id, attendance_status, mark_time)
VALUES
    (1, 1, 1, 'present', TIMESTAMP '2026-03-23 08:30:00'),
    (2, 2, 2, 'late', TIMESTAMP '2026-03-23 09:25:00'),
    (3, 3, 3, 'present', TIMESTAMP '2026-03-23 10:15:00'),
    (4, 4, 4, 'present', TIMESTAMP '2026-03-23 11:10:00'),
    (5, 5, 5, 'absent', TIMESTAMP '2026-03-23 12:05:00'),
    (6, 6, 6, 'present', TIMESTAMP '2026-03-23 13:00:00'),
    (7, 7, 1, 'late', TIMESTAMP '2026-03-23 08:37:00'),
    (8, 8, 2, 'present', TIMESTAMP '2026-03-23 09:20:00'),
    (9, 9, 3, 'present', TIMESTAMP '2026-03-23 10:10:00'),
    (10, 10, 4, 'absent', TIMESTAMP '2026-03-23 11:05:00'),
    (11, 11, 5, 'present', TIMESTAMP '2026-03-23 12:00:00'),
    (12, 12, 6, 'late', TIMESTAMP '2026-03-23 13:08:00'),
    (13, 1, 7, 'present', TIMESTAMP '2026-03-24 08:30:00'),
    (14, 2, 8, 'present', TIMESTAMP '2026-03-24 09:20:00'),
    (15, 3, 9, 'late', TIMESTAMP '2026-03-24 10:18:00'),
    (16, 4, 10, 'present', TIMESTAMP '2026-03-24 11:10:00'),
    (17, 5, 11, 'present', TIMESTAMP '2026-03-24 12:00:00'),
    (18, 6, 12, 'absent', TIMESTAMP '2026-03-24 13:00:00');

INSERT INTO confidential_data (id, name, hash)
VALUES
    (1, 'паспорт_ученика', encode(digest('4510 123456', 'sha256'), 'hex')),
    (2, 'телефон_родителя', encode(digest('+7-900-123-45-67', 'sha256'), 'hex')),
    (3, 'снилс_ученика', encode(digest('123-456-789 00', 'sha256'), 'hex')),
    (4, 'медицинская_карта', encode(digest('МК-2026-0001', 'sha256'), 'hex')),
    (5, 'адрес_проживания', encode(digest('Москва, Школьная улица, 10', 'sha256'), 'hex')),
    (6, 'email_родителя', encode(digest('parent@example.ru', 'sha256'), 'hex'));

INSERT INTO import_log (import_id, source_name, import_time, rows_loaded, status)
VALUES
    (1, 'ученики_xlsx', TIMESTAMP '2026-03-22 12:00:00', 12, 'completed'),
    (2, 'расписание_csv', TIMESTAMP '2026-03-22 12:30:00', 12, 'completed'),
    (3, 'оценки_json', TIMESTAMP '2026-03-22 13:00:00', 15, 'completed'),
    (4, 'посещаемость_csv', TIMESTAMP '2026-03-22 13:30:00', 18, 'completed'),
    (5, 'кабинеты_xlsx', TIMESTAMP '2026-03-22 14:00:00', 7, 'completed'),
    (6, 'родители_csv', TIMESTAMP '2026-03-22 14:30:00', 0, 'failed');

INSERT INTO monitoring_log (log_id, event_time, event_type, description)
VALUES
    (1, TIMESTAMP '2026-03-22 13:00:00', 'db_start', 'Контейнер PostgreSQL для Школы №1416 успешно запущен'),
    (2, TIMESTAMP '2026-03-22 13:10:00', 'import_completed', 'Тестовые данные загружены и доступны для демонстрации'),
    (3, TIMESTAMP '2026-03-22 13:20:00', 'data_check', 'Проверены связи между учениками и классами'),
    (4, TIMESTAMP '2026-03-22 13:40:00', 'import_completed', 'Импорт расписания завершен без конфликтов'),
    (5, TIMESTAMP '2026-03-22 14:10:00', 'data_check', 'Проверены ограничения уникальности для кабинетов'),
    (6, TIMESTAMP '2026-03-22 14:35:00', 'error', 'Файл родители_csv не прошел проверку структуры'),
    (7, TIMESTAMP '2026-03-22 15:00:00', 'data_check', 'Итоговая проверка демонстрационных данных выполнена');

SELECT setval('classes_class_id_seq', (SELECT MAX(class_id) FROM classes));
SELECT setval('teachers_teacher_id_seq', (SELECT MAX(teacher_id) FROM teachers));
SELECT setval('subjects_subject_id_seq', (SELECT MAX(subject_id) FROM subjects));
SELECT setval('classrooms_classroom_id_seq', (SELECT MAX(classroom_id) FROM classrooms));
SELECT setval('students_student_id_seq', (SELECT MAX(student_id) FROM students));
SELECT setval('schedule_schedule_id_seq', (SELECT MAX(schedule_id) FROM schedule));
SELECT setval('grades_grade_id_seq', (SELECT MAX(grade_id) FROM grades));
SELECT setval('attendance_attendance_id_seq', (SELECT MAX(attendance_id) FROM attendance));
SELECT setval('confidential_data_id_seq', (SELECT MAX(id) FROM confidential_data));
SELECT setval('import_log_import_id_seq', (SELECT MAX(import_id) FROM import_log));
SELECT setval('monitoring_log_log_id_seq', (SELECT MAX(log_id) FROM monitoring_log));
