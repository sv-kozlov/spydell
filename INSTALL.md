# Установка

Репозиторий приватный: для установки нужен доступ к `sv-kozlov/spydell` через git
(`gh auth login` или SSH-ключ GitHub).

## 1. Навыки Spydell

### Claude Code

```bash
claude plugin marketplace add sv-kozlov/spydell
claude plugin install spydell@spydell
```

То же внутри сессии: `/plugin marketplace add sv-kozlov/spydell`, затем `/plugin install spydell@spydell`.
Для одного проекта добавьте `--scope project`. Навыки доступны как `spydell:spydell`,
`spydell:spydell-roadmap` и т. д.

### Codex

```bash
codex plugin marketplace add sv-kozlov/spydell
codex plugin add spydell@spydell
```

### Другие агенты

Через [skills CLI](https://github.com/vercel-labs/skills); `-a` выбирает агента:

```bash
npx skills@latest add sv-kozlov/spydell -g -a codex
```

Или из клона репозитория: `python3 install.py` копирует восемь навыков в `$CODEX_HOME/skills`
(по умолчанию `~/.codex/skills`); другой каталог — `--skills-dir "/path/to/agent/skills"`.

Устанавливайте навыки одним способом. Если раньше они копировались вручную
(например, в `~/.codex/skills/spydell*`), удалите старые копии, чтобы одноимённые навыки не загружались дважды.
Если текущая сессия не видит новые навыки, откройте новую.

## 2. Навыки Matt Pocock

Spydell использует `grilling`, `grill-me`, `wayfinder`, `research`, `handoff`, `domain-modeling`,
`prototype` и `code-review`. Они ставятся из marketplace Matt:

```bash
claude plugin marketplace add mattpocock/skills
claude plugin install mattpocock-skills@mattpocock
```

```bash
codex plugin marketplace add mattpocock/skills
codex plugin add mattpocock-skills@mattpocock
```

Для других агентов: `npx skills@latest add mattpocock/skills -g -a <agent>`.
`research` и `code-review` требуют поддержки subagents и соответствующих инструментов.
Затем выполните `setup-matt-pocock-skills` в проекте для выбора tracker и размещения документов;
при использовании Spydell согласуйте его с существующими каноническими документами, не создавайте дубли.
Matt обновляется отдельно; после обновления сверяйте границы grilling, хранения решений и review.

## 3. OpenSpec CLI

Нужен Node.js с npm. Схема проверена с Node.js 26.7.0 и OpenSpec 1.14.3:

```bash
npm install -g @fission-ai/openspec@1.14.3
```

Можно выбрать более новую версию, но сначала проверьте совместимость схемы (раздел 6).

## 4. Подключить Spydell к проекту

В новом проекте сначала создайте интеграцию OpenSpec; в уже настроенном — `openspec update`:

```bash
cd /path/to/project
openspec init --tools codex
```

Выбор tools зависит от агента; смотрите `openspec init --help`.
Затем из клона Spydell (нужен Python 3.10+ и PyYAML):

```bash
gh repo clone sv-kozlov/spydell
cd spydell
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python install.py --project "/path/to/project" --project-only --dry-run
.venv/bin/python install.py --project "/path/to/project" --project-only
```

В Windows используйте `.venv\Scripts\python.exe`.
Установщик копирует `openspec/schemas/spydell` и добавляет context/rules/operations в config.
Существующие schema, store, references, дополнительные ключи и правила сохраняются.
Контекст Spydell добавляется к имеющемуся, повторная установка не дублирует его и списки правил.
Это структурное объединение, а не смысловой арбитраж: противоречащие пользовательские правила нужно согласовать.
При записи YAML комментарии и форматирование нормализуются; исходный config сохраняется в backup.
Существующий `config.yml` поддерживается; при наличии одновременно `.yaml` и `.yml` установка останавливается.
Содержимое `openspec/specs` и `openspec/changes` не изменяется.

Проверьте из корня проекта:

```bash
openspec schema validate spydell --json
openspec schema which spydell --json
openspec new change <change-name> --schema spydell
```

Последняя команда создаёт реальный change: выполните её только для выбранной инициативы.
Схема не назначается default автоматически; используйте явный `--schema spydell`.

## 5. Обновить

```bash
claude plugin marketplace update spydell
claude plugin update spydell@spydell
```

```bash
codex plugin marketplace upgrade spydell
```
```bash
codex plugin add spydell@spydell
```

После обновления откройте новую сессию агента.

Схему в проекте обновляет повторный запуск `install.py` из свежего клона. Совпадающие файлы пропускаются.
Context, rules и guidance объединяются по точному совпадению строк. Переформулированные Spydell правила
установщик вытесняет сам: замещённая запись удаляется из проектного config и выводится строкой
`Superseded entry removed from ...`. Правила самого проекта не затрагиваются.
Если skill или schema отличается, сначала выполните dry-run, а для сознательной замены укажите `--replace`:

```bash
.venv/bin/python install.py --project "/path/to/project" --project-only --replace
```

Перезаписываются только выбранные каталоги и config. Все существовавшие изменяемые targets сохраняются
в `~/.spydell-backups/<id>/`; путь выводится после установки. Можно задать `--backup-dir`.
Резервные копии должны находиться вне каталогов обнаружения skills.
`restore-map.json` содержит исходные пути и соответствующие backup-файлы/каталоги.
Для отката закройте использующие их процессы и скопируйте нужный backup на указанный target;
у записей с `backup: null` прежнего файла не было. Не удаляйте более поздние правки без сравнения.
Если запись завершается ошибкой, установщик пытается восстановить уже затронутые targets автоматически.

Установщик не запускает npm, git, OpenSpec или публикацию. Git commit не создаётся.
После подключения закоммитьте проектные schema/config обычным процессом вашего репозитория.

## 6. Проверить изменения Spydell

```bash
.venv/bin/python -m unittest discover -s tests -v
claude plugin validate .
```

Проверки установщика используют временные каталоги и не трогают настоящие глобальные skills.
После обновления OpenSpec сравните `openspec/schemas/spydell` с новой upstream-схемой `spec-driven`
пакета `@fission-ai/openspec`, прежде чем менять проектную схему.
