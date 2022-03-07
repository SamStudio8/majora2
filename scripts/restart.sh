#!/bin/sh
./kill.sh
cd /var/www/majora/majora2

CURRENT_MAJORA_HASH=$(git rev-parse --short HEAD)
echo "CURRENT_MAJORA_HASH=$CURRENT_MAJORA_HASH" > majora_version_file

CURRENT_MAJORA_VERSION=$(head -n1 version.py | cut -f2 -d'=' | tr -d '"')
echo "CURRENT_MAJORA_VERSION=$CURRENT_MAJORA_VERSION" >> majora_version_file

CURRENT_MAJORA_NAME=$(tail -n1 version.py | cut -f2 -d'=' | tr -d '"')
echo "CURRENT_MAJORA_NAME=$CURRENT_MAJORA_NAME" >> majora_version_file

uwsgi --ini wsgi.ini;
celery -A mylims worker -l info --concurrency 6 --max-tasks-per-child 1 > /var/www/majora/majora-celery.log  2>&1 &
