"""Поля сообщения Telethon без сети и без файла сессии.

Реакции считаются здесь и в дамп не попадают: сборщик их не записывает.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    ReactionPaid,
)

from app.summary.models import TelegramMessage

_ME = "me"


@dataclass(frozen=True)
class Focus:
    """Чьи сообщения свои: `me` — исходящие этого аккаунта, плюс id и username."""

    me: bool
    ids: frozenset[int]
    usernames: frozenset[str]

    @classmethod
    def parse(cls, entries: Sequence[int | str]) -> "Focus":
        """Разобрать `telegram.focus`.

        Args:
            entries: `me`, id или username с `@` или без.

        Returns:
            Правило для `dump_messages`.
        """
        ids = frozenset(entry for entry in entries if isinstance(entry, int))
        names = [entry for entry in entries if isinstance(entry, str) and entry != _ME]
        return cls(
            me=_ME in entries,
            ids=ids,
            usernames=frozenset(name.removeprefix("@").casefold() for name in names),
        )

    def covers(self, msg: object) -> bool:
        """Своё ли сообщение.

        Args:
            msg: Сообщение Telethon.

        Returns:
            `True`, если автор входит в правило.
        """
        if self.me and getattr(msg, "out", False) is True:
            return True
        user_id, _name, username = sender_fields(msg)
        if user_id is not None and user_id in self.ids:
            return True
        return username is not None and username.casefold() in self.usernames


def dump_messages(
    messages: list[object],
    *,
    forward_names: dict[int, str] | None = None,
    focus: Focus | None = None,
) -> list[TelegramMessage]:
    """Собрать сообщения дня: альбом — одна запись, служебные события пропущены.

    Порядок — от раннего к позднему. Пересланное получает пометку об авторстве.
    Подпись к медиа остаётся текстом, описание вложения — следующей строкой.

    Args:
        messages: Сообщения Telethon в любом порядке.
        forward_names: Имена по id из `fwd_from.from_id`, если в сообщении нет строки.
        focus: Чьи сообщения свои. `None` — только `me`.

    Returns:
        Записи дампа без пустых и служебных сообщений.
    """
    names = {} if forward_names is None else forward_names
    mine = Focus.parse([_ME]) if focus is None else focus
    visible = [message for message in messages if not _is_service(message)]
    rendered: list[TelegramMessage] = []
    for group in _chronological(group_albums(visible)):
        item = _render_group(group, names, mine)
        if item is not None:
            rendered.append(item)
    return rendered


def forward_peer_id(msg: object) -> int | None:
    """Id автора пересылки, если имя ещё не лежит в самом сообщении.

    Args:
        msg: Сообщение.

    Returns:
        `user_id`, `channel_id` или `chat_id`. `None`, если пересылки нет
        или имя уже записано в `from_name` / `post_author`.
    """
    forwarded = getattr(msg, "fwd_from", None)
    if forwarded is None or _forward_label(forwarded) != "":
        return None
    return _peer_id(getattr(forwarded, "from_id", None))


def media_type(msg: object) -> str | None:
    """Вид вложения: `photo`, `document` или имя типа Telethon.

    Args:
        msg: Сообщение.

    Returns:
        Короткая метка либо `None`, если вложения нет.
    """
    media = getattr(msg, "media", None)
    if not media:
        return None
    if isinstance(media, MessageMediaPhoto):
        return "photo"
    if isinstance(media, MessageMediaDocument):
        return "document"
    return type(media).__name__


def media_desc(msg: object) -> str | None:
    """Одна строка про вложение. Файл не скачивается.

    Args:
        msg: Сообщение.

    Returns:
        Описание либо `None`, если вложения нет.
    """
    kind = media_type(msg)
    if kind is None:
        return None
    media = getattr(msg, "media", None)
    if isinstance(media, MessageMediaDocument):
        return _document_desc(media, fallback=kind)
    return kind


def sender_fields(msg: object) -> tuple[int | None, str | None, str | None]:
    """Идентификатор, имя и username отправителя.

    Args:
        msg: Сообщение.

    Returns:
        Тройка `(user_id, имя, username)`.
    """
    sender = getattr(msg, "sender", None)
    if sender is None:
        return _peer_id(getattr(msg, "from_id", None)), None, None
    return _sender_id(sender), _sender_name(sender), _username(sender)


def count_reactions(msg: object) -> tuple[int, int]:
    """Число обычных реакций и звёзд. Сборщик дня это число не пишет в дамп.

    Args:
        msg: Сообщение.

    Returns:
        Пара `(реакции, звёзды)`.
    """
    results = getattr(getattr(msg, "reactions", None), "results", None)
    if not results:
        return 0, 0
    reactions = stars = 0
    for item in results:
        count = getattr(item, "count", 0)
        if not isinstance(count, int):
            continue
        if isinstance(getattr(item, "reaction", None), ReactionPaid):
            stars += count
        else:
            reactions += count
    return reactions, stars


def group_albums(messages: list[object]) -> list[list[object]]:
    """Сгруппировать альбом по `grouped_id`. Одиночные сообщения — группы из одного.

    Args:
        messages: Сообщения в исходном порядке.

    Returns:
        Сначала одиночные, затем альбомы.
    """
    groups: dict[int, list[object]] = {}
    standalone: list[list[object]] = []
    for message in messages:
        grouped_id = getattr(message, "grouped_id", None)
        if isinstance(grouped_id, int):
            groups.setdefault(grouped_id, []).append(message)
        else:
            standalone.append([message])
    return standalone + list(groups.values())


def _chronological(groups: list[list[object]]) -> list[list[object]]:
    return sorted(groups, key=lambda group: min(_sort_key(message) for message in group))


def _render_group(
    group: list[object],
    names: dict[int, str],
    focus: Focus,
) -> TelegramMessage | None:
    ordered = sorted(group, key=_sort_key)
    body = _body(ordered, names)
    if body == "":
        return None
    first = ordered[0]
    return TelegramMessage(
        id=_message_id(first),
        sent_at=_sent_at(first),
        author=_author(first),
        text=body,
        reply_to=next((parent for msg in ordered if (parent := _reply_to(msg)) is not None), None),
        mine=focus.covers(first),
        mentions_me=any(getattr(msg, "mentioned", False) is True for msg in ordered),
    )


def _reply_to(msg: object) -> int | None:
    header = getattr(msg, "reply_to", None)
    if header is None:
        return None
    # Сообщение топика без ответа ссылается на корень топика, а не на реплику.
    if getattr(header, "forum_topic", False) and getattr(header, "reply_to_top_id", None) is None:
        return None
    parent = getattr(header, "reply_to_msg_id", None)
    if isinstance(parent, int):
        return parent
    return None


def _body(messages: list[object], names: dict[int, str]) -> str:
    caption = next((_plain(message) for message in messages if _plain(message)), "")
    medias = [desc for desc in (media_desc(message) for message in messages) if desc]
    text = caption
    if medias:
        line = ", ".join(medias)
        text = f"{text}\n{line}" if text else line
    forwarded = next(
        (name for message in messages if (name := _forward_name(message, names))),
        "",
    )
    if forwarded:
        return f"переслано от {forwarded}: {text}" if text else f"переслано от {forwarded}"
    return text


def _is_service(msg: object) -> bool:
    return getattr(msg, "action", None) is not None


def _plain(msg: object) -> str:
    text = getattr(msg, "message", None)
    if not isinstance(text, str):
        return ""
    return text.strip()


def _forward_name(msg: object, names: dict[int, str]) -> str:
    forwarded = getattr(msg, "fwd_from", None)
    if forwarded is None:
        return ""
    label = _forward_label(forwarded)
    if label != "":
        return label
    peer_id = _peer_id(getattr(forwarded, "from_id", None))
    if peer_id is not None and peer_id in names:
        return names[peer_id]
    return "неизвестного автора"


def _forward_label(forwarded: object) -> str:
    for attr in ("from_name", "post_author"):
        value = getattr(forwarded, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _author(msg: object) -> str | None:
    _user_id, name, _username = sender_fields(msg)
    return name


def _sort_key(msg: object) -> tuple[datetime, int]:
    return _sent_at(msg), _message_id(msg) or 0


def _message_id(msg: object) -> int | None:
    message_id = getattr(msg, "id", None)
    if isinstance(message_id, int):
        return message_id
    return None


def _sent_at(msg: object) -> datetime:
    sent_at = getattr(msg, "date", None)
    if not isinstance(sent_at, datetime):
        message = "у сообщения нет даты"
        raise TypeError(message)
    return sent_at


def _document_desc(media: MessageMediaDocument, *, fallback: str) -> str:
    document = media.document
    name = _file_name(document)
    parts = [name or fallback]
    size = getattr(document, "size", None)
    if isinstance(size, int) and size:
        parts.append(f"({size:,} bytes)")
    return " ".join(parts)


def _file_name(document: object) -> str | None:
    attributes = getattr(document, "attributes", None)
    if not attributes:
        return None
    for attr in attributes:
        file_name = getattr(attr, "file_name", None)
        if isinstance(file_name, str) and file_name:
            return file_name
    return None


def _peer_id(peer: object) -> int | None:
    for attr in ("user_id", "channel_id", "chat_id"):
        value = getattr(peer, attr, None)
        if isinstance(value, int):
            return value
    return None


def _sender_id(sender: object) -> int | None:
    sender_id = getattr(sender, "id", None)
    if isinstance(sender_id, int):
        return sender_id
    return None


def _sender_name(sender: object) -> str | None:
    first = getattr(sender, "first_name", "") or ""
    last = getattr(sender, "last_name", "") or ""
    if not isinstance(first, str):
        first = ""
    if not isinstance(last, str):
        last = ""
    name = f"{first} {last}".strip()
    if name:
        return name
    title = getattr(sender, "title", None)
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _username(sender: object) -> str | None:
    username = getattr(sender, "username", None)
    if isinstance(username, str) and username:
        return username
    return None
