# Feed Management System

A Python-based application for managing data feeds and processing runs.

## Architecture

- **Data Layer**: SQLAlchemy ORM with PostgreSQL/SQLite
- **Business Layer**: Service classes with business logic
- **Presentation Layer**: Streamlit GUI + FastAPI REST API

## Setup

The project has been automatically set up. To get started:

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Configure Database
Edit `.env` file with your database connection details.

### 3. Run Applications

**Streamlit GUI:**
```bash
./run_streamlit.sh
# Or manually: streamlit run app/gui/main.py
```

**FastAPI (optional):**
```bash
./run_api.sh
# Or manually: uvicorn app.api.main:app --reload
```

## Project Structure

```
feed_management_system/
├── app/                    # Main application code
│   ├── config/            # Configuration files
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic services
│   ├── api/               # FastAPI routes
│   ├── gui/               # Streamlit interface
│   └── core/              # Core utilities
├── migrations/            # Database migrations
├── tests/                 # Test files
├── data/                  # Data files
├── logs/                  # Log files
├── venv/                  # Virtual environment
└── requirements.txt       # Python dependencies
```

## Development

- **Format code**: `black app/`
- **Sort imports**: `isort app/`
- **Run tests**: `pytest`
- **Lint code**: `flake8 app/`

## Database Schema

The application uses the following main tables:
- `code_type`: Code type definitions
- `system_codes`: System enumeration values
- `feed`: Feed configurations
- `feed_run`: Feed execution runs
- `feed_run_details`: Detailed run information

See the database schema documentation for complete details.
