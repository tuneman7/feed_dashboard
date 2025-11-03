#!/bin/bash

APP_DIR="$HOME/app/feed_management_system"
RUN_SCRIPT="$APP_DIR/run_processor.sh"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/alert_processor.log"

# -----------------------------------
# Trim log file to last 10,000 lines
# -----------------------------------
if [ -f "$LOG_FILE" ]; then
  LINE_COUNT=$(wc -l < "$LOG_FILE")
  MAX_LINES=10000

  if [ "$LINE_COUNT" -gt "$MAX_LINES" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') trimming log... ($LINE_COUNT → $MAX_LINES lines)" >> "$LOG_FILE"
    # keep last 10,000 lines safely
    tail -n "$MAX_LINES" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') log trimmed." >> "$LOG_FILE"
  fi
fi
# -----------------------------------

deactivate 2>/dev/null

source "$HOME/app/feed_management_system/venv/bin/activate"

select_database() {
  # Default to option 3 without prompting
  choice=3
  case "$choice" in
    1)
      DB_HOST="localhost"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="$USER"
      DB_PASSWORD=""
      ;;
    2)
      DB_HOST="dst-pipeline-dashboard.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="postgres"
      DB_PASSWORD="Dashboard2025!$"
      ;;
    3)
      DB_HOST="dst-dashboard-database-fast.ckqboenmhdca.us-east-1.rds.amazonaws.com"
      DB_PORT="5432"
      DB_NAME="pipeline_management"
      DB_USER="postgres"
      DB_PASSWORD="Dashboard2025!$"
      ;;
    *)
      echo "Invalid choice. Please choose 1, 2, or 3."
      select_database
      return
      ;;
  esac

  ENV_FILE="$APP_DIR/db.env"

  cat > "$ENV_FILE" <<EOF
DB_HOST="$DB_HOST"
DB_PORT="$DB_PORT"
DB_NAME="$DB_NAME"
DB_USER="$DB_USER"
DB_PASSWORD="$DB_PASSWORD"
EOF

  export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
  echo "✅ Environment configured and exported (using AWS RDS dst-dashboard-fast)."
}

select_database

python alert_processor.py >> "$LOG_FILE" 2>&1
