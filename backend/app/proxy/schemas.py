from pydantic import BaseModel, Field


DEFAULT_PROXY_CONFIG = {
    "method": "GET",
    "allowed_query_params": [],
    "required_query_params": [],
    "allowed_request_headers": [],
    "allowed_response_content_types": ["application/json", "text/plain"],
    "cache_ttl_seconds": 0,
    "timeout_seconds": 10,
    "max_response_bytes": 1048576,
    "follow_redirects": False,
    "auth": {
        "mode": "private",
        "scope_app": None,
        "required_scope": "read",
    },
}


class ProxyAuthConfig(BaseModel):
    mode: str = "private"
    scope_app: str | None = None
    required_scope: str = "read"


class ProxySourceConfig(BaseModel):
    base_url: str
    method: str = "GET"
    allowed_query_params: list[str] = Field(default_factory=list)
    required_query_params: list[str] = Field(default_factory=list)
    allowed_request_headers: list[str] = Field(default_factory=list)
    allowed_response_content_types: list[str] = Field(
        default_factory=lambda: ["application/json", "text/plain"]
    )
    cache_ttl_seconds: int = 0
    timeout_seconds: float = 10
    max_response_bytes: int = 1048576
    follow_redirects: bool = False
    auth: ProxyAuthConfig = Field(default_factory=ProxyAuthConfig)


class ProxySourceCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    enabled: bool = True
    public: bool = False
    config: dict


class ProxySourcePatch(BaseModel):
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    public: bool | None = None
    config: dict | None = None


class ProxySourceOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    enabled: bool
    public: bool
    config: dict
    created_at: str
    updated_at: str
    deleted_at: str | None


class ProxySourceTestRequest(BaseModel):
    query_params: dict[str, str] = Field(default_factory=dict)
