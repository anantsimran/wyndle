from dataclasses import fields

import yaml

from wyndle.lib.config import (
    Features,
    TimerConfig,
    WyndleConfig,
    init_default_config,
    load_config,
)


def test_defaults_without_file(home):
    assert load_config() == WyndleConfig()


def test_partial_yaml_hydrates_nested_sections(home):
    path = home / ".wyndle" / "config.yaml"
    path.parent.mkdir()
    path.write_text(yaml.dump({"user_name": "A", "timer": {"long_block": 45}}))
    cfg = load_config()
    assert cfg.user_name == "A"
    assert cfg.timer == TimerConfig(long_block=45)
    assert cfg.features == Features()


def test_bundled_default_config_only_uses_known_keys(home):
    """A typo in the shipped YAML would otherwise crash every first run."""
    data = yaml.safe_load(init_default_config().read_text())
    known = {f.name for f in fields(WyndleConfig)}
    assert set(data) <= known
    for section in ("late_thresholds", "timer", "hard_stop_settings", "features"):
        section_fields = {f.name for f in fields(type(getattr(WyndleConfig(), section)))}
        assert set(data[section]) <= section_fields, section
    load_config()
