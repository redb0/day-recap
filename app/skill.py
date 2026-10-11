"""Установленный скилл: одна копия на человека, откуда её читает агент."""

import shutil
import tempfile
import uuid
from pathlib import Path

from app.assets import read_package_text

_SKILL_FILE = "SKILL.md"
_MISSING = "В поставке нет SKILL.md."
_MISSING_HINT = "Положите SKILL.md в пакет app и переустановите пакет."


def installed_skill_dir() -> Path:
    """Каталог единственной копии скилла.

    Returns:
        `~/.agents/skills/day-recap`.
    """
    return Path.home() / ".agents" / "skills" / "day-recap"


def install_skill() -> Path:
    """Заменить каталог установленного скилла копией из пакета.

    Незавершённая замена оставляет прежний каталог. Симлинк на этом пути
    снимается, запись по ссылке не идёт.

    Returns:
        Абсолютный путь записанного `SKILL.md`.

    Raises:
        PackageAssetError: В пакете нет `SKILL.md`. Прежний каталог не тронут.
        OSError: Запись не завершилась. Прежний каталог на месте.
    """
    text = read_package_text(_SKILL_FILE, _MISSING, _MISSING_HINT)
    destination = installed_skill_dir()
    _ensure_parents(destination.parent)
    staging = _stage(destination.parent, text)
    try:
        _swap_in(destination, staging)
    except OSError:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / _SKILL_FILE


def uninstall_skill() -> tuple[str, Path]:
    """Удалить установленный скилл.

    Симлинк снимается сам, каталог по ссылке не удаляется. Обычный файл
    на этом пути не скилл: его заменяет каталогом только `install`.

    Returns:
        `удалён` или `уже отсутствует` и абсолютный путь слота.
    """
    destination = installed_skill_dir()
    if destination.is_symlink():
        destination.unlink()
        return "удалён", destination
    if destination.is_dir():
        shutil.rmtree(destination)
        return "удалён", destination
    return "уже отсутствует", destination


def _ensure_parents(directory: Path) -> None:
    missing: list[Path] = []
    current = directory
    while not current.exists() and current != current.parent:
        missing.append(current)
        current = current.parent
    for item in reversed(missing):
        item.mkdir()
        item.chmod(0o755)


def _stage(parent: Path, text: str) -> Path:
    staging = Path(tempfile.mkdtemp(dir=parent, prefix=".day-recap."))
    try:
        staging.chmod(0o755)
        skill = staging / _SKILL_FILE
        skill.write_text(text, encoding="utf-8")
        skill.chmod(0o644)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def _swap_in(destination: Path, staging: Path) -> None:
    if not destination.is_symlink() and not destination.exists():
        staging.rename(destination)
        return
    if destination.is_symlink() or not destination.is_dir():
        _replace_non_directory(destination, staging)
        return
    _swap_directory(destination, staging)


def _replace_non_directory(destination: Path, staging: Path) -> None:
    if destination.is_symlink():
        target = destination.readlink()
        destination.unlink()
        try:
            staging.rename(destination)
        except OSError:
            destination.symlink_to(target)
            raise
        return
    backup = _backup_name(destination)
    destination.rename(backup)
    try:
        staging.rename(destination)
    except OSError:
        backup.rename(destination)
        raise
    backup.unlink()


def _swap_directory(destination: Path, staging: Path) -> None:
    backup = _backup_name(destination)
    destination.rename(backup)
    try:
        staging.rename(destination)
    except OSError:
        backup.rename(destination)
        raise
    shutil.rmtree(backup)


def _backup_name(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{uuid.uuid4().hex}")
