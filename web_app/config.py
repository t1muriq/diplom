"""Конфигурация веб-приложения."""

import os


class Config:
    """Базовая конфигурация."""

    # Соль для подписи cookie сессий. В production задаётся через env.
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "school1416-dev-secret-CHANGE-IN-PRODUCTION",
    )

    # Параметры подключения к PostgreSQL для каждой роли.
    # Логика: пользователь авторизуется через connect под своими
    # учётными данными — если соединение установилось, значит роль
    # существует и пароль верный. PostgreSQL сам обеспечивает
    # разграничение доступа к таблицам.
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "school_1416_db")

    # Допустимые роли (должны существовать в PostgreSQL — см. 02_roles.sql)
    ALLOWED_ROLES = ("admin_db", "operator_user", "auditor_user")

    # Где сохранять загруженные через веб файлы импорта
    UPLOAD_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "uploads",
    )
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 МБ
