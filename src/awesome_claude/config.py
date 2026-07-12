"""Load a --config file (JSON or TOML, picked by extension) with the same
schema `generate` accepts as flags. CLI flags passed alongside always
override the matching config value - see cli.py's merge step."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path


class ConfigError(Exception):
    """Invalid --config input - the CLI surfaces this as an error message."""


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        if p.suffix.lower() == ".toml":
            with p.open("rb") as fh:
                return tomllib.load(fh)
        return json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config file '{path}': {exc}") from exc
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"invalid config file '{path}': {exc}") from exc
