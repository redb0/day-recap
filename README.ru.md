# day-recap

[English](README.md)

[![tests](https://github.com/redb0/day-recap/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/redb0/day-recap/actions/workflows/test.yaml)
[![coverage](https://codecov.io/gh/redb0/day-recap/branch/main/graph/badge.svg)](https://codecov.io/gh/redb0/day-recap)
![python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

Собирает проделанное за день из локальных репозиториев git, транскриптов
Cursor, сессий OpenCode и белого списка Telegram. В ежедневную заметку
Obsidian попадает только подтверждённый блок.

Дамп лежит вне хранилища. Пустой день заметку не меняет.

```markdown
## 🤖 Итоги дня

### Сделано
- **billing** — сузил окно повторной оплаты до одного счёта

### Решения и обоснования
Оставили повтор по idempotency-key. Повтор всей корзины отбросили: он списывал деньги второй раз.
```

## Установка и конфигурация

```sh
uv tool install day-recap
```

`day-recap init` запускайте в своём терминале, не в чате агента. Команда
спрашивает секреты Telegram, каталог заметок, шаблон, один корень обхода и
белый список. `api_id` и `api_hash` в чат не вводите. Если
`~/.config/day-recap/config.toml` ещё нет, `init` копирует пример из пакета
и записывает ответы поверх. Уже существующий файл целиком не заменяется.
`init` спрашивает `qr` или `code`. `qr` печатает код для сканирования:
Настройки → Устройства → Подключить устройство. `code` ждёт код из чата
«Telegram» на уже открытом аккаунте. `--login qr` или `--login code`
пропускают вопрос. `--relogin` входит заново и сам toml не переписывает.
После входа `init` показывает ту же нумерованную таблицу, что `day-recap chats`,
и записывает выбранные номера. Пустой белый список спрашивается сразу, непустой
меняется только после согласия.

`day-recap chats` печатает таблицу и готовые блоки `[[telegram.chats]]` и
не меняет конфиг. В дамп читаются только чаты из белого списка.

| Секция | Что задаёт |
| --- | --- |
| `[notes]` | Куда писать ежедневную заметку. |
| `[state]` | Где лежат дампы. |
| `[git]` | Какие каталоги обходить и чьи коммиты брать. |
| `[transcripts]` | Корни JSONL Cursor и обрезка реплик. |
| `[opencode]` | База OpenCode и та же обрезка. |
| `[telegram]` | Включён ли источник и белый список. |
| `[summary]` | Порог. |

Ключи и значения по умолчанию лежат в пакете: `app/config.example.toml`.

- Порог — 100000 байт.
- Дамп хранится 14 дней.
- `~/.config/day-recap/.env` создаётся с правами 600.

## В агенте

`day-recap install` ставит скилл в `~/.agents/skills/day-recap/SKILL.md`.
Повторный запуск заменяет этот каталог целиком. `day-recap uninstall` удаляет
только его. Обе команды запускайте в своём терминале, не в чате агента.

```text
/day-recap
/day-recap yesterday
/day-recap 2026-10-05
```

Дата — `today`, `yesterday` или `YYYY-MM-DD`. Без даты окно идёт с локальной
полуночи до момента запуска.

Скилл показывает черновик и спрашивает, что решили и что отбросили. Заметка
меняется только после отдельного согласия. Пустой день заметку не меняет.
Если сессии Telegram нет, остальные источники всё равно собираются, а в блоке
есть строка «Telegram недоступен, чаты не учтены».

## Дополнительные команды

`collect` сохраняет дамп. `show` печатает сводку, а с именем источника — его
тело. Источник необязателен: `git`, `transcripts`, `opencode` или `telegram`.
Обе команды принимают `--date` (`today`, `yesterday` или `YYYY-MM-DD`) и
`--config PATH`.

`write` читает блок из stdin. Ей нужны `--date YYYY-MM-DD` и `--body -`,
принимает `--config PATH`. Без `--apply` заметка не меняется.

```sh
day-recap collect --date yesterday
day-recap show git --date 2026-10-05
day-recap write --date 2026-10-05 --body - --apply
```

## Разработка

Из каталога этого репозитория:

```sh
uv tool install --editable .
just lint    # ruff
just fmt     # ruff format
just types   # mypy
just test    # pytest
```
