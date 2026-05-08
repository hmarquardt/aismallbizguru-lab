from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.models import AppConfig, AppsConfig, ResourceConfig
from app.settings import get_settings


class ConfigLoadError(RuntimeError):
    pass


class AppConfigRegistry:
    def __init__(self, config: AppsConfig) -> None:
        self.config = config

    def list_apps(self) -> dict[str, AppConfig]:
        return self.config.apps

    def get_app(self, app_id: str) -> AppConfig | None:
        return self.config.apps.get(app_id)

    def get_resource(self, app_id: str, resource_name: str) -> ResourceConfig | None:
        app = self.get_app(app_id)
        if app is None:
            return None
        return app.resources.get(resource_name)


def load_config_from_path(path: str | Path) -> AppsConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigLoadError(f"App config file not found: {config_path}")

    try:
        raw_config = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"App config YAML is invalid: {exc}") from exc

    try:
        return AppsConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ConfigLoadError(f"App config validation failed: {exc}") from exc


@lru_cache
def get_registry() -> AppConfigRegistry:
    settings = get_settings()
    return AppConfigRegistry(load_config_from_path(settings.app_config_path))


def clear_registry_cache() -> None:
    get_registry.cache_clear()
