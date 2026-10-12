"""Helper per il tracking dei lead: estrazione IP, paese, e parsing User-Agent."""
import logging

logger = logging.getLogger("st_core.tracking")


def client_ip(request) -> str | None:
    """IP reale del client. Rispetta proxy (Cloudflare / X-Forwarded-For)."""
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            first = value.split(",")[0].strip()
            if first and first.lower() != "unknown":
                return first
    if request.client:
        return request.client.host
    return None


def client_country(request) -> str | None:
    """Paese da header Cloudflare (CF-IPCountry) o verisign. None se assente."""
    for header in ("cf-ipcountry", "x-vercel-ip-country", "x-country-code"):
        value = request.headers.get(header)
        if value and value.lower() not in ("xx", "unknown", ""):
            return value.upper()
    return None


def _lower(ua: str) -> str:
    return ua.lower()


def parse_user_agent(user_agent: str | None) -> dict:
    """Parsa device_type, browser, os_name da un User-Agent HTTP."""
    if not user_agent:
        return {"device_type": None, "browser": None, "os_name": None}
    ua = _lower(user_agent)

    if "bot" in ua or "crawl" in ua or "spider" in ua or "headlesschrome" in ua:
        device = "bot"
    elif "mobile" in ua or "android" in ua or "iphone" in ua or "ipod" in ua:
        device = "mobile"
    elif "ipad" in ua or "tablet" in ua:
        device = "tablet"
    else:
        device = "desktop"

    browser = None
    if "edg/" in ua:
        browser = "edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "opera"
    elif "samsungbrowser" in ua:
        browser = "samsung_internet"
    elif "chrome" in ua:
        browser = "chrome"
    elif "firefox" in ua:
        browser = "firefox"
    elif "safari" in ua:
        browser = "safari"
    elif "msie" in ua or "trident" in ua:
        browser = "ie"

    os_name = None
    if "windows" in ua:
        os_name = "windows"
    elif "android" in ua:
        os_name = "android"
    elif "iphone" in ua or "ipod" in ua or "ios" in ua:
        os_name = "ios"
    elif "ipad" in ua:
        os_name = "ipados"
    elif "mac os x" in ua or "macintosh" in ua:
        os_name = "macos"
    elif "linux" in ua:
        os_name = "linux"
    elif "cros" in ua:
        os_name = "chromeos"

    return {"device_type": device, "browser": browser, "os_name": os_name}


def extract_request_context(request) -> dict:
    """Crea il contesto completo di tracking dal Request FastAPI."""
    user_agent = request.headers.get("user-agent")
    parsed = parse_user_agent(user_agent)
    return {
        "ip_address": client_ip(request),
        "country": client_country(request),
        "user_agent": user_agent,
        **parsed,
    }
