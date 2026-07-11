import logging
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse

logger = logging.getLogger("st_core.errors")


def register_error_handlers(app):
    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/admin"):
            return HTMLResponse(
                content="""<html><body style="font-family:Georgia;background:#f5f2ec;padding:60px;text-align:center;">
                <h1 style="color:#8c8c8c;font-size:48px;font-weight:400;">404</h1>
                <p style="color:#b89a5a;font-size:16px;">Page not found</p>
                <a href="/admin" style="color:#2d5a27;font-size:13px;">← Back to Dashboard</a>
                </body></html>""",
                status_code=404,
            )
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.exception_handler(422)
    async def validation_error(request: Request, exc):
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(500)
    async def server_error(request: Request, exc):
        logger.exception("Unhandled error on %s", request.url.path)
        if request.url.path.startswith("/admin"):
            return HTMLResponse(
                content="""<html><body style="font-family:Georgia;background:#f5f2ec;padding:60px;text-align:center;">
                <h1 style="color:#8c8c8c;font-size:48px;font-weight:400;">500</h1>
                <p style="color:#b89a5a;font-size:16px;">Internal server error</p>
                <a href="/admin" style="color:#2d5a27;font-size:13px;">← Back to Dashboard</a>
                </body></html>""",
                status_code=500,
            )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
