from pathlib import Path

import pytest

from app.config.loader import ConfigLoadError, load_config_from_path


def test_loads_sample_config() -> None:
    config = load_config_from_path(Path(__file__).parents[2] / "config" / "apps.yaml")

    app = config.apps["junk-drawer"]
    assert app.title == "Junk Drawer"
    assert app.resources["notes"].fields["title"].required is True
    assert app.resources["notes"].files.enabled is True

    top_hat = config.apps["top-hat-ferals"]
    assert top_hat.auth.default_read == "public"
    assert top_hat.auth.default_write == "token"
    assert set(top_hat.resources) == {"cats", "sightings", "interactions"}
    assert top_hat.resources["cats"].files.enabled is True
    assert "image/webp" in top_hat.resources["interactions"].files.allowed_types

    wfr = config.apps["wildlife-field-recorder"]
    assert wfr.title == "Wildlife Field Recorder"
    assert wfr.auth.default_read == "token"
    assert wfr.auth.default_write == "token"
    assert set(wfr.resources) == {"observations", "trips"}

    obs = wfr.resources["observations"]
    assert obs.files.enabled is True
    assert "audio/webm" in obs.files.allowed_types
    assert "image/jpeg" in obs.files.allowed_types
    assert obs.files.max_size_mb == 50
    assert obs.fields["localId"].required is True
    assert obs.fields["createdAt"].required is True

    trips = wfr.resources["trips"]
    assert trips.files.enabled is True
    assert "application/geo+json" in trips.files.allowed_types
    assert trips.fields["localTripId"].required is True
    assert trips.fields["title"].required is True
    assert trips.fields["startedAt"].required is True


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
