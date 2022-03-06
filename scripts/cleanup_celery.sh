#!/usr/bin/bash
find /var/www/majora/private/celery_results -type f -daystart -mtime +7 -exec rm -rf {} \;
