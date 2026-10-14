"""Подкоманды `init` и `chats`: клиент подменён, сеть не вызывается."""

from collections.abc import Callable
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from telethon.errors import SessionPasswordNeededError

from app.cli import main
from app.errors import ErrorCode, SummaryError

_MOSCOW = ZoneInfo("Europe/Moscow")
_HASH = "hash-secret-value"
_PHONE = "+79990000000"


def test_init_asks_only_for_the_missing_phone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\n")
    monkeypatch.setattr("builtins.input", _input_map({"TG_PHONE": _PHONE}))
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=False))
    config = _config(tmp_path)

    exit_code = main(["init", "--login", "qr", "--config", str(config)])

    env = (home / ".config" / "day-recap" / ".env").read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert (exit_code, env, out) == (
        0,
        f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n",
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
    )


def test_init_from_scratch_writes_a_private_env_and_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    monkeypatch.setattr(
        "builtins.input",
        _input_map({"TG_API_ID": "1", "TG_PHONE": _PHONE}),
    )
    monkeypatch.setattr("getpass.getpass", lambda _prompt: _HASH)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=False))
    config = _config(tmp_path)

    exit_code = main(["init", "--login", "qr", "--config", str(config)])

    env_path = home / ".config" / "day-recap" / ".env"
    session = tmp_path / "state" / "session.session"
    out = capsys.readouterr().out
    assert (
        exit_code,
        env_path.read_text(encoding="utf-8"),
        oct(env_path.stat().st_mode & 0o777),
        oct(env_path.parent.stat().st_mode & 0o777),
        oct(session.stat().st_mode & 0o777),
        session.read_bytes(),
        out,
    ) == (
        0,
        f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n",
        "0o600",
        "0o700",
        "0o600",
        b"new",
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
    )


def test_init_keeps_a_live_session_without_asking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    session = tmp_path / "state" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"live")
    monkeypatch.setattr("builtins.input", _input_map({}))
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))

    exit_code = main(["init", "--config", str(_config(tmp_path))])

    assert (exit_code, session.read_bytes(), capsys.readouterr().out) == (
        0,
        b"live",
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
    )


def test_relogin_deletes_the_session_file_instead_of_log_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    session = tmp_path / "state" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"old")
    monkeypatch.setattr("builtins.input", _input_map({}))
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_factory(live=True, relogin=True),
    )
    config = _config(tmp_path)
    original = config.read_text(encoding="utf-8")

    exit_code = main(["init", "--relogin", "--login", "qr", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, config.read_text(encoding="utf-8")) == (
        0,
        "Вошли как Новая / @new / +79990000000\nчатов нет\n",
        original,
    )


def test_qr_login_asks_for_the_cloud_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    monkeypatch.setattr("builtins.input", _input_map({}))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "cloud")
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_factory(live=False, cloud="cloud"),
    )

    exit_code = main(["init", "--login", "qr", "--config", str(_config(tmp_path))])

    assert (exit_code, capsys.readouterr().out) == (
        0,
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
    )


def test_init_without_flag_uses_the_typed_login(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    monkeypatch.setattr("builtins.input", _input_map({"Вход": "code"}))
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=False))

    exit_code = main(["init", "--config", str(_config(tmp_path))])

    session = tmp_path / "state" / "session.session"
    assert (exit_code, session.read_bytes(), capsys.readouterr().out) == (
        0,
        b"code",
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
    )


def test_chats_prints_private_and_group_with_toml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    session = tmp_path / "state" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"live")
    when = datetime(2026, 10, 5, 18, 30, tzinfo=_MOSCOW)
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        lambda _session, _api_id, _api_hash: _Dialogs(when),
    )

    exit_code = main(["chats", "--config", str(_config(tmp_path))])

    assert (exit_code, capsys.readouterr().out) == (
        0,
        (
            "id\tназвание\tтип\tпоследнее\n"
            f'7\tЛичка "Аня"\tличный\t{when.isoformat()}\n'
            f"-100\tРабота\tгруппа\t{when.isoformat()}\n"
            "\n"
            "[[telegram.chats]]\n"
            "id = 7\n"
            'name = "Личка \\"Аня\\""\n'
            "\n"
            "[[telegram.chats]]\n"
            "id = -100\n"
            'name = "Работа"\n'
        ),
    )


