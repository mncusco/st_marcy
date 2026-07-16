# ST CORE

CRM e automazione per Shamanic Travels.

## Quick Start

```bash
cd st_core
pip install -r requirements.txt
cp .env.example .env
# edit .env with your settings
python -c "from database import engine, Base; Base.metadata.create_all(bind=engine)"
uvicorn app:app --reload
```

## Documentation

| Document | Description |
|---|---|
| [INSTALL.md](INSTALL.md) | Full installation guide |
| [DEPLOY.md](DEPLOY.md) | Production deployment |
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | Dashboard and workflows |
| [BACKUP.md](BACKUP.md) | Backup and restore |
| [st_core/API.md](st_core/API.md) | API reference |
| [st_core/ARCHITECTURE.md](st_core/ARCHITECTURE.md) | Architecture overview |
| [st_core/PRODUCTION_REPORT.md](st_core/PRODUCTION_REPORT.md) | Production readiness report |

## Version

1.0.0

## License

Proprietary — Shamanic Travels
