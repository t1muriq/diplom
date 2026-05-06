CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE classes (
    class_id SERIAL PRIMARY KEY,
    class_name VARCHAR(10) NOT NULL UNIQUE,
    grade_level INT NOT NULL CHECK (grade_level BETWEEN 1 AND 11),
    academic_year VARCHAR(9) NOT NULL,
    profile_name VARCHAR(100) NOT NULL DEFAULT 'general'
);

CREATE TABLE teachers (
    teacher_id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    position_title VARCHAR(100) NOT NULL,
    UNIQUE (last_name, first_name, middle_name)
);

CREATE TABLE subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_name VARCHAR(150) NOT NULL UNIQUE,
    weekly_hours INT NOT NULL CHECK (weekly_hours > 0)
);

CREATE TABLE classrooms (
    classroom_id SERIAL PRIMARY KEY,
    room_number VARCHAR(20) NOT NULL,
    building VARCHAR(100) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    UNIQUE (room_number, building)
);

CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    birth_date DATE NOT NULL,
    class_id INT NOT NULL REFERENCES classes(class_id) ON DELETE RESTRICT,
    admission_year INT NOT NULL CHECK (admission_year BETWEEN 2015 AND 2100),
    student_status VARCHAR(20) NOT NULL DEFAULT 'active',
    CHECK (student_status IN ('active', 'graduated', 'expelled')),
    UNIQUE (last_name, first_name, birth_date)
);

CREATE TABLE schedule (
    schedule_id SERIAL PRIMARY KEY,
    class_id INT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    teacher_id INT NOT NULL REFERENCES teachers(teacher_id) ON DELETE RESTRICT,
    classroom_id INT NOT NULL REFERENCES classrooms(classroom_id) ON DELETE RESTRICT,
    lesson_date DATE NOT NULL,
    lesson_number INT NOT NULL CHECK (lesson_number BETWEEN 1 AND 8),
    UNIQUE (class_id, lesson_date, lesson_number),
    UNIQUE (classroom_id, lesson_date, lesson_number),
    UNIQUE (teacher_id, lesson_date, lesson_number)
);

CREATE TABLE grades (
    grade_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    teacher_id INT NOT NULL REFERENCES teachers(teacher_id) ON DELETE RESTRICT,
    grade_value INT NOT NULL CHECK (grade_value BETWEEN 2 AND 5),
    grade_date DATE NOT NULL DEFAULT CURRENT_DATE,
    grade_comment VARCHAR(255)
);

CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    schedule_id INT NOT NULL REFERENCES schedule(schedule_id) ON DELETE CASCADE,
    attendance_status VARCHAR(20) NOT NULL,
    mark_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (attendance_status IN ('present', 'absent', 'late')),
    UNIQUE (student_id, schedule_id)
);

CREATE TABLE confidential_data (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE import_log (
    import_id SERIAL PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    import_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rows_loaded INT NOT NULL DEFAULT 0 CHECK (rows_loaded >= 0),
    status VARCHAR(30) NOT NULL CHECK (status IN ('completed', 'failed', 'in_progress'))
);

CREATE TABLE monitoring_log (
    log_id SERIAL PRIMARY KEY,
    event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(100) NOT NULL CHECK (event_type IN ('db_start', 'import_completed', 'data_check', 'error', 'warning', 'metric_check')),
    description TEXT NOT NULL
);

CREATE INDEX idx_students_class_id ON students(class_id);
CREATE INDEX idx_schedule_class_id ON schedule(class_id);
CREATE INDEX idx_schedule_teacher_id ON schedule(teacher_id);
CREATE INDEX idx_grades_student_id ON grades(student_id);
CREATE INDEX idx_grades_subject_id ON grades(subject_id);
CREATE INDEX idx_attendance_student_id ON attendance(student_id);
CREATE INDEX idx_confidential_data_name ON confidential_data(name);
