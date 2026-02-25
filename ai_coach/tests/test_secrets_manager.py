import base64
import json
import runpy
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_coach import secrets_manager as sm


class TestFileKeyring:
    def test_load_returns_empty_when_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        keyring = sm.FileKeyring()

        assert keyring.get_password("svc", "key") is None

    def test_load_returns_empty_on_invalid_data(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".homegym_secrets").write_text("not-base64", encoding="utf-8")

        keyring = sm.FileKeyring()

        assert keyring.get_password("svc", "key") is None

    def test_set_get_delete_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        keyring = sm.FileKeyring()
        keyring.set_password("svc", "key", "value")

        assert keyring.get_password("svc", "key") == "value"

        keyring.delete_password("svc", "key")
        assert keyring.get_password("svc", "key") is None

    def test_save_ignores_chmod_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(sm.os, "chmod", MagicMock(side_effect=OSError("denied")))

        keyring = sm.FileKeyring()
        keyring.set_password("svc", "key", "value")

        raw = (tmp_path / ".homegym_secrets").read_text(encoding="utf-8")
        decoded = json.loads(base64.b64decode(raw).decode("utf-8"))
        assert decoded["svc:key"] == "value"


class TestSecretsManagerInitAndCore:
    def test_init_uses_os_keyring_when_available(self):
        fake_keyring = types.SimpleNamespace(get_password=MagicMock(return_value=None))

        with patch.dict("sys.modules", {"keyring": fake_keyring}):
            manager = sm.SecretsManager()

        assert manager.keyring_available is True
        assert manager.using_file_keyring is False
        assert manager.keyring is fake_keyring

    def test_init_falls_back_to_file_keyring(self):
        failing_keyring = types.SimpleNamespace(
            get_password=MagicMock(side_effect=RuntimeError("boom"))
        )

        with (
            patch.dict("sys.modules", {"keyring": failing_keyring}),
            patch("ai_coach.secrets_manager.FileKeyring", return_value="file-keyring") as file_cls,
        ):
            manager = sm.SecretsManager()

        file_cls.assert_called_once()
        assert manager.keyring_available is True
        assert manager.using_file_keyring is True
        assert manager.keyring == "file-keyring"

    def test_get_secret_prefers_keyring_value(self):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(get_password=MagicMock(return_value="from-keyring"))

        assert manager.get_secret("OPENROUTER_API_KEY") == "from-keyring"

    def test_get_secret_uses_env_when_keyring_empty(self, monkeypatch):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(get_password=MagicMock(return_value=None))
        monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")

        assert manager.get_secret("OPENROUTER_API_KEY") == "from-env"

    def test_get_secret_ignores_placeholder_env(self, monkeypatch):
        manager = sm.SecretsManager()
        manager.keyring_available = False
        monkeypatch.setenv("OPENROUTER_API_KEY", "your_openrouter_api_key_here")

        assert manager.get_secret("OPENROUTER_API_KEY", allow_env_fallback=False) is None

    def test_get_secret_keyring_error_falls_back_to_env(self, monkeypatch):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(get_password=MagicMock(side_effect=RuntimeError("fail")))
        monkeypatch.setenv("OPENROUTER_API_KEY", "env-after-error")

        assert manager.get_secret("OPENROUTER_API_KEY") == "env-after-error"

    def test_get_secret_uses_dotenv_fallback(self, monkeypatch):
        manager = sm.SecretsManager()
        manager.keyring_available = False

        def fake_load_dotenv():
            monkeypatch.setenv("OPENROUTER_API_KEY", "from-dotenv")

        fake_dotenv = types.SimpleNamespace(load_dotenv=fake_load_dotenv)

        with patch.dict("sys.modules", {"dotenv": fake_dotenv}):
            value = manager.get_secret("OPENROUTER_API_KEY", allow_env_fallback=True)

        assert value == "from-dotenv"

    def test_get_secret_without_fallback_returns_none(self):
        manager = sm.SecretsManager()
        manager.keyring_available = False

        assert manager.get_secret("OPENROUTER_API_KEY", allow_env_fallback=False) is None

    def test_set_secret_returns_false_without_keyring(self):
        manager = sm.SecretsManager()
        manager.keyring_available = False

        assert manager.set_secret("OPENROUTER_API_KEY", "x") is False

    def test_set_secret_success_and_file_keyring_hint(self):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(set_password=MagicMock())
        manager.using_file_keyring = True

        assert manager.set_secret("OPENROUTER_API_KEY", "abc") is True

    @pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
    def test_set_secret_success_platform_branches(self, monkeypatch, platform):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(set_password=MagicMock())
        manager.using_file_keyring = False
        monkeypatch.setattr(sm.sys, "platform", platform, raising=False)

        assert manager.set_secret("OPENROUTER_API_KEY", "abc") is True

    def test_set_secret_failure_returns_false(self):
        manager = sm.SecretsManager()
        manager.keyring_available = True
        manager.keyring = MagicMock(set_password=MagicMock(side_effect=RuntimeError("write-fail")))

        assert manager.set_secret("OPENROUTER_API_KEY", "abc") is False

    def test_delete_secret_paths(self):
        manager = sm.SecretsManager()
        manager.keyring_available = False
        assert manager.delete_secret("OPENROUTER_API_KEY") is False

        manager.keyring_available = True
        manager.keyring = MagicMock(delete_password=MagicMock(return_value=None))
        assert manager.delete_secret("OPENROUTER_API_KEY") is True

        manager.keyring = MagicMock(delete_password=MagicMock(side_effect=RuntimeError("missing")))
        assert manager.delete_secret("OPENROUTER_API_KEY") is False

    def test_list_secrets_only_returns_present_keys(self):
        manager = sm.SecretsManager()

        def fake_get_secret(name, allow_env_fallback=False):
            return "value" if name in {"OPENROUTER_API_KEY", "DB_PASSWORD"} else None

        manager.get_secret = fake_get_secret

        assert manager.list_secrets() == ["OPENROUTER_API_KEY", "DB_PASSWORD"]


