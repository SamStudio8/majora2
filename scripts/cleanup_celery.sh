#!/usr/bin/bash
find /var/www/majora/private/celery_results -type f -daystart -mtime +2 -exec rm -rf {} \;