def test_init_enter_keeps_the_packaged_example(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    session = home / ".local" / "state" / "day-recap" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"live")
    monkeypatch.setattr("builtins.input", _input_map({}))
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))
    example = Path(str(files("app").joinpath("config.example.toml"))).read_text(encoding="utf-8")

    exit_code = main(["init", "--login", "qr"])

    config = home / ".config" / "day-recap" / "config.toml"
    captured = capsys.readouterr()
    assert (exit_code, captured.out, captured.err, config.read_text(encoding="utf-8")) == (
        0,
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
        "",
        example,
    )


def test_init_copies_the_example_and_writes_answers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    (home / "template.md").write_text("шаблон\n", encoding="utf-8")
    (home / "work").mkdir()
    session = home / ".local" / "state" / "day-recap" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"live")
    prompts, answer = _script(
        [
            ("TG_API_ID", "1"),
            ("TG_PHONE", _PHONE),
            ("Каталог заметок", "~/notes"),
            ("Шаблон заметки", "~/template.md"),
            ("Корень git", "~/work"),
            ("Номера чатов", "2, 1"),
        ],
    )
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: _HASH)
    when = datetime(2026, 10, 5, 18, 30, tzinfo=_MOSCOW)
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_with_dialogs(when, live=True),
    )
    example = Path(str(files("app").joinpath("config.example.toml"))).read_text(encoding="utf-8")
    expected = example.replace('daily_dir = ""', 'daily_dir = "~/notes"', 1)
    expected = expected.replace('template = ""', 'template = "~/template.md"', 1)
    expected = expected.replace('roots = ["~/projects"]', 'roots = ["~/work"]', 1)
    marker = '# name = "название"\n'
    blocks = (
        "\n"
        "[[telegram.chats]]\n"
        "id = 7\n"
        'name = "Личка \\"Аня\\""\n'
        "\n"
        "[[telegram.chats]]\n"
        "id = -100\n"
        'name = "Работа"\n'
    )
    expected = expected.replace(marker, marker + blocks, 1)

    exit_code = main(["init", "--login", "qr"])

    config = home / ".config" / "day-recap" / "config.toml"
    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.err,
        prompts,
        captured.out,
        config.read_text(encoding="utf-8"),
        (home / "notes").exists(),
    ) == (
        0,
        "",
        [
            "TG_API_ID (https://my.telegram.org/apps): ",
            "TG_PHONE (+7999…): ",
            "Каталог заметок (Enter — не задан):",
            "Шаблон заметки (Enter — не задан):",
            "Корень git (Enter — ~/projects):",
            "Номера чатов через запятую (Enter — пустой список):",
        ],
        (
            "Вошли как Анна / @anna / +79990000000\n"
            "id\tназвание\tтип\tпоследнее\n"
            f'1\t7\tЛичка "Аня"\tличный\t{when.isoformat()}\n'
            f"2\t-100\tРабота\tгруппа\t{when.isoformat()}\n"
        ),
        expected,
        False,
    )


def test_init_patches_only_the_answered_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    (home / "template.md").write_text("шаблон\n", encoding="utf-8")
    (home / "work").mkdir()
    state = tmp_path / "state"
    config, _original = _rich_config(tmp_path, state)
    prompts, answer = _script(
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", "~/template.md"),
            ("Корень git", "~/work"),
            ("Заменить список чатов", " Да "),
            ("Номера чатов", "2, 1, 2"),
        ],
    )
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    when = datetime(2026, 10, 5, 18, 30, tzinfo=_MOSCOW)
    session = state / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"live")
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_with_dialogs(when, live=True),
    )

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.err,
        prompts,
        config.read_text(encoding="utf-8"),
    ) == (
        0,
        "",
        [
            "Каталог заметок (Enter — ~/vault/daily):",
            "Шаблон заметки (Enter — ~/vault/template.md):",
            "Корень git (Enter — ~/projects, ~/other):",
            "Заменить список чатов? (да/нет) [нет]:",
            "Номера чатов через запятую (Enter — пустой список):",
        ],
        _patched_config(state),
    )