class TestSecretsManagerHelpers:
    def test_get_openrouter_key_uses_manager(self):
        fake_manager = MagicMock(get_secret=MagicMock(return_value="or-key"))

        with patch("ai_coach.secrets_manager.SecretsManager", return_value=fake_manager):
            value = sm.get_openrouter_key()

        assert value == "or-key"
        fake_manager.get_secret.assert_called_once_with("OPENROUTER_API_KEY")

    def test_get_db_password_uses_manager(self):
        fake_manager = MagicMock(get_secret=MagicMock(return_value="db-pass"))

        with patch("ai_coach.secrets_manager.SecretsManager", return_value=fake_manager):
            value = sm.get_db_password()

        assert value == "db-pass"
        fake_manager.get_secret.assert_called_once_with("DB_PASSWORD")


class TestSecretsManagerCLI:
    def _run_cli(self, monkeypatch, tmp_path, argv, *, input_value=None, getpass_value=None):
        monkeypatch.setenv("HOME", str(tmp_path))

        if input_value is not None:
            monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: input_value)

        if getpass_value is not None:
            fake_getpass_module = types.SimpleNamespace(getpass=lambda _prompt="": getpass_value)
            with patch.dict("sys.modules", {"getpass": fake_getpass_module}):
                with patch.object(sys, "argv", argv):
                    return runpy.run_module("ai_coach.secrets_manager", run_name="__main__")

        with patch.object(sys, "argv", argv):
            return runpy.run_module("ai_coach.secrets_manager", run_name="__main__")

    def test_cli_without_args_exits_zero(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py"])

        assert exc.value.code == 0

    def test_cli_unknown_command_exits_one(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "wat"])

        assert exc.value.code == 1

    def test_cli_set_requires_key_name(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "set"])

        assert exc.value.code == 1

    def test_cli_get_requires_key_name(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "get"])

        assert exc.value.code == 1

    def test_cli_delete_requires_key_name(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "delete"])

        assert exc.value.code == 1

    def test_cli_set_empty_value_exits_one(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as exc:
            self._run_cli(
                monkeypatch,
                tmp_path,
                ["secrets_manager.py", "set", "OPENROUTER_API_KEY"],
                getpass_value="",
            )

        assert exc.value.code == 1

    def test_cli_full_set_get_list_delete_flow(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit) as set_exc:
            self._run_cli(
                monkeypatch,
                tmp_path,
                ["secrets_manager.py", "set", "OPENROUTER_API_KEY"],
                getpass_value="abcd1234",
            )
        assert set_exc.value.code == 0

        self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "list"])

        self._run_cli(
            monkeypatch,
            tmp_path,
            ["secrets_manager.py", "get", "OPENROUTER_API_KEY"],
        )

        with pytest.raises(SystemExit) as del_abort_exc:
            self._run_cli(
                monkeypatch,
                tmp_path,
                ["secrets_manager.py", "delete", "OPENROUTER_API_KEY"],
                input_value="no",
            )
        assert del_abort_exc.value.code == 0

        with pytest.raises(SystemExit) as del_exc:
            self._run_cli(
                monkeypatch,
                tmp_path,
                ["secrets_manager.py", "delete", "OPENROUTER_API_KEY"],
                input_value="yes",
            )
        assert del_exc.value.code == 0

        with pytest.raises(SystemExit) as get_missing_exc:
            self._run_cli(
                monkeypatch,
                tmp_path,
                ["secrets_manager.py", "get", "OPENROUTER_API_KEY"],
            )
        assert get_missing_exc.value.code == 1

    def test_cli_list_empty_branch(self, monkeypatch, tmp_path):
        self._run_cli(monkeypatch, tmp_path, ["secrets_manager.py", "list"])
