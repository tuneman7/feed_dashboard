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

echo "[1/8] Stopping and removing any existing container named $CONTAINER_NAME..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop $CONTAINER_NAME > /dev/null 2>&1
    docker rm $CONTAINER_NAME > /dev/null 2>&1
fi

echo "[2/8] Ensuring pgAdmin data directory exists at $PGADMIN_DIR"
mkdir -p "$PGLADMIN_DIR"

# Fix permissions for pgAdmin container
sudo chown -R 5050:5050 "$PGADMIN_DIR" 2>/dev/null || chmod -R 777 "$PGADMIN_DIR"

echo "[3/8] Pulling pgAdmin image if not already present..."
docker image inspect dpage/pgadmin4:latest > /dev/null 2>&1 || docker pull dpage/pgadmin4:latest

echo "[4/8] Starting container on port $PGADMIN_PORT..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PGADMIN_PORT:80 \
  -e PGADMIN_DEFAULT_EMAIL="$EMAIL" \
  -e PGADMIN_DEFAULT_PASSWORD="$PASSWORD" \
  -v "$PGADMIN_DIR":/var/lib/pgadmin \
  dpage/pgadmin4 > /dev/null

echo "[5/8] Waiting for pgAdmin to become available..."
# Get EC2 public IP for access URL
EC2_PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
PGADMIN_URL="http://$EC2_PUBLIC_IP:$PGLADMIN_PORT"

RETRIES=30
until curl --silent --output /dev/null --head http://localhost:$PGLADMIN_PORT; do
  ((RETRIES--))
  if [ $RETRIES -le 0 ]; then
    echo "pgAdmin did not start in time. Check docker logs with: docker logs $CONTAINER_NAME"
    echo "Try fixing permissions manually:"
    echo "  sudo rm -rf $PGLADMIN_DIR"
    echo "  mkdir -p $PGLADMIN_DIR"
    echo "  sudo chown -R 5050:5050 $PGLADMIN_DIR"
    return 0 2>/dev/null || exit 0
  fi
  sleep 1
done

echo "[6/8] pgAdmin is now running successfully!"

echo "[7/8] Testing RDS connectivity..."
timeout 5 bash -c "</dev/tcp/$RDS_ENDPOINT/$RDS_PORT" && \
  echo "RDS connection test successful" || \
  echo "RDS connection test failed"

echo
echo "[8/8] === pgAdmin Setup Complete ==="
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
echo "      Database: your_database_name"
echo "      Username: your_rds_username"
echo "      Password: your_rds_password"
echo
echo " Notes:"
echo "   - Make sure your RDS security group allows connections from this EC2"
echo "   - Access pgAdmin from your local browser using the URL above"
echo "   - Port $PGLADMIN_PORT should be open in your EC2 security group"
echo
echo " Troubleshooting:"
echo "   - View logs: docker logs $CONTAINER_NAME"
echo "   - Restart: docker restart $CONTAINER_NAME"
echo "   - Stop: docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"