def test_init_repeats_until_the_template_and_root_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    (home / "template.md").write_text("шаблон\n", encoding="utf-8")
    (home / "work").mkdir()
    config = _config(tmp_path)
    session = tmp_path / "state" / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", "~/new-notes"),
            ("Шаблон заметки", "missing.md"),
            ("Шаблон заметки", "~/template.md"),
            ("Корень git", "missing-root"),
            ("Корень git", "~/work"),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    state = tmp_path / "state"
    assert (
        exit_code,
        captured.err,
        config.read_text(encoding="utf-8"),
        (home / "new-notes").exists(),
    ) == (
        0,
        "Файл шаблона не найден: missing.md\nКаталог не найден: missing-root\n",
        (
            "[notes]\n"
            'daily_dir = "~/new-notes"\n'
            'timezone = "Europe/Moscow"\n'
            "\n"
            'template = "~/template.md"\n'
            "[state]\n"
            f'dir = "{state}"\n'
            "\n"
            "[git]\n"
            'roots = ["~/work"]\n'
        ),
        False,
    )


def test_init_keeps_the_allowlist_when_replace_is_declined(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    state = tmp_path / "state"
    config, original = _rich_config(tmp_path, state)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", ""),
            ("Заменить список чатов", ""),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, captured.err, config.read_text(encoding="utf-8")) == (
        0,
        "Вошли как Анна / @anna / +79990000000\n",
        "",
        original,
    )


def test_init_repeats_an_answer_that_is_not_yes_or_no(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    state = tmp_path / "state"
    config, original = _rich_config(tmp_path, state)
    prompts, answer = _script(
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", ""),
            ("Заменить список чатов", "может"),
            ("Заменить список чатов", "Нет"),
        ],
    )
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.err,
        prompts[-2:],
        config.read_text(encoding="utf-8"),
    ) == (
        0,
        "Ожидается да или нет.\n",
        [
            "Заменить список чатов? (да/нет) [нет]:",
            "Заменить список чатов? (да/нет) [нет]:",
        ],
        original,
    )


def test_init_repeats_a_number_outside_the_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    state = tmp_path / "state"
    config, _original = _rich_config(tmp_path, state)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", ""),
            ("Заменить список чатов", "да"),
            ("Номера чатов", "9"),
            ("Номера чатов", "1"),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    when = datetime(2026, 10, 5, 18, 30, tzinfo=_MOSCOW)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_with_dialogs(when, live=True),
    )

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.err, config.read_text(encoding="utf-8")) == (
        0,
        "Номер вне таблицы: 9\n",
        _single_chat_config(state),
    )


def test_init_clears_allowlist_blocks_on_an_empty_number_line(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    state = tmp_path / "state"
    config, _original = _rich_config(tmp_path, state)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", ""),
            ("Заменить список чатов", "да"),
            ("Номера чатов", ""),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    when = datetime(2026, 10, 5, 18, 30, tzinfo=_MOSCOW)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_with_dialogs(when, live=True),
    )

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.err, config.read_text(encoding="utf-8")) == (
        0,
        "",
        _cleared_allowlist(state),
    )


def test_init_clears_allowlist_when_there_are_no_dialogs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    state = tmp_path / "state"
    config, _original = _rich_config(tmp_path, state)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", ""),
            ("Заменить список чатов", "да"),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr("app.collectors.telegram.tg.make_client", _client_factory(live=True))

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, config.read_text(encoding="utf-8")) == (
        0,
        "Вошли как Анна / @anna / +79990000000\nчатов нет\n",
        _cleared_allowlist(state),
    )


