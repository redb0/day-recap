# day-recap

[Русский](README.ru.md)

[![tests](https://github.com/redb0/day-recap/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/redb0/day-recap/actions/workflows/test.yaml)
[![coverage](https://codecov.io/gh/redb0/day-recap/branch/main/graph/badge.svg)](https://codecov.io/gh/redb0/day-recap)
![python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

Collects a day's work from local git repositories, Cursor transcripts, OpenCode
sessions, and a Telegram allowlist. Only a confirmed block is appended to the
Obsidian daily note.

The raw dump stays outside the vault. An empty day does not change the note.

```markdown
## 🤖 Итоги дня

### Сделано
- **billing** — сузил окно повторной оплаты до одного счёта

### Решения и обоснования
Оставили повтор по idempotency-key. Повтор всей корзины отбросили: он списывал деньги второй раз.
```

## Install and configure

```sh
uv tool install day-recap
```

Run `day-recap init` in your own terminal, not in the agent chat. It asks for
the Telegram secrets, the notes directory, the template, one walk root, and
the allowlist. Do not type `api_id` or `api_hash` into the chat. When
`~/.config/day-recap/config.toml` is missing, `init` copies the packaged
example and writes your answers over it. An existing file is not replaced
wholesale. `init` asks `qr` or `code`. `qr` prints a code to scan: Settings →
Devices → Link desktop device. `code` waits for the login code in the Telegram
service chat. `--login qr` or `--login code` skips the question. `--relogin`
signs in again and does not rewrite the toml by itself. After login, `init`
shows the same numbered table as `day-recap chats` and records the selected
numbers. An empty allowlist is asked for immediately. A non-empty one changes
only after you agree.

`day-recap chats` prints a table and ready `[[telegram.chats]]` blocks and
does not change the config. Only allowlisted chats are read into the raw dump.

| Section | What it sets |
| --- | --- |
| `[notes]` | Where to write the daily note. |
| `[state]` | Where raw dumps are stored. |
| `[git]` | Which directories to walk and whose commits to take. |
| `[transcripts]` | Cursor JSONL roots and how messages are trimmed. |
| `[opencode]` | OpenCode database and the same trim. |
| `[telegram]` | Whether the source is on, and the allowlist. |
| `[summary]` | Size threshold. |

Keys and defaults ship in the package as `app/config.example.toml`.

- The size threshold is 100000 bytes.
- Raw dumps are kept for 14 days.
- `~/.config/day-recap/.env` is mode 600.

## In the agent

`day-recap install` puts the skill at `~/.agents/skills/day-recap/SKILL.md`.
Running it again replaces that directory wholesale. `day-recap uninstall`
removes only that copy. Run both in your own terminal, not in the agent chat.

```text
/day-recap
/day-recap yesterday
/day-recap 2026-10-05
```

The date is `today`, `yesterday`, or `YYYY-MM-DD`. With no date, the window
runs from local midnight to the moment you start.

The skill shows a draft and asks what you decided and what you rejected. The
note changes only after a separate yes. An empty day does not change the note.
With no Telegram session the other sources are still collected, and the block
contains the line «Telegram недоступен, чаты не учтены».

## Other commands

`collect` stores a raw dump. `show` prints the day status, or one source when
you name it. The source is optional: `git`, `transcripts`, `opencode`, or
`telegram`. Both take `--date` (`today`, `yesterday`, or `YYYY-MM-DD`) and
`--config PATH`.

`write` reads the block from stdin. It needs `--date YYYY-MM-DD` and
`--body -`, and takes `--config PATH`. Without `--apply` the note stays
unchanged.

```sh
day-recap collect --date yesterday
day-recap show git --date 2026-10-05
day-recap write --date 2026-10-05 --body - --apply
```

## Development

From a checkout of this repository:

```sh
uv tool install --editable .
just lint    # ruff
just fmt     # ruff format
just types   # mypy
just test    # pytest
```
