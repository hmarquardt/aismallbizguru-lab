from __future__ import annotations


def _version_after(user_agent: str, marker: str) -> str | None:
    if marker not in user_agent:
        return None
    value = user_agent.split(marker, 1)[1].split(" ", 1)[0].split(")", 1)[0]
    return value.replace("_", ".")[:32] or None


def parse_user_agent(user_agent: str | None) -> dict[str, str | None]:
    ua = user_agent or ""
    browser_name = "Unknown"
    browser_version = None
    if "Edg/" in ua:
        browser_name = "Edge"
        browser_version = _version_after(ua, "Edg/")
    elif "Chrome/" in ua and "Chromium" not in ua:
        browser_name = "Chrome"
        browser_version = _version_after(ua, "Chrome/")
    elif "Firefox/" in ua:
        browser_name = "Firefox"
        browser_version = _version_after(ua, "Firefox/")
    elif "Safari/" in ua and "Version/" in ua:
        browser_name = "Safari"
        browser_version = _version_after(ua, "Version/")

    os_name = "Unknown"
    os_version = None
    if "Windows NT" in ua:
        os_name = "Windows"
        os_version = _version_after(ua, "Windows NT ")
    elif "Android" in ua:
        os_name = "Android"
        os_version = _version_after(ua, "Android ")
    elif "iPhone OS" in ua or "CPU OS" in ua:
        os_name = "iOS"
        marker = "iPhone OS " if "iPhone OS" in ua else "CPU OS "
        os_version = _version_after(ua, marker)
    elif "Mac OS X" in ua:
        os_name = "macOS"
        os_version = _version_after(ua, "Mac OS X ")
    elif "Linux" in ua:
        os_name = "Linux"

    lowered = ua.lower()
    if "mobile" in lowered or "iphone" in lowered or "android" in lowered:
        device_type = "mobile"
    elif "ipad" in lowered or "tablet" in lowered:
        device_type = "tablet"
    else:
        device_type = "desktop"

    return {
        "browser_name": browser_name,
        "browser_version": browser_version,
        "os_name": os_name,
        "os_version": os_version,
        "device_type": device_type,
    }

