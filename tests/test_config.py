from __future__ import annotations

import pytest

from awesome_claude.config import ConfigError, load_config


def test_load_json_config(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"preset": "python-minimal", "project": {"name": "Acme"}}')
    cfg = load_config(str(p))
    assert cfg["preset"] == "python-minimal"
    assert cfg["project"]["name"] == "Acme"


def test_load_toml_config(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('preset = "python-minimal"\n\n[project]\nname = "Acme"\n')
    cfg = load_config(str(p))
    assert cfg["preset"] == "python-minimal"
    assert cfg["project"]["name"] == "Acme"


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(str(tmp_path / "nope.json"))


def test_load_config_invalid_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    with pytest.raises(ConfigError, match="invalid config file"):
        load_config(str(p))
