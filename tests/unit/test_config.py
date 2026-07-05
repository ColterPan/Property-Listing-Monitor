from pathlib import Path

import pytest

from property_monitor.config import ConfigError, load_config

VALID_CONFIG = """
poll_interval_minutes: 20
searches:
  - name: "Search A"
    portal: propertyguru
    intent: sale
    property_type: hdb
    location: "Tampines"
    min_price: 400000
    max_price: 500000
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _write_env(tmp_path: Path) -> Path:
    return _write(tmp_path, ".env", "TELEGRAM_BOT_TOKEN=abc\nTELEGRAM_CHAT_ID=123\n")


def test_valid_config_loads(tmp_path: Path) -> None:
    config_path = _write(tmp_path, "config.yaml", VALID_CONFIG)
    env_path = _write_env(tmp_path)

    config = load_config(config_path, env_path=env_path)

    assert config.telegram_bot_token == "abc"
    assert config.telegram_chat_id == "123"
    assert len(config.searches) == 1
    assert config.searches[0].name == "Search A"


def test_missing_env_var_raises_config_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    config_path = _write(tmp_path, "config.yaml", VALID_CONFIG)
    empty_env = _write(tmp_path, ".env", "")

    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_config(config_path, env_path=empty_env)


def test_duplicate_search_names_rejected(tmp_path: Path) -> None:
    config_content = VALID_CONFIG + """
  - name: "Search A"
    portal: propertyguru
    intent: rent
    property_type: condo
    location: "Queenstown"
"""
    config_path = _write(tmp_path, "config.yaml", config_content)
    env_path = _write_env(tmp_path)

    with pytest.raises(ConfigError, match="Duplicate search name"):
        load_config(config_path, env_path=env_path)


def test_min_price_greater_than_max_price_rejected(tmp_path: Path) -> None:
    config_content = """
searches:
  - name: "Bad range"
    portal: propertyguru
    intent: sale
    property_type: hdb
    location: "Tampines"
    min_price: 900000
    max_price: 100000
"""
    config_path = _write(tmp_path, "config.yaml", config_content)
    env_path = _write_env(tmp_path)

    with pytest.raises(ConfigError, match="min_price"):
        load_config(config_path, env_path=env_path)


def test_unknown_enum_value_rejected(tmp_path: Path) -> None:
    config_content = """
searches:
  - name: "Bad type"
    portal: propertyguru
    intent: sale
    property_type: mansion
    location: "Tampines"
"""
    config_path = _write(tmp_path, "config.yaml", config_content)
    env_path = _write_env(tmp_path)

    with pytest.raises(ConfigError, match="invalid enum value"):
        load_config(config_path, env_path=env_path)


def test_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")
