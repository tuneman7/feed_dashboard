#!/bin/bash

# Pipeline Management System Setup Script
# This script creates the project structure, virtual environment, and installs dependencies

# Script continues on errors - no automatic exit

# Configuration
PROJECT_NAME="pipeline_management_system"
PYTHON_VERSION="python3"
VENV_NAME="venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists $PYTHON_VERSION; then
    print_error "Python 3 is not installed. Please install Python 3.8+ first."
    print_warning "Continuing with errors - script will not exit automatically"
    return 1
fi

if ! command_exists pip; then
    print_error "pip is not installed. Please install pip first."
    print_warning "Continuing with errors - script will not exit automatically"
    return 1
fi

PYTHON_VER=$($PYTHON_VERSION --version 2>&1 | awk '{print $2}')
print_success "Found Python $PYTHON_VER"

# Create project root directory
print_status "Creating project structure..."
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Create directory structure
print_status "Setting up directory structure..."

# Main application directories
mkdir -p app/{config,models,services,api/routes,gui/pages,gui/components,core}
mkdir -p migrations/versions
mkdir -p tests
mkdir -p docs
mkdir -p scripts
mkdir -p data/{raw,processed,exports}
mkdir -p logs

# Create __init__.py files for Python packages
touch app/__init__.py
touch app/config/__init__.py
touch app/models/__init__.py
touch app/services/__init__.py
touch app/api/__init__.py
touch app/api/routes/__init__.py
touch app/gui/__init__.py
touch app/gui/pages/__init__.py
touch app/gui/components/__init__.py
touch app/core/__init__.py
touch tests/__init__.py

print_success "Directory structure created"

# Create requirements.txt
print_status "Creating requirements.txt..."
cat > requirements.txt << 'EOF'
# Core Framework
streamlit>=1.28.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Database
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.7
databases[postgresql]>=0.8.0

# Data Visualization
altair>=5.1.0
plotly>=5.17.0
pandas>=2.1.0
numpy>=1.24.0

# Data Validation & Settings
pydantic>=2.4.0
pydantic-settings>=2.0.0

# Utilities
python-dotenv>=1.0.0
pendulum>=2.1.2
structlog>=23.2.0
rich>=13.6.0

# Development & Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.9.0
isort>=5.12.0
flake8>=6.1.0

# Optional: If using SQLite for development
# sqlite3 is included in Python standard library

# Optional: For advanced data tables in Streamlit
streamlit-aggrid>=0.3.4

# Optional: For authentication
# streamlit-authenticator>=0.2.3
EOF

print_success "requirements.txt created"

# Create environment file template
print_status "Creating environment configuration..."
cat > .env.example << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/pipeline_management
# For SQLite development: DATABASE_URL=sqlite:///./pipeline_management.db

# Application Settings
APP_NAME=Pipeline Management System
APP_VERSION=1.0.0
DEBUG=True
LOG_LEVEL=INFO

# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Streamlit Settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Security (generate secure random keys for production)
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
EOF

# Copy to actual .env file
cp .env.example .env
print_success "Environment files created"

# Create virtual environment or handle existing one
print_status "Checking for existing virtual environment..."

if [[ -d "$VENV_NAME" ]]; then
    print_warning "Virtual environment '$VENV_NAME' already exists."
    echo -n "Do you want to destroy and recreate it? (y/n): "
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Destroying existing virtual environment..."
        
        # Deactivate if currently active
        if [[ "$VIRTUAL_ENV" != "" ]]; then
            print_status "Deactivating current virtual environment..."
            deactivate 2>/dev/null || true
        fi
        
        # Remove the directory
        rm -rf "$VENV_NAME"
        print_success "Existing virtual environment removed"
        
        # Create new virtual environment
        print_status "Creating new virtual environment..."
        $PYTHON_VERSION -m venv $VENV_NAME
        
        if [[ ! -d "$VENV_NAME" ]]; then
            print_error "Failed to create virtual environment"
            print_warning "Continuing with errors - please check manually"
        else
            print_success "New virtual environment created: $VENV_NAME"
        fi
    else
        print_status "Using existing virtual environment"
    fi
else
    # Create virtual environment
    print_status "Creating virtual environment..."
    $PYTHON_VERSION -m venv $VENV_NAME
    
    if [[ ! -d "$VENV_NAME" ]]; then
        print_error "Failed to create virtual environment"
        print_warning "Continuing with errors - please check manually"
    else
        print_success "Virtual environment created: $VENV_NAME"
    fi
fi

# Activate virtual environment and install packages
print_status "Activating virtual environment and installing dependencies..."

# Check if virtual environment exists before trying to activate
if [[ ! -d "$VENV_NAME" ]]; then
    print_error "Virtual environment directory not found. Cannot continue with package installation."
    print_warning "Please run the script again or create the virtual environment manually"
