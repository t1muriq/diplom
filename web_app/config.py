"""Конфигурация веб-приложения школы №1416."""

import os


class Config:
    """Базовая конфигурация."""

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "school1416-dev-secret-CHANGE-IN-PRODUCTION",
    )

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "school_1416_db")

    # Технические роли (вход по логину = имя роли + пароль роли)
    ALLOWED_ROLES = ("admin_db", "operator_user", "auditor_user")

    # Учётные данные служебной роли teacher_user, под которой
    # веб-приложение подключается к СУБД от имени учителей.
    # Конкретный учитель идентифицируется параметром сессии
    # app.current_teacher_id, который читают RLS-политики.
    TEACHER_DB_ROLE = "teacher_user"
    TEACHER_DB_PASSWORD = os.getenv("TEACHER_DB_PASSWORD", "Teacher123!")

    UPLOAD_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "uploads",
    )
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 МБ
