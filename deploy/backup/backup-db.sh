#!/bin/bash
# Saves a copy of the TaskFlow database into ~/backups
# Runs every night at 16:00 UTC (3am Melbourne) using cron:
#   0 16 * * * /home/azureuser/backup-db.sh
mkdir -p ~/backups
docker exec taskflow-db pg_dump -U taskflow taskflow > ~/backups/taskflow_$(date +%F).sql
# Keep only the 7 newest backups
ls -t ~/backups/*.sql | tail -n +8 | xargs -r rm