# База данных и система администрирования ГБОУ Школа № 1416

Практическая часть выпускной квалификационной работы. Включает:

- развёртывание PostgreSQL 16 в Docker;
- DDL-схема, ролевая модель, представления, триггеры;
- ETL-модуль автоматизированного импорта (CSV / XLSX / JSON);
- модуль мониторинга СУБД (6 ключевых метрик);
- скрипт резервного копирования;
- веб-приложение администратора на Flask;
- набор тестов pytest (импорт, производительность, ролевая модель).

## Структура проекта

```
school_1416_db/
├── docker-compose.yml      Контейнер PostgreSQL 16
├── requirements.txt        Зависимости Python
├── README.md               Этот документ
│
├── sql/                    Скрипты инициализации БД
│   ├── 01_schema.sql         DDL — 11 таблиц + индексы
│   ├── 02_roles.sql          Роли admin_db / operator_user / auditor_user
│   ├── 03_seed.sql           Демонстрационные данные
│   ├── 04_views.sql          Представления для типовых запросов
│   └── 05_triggers.sql       Триггеры журналирования и контроля
│
├── etl/                    Модуль импорта
│   ├── import_data.py        Универсальный импортёр
│   ├── validators.py         Проверка структуры файлов
│   ├── generate_samples.py   Генератор тестовых файлов
│   └── samples/              Тестовые файлы импорта
│
├── monitoring/             Модуль мониторинга
│   ├── monitoring.py         Сбор метрик и запись в журнал
│   └── queries.sql           Готовые SQL для DBeaver
│
├── backup/                 Резервное копирование
│   ├── backup.sh             Linux / macOS
│   └── backup.bat            Windows
│
├── web_app/                Веб-приложение администратора
│   ├── app.py                Точка входа Flask
│   ├── config.py             Конфигурация
│   ├── templates/            Jinja2-шаблоны
│   └── static/               CSS
│
└── tests/                  Тесты pytest
    ├── conftest.py
    ├── test_import.py
    ├── test_performance.py
    └── test_roles.py
```

## Требования к окружению

| Компонент | Версия | Назначение |
|---|---|---|
| Docker | ≥ 24.0 | Запуск PostgreSQL |
| Python | ≥ 3.11 | ETL, мониторинг, веб |
| Браузер | любой современный | Веб-интерфейс |
| DBeaver | ≥ 23 | Графическое администрирование (опционально) |

## Быстрый старт

### 1. Запуск базы данных

```bash
docker compose up -d
```

При первом запуске контейнер автоматически выполнит все скрипты из `sql/`
в алфавитном порядке: создаст схему, роли, представления, триггеры
и загрузит демонстрационные данные.

Проверка статуса:

```bash
docker ps                                     # контейнер должен быть Up
docker logs school_1416_postgres | tail -30   # проверка инициализации
```

### 2. Установка Python-зависимостей

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Запуск веб-приложения

```bash
cd web_app
python app.py
```

Откройте `http://localhost:5000`. Учётные данные по умолчанию:

| Роль | Логин | Пароль |
|---|---|---|
| Администратор БД | `admin_db` | `Admin123!` |
| Оператор | `operator_user` | `Operator123!` |
| Аудитор | `auditor_user` | `Auditor123!` |

## Сценарии работы

### Импорт из командной строки

```bash
cd etl
python import_data.py samples/students_import.xlsx students
python import_data.py samples/grades_import.csv  grades
python import_data.py samples/schedule_import.json schedule
```

### Импорт через веб-интерфейс

1. Войти как `admin_db` или `operator_user`.
2. Меню → «Импорт».
3. Выбрать целевую таблицу и файл.
4. После загрузки результат отобразится на этой же странице,
   запись появится в «Журнале импорта».

### Снятие метрик мониторинга

Разовый снимок в консоль:
```bash
cd monitoring
python monitoring.py
```

