# ST CORE — Installation Guide

## Prerequisites

- Python 3.14+
- pip
- (Optional) virtualenv or venv

## Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/st_core.git
cd st_core

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# Enter the project directory
cd st_core

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (generate a strong SECRET_KEY)

# Initialize database tables
python -c "from database import engine, Base; Base.metadata.create_all(bind=engine)"

# Run the server
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| PROJECT_NAME | Yes | — | Application name |
| DATABASE_URL | Yes | `sqlite:///./shamanic.db` | SQLite path |
| ADMIN_USERNAME | Yes | — | Dashboard login username |
| ADMIN_PASSWORD | Yes | — | Dashboard login password |
| CONTACT_EMAIL | Yes | — | Contact email for replies |
| SECRET_KEY | Yes | — | 32+ char random string |
| DEBUG | No | `false` | Enable debug mode |
| EMAIL_BACKEND | No | `log` | `log`, `smtp`, or future providers |

## Verify Installation

```bash
# From the st_core/ directory
python -m pytest tests/ -q

# Or manually
curl http://localhost:8000/health
```

Expected response: `{"status": "ok", "service": "ST CORE", ...}`
