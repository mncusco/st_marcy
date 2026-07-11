import secrets
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config import settings

security = HTTPBasic(auto_error=False)


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    correct_username = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def verify_csrf(request: Request):
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    if not request.url.path.startswith("/admin"):
        return
    origin = request.headers.get("origin") or ""
    referer = request.headers.get("referer") or ""
    allowed = {"http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173"}
    if settings.DEBUG:
        allowed.add(origin)
        allowed.add(referer.rstrip("/"))
    if origin and origin not in allowed and referer and referer.rstrip("/").split("?")[0] not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF check failed: unrecognized origin",
        )