Регулярный сбор каждые 60 секунд (например, в фоне на сервере):
```bash
python monitoring.py --daemon --interval 60
```

Снимок через веб (только `admin_db`):
- Меню → «Мониторинг» → кнопка «📸 Снять снимок метрик сейчас».

### Резервное копирование

Linux / macOS:
```bash
./backup/backup.sh
```

Windows:
```cmd
backup\backup.bat
```

Скрипт создаёт файл вида `school_1416_db_YYYYMMDD_HHMMSS.dump` в формате
PostgreSQL custom (`-Fc`). Восстановление:

```bash
docker exec -i school_1416_postgres pg_restore \
    -U admin -d school_1416_db -c < backup/school_1416_db_20260101_120000.dump
```

Автоматизация в cron (Linux):
```cron
0 3 * * *  /home/user/school_1416_db/backup/backup.sh >> /var/log/school_backup.log 2>&1
```

### Запуск тестов

```bash
pytest tests/ -v
```

При запущенной БД будут выполнены три набора:
- `test_import.py` — корректность ETL,
- `test_performance.py` — время выполнения SELECT на представлениях,
- `test_roles.py` — соответствие матрицы доступа.

## Руководство администратора

### Подключение через DBeaver

1. New Database Connection → PostgreSQL.
2. Host: `localhost`, Port: `5432`, Database: `school_1416_db`.
3. User: `admin` / Password: `Admin123!` (для полного доступа)
   или одна из ролей ограниченного доступа.
4. Test Connection → Finish.

В дереве подключений будут видны:
- 11 таблиц предметной области и журналов;
- 5 представлений (`v_student_grades`, `v_class_schedule`,
  `v_attendance_summary`, `v_recent_imports`, `v_recent_monitoring`);
- 2 триггера (`trg_import_to_monitoring`, `trg_check_grade_active`);
- роли `admin_db`, `operator_user`, `auditor_user`.

ER-диаграмма: правый клик на схеме `public` → View Diagram.

### Регламентные работы

| Операция | Периодичность | Кто выполняет | Команда |
|---|---|---|---|
| Резервное копирование | Ежедневно в 03:00 | cron | `backup.sh` |
| Сбор метрик | Каждые 60 с | systemd / supervisor | `monitoring.py --daemon` |
| Проверка целостности | Еженедельно | DBA вручную | `pytest tests/` |
| Обновление PostgreSQL | По выходу патч-версий | DBA | `docker compose pull && docker compose up -d` |

### Действия при инцидентах

- **Импорт завершился ошибкой.** Открыть «Журнал импорта», найти запись
  со статусом `failed`. Проверить структуру файла (см. подсказку колонок
  на странице «Импорт»). Транзакция отката гарантирует, что данные в БД
  не повреждены.
- **Cache hit ratio упал ниже 0.9.** Возможен недостаток `shared_buffers`
  или активная индексная просадка. Проверить через `queries.sql` запрос 7
  (использование индексов).
- **Появились deadlocks.** Журнал PostgreSQL: `docker logs school_1416_postgres`.

### Разграничение доступа

Реализуется через роли PostgreSQL (см. `sql/02_roles.sql`):

| Таблица | admin_db | operator_user | auditor_user |
|---|---|---|---|
| students, teachers, classes, subjects, classrooms | S/I/U/D | S/I/U | SELECT |
| schedule, grades, attendance | S/I/U/D | S/I/U | SELECT |
| confidential_data | S/I/U/D | — | SELECT |
| import_log | S/I/U/D | SELECT | SELECT |
| monitoring_log | S/I/U/D | — | SELECT |

S = SELECT, I = INSERT, U = UPDATE, D = DELETE.

Веб-приложение использует переданный пользователем пароль для прямого
подключения к СУБД от имени роли. Это гарантирует, что разграничение
прав происходит **на уровне PostgreSQL** и не может быть обойдено
ошибкой в коде приложения.
