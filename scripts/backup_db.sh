#!/bin/bash
set -e

BACKUP_DIR="/home/ubuntu/energy-iot-saas/backups"
RETENTION_DAYS=30
DB_USER="energy_iot"
DB_NAME="energy_iot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

cd /home/ubuntu/energy-iot-saas/backend

sudo docker compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup created: ${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"