def test_init_keeps_paths_when_login_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    (home / "work").mkdir()
    config = _config(tmp_path)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", "~/notes"),
            ("Шаблон заметки", ""),
            ("Корень git", "~/work"),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_factory(live=False, fail_connect=True),
    )

    exit_code = main(["init", "--login", "qr", "--config", str(config)])

    captured = capsys.readouterr()
    state = tmp_path / "state"
    assert (
        exit_code,
        captured.out,
        captured.err,
        config.read_text(encoding="utf-8"),
        (home / "notes").exists(),
    ) == (
        1,
        "",
        "code: NO_CREDENTIALS\nвход сломался\nповторите init\n",
        (
            "[notes]\n"
            'daily_dir = "~/notes"\n'
            'timezone = "Europe/Moscow"\n'
            "\n"
            "[state]\n"
            f'dir = "{state}"\n'
            "\n"
            "[git]\n"
            'roots = ["~/work"]\n'
        ),
        False,
    )


def test_init_keeps_paths_when_dialogs_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    _write_env(home, f"TG_API_ID=1\nTG_API_HASH={_HASH}\nTG_PHONE={_PHONE}\n")
    (home / "work").mkdir()
    state = tmp_path / "state"
    config, _original = _rich_config(tmp_path, state)
    _script_input(
        monkeypatch,
        [
            ("Каталог заметок", ""),
            ("Шаблон заметки", ""),
            ("Корень git", "~/work"),
            ("Заменить список чатов", "да"),
        ],
    )
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    session = state / "session.session"
    session.parent.mkdir()
    session.write_bytes(b"live")
    monkeypatch.setattr(
        "app.collectors.telegram.tg.make_client",
        _client_factory(live=True, fail_dialogs=True),
    )

    exit_code = main(["init", "--config", str(config)])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, captured.err, config.read_text(encoding="utf-8")) == (
        1,
        "Вошли как Анна / @anna / +79990000000\n",
        "code: TELEGRAM\nдиалоги недоступны\nповторите\n",
        _roots_replaced(state),
    )


def test_missing_config_flag_asks_nothing_and_copies_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    missing = tmp_path / "nope.toml"
    monkeypatch.setattr("builtins.input", _refuse_input)
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)

    exit_code = main(["init", "--config", str(missing)])

    captured = capsys.readouterr()
    default = home / ".config" / "day-recap" / "config.toml"
    assert (exit_code, captured.err, captured.out, missing.exists(), default.exists()) == (
        1,
        f"Файл конфигурации не найден: {missing}\n",
        "",
        False,
        False,
    )


def test_init_reports_a_missing_packaged_example(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    packaged = Path(str(files("app").joinpath("config.example.toml")))
    saved = packaged.read_bytes()
    packaged.unlink()
    monkeypatch.setattr("builtins.input", _refuse_input)
    monkeypatch.setattr("getpass.getpass", _refuse_getpass)
    try:
        exit_code = main(["init"])
        captured = capsys.readouterr()
        config = home / ".config" / "day-recap" / "config.toml"
        assert (exit_code, captured.out, captured.err, config.exists()) == (
            1,
            "",
            (
                "В поставке нет config.example.toml.\n"
                "Положите config.example.toml в пакет app и переустановите пакет.\n"
            ),
            False,
        )
    finally:
        packaged.write_bytes(saved)


def _refuse_input(_prompt: str) -> str:
    message = "input"
    raise AssertionError(message)


def _refuse_getpass(_prompt: str) -> str:
    message = "getpass"
    raise AssertionError(message)


def _isolate_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)


def _write_env(home: Path, text: str) -> None:
    path = home / ".config" / "day-recap" / ".env"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")


