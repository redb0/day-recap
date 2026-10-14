"""Точечная правка toml: четыре места, остальной текст остаётся."""

import tomllib
from pathlib import Path

from app.assets import read_package_text
from app.atomic import replace_text

_EXAMPLE_MISSING = "В поставке нет config.example.toml."
_EXAMPLE_HINT = "Положите config.example.toml в пакет app и переустановите пакет."
_FORM = (
    "# [[telegram.chats]]",
    "# id = 123456789",
    '# name = "название"',
)
_DEFAULT_ROOT = "~/projects"


def copy_packaged_example(destination: Path) -> None:
    """Положить пример конфига в `destination`, не спрашивая терминал.

    Args:
        destination: Куда записать пример. Родитель создаётся, каталог заметок нет.

    Raises:
        PackageAssetError: Примера нет в пакете. `destination` не создаётся.
    """
    text = read_package_text("config.example.toml", _EXAMPLE_MISSING, _EXAMPLE_HINT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    replace_text(destination, text)


def prompt_fields(text: str) -> tuple[str | None, str | None, str]:
    """Текущие каталог заметок, шаблон и подпись корней обхода.

    Пустая строка и отсутствующий ключ — «не задано». Нет ключа `roots` —
    подпись `~/projects`, как в примере. Пустой и непустой список — как в файле.

    Args:
        text: Текст конфига.

    Returns:
        Каталог или `None`, шаблон или `None`, подпись корней для скобок.
    """
    parsed = tomllib.loads(text)
    return (
        _field(parsed, "notes", "daily_dir"),
        _field(parsed, "notes", "template"),
        _roots_label(parsed),
    )


def apply_paths(
    text: str,
    *,
    notes: str | None,
    template: str | None,
    root: str | None,
) -> str:
    """Записать только те пути, которые человек ввёл.

    `None` значит «оставить строку как есть». Введённый путь кладётся
    как напечатан, без разворачивания `~`. Корень заменяет весь список,
    комментарии на его строках остаются.

    Args:
        text: Исходный текст.
        notes: Новый каталог заметок либо `None`.
        template: Новый шаблон либо `None`.
        root: Новый единственный корень обхода либо `None`.

    Returns:
        Текст с заменёнными присваиваниями.
    """
    if notes is not None:
        text = _replace_assignment(text, "notes", "daily_dir", literal=_basic(notes))
    if template is not None:
        text = _replace_assignment(text, "notes", "template", literal=_basic(template))
    if root is not None:
        literal = "[" + _basic(root) + "]"
        text = _replace_assignment(text, "git", "roots", literal=literal)
    return text


def apply_allowlist(text: str, chats: list[tuple[int, str]]) -> str:
    """Заменить блоки белого списка и оставить комментарий с формой.

    Args:
        text: Исходный текст.
        chats: Пары id и названия в порядке строк таблицы. Пустой список снимает блоки.

    Returns:
        Текст без прежних блоков `[[telegram.chats]]`.
    """
    lines = text.splitlines(keepends=True)
    kept = _drop_chat_blocks(lines)
    with_form = _ensure_form(kept)
    if not chats:
        return "".join(with_form)
    return "".join(_insert_blocks(with_form, chats))


def _field(parsed: object, section: str, key: str) -> str | None:
    if not isinstance(parsed, dict):
        return None
    body = parsed.get(section)
    if not isinstance(body, dict) or key not in body:
        return None
    value = body[key]
    if isinstance(value, str) and value != "":
        return value
    return None


def _roots_label(parsed: object) -> str:
    if not isinstance(parsed, dict):
        return _DEFAULT_ROOT
    git = parsed.get("git")
    if not isinstance(git, dict) or "roots" not in git:
        return _DEFAULT_ROOT
    roots = git["roots"]
    if not isinstance(roots, list):
        return _DEFAULT_ROOT
    labels: list[str] = []
    for item in roots:
        if not isinstance(item, str):
            return _DEFAULT_ROOT
        labels.append(item)
    return ", ".join(labels)


def _basic(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _replace_assignment(text: str, section: str, key: str, *, literal: str) -> str:
    lines = text.splitlines(keepends=True)
    bounds = _section_bounds(lines, section)
    if bounds is None:
        return _append_section(text, section, key, literal=literal)
    start, end = bounds
    for index in range(start + 1, end):
        rest = _assignment_rest(lines[index], key)
        if rest is None:
            continue
        finish, suffix = _assignment_span(lines, index, rest)
        indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
        lines[index:finish] = [f"{indent}{key} = {literal}{suffix}\n"]
        return "".join(lines)
    lines.insert(end, f"{key} = {literal}\n")
    return "".join(lines)


def _append_section(text: str, section: str, key: str, *, literal: str) -> str:
    block = f"[{section}]\n{key} = {literal}\n"
    if not text:
        return block
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block


def _section_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    start: int | None = None
    for index, line in enumerate(lines):
        header = _section_name(line)
        if header is None:
            continue
        if start is not None:
            return start, index
        if header == name:
            start = index
    if start is None:
        return None
    return start, len(lines)


def _section_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or stripped.startswith("[["):
        return None
    end = stripped.find("]")
    if end < 0:
        return None
    return stripped[1:end].strip()


def _assignment_rest(line: str, key: str) -> str | None:
    body = line.rstrip("\r\n")
    stripped = body.lstrip()
    if stripped.startswith(("#", "[")):
        return None
    left, sep, rest = body.partition("=")
    if sep != "=" or left.strip() != key:
        return None
    return rest


def _assignment_span(lines: list[str], index: int, rest: str) -> tuple[int, str]:
    end, complete = _value_span(rest)
    if complete:
        return index + 1, rest[end:].rstrip("\r\n")
    comments = _line_comments(rest)
    finish = index + 1
    depth = _bracket_depth(rest)
    while finish < len(lines) and depth > 0:
        body = lines[finish].rstrip("\r\n")
        comments.extend(_line_comments(body))
        depth += _bracket_depth(body)
        finish += 1
    if not comments:
        return finish, ""
    return finish, " " + " ".join(comments)


def _line_comments(text: str) -> list[str]:
    comment = _hash_comment(text)
    if comment == "":
        return []
    return [comment]


def _hash_comment(text: str) -> str:
    index = 0
    while index < len(text):
        char = text[index]
        if char in {'"', "'"}:
            index, done = _span_string(text, index, quote=char)
            if not done:
                return ""
            continue
        if char == "#":
            return text[index:].rstrip("\r\n")
        index += 1
    return ""


def _value_span(rest: str) -> tuple[int, bool]:
    index = _skip_spaces(rest)
    if index >= len(rest):
        return index, True
    return _typed_span(rest, index)


def _skip_spaces(rest: str) -> int:
    index = 0
    while index < len(rest) and rest[index] in " \t":
        index += 1
    return index


def _typed_span(rest: str, index: int) -> tuple[int, bool]:
    char = rest[index]
    if char == "[":
        return _span_brackets(rest, index)
    if char == '"':
        return _span_string(rest, index, quote='"')
    if char == "'":
        return _span_string(rest, index, quote="'")
    while index < len(rest) and rest[index] not in " \t#":
        index += 1
    return index, True


def _span_string(text: str, start: int, *, quote: str) -> tuple[int, bool]:
    if text.startswith(quote * 3, start):
        end = text.find(quote * 3, start + 3)
        if end < 0:
            return len(text), False
        return end + 3, True
    index = start + 1
    while index < len(text):
        if quote == '"' and text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index + 1, True
        index += 1
    return len(text), False


def _span_brackets(text: str, start: int) -> tuple[int, bool]:
    depth = 0
    index = start
    while index < len(text):
        step = _bracket_step(text, index, depth)
        if step is None:
            return index, depth == 0
        index, depth, closed = step
        if closed:
            return index, True
    return len(text), depth == 0


def _bracket_depth(text: str) -> int:
    depth = 0
    index = 0
    while index < len(text):
        step = _bracket_step(text, index, depth)
        if step is None:
            return depth
        index, depth, _closed = step
    return depth


def _bracket_step(text: str, index: int, depth: int) -> tuple[int, int, bool] | None:
    char = text[index]
    if char in {'"', "'"}:
        return _string_step(text, index, depth, quote=char)
    if char == "#":
        return None
    if char == "[":
        return index + 1, depth + 1, False
    if char == "]":
        depth -= 1
        return index + 1, depth, depth == 0
    return index + 1, depth, False


def _string_step(text: str, index: int, depth: int, *, quote: str) -> tuple[int, int, bool]:
    index, done = _span_string(text, index, quote=quote)
    if not done:
        return len(text), depth, False
    return index, depth, False


def _drop_chat_blocks(lines: list[str]) -> list[str]:
    kept: list[str] = []
    index = 0
    while index < len(lines):
        if _is_chat_header(lines[index]):
            index += 1
            while index < len(lines) and _is_block_body(lines[index]):
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    return kept


def _is_chat_header(line: str) -> bool:
    return line.strip().startswith("[[telegram.chats]]")


def _is_block_body(line: str) -> bool:
    stripped = line.strip()
    if stripped == "" or stripped.startswith("#"):
        return True
    if stripped.startswith("["):
        return False
    return "=" in stripped


def _ensure_form(lines: list[str]) -> list[str]:
    if _form_end(lines) is not None:
        return lines
    bounds = _section_bounds(lines, "telegram")
    at = len(lines) if bounds is None else bounds[1]
    prefix: list[str] = []
    if at == 0 or lines[at - 1].strip() != "":
        prefix = ["\n"]
    form = [line + "\n" for line in _FORM]
    return [*lines[:at], *prefix, *form, *lines[at:]]


def _form_end(lines: list[str]) -> int | None:
    stripped = [line.strip() for line in lines]
    last = len(stripped) - 2
    for index in range(max(last, 0)):
        if tuple(stripped[index : index + 3]) == _FORM:
            return index + 3
    return None


def _insert_blocks(lines: list[str], chats: list[tuple[int, str]]) -> list[str]:
    at = _block_insert_at(lines)
    leading_blank = at == 0 or lines[at - 1].strip() != ""
    chunks = _chat_chunks(chats, leading_blank=leading_blank)
    following = lines[at] if at < len(lines) else ""
    if following.strip() != "":
        chunks.append("\n")
    return [*lines[:at], *chunks, *lines[at:]]


def _block_insert_at(lines: list[str]) -> int:
    at = _form_end(lines)
    if at is None:
        return len(lines)
    if at < len(lines) and lines[at].strip() == "":
        return at + 1
    return at


def _chat_chunks(chats: list[tuple[int, str]], *, leading_blank: bool) -> list[str]:
    chunks: list[str] = ["\n"] if leading_blank else []
    for index, (chat_id, name) in enumerate(chats):
        if index:
            chunks.append("\n")
        chunks.append(f"[[telegram.chats]]\nid = {chat_id}\nname = {_basic(name)}\n")
    return chunks
