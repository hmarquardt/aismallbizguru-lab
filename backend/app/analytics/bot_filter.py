BOT_PATTERNS = (
    ("empty", ""),
    ("bot", "bot"),
    ("crawler", "crawler"),
    ("spider", "spider"),
    ("curl", "curl"),
    ("wget", "wget"),
    ("python-requests", "python-requests"),
    ("http client", "httpclient"),
    ("headless", "headless"),
    ("scrapy", "scrapy"),
)


def detect_bot(user_agent: str | None) -> tuple[bool, str | None]:
    if not user_agent or not user_agent.strip():
        return True, "empty user agent"
    normalized = user_agent.lower()
    for reason, pattern in BOT_PATTERNS[1:]:
        if pattern in normalized:
            return True, reason
    return False, None