def _config(root: Path) -> Path:
    path = root / "config.toml"
    path.write_text(
        "\n".join(
            [
                "[notes]",
                'daily_dir = ""',
                'timezone = "Europe/Moscow"',
                "",
                "[state]",
                f'dir = "{root / "state"}"',
            ],
        ),
        encoding="utf-8",
    )
    return path


def _client_factory(
    *,
    live: bool,
    relogin: bool = False,
    cloud: str | None = None,
    fail_connect: bool = False,
    fail_dialogs: bool = False,
) -> object:
    def make(session: Path, _api_id: int, _api_hash: str) -> _Login:
        client = _Login(session, live=live, relogin=relogin, cloud=cloud)
        client.fail_connect = fail_connect
        client.fail_dialogs = fail_dialogs
        return client

    return make


_PATH_PROMPTS = ("Каталог заметок", "Шаблон заметки", "Корень git")


def _input_map(replies: dict[str, str]) -> Callable[[str], str]:
    def answer(prompt: str) -> str:
        if prompt.startswith(_PATH_PROMPTS):
            return ""
        for prefix, value in replies.items():
            if prompt.startswith(prefix):
                return value
        message = prompt
        raise AssertionError(message)

    return answer


def _script(steps: list[tuple[str, str]]) -> tuple[list[str], Callable[[str], str]]:
    prompts: list[str] = []
    remaining = list(steps)

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        if not remaining:
            message = prompt
            raise AssertionError(message)
        prefix, value = remaining.pop(0)
        if not prompt.startswith(prefix):
            message = prompt
            raise AssertionError(message)
        return value

    return prompts, answer


def _script_input(monkeypatch: pytest.MonkeyPatch, steps: list[tuple[str, str]]) -> None:
    _prompts, answer = _script(steps)
    monkeypatch.setattr("builtins.input", answer)


def _client_with_dialogs(when: datetime, *, live: bool = False) -> object:
    dialogs = _dialog_pair(when)

    def make(session: Path, _api_id: int, _api_hash: str) -> _Login:
        client = _Login(session, live=live, relogin=False)
        client.dialogs = dialogs
        return client

    return make


def _dialog_pair(when: datetime) -> tuple[SimpleNamespace, SimpleNamespace]:
    return (
        SimpleNamespace(
            id=7,
            name='Личка "Аня"',
            date=when,
            is_user=True,
            is_group=False,
            is_channel=False,
        ),
        SimpleNamespace(
            id=-100,
            name="Работа",
            date=when,
            is_user=False,
            is_group=True,
            is_channel=True,
        ),
    )


def _rich_config(root: Path, state: Path) -> tuple[Path, str]:
    text = _rich_text(state)
    path = root / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path, text


def _rich_text(state: Path) -> str:
    return f"""\
# комментарий сверху
[notes]
daily_dir = "~/vault/daily" # куда писать
template = "~/vault/template.md"
filename_format = "%Y-%m-%d"
timezone = "Europe/Moscow"

[state]
dir = "{state}"

[git]
roots = [
    "~/projects", # первый
    "~/other",
] # обход
max_depth = 3

[telegram]
enabled = true

# [[telegram.chats]]
# id = 123456789
# name = "название"

[[telegram.chats]]
id = 1
# внутри
name = "старый"

[summary]
two_stage_threshold_bytes = 100000
"""


def _patched_config(state: Path) -> str:
    return f"""\
# комментарий сверху
[notes]
daily_dir = "~/vault/daily" # куда писать
template = "~/template.md"
filename_format = "%Y-%m-%d"
timezone = "Europe/Moscow"

[state]
dir = "{state}"

[git]
roots = ["~/work"] # первый # обход
max_depth = 3

[telegram]
enabled = true

# [[telegram.chats]]
# id = 123456789
# name = "название"

[[telegram.chats]]
id = 7
name = "Личка \\"Аня\\""

[[telegram.chats]]
id = -100
name = "Работа"

[summary]
two_stage_threshold_bytes = 100000
"""


