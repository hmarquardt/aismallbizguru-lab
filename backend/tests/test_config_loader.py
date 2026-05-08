from pathlib import Path

import pytest

from app.config.loader import ConfigLoadError, load_config_from_path


def test_loads_sample_config() -> None:
    config = load_config_from_path(Path(__file__).parents[2] / "config" / "apps.yaml")

    app = config.apps["junk-drawer"]
    assert app.title == "Junk Drawer"
    assert app.resources["notes"].fields["title"].required is True
    assert app.resources["notes"].files.enabled is True


def test_invalid_field_type_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "apps.yaml"
    config_path.write_text(
        """
apps:
  bad-app:
    title: Bad App
    resources:
      items:
        label: Items
        fields:
          title:
            type: unsupported
""",
    )

    with pytest.raises(ConfigLoadError, match="validation failed"):
        load_config_from_path(config_path)


def test_missing_config_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError, match="not found"):
        load_config_from_path(tmp_path / "missing.yaml")
