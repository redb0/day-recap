"""`install` и `uninstall`: слот скилла, поставка и чужие каталоги."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.cli import main

_PACKAGE_SKILL = Path(__file__).resolve().parents[1] / "app" / "SKILL.md"
_SKILL_TEXT = "скилл из поставки\n"


@contextmanager
def _packaged_skill() -> Iterator[None]:
    saved = _PACKAGE_SKILL.read_bytes() if _PACKAGE_SKILL.is_file() else None
    _PACKAGE_SKILL.write_text(_SKILL_TEXT, encoding="utf-8")
    try:
        yield
    finally:
        if saved is None:
            _PACKAGE_SKILL.unlink(missing_ok=True)
        else:
            _PACKAGE_SKILL.write_bytes(saved)


def test_install_creates_the_skill_and_parent_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    config, session, vault = _untouched(home)

    with _packaged_skill():
        exit_code = main(["install"])

    skill_dir = home / ".agents" / "skills" / "day-recap"
    skill = skill_dir / "SKILL.md"
    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.out,
        captured.err,
        skill.read_text(encoding="utf-8"),
        _mode(skill),
        _mode(skill_dir),
        _mode(skill_dir.parent),
        _mode(home / ".agents"),
        sorted(path.name for path in skill_dir.iterdir()),
        config.read_text(encoding="utf-8"),
        session.read_bytes(),
        vault.read_text(encoding="utf-8"),
    ) == (
        0,
        f"установлен: {skill}\n",
        "",
        _SKILL_TEXT,
        "0o644",
        "0o755",
        "0o755",
        "0o755",
        ["SKILL.md"],
        "не трогать\n",
        b"session",
        "заметка\n",
    )


def test_install_replaces_the_directory_and_keeps_neighbors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    agents = home / ".agents"
    skills = agents / "skills"
    slot = skills / "day-recap"
    slot.mkdir(parents=True)
    (slot / "SKILL.md").write_text("старый\n", encoding="utf-8")
    (slot / "NOTES.md").write_text("лишний\n", encoding="utf-8")
    other = skills / "other" / "SKILL.md"
    other.parent.mkdir()
    other.write_text("чужой\n", encoding="utf-8")
    agents.chmod(0o750)
    skills.chmod(0o750)

    with _packaged_skill():
        exit_code = main(["install"])

    skill = slot / "SKILL.md"
    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.out,
        skill.read_text(encoding="utf-8"),
        sorted(path.name for path in slot.iterdir()),
        sorted(path.name for path in skills.iterdir()),
        other.read_text(encoding="utf-8"),
        _mode(agents),
        _mode(skills),
        _mode(slot),
        _mode(skill),
    ) == (
        0,
        f"установлен: {skill}\n",
        _SKILL_TEXT,
        ["SKILL.md"],
        ["day-recap", "other"],
        "чужой\n",
        "0o750",
        "0o750",
        "0o755",
        "0o644",
    )


def test_install_replaces_a_symlink_with_a_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text("цель\n", encoding="utf-8")
    (target / "extra").write_text("x\n", encoding="utf-8")
    slot = home / ".agents" / "skills" / "day-recap"
    slot.parent.mkdir(parents=True)
    slot.symlink_to(target)

    with _packaged_skill():
        exit_code = main(["install"])

    skill = slot / "SKILL.md"
    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.out,
        slot.is_symlink(),
        slot.is_dir(),
        skill.read_text(encoding="utf-8"),
        (target / "SKILL.md").read_text(encoding="utf-8"),
        (target / "extra").read_text(encoding="utf-8"),
    ) == (
        0,
        f"установлен: {skill}\n",
        False,
        True,
        _SKILL_TEXT,
        "цель\n",
        "x\n",
    )


def test_install_replaces_a_file_with_the_skill_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    slot = home / ".agents" / "skills" / "day-recap"
    slot.parent.mkdir(parents=True)
    slot.write_text("не каталог\n", encoding="utf-8")

    with _packaged_skill():
        exit_code = main(["install"])

    skill = slot / "SKILL.md"
    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.out,
        slot.is_symlink(),
        slot.is_dir(),
        skill.read_text(encoding="utf-8"),
        sorted(path.name for path in slot.iterdir()),
    ) == (
        0,
        f"установлен: {skill}\n",
        False,
        True,
        _SKILL_TEXT,
        ["SKILL.md"],
    )


def test_install_reports_a_missing_package_skill_and_keeps_the_old_one(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    slot = home / ".agents" / "skills" / "day-recap"
    slot.mkdir(parents=True)
    skill = slot / "SKILL.md"
    skill.write_text("прежний\n", encoding="utf-8")
    saved = _PACKAGE_SKILL.read_bytes() if _PACKAGE_SKILL.is_file() else None
    _PACKAGE_SKILL.unlink(missing_ok=True)
    try:
        exit_code = main(["install"])
        captured = capsys.readouterr()
        assert (exit_code, captured.out, captured.err, skill.read_text(encoding="utf-8")) == (
            1,
            "",
            "В поставке нет SKILL.md.\nПоложите SKILL.md в пакет app и переустановите пакет.\n",
            "прежний\n",
        )
    finally:
        if saved is None:
            _PACKAGE_SKILL.unlink(missing_ok=True)
        else:
            _PACKAGE_SKILL.write_bytes(saved)


def test_uninstall_removes_the_slot_and_leaves_neighbors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    slot = home / ".agents" / "skills" / "day-recap"
    slot.mkdir(parents=True)
    (slot / "SKILL.md").write_text("старый\n", encoding="utf-8")
    (slot / "NOTES.md").write_text("лишний\n", encoding="utf-8")
    other = home / ".agents" / "skills" / "other" / "SKILL.md"
    other.parent.mkdir()
    other.write_text("чужой\n", encoding="utf-8")

    exit_code = main(["uninstall"])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, slot.exists(), other.read_text(encoding="utf-8")) == (
        0,
        f"удалён: {slot}\n",
        False,
        "чужой\n",
    )


def test_uninstall_reports_a_missing_slot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    slot = home / ".agents" / "skills" / "day-recap"

    exit_code = main(["uninstall"])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, slot.exists()) == (
        0,
        f"уже отсутствует: {slot}\n",
        False,
    )


def test_uninstall_leaves_a_file_at_the_slot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    slot = home / ".agents" / "skills" / "day-recap"
    slot.parent.mkdir(parents=True)
    slot.write_text("не каталог\n", encoding="utf-8")

    exit_code = main(["uninstall"])

    captured = capsys.readouterr()
    assert (exit_code, captured.out, slot.read_text(encoding="utf-8")) == (
        0,
        f"уже отсутствует: {slot}\n",
        "не каталог\n",
    )


def test_uninstall_unlinks_a_symlink_and_keeps_its_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text("цель\n", encoding="utf-8")
    slot = home / ".agents" / "skills" / "day-recap"
    slot.parent.mkdir(parents=True)
    slot.symlink_to(target)

    exit_code = main(["uninstall"])

    captured = capsys.readouterr()
    assert (
        exit_code,
        captured.out,
        slot.is_symlink(),
        slot.exists(),
        (target / "SKILL.md").read_text(encoding="utf-8"),
    ) == (
        0,
        f"удалён: {slot}\n",
        False,
        False,
        "цель\n",
    )


def _isolate_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)


def _untouched(home: Path) -> tuple[Path, Path, Path]:
    config = home / ".config" / "day-recap" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text("не трогать\n", encoding="utf-8")
    session = home / ".local" / "state" / "day-recap" / "session.session"
    session.parent.mkdir(parents=True)
    session.write_bytes(b"session")
    vault = home / "notes" / "day.md"
    vault.parent.mkdir(parents=True)
    vault.write_text("заметка\n", encoding="utf-8")
    return config, session, vault


def _mode(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)
