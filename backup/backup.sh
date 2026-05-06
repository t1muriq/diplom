#!/usr/bin/env bash
# Резервное копирование БД school_1416_db.
# Запускается из корня проекта или может быть добавлен в cron.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
DUMP_FILE="${BACKUP_DIR}/school_1416_db_${TIMESTAMP}.dump"

CONTAINER="${CONTAINER:-school_1416_postgres}"
DB_NAME="${DB_NAME:-school_1416_db}"
DB_USER="${DB_USER:-admin}"

# Проверяем, что контейнер запущен
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ОШИБКА: контейнер ${CONTAINER} не запущен" >&2
    exit 1
fi

echo "[$(date +'%H:%M:%S')] Создание бэкапа: ${DUMP_FILE}"

docker exec -t "${CONTAINER}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc \
    > "${DUMP_FILE}"

SIZE=$(du -h "${DUMP_FILE}" | cut -f1)
echo "[$(date +'%H:%M:%S')] Готово. Размер: ${SIZE}"

# Ротация: оставляем 7 последних бэкапов
cd "${BACKUP_DIR}"
ls -1t school_1416_db_*.dump 2>/dev/null | tail -n +8 | xargs -r rm -v