def _single_chat_config(state: Path) -> str:
    return _rich_text(state).replace(
        '[[telegram.chats]]\nid = 1\n# внутри\nname = "старый"\n',
        '[[telegram.chats]]\nid = 7\nname = "Личка \\"Аня\\""\n',
        1,
    )


def _cleared_allowlist(state: Path) -> str:
    return _rich_text(state).replace(
        '[[telegram.chats]]\nid = 1\n# внутри\nname = "старый"\n\n',
        "",
        1,
    )


def _roots_replaced(state: Path) -> str:
    return _rich_text(state).replace(
        'roots = [\n    "~/projects", # первый\n    "~/other",\n] # обход\n',
        'roots = ["~/work"] # первый # обход\n',
        1,
    )


class _PendingQr:
    url = "tg://login?token=test"

    def __init__(self, login: "_Login") -> None:
        self.login = login

    async def wait(self) -> None:
        login = self.login
        if login.cloud is not None and not login.signed_in:
            raise SessionPasswordNeededError(request=None)


class _Login:
    def __init__(
        self,
        session: Path,
        *,
        live: bool,
        relogin: bool,
        cloud: str | None = None,
    ) -> None:
        self.session = session
        self.live = live
        self.relogin = relogin
        self.cloud = cloud
        self.started = False
        self.signed_in = cloud is None
        self.dialogs: tuple[object, ...] = ()
        self.fail_dialogs = False
        self.fail_connect = False

    async def connect(self) -> None:
        if self.fail_connect:
            message = "вход сломался"
            raise SummaryError(message, "повторите init", ErrorCode.NO_CREDENTIALS)

    async def iter_dialogs(self) -> object:
        if self.fail_dialogs:
            message = "диалоги недоступны"
            raise SummaryError(message, "повторите", ErrorCode.TELEGRAM)
        for dialog in self.dialogs:
            yield dialog

    async def disconnect(self) -> None:
        return None

    async def is_user_authorized(self) -> bool:
        if self.started:
            return True
        if not self.session.is_file():
            return False
        if self.live:
            return True
        return self.session.read_bytes() in {b"new", b"code"}

    async def qr_login(self) -> _PendingQr:
        self.started = True
        self.session.parent.mkdir(parents=True, exist_ok=True)
        self.session.write_bytes(b"new")
        return _PendingQr(self)

    async def start(self, phone: str, **_kwargs: object) -> None:
        if phone != _PHONE:
            message = phone
            raise RuntimeError(message)
        self.started = True
        self.session.parent.mkdir(parents=True, exist_ok=True)
        self.session.write_bytes(b"code")

    async def sign_in(self, password: str) -> None:
        if password != self.cloud:
            message = "пароль"
            raise RuntimeError(message)
        self.signed_in = True

    async def get_me(self) -> SimpleNamespace:
        if self.cloud is not None and not self.signed_in:
            message = "нет пароля"
            raise RuntimeError(message)
        if self.started and self.relogin:
            return SimpleNamespace(
                first_name="Новая",
                last_name=None,
                username="new",
                phone="79990000000",
            )
        if self.started or self.live:
            return SimpleNamespace(
                first_name="Анна",
                last_name=None,
                username="anna",
                phone="79990000000",
            )
        message = "нет сессии"
        raise RuntimeError(message)

    async def log_out(self) -> None:
        message = "log_out"
        raise AssertionError(message)


class _Dialogs:
    def __init__(self, when: datetime) -> None:
        self.when = when

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def is_user_authorized(self) -> bool:
        return True

    async def iter_dialogs(self) -> object:
        yield SimpleNamespace(
            id=7,
            name='Личка "Аня"',
            date=self.when,
            is_user=True,
            is_group=False,
            is_channel=False,
        )
        yield SimpleNamespace(
            id=-100,
            name="Работа",
            date=self.when,
            is_user=False,
            is_group=True,
            is_channel=True,
        )
