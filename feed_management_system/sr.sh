#!/bin/bash
source ./venv-bootstrap.sh
APP="streamlit_app.py"
LOG_FILE="streamlit.log"
PID_FILE=".streamlit_pid"
ENV_FILE="db.env"

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
  # Write values to db.env (with quoting for special characters)
  cat > "$ENV_FILE" <<EOF
DB_HOST="$DB_HOST"
DB_PORT="$DB_PORT"
DB_NAME="$DB_NAME"
DB_USER="$DB_USER"
DB_PASSWORD="$DB_PASSWORD"
EOF
  # Export values for current shell
  export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
  echo "✅ Environment configured and exported (using AWS RDS dst-dashboard-fast)."
}

start_streamlit() {
  echo "🚀 Starting Streamlit..."
  nohup streamlit run "$APP" > "$LOG_FILE" 2>&1 &
  PID=$!
  echo $PID > "$PID_FILE"
  echo "✅ Streamlit started with PID $PID"
  tail -f "$LOG_FILE" &
  TAIL_PID=$!
}

kill_streamlit() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "🛑 Killing Streamlit process $PID"
      kill "$PID"
    fi
    rm -f "$PID_FILE"
  fi
  if [ -n "$TAIL_PID" ]; then
    kill "$TAIL_PID" 2>/dev/null
  fi
}

# Prompt DB config & always export fresh
select_database

kill_streamlit

# Start Streamlit and tail log
start_streamlit

# Kill the tail process and exit, leaving Streamlit running in background
if [ -n "$TAIL_PID" ]; then
  kill "$TAIL_PID" 2>/dev/null
fi

echo "🎉 Streamlit is running in the background with PID $(cat $PID_FILE)"
echo "📋 To check status: ps aux | grep streamlit"
echo "📋 To view logs: tail -f $LOG_FILE"
echo "📋 To stop: kill \$(cat $PID_FILE)"

# **PRINT OUT THE PORTS**
echo ""
echo "🌐 Access URLs:"
echo "   Local: http://localhost:8501"
echo "   External: http://$(curl -s http://checkip.amazonaws.com/):8501"

# **EXPLICIT EXIT COMMAND**
exit 0