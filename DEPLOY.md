# ST CORE — Deployment Guide

## Production Checklist

- [ ] SECRET_KEY is a strong random string (32+ characters)
- [ ] ADMIN_PASSWORD is changed from defaults
- [ ] DEBUG is set to `false`
- [ ] DATABASE_URL points to a persistent location
- [ ] EMAIL_BACKEND is configured (smtp or log)
- [ ] Backups are scheduled (see BACKUP.md)

## Linux (systemd)

```bash
# Copy service file
sudo cp deploy/st_core.service /etc/systemd/system/

# Edit to match your paths and user
sudo systemctl daemon-reload
sudo systemctl enable st_core
sudo systemctl start st_core

# Check status
sudo systemctl status st_core
```

Example systemd unit (`deploy/st_core.service`):

```ini
[Unit]
Description=ST CORE
After=network.target

[Service]
User=stcore
WorkingDirectory=/opt/st_core
EnvironmentFile=/opt/st_core/.env
ExecStart=/opt/st_core/venv/bin/uvicorn st_core.app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Windows (IIS via FastCGI / NSSM)

Using NSSM (Non-Sucking Service Manager):

```cmd
nssm install STCORE "C:\path\to\venv\Scripts\uvicorn.exe" "st_core.app:app --host 127.0.0.1 --port 8000"
nssm set STCORE AppDirectory "C:\path\to\st_core"
nssm start STCORE
```

## Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/st_core/static/;
    }
}
```

## Docker-Ready

The application is designed to be Docker-ready. A `Dockerfile` will be added in a future phase. Key considerations:

- Use `python:3.11-slim` base image
- Mount `/database` as a volume for persistence
- Mount `/backups` for backup storage
- Pass environment variables via `--env-file`
- Use `gunicorn -k uvicorn.workers.UvicornWorker` for production
