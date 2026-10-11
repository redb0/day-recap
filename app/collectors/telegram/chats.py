"""Список диалогов и фрагмент `[[telegram.chats]]` для конфига."""

from datetime import datetime

from app.collectors.telegram.tg import connected
from app.config import Config


def format_chats(rows: list[tuple[int, str, str, datetime | None]]) -> str:
    """Таблица и готовый фрагмент конфига.

    Args:
        rows: Id, название, тип и дата последнего сообщения.

    Returns:
        Текст для stdout. Пустой список — строка «чатов нет».
    """
    if not rows:
        return "чатов нет\n"
    lines = ["id\tназвание\tтип\tпоследнее"]
    blocks: list[str] = []
    for row in rows:
        lines.append(_format_row(row))
        blocks.append(f"[[telegram.chats]]\nid = {row[0]}\nname = {_toml(row[1])}")
    return "\n".join(lines) + "\n\n" + "\n\n".join(blocks) + "\n"


def format_numbered(rows: list[tuple[int, str, str, datetime | None]]) -> str:
    """Та же таблица, что у просмотра чатов, с номером строки с единицы.

    Args:
        rows: Id, название, тип и дата последнего сообщения.

    Returns:
        Текст для stdout. Пустой список — строка «чатов нет».
    """
    if not rows:
        return "чатов нет\n"
    lines = ["id\tназвание\tтип\tпоследнее"]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}\t{_format_row(row)}")
    return "\n".join(lines) + "\n"


async def dialog_rows(config: Config) -> list[tuple[int, str, str, datetime | None]]:
    """Диалоги текущей сессии в порядке `iter_dialogs`.

    Args:
        config: Настройки с секретами и каталогом сессии.

    Returns:
        Id, название, тип и дата последнего сообщения.
    """
    rows: list[tuple[int, str, str, datetime | None]] = []
    async with connected(config) as client:
        async for dialog in client.iter_dialogs():
            row = _row(dialog)
            if row is not None:
                rows.append(row)
    return rows


async def load_chats(config: Config) -> str:
    """Прочитать диалоги текущей сессии.

    Args:
        config: Настройки с секретами и каталогом сессии.

    Returns:
        Текст `format_chats`. Файл конфига не меняется.
    """
    return format_chats(await dialog_rows(config))


def _format_row(row: tuple[int, str, str, datetime | None]) -> str:
    chat_id, title, kind, last = row
    stamp = "" if last is None else last.isoformat()
    return f"{chat_id}\t{title}\t{kind}\t{stamp}"


def _row(dialog: object) -> tuple[int, str, str, datetime | None] | None:
    chat_id = getattr(dialog, "id", None)
    title = getattr(dialog, "name", None)
    if not isinstance(chat_id, int) or not isinstance(title, str):
        return None
    last = getattr(dialog, "date", None)
    if last is not None and not isinstance(last, datetime):
        last = None
    return chat_id, title, _kind(dialog), last


def _kind(dialog: object) -> str:
    if getattr(dialog, "is_user", False):
        return "личный"
    if getattr(dialog, "is_group", False):
        return "группа"
    if getattr(dialog, "is_channel", False):
        return "канал"
    return "чат"


def _toml(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
