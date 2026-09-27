"""Configuration management for Wyndle.

The configuration lives at ``~/.wyndle/config.yaml``.  On first run a
default copy is written from the bundled ``default_config.yaml``.

All config sections are plain :mod:`dataclasses` with default values,
so every field is optional in the YAML.  Nested sections (like
``timer`` or ``features``) are automatically hydrated into their
corresponding dataclass via :func:`_hydrate`.
"""

from __future__ import annotations

import dataclasses
import shutil
from dataclasses import dataclass, field, fields
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar, get_type_hints

import yaml

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic dataclass <-> dict helpers
# ---------------------------------------------------------------------------

def _hydrate(cls: type[T], data: dict[str, Any]) -> T:
    """Recursively build a dataclass instance from a plain dict.

    For each field of *cls*:
      - If the field's type is itself a dataclass and the corresponding
        value in *data* is a dict, recurse.
      - Otherwise assign the value directly.
      - Missing keys silently fall back to the field's default.

    Args:
        cls:  The dataclass type to instantiate.
        data: A flat or nested dict (typically from ``yaml.safe_load``).

    Returns:
        A fully populated instance of *cls*.
    """
    kwargs: dict[str, Any] = {}
    hints = get_type_hints(cls)
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        field_type = hints[f.name]
        if dataclasses.is_dataclass(field_type) and isinstance(value, dict):
            kwargs[f.name] = _hydrate(field_type, value)
        else:
            kwargs[f.name] = value
    return cls(**kwargs)


def _to_dict(instance: Any) -> dict[str, Any]:
    """Serialize a dataclass instance to a plain dict (recursive).

    :class:`~pathlib.Path` values are converted to strings.

    Args:
        instance: A dataclass instance.

    Returns:
        Nested plain dict suitable for ``yaml.dump``.
    """
    result: dict[str, Any] = {}
    for f in fields(instance):
        value = getattr(instance, f.name)
        if dataclasses.is_dataclass(value):
            result[f.name] = _to_dict(value)
        elif isinstance(value, Path):
            result[f.name] = str(value)
        else:
            result[f.name] = value
    return result


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LateThresholds:
    """When to escalate "day not started" notifications.

    Each value is an ``HH:MM`` time string.
    """
    mild: str = "10:30"
    moderate: str = "12:00"
    severe: str = "14:00"


@dataclass
class TimerConfig:
    """Focus block durations in minutes."""
    micro_block: int = 5
    short_block: int = 15
    long_block: int = 30


@dataclass
class HardStopSettings:
    """Controls for the hard-stop enforcement system.

    Attributes:
        warn_before_min: Minutes before hard stop to start warning.
        grace_min:       Minutes after hard stop before escalation.
        max_extensions:  How many 30-min extensions are allowed.
        extension_min:   Duration of each extension in minutes.
    """
    warn_before_min: int = 15
    grace_min: int = 10
    max_extensions: int = 2
    extension_min: int = 30


@dataclass
class Features:
    """Feature toggles.

    Attributes:
        obsidian:       Read/write Obsidian daily notes.
        notifications:  macOS notification banners (daemon + inline).
        hard_stop:      Enforce the hard-stop time.
    """
    obsidian: bool = True
    notifications: bool = True
    hard_stop: bool = True


@dataclass
class WyndleConfig:
    """Top-level configuration.

    Loaded from ``~/.wyndle/config.yaml``.  Every field has a sensible
    default so the file can be partially filled or even empty.
    """
    user_name: str = "friend"
    obsidian_vault: str = "~/Documents/ObsidianVault"
    wake_target: str = "07:00"
    work_start: str = "09:30"
    hard_stop: str = "20:00"
    sleep_target: str = "23:00"
    daily_chores: list[str] = field(
        default_factory=lambda: ["Plan the day", "Reply to Slack", "Meetings"],
    )
    chore_estimate_min: int = 15
    scheduled_notifications: list[dict] = field(default_factory=list)
    late_thresholds: LateThresholds = field(default_factory=LateThresholds)
    timer: TimerConfig = field(default_factory=TimerConfig)
    hard_stop_settings: HardStopSettings = field(default_factory=HardStopSettings)
    features: Features = field(default_factory=Features)

    # -- Derived paths (not in YAML) --

    @property
    def wyndle_dir(self) -> Path:
        """Root data directory: ``~/.wyndle``."""
        return Path.home() / ".wyndle"

    @property
    def state_dir(self) -> Path:
        """Directory for file-based state: ``~/.wyndle/state``."""
        return self.wyndle_dir / "state"

    @property
    def obsidian_vault_path(self) -> Path:
        """Resolved, expanded path to the Obsidian vault."""
        return Path(self.obsidian_vault).expanduser()

    @property
    def obsidian_daily_dir(self) -> Path:
        """Directory containing Obsidian daily notes."""
        return self.obsidian_vault_path / "daily"

    @property
    def obsidian_tasks_dir(self) -> Path:
        """Directory containing persistent per-task note files."""
        return self.obsidian_vault_path / "tasks"

    def ensure_dirs(self) -> None:
        """Create all required directories if they don't exist."""
        for d in (self.wyndle_dir, self.state_dir, self.obsidian_daily_dir,
                  self.obsidian_tasks_dir, self.obsidian_vault_path / "weekly"):
            d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Load / init helpers
# ---------------------------------------------------------------------------

def load_config() -> WyndleConfig:
    """Load configuration from ``~/.wyndle/config.yaml``.

    Returns a default :class:`WyndleConfig` if the file doesn't exist
    or is empty.
    """
    config_path = Path.home() / ".wyndle" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return _hydrate(WyndleConfig, data)
    return WyndleConfig()


def init_default_config() -> Path:
    """Write a default config to ``~/.wyndle/config.yaml`` if missing.

    Tries to copy the bundled ``default_config.yaml`` first.  If the
    bundled file is not found (e.g. packaging issue), falls back to
    generating a config from the dataclass defaults via ``yaml.dump``.

    Returns:
        Path to the config file.
    """
    config_path = Path.home() / ".wyndle" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        return config_path

    # Try bundled file first
    try:
        default = resources.files("wyndle") / "default_config.yaml"
        with resources.as_file(default) as src:
            shutil.copy(src, config_path)
        return config_path
    except (FileNotFoundError, OSError, TypeError):
        pass

    # Fallback: generate from dataclass defaults
    cfg = WyndleConfig()
    data = _to_dict(cfg)
    header = (
        "# Wyndle config — edit to customise your system\n"
        "# Location: ~/.wyndle/config.yaml\n\n"
    )
    config_path.write_text(header + yaml.dump(data, default_flow_style=False, sort_keys=False))
    return config_path
