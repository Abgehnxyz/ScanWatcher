"""
Tests fuer config.py – API-Keys und Autostart.
Ausfuehren: py -m pytest tests/
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Config in tmp_path, Keyring und Registry als Attrappen."""
    store: dict[str, str] = {}
    monkeypatch.setattr(config.keyring, "get_password", lambda s, a: store.get(a))
    monkeypatch.setattr(config.keyring, "set_password", lambda s, a, k: store.__setitem__(a, k))
    monkeypatch.setattr(config.keyring, "delete_password", lambda s, a: store.pop(a, None))
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    registry = {"enabled": False, "writes": 0}
    monkeypatch.setattr(config, "is_autostart_enabled", lambda: registry["enabled"])

    def fake_apply(enabled):
        if enabled != registry["enabled"]:
            registry["enabled"] = enabled
            registry["writes"] += 1
    monkeypatch.setattr(config, "_apply_autostart", fake_apply)
    return store, registry


def test_stale_cfg_does_not_delete_new_key(env):
    """Bug: Heartbeat/MOTD speicherten das cfg vom Programmstart und löschten
    damit einen später eingetragenen API-Key."""
    store, _ = env
    stale = config.load()                       # Tray hält dieses cfg
    config.set_model_key("claude", "sk-ant-NEU")
    config.save(stale)
    assert store == {"anthropic_api_key": "sk-ant-NEU"}


def test_save_never_writes_keys_to_json(env):
    config.save({**config.DEFAULT_CONFIG, "claude_key": "sk-ant-geheim"})
    data = json.loads(config.CONFIG_FILE.read_text("utf-8"))
    assert not any(k.endswith("_key") for k in data)


def test_load_contains_no_keys(env):
    store, _ = env
    store["anthropic_api_key"] = "sk-ant-x"
    cfg = config.load()
    assert not any(k.endswith("_key") for k in cfg)
    assert config.get_model_key("claude") == "sk-ant-x"


def test_legacy_json_key_migrated_and_removed(env):
    store, _ = env
    config.CONFIG_FILE.write_text(json.dumps({"anthropic_key": "sk-ant-alt"}), "utf-8")
    cfg = config.load()
    assert store["anthropic_api_key"] == "sk-ant-alt"
    assert cfg["active_model"] == "claude"
    config.save(cfg)
    assert "anthropic_key" not in json.loads(config.CONFIG_FILE.read_text("utf-8"))


def test_installer_autostart_survives_first_save(env):
    """Bug: Default autostart=False → das erste save() löschte den Run-Eintrag
    des Installers."""
    _, registry = env
    registry["enabled"] = True                  # vom Installer gesetzt
    cfg = config.load()
    assert cfg["autostart"] is True
    config.save(cfg)
    assert registry["enabled"] is True
    assert registry["writes"] == 0


def test_autostart_toggle_writes_registry(env):
    _, registry = env
    cfg = config.load()
    cfg["autostart"] = True
    config.save(cfg)
    assert registry["enabled"] is True and registry["writes"] == 1


def test_autostart_command_dev_mode_points_to_run_py():
    cmd = config._autostart_command()
    assert cmd.endswith('run.py"')
