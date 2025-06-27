#!/bin/bash
# Activate virtual environment and run Streamlit app
source venv/bin/activate
streamlit run app/gui/main.py --server.port 8501 --server.address 0.0.0.0
