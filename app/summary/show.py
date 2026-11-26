"""Печать тела дампа. Файл не меняется: режется только то, что видит агент."""

import re

from app.summary.models import (
    GitCommit,
    GitDirty,
    GitDump,
    GitRepo,
    SessionDump,
    TelegramChatLog,
    TelegramDump,
    TelegramMessage,
    TranscriptMessage,
    TranscriptSession,
)

_SUMMARY_CALL = re.compile(
    r"^/day-recap(?:[ \t]+(?:today|yesterday|\d{4}-\d{2}-\d{2}))?$",
)
_BRIEFLY = "Briefly inform the user"
_REVIEW = re.compile(r"^you are the (?:standards|spec) axis\b", re.IGNORECASE)
_SPACES = re.compile(r"[ \t]+")
_COMMIT_SHA = re.compile(r"(diff коммита) \S+")
_SESSION_ID = re.compile(r"(сессия) \S+")
_CHAT_ID = re.compile(r"(чат) \d+")


def visible_truncation(note: str) -> str:
    """Убрать sha, id сессии и id чата из строки обрезки.

    Файл дампа эта функция не читает и не меняет.

    Args:
        note: Строка `truncations`, как она лежит в дампе.

    Returns:
        Та же строка без идентификаторов.
    """
    text = _COMMIT_SHA.sub(r"\1", note)
    text = _SESSION_ID.sub(r"\1", text)
    return _CHAT_ID.sub(r"\1", text)


def render_git(dump: GitDump) -> str:
    """Напечатать коммиты и отдельно незакоммиченные файлы.

    Sha в текст не входит. Пустой дамп — пустая строка.

    Args:
        dump: Записанный дамп git.

    Returns:
        Текст тела.
    """
    blocks = [_repo_block(repo) for repo in dump.repos]
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def _repo_block(repo: GitRepo) -> str:
    sections = [_commit_block(commit) for commit in repo.commits]
    if repo.dirty is not None:
        sections.append(_dirty_block(repo.dirty))
    return f"# {repo.path}\n" + "\n\n".join(sections)


def _commit_block(commit: GitCommit) -> str:
    lines = [
        f"## commit {commit.committed_at.isoformat()}",
        commit.message,
        f"files: {', '.join(commit.files)}",
        commit.diffstat,
    ]
    if commit.diff:
        lines.append(commit.diff.rstrip("\n"))
    return "\n".join(lines)


def _dirty_block(dirty: GitDirty) -> str:
    return "\n".join(["## в процессе", *dirty.files, dirty.diffstat])


def render_sessions(dump: SessionDump) -> str:
    """Напечатать реплики сессий без id.

    Вызов саммари и реплика, которая начинается с «Briefly inform the user»,
    не печатаются. Сессия без оставшегося текста человека пропускается.
    Ревью-ось помечается `review`, повтор первого запроса в том же проекте —
    `repeat`. Файл дампа эта функция не читает и не меняет.

    Args:
        dump: Дамп транскриптов или OpenCode.

    Returns:
        Текст тела. Нечего печатать — пустая строка.
    """
    blocks: list[str] = []
    seen: set[tuple[str, str]] = set()
    for session in dump.sessions:
        kept = _visible(session)
        if kept is None:
            continue
        key = (session.project, _collapsed(_opening(kept)))
        blocks.append(_session_block(session.project, kept, _marks(key, seen)))
        seen.add(key)
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def _visible(session: TranscriptSession) -> list[TranscriptMessage] | None:
    kept = [message for message in session.messages if not _service(message)]
    if any(message.role == "user" for message in kept):
        return kept
    return None


def _service(message: TranscriptMessage) -> bool:
    text = message.text.strip()
    return text.startswith(_BRIEFLY) or _SUMMARY_CALL.fullmatch(text) is not None


def _opening(messages: list[TranscriptMessage]) -> str:
    for message in messages:
        if message.role == "user":
            return message.text
    return ""


def _collapsed(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def _marks(key: tuple[str, str], seen: set[tuple[str, str]]) -> list[str]:
    marks: list[str] = []
    if _REVIEW.match(key[1]):
        marks.append("review")
    if key in seen:
        marks.append("repeat")
    return marks


def _session_block(
    project: str,
    messages: list[TranscriptMessage],
    marks: list[str],
) -> str:
    heading = f"## {project}"
    if marks:
        heading = f"{heading} {' '.join(marks)}"
    lines = [heading, *[_message_line(message) for message in messages]]
    return "\n".join(lines)


def _message_line(message: TranscriptMessage) -> str:
    return f"{message.role}: {message.text}"


def render_telegram(dump: TelegramDump) -> str:
    """Напечатать чаты белого списка без id чата.

    Строка сообщения начинается с `#id`, ответ — `↩#id` родителя. Своё
    сообщение помечено `моё`, остальное якорное — `якорное`. Заголовок чата
    без якорных сообщений помечен `(чат без участия)`.

    Args:
        dump: Записанный дамп Telegram.

    Returns:
        Текст тела, включая число чатов вне конфига.
    """
    blocks = [_chat_block(chat) for chat in dump.chats]
    head = f"unlisted_active {dump.unlisted_active}"
    if not blocks:
        return head + "\n"
    return head + "\n" + "\n\n".join(blocks) + "\n"


def without_participation(dump: TelegramDump) -> int:
    """Число чатов без участия: за окно в них нет якорных сообщений.

    Args:
        dump: Записанный дамп Telegram.

    Returns:
        Сколько чатов дампа без якорных сообщений.
    """
    return sum(1 for chat in dump.chats if not any(_anchors(chat)))


def _anchors(chat: TelegramChatLog) -> list[bool]:
    """Якорное ли каждое сообщение чата.

    Якорное — своё, с упоминанием меня или ответ на своё сообщение этого дампа.
    Родителя вне окна заменяет флаг упоминания.
    """
    mine = {message.id for message in chat.messages if message.mine and message.id is not None}
    return [
        message.mine or message.mentions_me or message.reply_to in mine for message in chat.messages
    ]


def _chat_block(chat: TelegramChatLog) -> str:
    anchors = _anchors(chat)
    heading = f"# {chat.name}" if any(anchors) else f"# {chat.name} (чат без участия)"
    lines = [heading]
    for message, anchored in zip(chat.messages, anchors, strict=True):
        marks = _marks_of(message, anchored=anchored)
        author = message.author or ""
        lines.append(f"{marks}{message.sent_at.isoformat()} {author}: {message.text}")
    return "\n".join(lines)


def _marks_of(message: TelegramMessage, *, anchored: bool) -> str:
    marks: list[str] = []
    if message.id is not None:
        marks.append(f"#{message.id}")
    if message.reply_to is not None:
        marks.append(f"↩#{message.reply_to}")
    if message.mine:
        marks.append("моё")
    elif anchored:
        marks.append("якорное")
    return "".join(f"{mark} " for mark in marks)
