"""Вопросы `init`: пути до входа, затем белый список."""

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path

from app.atomic import replace_text
from app.collectors.telegram.chats import dialog_rows, format_numbered
from app.collectors.telegram.init import open_account, store_credentials
from app.config import Config, default_config_path, load_config
from app.config_text import apply_allowlist, apply_paths, copy_packaged_example, prompt_fields

_NOTES = "Каталог заметок"
_TEMPLATE = "Шаблон заметки"
_ROOT = "Корень git"
_REPLACE = "Заменить список чатов? (да/нет) [нет]:"
_NUMBERS = "Номера чатов через запятую (Enter — пустой список):"
_YES = "да"
_NO = "нет"


def run_setup(
    config_path: Path | None,
    *,
    relogin: bool,
    login: str | None,
    ask: Callable[[str], str],
    choose: Callable[[], str],
) -> None:
    """Спросить пути и белый список и войти в Telegram.

    Секреты — только недостающие. Ответы о путях пишутся до входа.
    Явный отсутствующий `--config` — ошибка до вопросов.

    Args:
        config_path: Путь флага `--config`. `None` — файл по умолчанию.
        relogin: Удалить файл сессии перед входом.
        login: `qr` или `code`. `None` — спросить, когда входа ещё нет.
        ask: Вопрос секрета. Ключ — имя переменной.
        choose: Ответ на `qr` или `code`.

    Raises:
        FileNotFoundError: Явный `--config` не указывает на файл.
        PackageAssetError: Примера конфига нет в пакете.
        SummaryError: Секреты не собраны, вход или диалоги отклонены.
    """
    path = _prepare_config(config_path)
    store_credentials(ask)
    _collect_paths(path)
    config = load_config(path)
    account = open_account(config, relogin=relogin, login=login, choose=choose)
    sys.stdout.write(f"Вошли как {account}\n")
    _collect_allowlist(path, config)


def _prepare_config(config_path: Path | None) -> Path:
    if config_path is not None:
        path = config_path.expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    path = default_config_path()
    if not path.is_file():
        copy_packaged_example(path)
    return path


def _collect_paths(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    notes_now, template_now, roots_now = prompt_fields(original)
    notes = _ask_kept(_NOTES, notes_now)
    template = _ask_file(template_now)
    root = _ask_directory(roots_now)
    if notes is None and template is None and root is None:
        return
    updated = apply_paths(original, notes=notes, template=template, root=root)
    replace_text(path, updated)


def _ask_kept(label: str, current: str | None) -> str | None:
    shown = "не задан" if current is None else current
    answer = input(f"{label} (Enter — {shown}):").strip()
    if answer == "":
        return None
    return answer


def _ask_file(current: str | None) -> str | None:
    while True:
        answer = _ask_kept(_TEMPLATE, current)
        if answer is None or Path(answer).expanduser().is_file():
            return answer
        sys.stderr.write(f"Файл шаблона не найден: {answer}\n")


def _ask_directory(current: str) -> str | None:
    while True:
        answer = _ask_kept(_ROOT, current)
        if answer is None or Path(answer).expanduser().is_dir():
            return answer
        sys.stderr.write(f"Каталог не найден: {answer}\n")


def _collect_allowlist(path: Path, config: Config) -> None:
    if config.telegram.chats and not _wants_replace():
        return
    rows = asyncio.run(dialog_rows(config))
    sys.stdout.write(format_numbered(rows))
    if not rows:
        if config.telegram.chats:
            _write_allowlist(path, [])
        return
    picked = _ask_numbers(len(rows))
    chosen = [(rows[number - 1][0], rows[number - 1][1]) for number in picked]
    _write_allowlist(path, chosen)


def _wants_replace() -> bool:
    while True:
        answer = input(_REPLACE).strip().casefold()
        if answer in {"", _NO}:
            return False
        if answer == _YES:
            return True
        sys.stderr.write("Ожидается да или нет.\n")


def _ask_numbers(size: int) -> list[int]:
    while True:
        raw = input(_NUMBERS).strip()
        if raw == "":
            return []
        numbers, bad = _parse_numbers(raw, size)
        if bad is not None:
            sys.stderr.write(f"Номер вне таблицы: {bad}\n")
            continue
        return numbers


def _parse_numbers(raw: str, size: int) -> tuple[list[int], str | None]:
    chosen: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if token == "":
            continue
        if not token.isdigit():
            return [], token
        number = int(token)
        if number < 1 or number > size:
            return [], token
        if number not in chosen:
            chosen.append(number)
    chosen.sort()
    return chosen, None


def _write_allowlist(path: Path, chats: list[tuple[int, str]]) -> None:
    original = path.read_text(encoding="utf-8")
    updated = apply_allowlist(original, chats)
    if updated != original:
        replace_text(path, updated)
