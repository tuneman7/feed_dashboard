#!/bin/bash

VENV_DIR="./venv"
REQUIREMENTS="requirements.txt"

echo "[1/4] Checking Python virtual environment..."

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -d "$VENV_DIR" ]]; then
        echo "Activating existing virtual environment at $VENV_DIR"
        source "$VENV_DIR/bin/activate"
    else
        echo "Virtual environment not found. Creating one at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"

        if [[ -f "$REQUIREMENTS" ]]; then
            echo "[2/4] Installing requirements from $REQUIREMENTS"
            pip install --upgrade pip
            pip install -r "$REQUIREMENTS"
        else
            echo "No $REQUIREMENTS file found. Skipping package install."
        fi
    fi
else
    echo "Already running inside a virtual environment: $VIRTUAL_ENV"
fi

echo "[3/4] Verifying Python and pip environment..."
which python
python --version
which pip

echo "[4/4] Environment is ready."