else
    # Source activation script
    print_status "Activating virtual environment..."
    source $VENV_NAME/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip || print_warning "Failed to upgrade pip, continuing anyway..."
    
    # Install requirements
    print_status "Installing Python packages from requirements.txt..."
    if pip install -r requirements.txt; then
        print_success "All dependencies installed successfully"
    else
        print_error "Some packages failed to install"
        print_warning "Check the error messages above and install manually if needed"
    fi
fi

# Create basic application files
print_status "Creating basic application files..."

# Create main Streamlit app
cat > app/gui/main.py << 'EOF'
"""
Main Streamlit Application Entry Point
"""
import streamlit as st
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Configure Streamlit page
st.set_page_config(
    page_title="Pipeline Management System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.title("📊 Pipeline Management System")
    st.markdown("---")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Dashboard", "Pipelines", "Pipeline Runs", "System Codes", "Admin"]
    )
    
    # Main content area
    if page == "Dashboard":
        st.header("Dashboard")
        st.info("Welcome to the Pipeline Management System!")
        
        # Sample metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Pipelines", "12", "2")
        with col2:
            st.metric("Active Runs", "3", "-1")
        with col3:
            st.metric("Success Rate", "94.5%", "1.2%")
        with col4:
            st.metric("Avg Runtime", "2.3m", "-0.1m")
    
    elif page == "Pipelines":
        st.header("Pipeline Configuration")
        st.info("Pipeline management interface coming soon...")
    
    elif page == "Pipeline Runs":
        st.header("Pipeline Run History")
        st.info("Pipeline run monitoring interface coming soon...")
    
    elif page == "System Codes":
        st.header("System Codes Management")
        st.info("System codes administration interface coming soon...")
    
    elif page == "Admin":
        st.header("System Administration")
        st.info("Admin panel coming soon...")

if __name__ == "__main__":
    main()
EOF

# Create FastAPI main file
cat > app/api/main.py << 'EOF'
"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Pipeline Management System API",
    description="API for managing data pipelines and processing runs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Pipeline Management System API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Create run scripts
print_status "Creating run scripts..."

cat > run_streamlit.sh << 'EOF'
#!/bin/bash
# Activate virtual environment and run Streamlit app
source venv/bin/activate
streamlit run app/gui/main.py --server.port 8501 --server.address 0.0.0.0
EOF

cat > run_api.sh << 'EOF'
#!/bin/bash
# Activate virtual environment and run FastAPI
source venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
EOF

# Make run scripts executable
chmod +x run_streamlit.sh
chmod +x run_api.sh

# Create README
cat > README.md << 'EOF'
# Pipeline Management System

A Python-based application for managing data pipelines and processing runs.

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
pipeline_management_system/
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
- `pipeline`: Pipeline configurations
- `pipeline_run`: Pipeline execution runs
- `pipeline_run_details`: Detailed run information

See the database schema documentation for complete details.
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
venv/
env/
ENV/

# Environment Variables
.env
.env.local
.env.production

# Database
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Streamlit
.streamlit/

# Data files (adjust as needed)
data/raw/*
data/processed/*
data/exports/*
!data/raw/.gitkeep
!data/processed/.gitkeep
!data/exports/.gitkeep

# Temporary files
tmp/
temp/
EOF

# Create placeholder files for data directories
touch data/raw/.gitkeep
touch data/processed/.gitkeep
touch data/exports/.gitkeep

print_success "Basic application files created"

# Change to project directory and activate environment for immediate use
print_status "Changing to project directory and activating environment..."
cd $PROJECT_NAME

# Activate the virtual environment in the current shell
if [[ -d "$VENV_NAME" ]]; then
    print_status "Activating virtual environment for current session..."
    source $VENV_NAME/bin/activate
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        print_success "Virtual environment activated: $VIRTUAL_ENV"
        print_status "Python location: $(which python)"
        print_status "Pip location: $(which pip)"
        
        # Show installed packages
        print_status "Key installed packages:"
        pip list | grep -E "(streamlit|altair|sqlalchemy|fastapi)" || print_warning "Some packages may not be installed"
    else
        print_warning "Virtual environment activation may have failed"
    fi
else
    print_error "Virtual environment directory not found in project"
fi

# Final instructions
print_success "🎉 Setup completed successfully!"
echo
print_status "Current status:"
echo "- Working directory: $(pwd)"
echo "- Virtual environment: ${VIRTUAL_ENV:-'Not activated'}"
echo
print_status "You can now run:"
echo "1. ./run_streamlit.sh  # Start the Streamlit application"
echo "2. ./run_api.sh        # Start the FastAPI backend"
echo "3. streamlit run app/gui/main.py  # Direct Streamlit command"
echo
print_status "URLs will be:"
echo "- Streamlit GUI: http://localhost:8501"
echo "- FastAPI docs: http://localhost:8000/docs"
echo
print_warning "Don't forget to:"
echo "- Configure your database connection in .env"
echo "- Review and customize the requirements.txt if needed"
echo "- Set up your database schema using the provided SQL"
echo
print_success "Environment is ready! 🚀"