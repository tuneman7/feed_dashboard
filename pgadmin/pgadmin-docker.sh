#!/bin/bash

# pgAdmin setup script for EC2 to connect to RDS
# Run this on your EC2 instance

CONTAINER_NAME="pgadmin4"
PGADMIN_DIR="$(pwd -P)/.pgadmin"   # Resolves physical path
PGADMIN_PORT=5050
EMAIL="admin@example.com"
PASSWORD="admin"

# RDS connection details
RDS_ENDPOINT="dst-dashboard-database-fast.ckqboenmhdca.us-east-1.rds.amazonaws.com"
RDS_PORT="5432"

echo "[1/9] Stopping and removing any existing container named $CONTAINER_NAME..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop $CONTAINER_NAME > /dev/null 2>&1
    docker rm $CONTAINER_NAME > /dev/null 2>&1
fi

echo "[2/9] Cleaning up old pgAdmin directory..."
if [ -d "$PGADMIN_DIR" ]; then
    sudo rm -rf "$PGADMIN_DIR"
fi

echo "[3/9] Creating pgAdmin data directory at $PGADMIN_DIR"
mkdir -p "$PGADMIN_DIR"

# Create required subdirectories with correct permissions
mkdir -p "$PGADMIN_DIR/sessions"
mkdir -p "$PGADMIN_DIR/storage"

echo "[4/9] Setting proper permissions for pgAdmin container..."
# pgAdmin runs as user ID 5050, so set ownership accordingly
sudo chown -R 5050:5050 "$PGADMIN_DIR"
sudo chmod -R 755 "$PGADMIN_DIR"

echo "[5/9] Pulling pgAdmin image if not already present..."
docker image inspect dpage/pgadmin4:latest > /dev/null 2>&1 || docker pull dpage/pgadmin4:latest

echo "[6/9] Starting container on port $PGADMIN_PORT..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PGADMIN_PORT:80 \
  -e PGADMIN_DEFAULT_EMAIL="$EMAIL" \
  -e PGADMIN_DEFAULT_PASSWORD="$PASSWORD" \
  -e PGADMIN_CONFIG_SESSION_DB_PATH="'/var/lib/pgadmin/sessions'" \
  -e PGADMIN_CONFIG_STORAGE_DIR="'/var/lib/pgadmin/storage'" \
  -v "$PGADMIN_DIR":/var/lib/pgadmin \
  --user 5050:5050 \
  dpage/pgadmin4 > /dev/null

echo "[7/9] Waiting for pgAdmin to become available..."
# Get EC2 public IP for access URL
EC2_PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
PGADMIN_URL="http://$EC2_PUBLIC_IP:$PGADMIN_PORT"

RETRIES=60
echo "Waiting for pgAdmin to start (this may take up to 60 seconds)..."
until curl --silent --output /dev/null --head http://localhost:$PGADMIN_PORT; do
  ((RETRIES--))
  if [ $RETRIES -le 0 ]; then
    echo "pgAdmin did not start in time. Checking logs..."
    docker logs $CONTAINER_NAME
    echo
    echo "Troubleshooting steps:"
    echo "1. Check if the container is running: docker ps -a"
    echo "2. View full logs: docker logs $CONTAINER_NAME"
    echo "3. Try restarting: docker restart $CONTAINER_NAME"
    echo "4. If still failing, try recreating with different permissions:"
    echo "   sudo rm -rf $PGADMIN_DIR"
    echo "   mkdir -p $PGADMIN_DIR"
    echo "   sudo chmod -R 777 $PGADMIN_DIR"
    return 0 2>/dev/null || exit 1
  fi
  if [ $((RETRIES % 10)) -eq 0 ]; then
    echo "Still waiting... ($RETRIES attempts remaining)"
  fi
  sleep 2
done

echo "[8/9] pgAdmin is now running successfully!"

echo "[9/9] Testing RDS connectivity..."
timeout 5 bash -c "</dev/tcp/$RDS_ENDPOINT/$RDS_PORT" && \
  echo "RDS connection test successful" || \
  echo "RDS connection test failed"

echo
echo "=== pgAdmin Setup Complete ==="
echo
echo " Access pgAdmin at: $PGADMIN_URL"
echo " Login with:"
echo "   Email   : $EMAIL"
echo "   Password: $PASSWORD"
echo
echo " To connect to your RDS database in pgAdmin:"
echo "   1. Click 'Add New Server'"
echo "   2. General tab:"
echo "      Name: RDS PostgreSQL"
echo "   3. Connection tab:"
echo "      Host: $RDS_ENDPOINT"
echo "      Port: $RDS_PORT"
echo "      Database: pipeline_management"
echo "      Username: postgres"
echo "      Password: Dashboard2025!\$"
echo
echo " Notes:"
echo "   - Make sure your RDS security group allows connections from this EC2"
echo "   - Access pgAdmin from your local browser using the URL above"
echo "   - Port $PGADMIN_PORT should be open in your EC2 security group"
echo
echo " Troubleshooting:"
echo "   - View logs: docker logs $CONTAINER_NAME"
echo "   - Restart: docker restart $CONTAINER_NAME"
echo "   - Stop: docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
echo "   - Container status: docker ps -a | grep $CONTAINER_NAME"