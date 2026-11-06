import json
import logging
import os

import pytest

from moodle_mcp import utils
from moodle_mcp.utils import DEBUG_DIR_ENV, to_json_file


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    # Do not let a developer's .env or shell environment leak into the tests.
    monkeypatch.setattr(utils, "ENV_LOADED", True)
    monkeypatch.delenv(DEBUG_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)


def test_no_write_when_env_var_unset(tmp_path):
    to_json_file({"a": 1}, "data.json")

    assert list(tmp_path.iterdir()) == []


def test_no_write_when_env_var_empty(monkeypatch, tmp_path):
    monkeypatch.setenv(DEBUG_DIR_ENV, "")

    to_json_file({"a": 1}, "data.json")

    assert list(tmp_path.iterdir()) == []


def test_writes_when_env_var_set(monkeypatch, tmp_path):
    debug_dir = tmp_path / "debug" / "nested"
    monkeypatch.setenv(DEBUG_DIR_ENV, str(debug_dir))

    to_json_file({"name": "Kurs ä"}, "data.json")

    target = debug_dir / "data.json"
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == {"name": "Kurs ä"}


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores directory permissions",
)
def test_unwritable_dir_does_not_raise(monkeypatch, tmp_path, caplog):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    monkeypatch.setenv(DEBUG_DIR_ENV, str(readonly / "debug"))

    try:
        with caplog.at_level(logging.WARNING, logger="moodle-mcp"):
            to_json_file({"a": 1}, "data.json")
    finally:
        readonly.chmod(0o700)

    assert "Could not write debug file" in caplog.text


def test_invalid_target_does_not_raise(monkeypatch, tmp_path, caplog):
    # A regular file where a directory is expected fails for every user,
    # including root, so this covers the error path unconditionally.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setenv(DEBUG_DIR_ENV, str(blocker))

    with caplog.at_level(logging.WARNING, logger="moodle-mcp"):
        to_json_file({"a": 1}, "data.json")

    assert "Could not write debug file" in caplog.text
