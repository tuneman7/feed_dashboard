#!/bin/bash

# Clean and safe pgAdmin 4 installer using module launch and config override

echo "[1/5] Removing previous installations..."
pip uninstall -y pgadmin4 2>/dev/null
rm -rf .pgadmin ./pgadmin-venv /var/lib/pgadmin 2>/dev/null

echo "[2/5] Creating and activating virtual environment..."
VENV_DIR="./pgadmin-venv"
python3 -m venv "$VENV_DIR"

if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Failed to activate virtual environment. Skipping remaining steps."
    return 0 2>/dev/null || exit 0
fi

echo "[3/5] Installing pgAdmin4 from official wheel..."
pip install --upgrade pip
pip install https://ftp.postgresql.org/pub/pgadmin/pgadmin4/v9.4/pip/pgadmin4-9.4-py3-none-any.whl

echo "[4/5] Writing config_local.py and setting up storage..."
mkdir -p .pgadmin/storage .pgadmin/sessions

# Locate pgadmin4 package install path
PGADMIN_PKG_DIR=$(python -c "
try:
    import pgadmin4, os
    print(os.path.dirname(pgadmin4.__file__) or '')
except:
    print('')
")

if [[ -z "$PGADMIN_PKG_DIR" || ! -d "$PGADMIN_PKG_DIR" ]]; then
    echo "Could not determine pgadmin4 package path. Skipping config_local.py write."
else
    cat > "$PGADMIN_PKG_DIR/config_local.py" <<EOL
import os
DATA_DIR = os.path.abspath(".pgadmin")
LOG_FILE = os.path.join(DATA_DIR, "pgadmin4.log")
SQLITE_PATH = os.path.join(DATA_DIR, "pgadmin4.db")
SESSION_DB_PATH = os.path.join(DATA_DIR, "sessions")
STORAGE_DIR = os.path.join(DATA_DIR, "storage")
SERVER_MODE = True
EOL
    echo "config_local.py written to: $PGADMIN_PKG_DIR"
fi

echo "[5/5] Creating launch script using module entrypoint..."
cat > ./pgadmin-start.sh <<'EOL'
#!/bin/bash
source ./pgadmin-venv/bin/activate
python -m pgadmin4
EOL

chmod +x ./pgadmin-start.sh
echo "Launch script created: ./pgadmin-start.sh"

echo
echo "Installation complete. To start pgAdmin4:"
echo "1. Run: ./pgadmin-start.sh"
echo "2. Access the web interface at: http://localhost:5050"
echo "3. Press Ctrl+C to stop"

read -p "Launch pgAdmin4 now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] && [[ -f ./pgadmin-start.sh ]]; then
    ./pgadmin-start.sh
fi
