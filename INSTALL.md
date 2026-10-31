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
Ставьте навыки Matt один раз на уровне пользователя. `npx skills add` внутри репозитория создаёт
копии и `skills-lock.json`, которые расходятся с плагином и перекрывают его.
`research` и `code-review` требуют поддержки subagents и соответствующих инструментов.

`wayfinder`, `to-spec`, `to-tickets`, `grill-me`, `handoff` и ряд других помечены
`disable-model-invocation`: агент не может вызвать их сам. Когда процессу нужен Wayfinder,
Spydell готовит передачу и просит пользователя запустить `/wayfinder` (Claude Code)
или `$wayfinder` (Codex). `grilling`, `research`, `domain-modeling`, `prototype` и `code-review`
агент вызывает сам.
Затем выполните `setup-matt-pocock-skills` в проекте для выбора tracker и размещения документов;
при использовании Spydell согласуйте его с существующими каноническими документами, не создавайте дубли.
Matt обновляется отдельно; после обновления сверяйте границы grilling, хранения решений и review.

## 3. OpenSpec CLI

Нужен Node.js с npm. Схема проверена с Node.js 26.7.0 и OpenSpec 1.16.0 (ранее — 1.14.3):

```bash
npm install -g @fission-ai/openspec@1.16.0
```

Можно выбрать более новую версию, но сначала проверьте совместимость схемы (раздел 6).

Spydell использует также навыки `new`, `continue`, `ff` и `verify` — в профиле по умолчанию `core`
их нет. Включите их в глобальном конфиге OpenSpec (пресета `expanded` нет):

```bash
openspec config set profile custom
```
```bash
openspec config set workflows '["propose","explore","new","continue","apply","update","ff","sync","archive","verify"]'
```

То же интерактивно: `openspec config profile` без аргумента. Конфиг задаёт набор навыков,
а сами файлы появляются при следующей генерации (`openspec init`/`openspec update` или способ из раздела 4).

## 4. Подключить Spydell к проекту

### Навыки OpenSpec — в одном месте

`openspec init` по умолчанию кладёт копии навыков OpenSpec в каталоги инструментов проекта
(`.claude/`, `.agents/`). Держите их в одном месте и не смешивайте варианты:
локальная копия перекрывает общую и молча расходится с ней.

- **В каждом проекте** — штатный способ OpenSpec: `openspec init --tools <агенты>`,
  после обновления CLI — `openspec update` в каждом проекте. Выбор tools смотрите в `openspec init --help`.
- **Один раз на уровне пользователя** — удобно, когда проектов несколько. Проект создаётся без копий:

  ```bash
  cd /path/to/project
  openspec init --tools none
  ```

  Навыки генерируются во временном каталоге и копируются в каталоги пользователя;
  повторите после обновления CLI:

  ```bash
  tmp="$(mktemp -d)" && (cd "$tmp" && openspec init --tools claude,codex --force)
  ```
  ```bash
  rm -rf ~/.claude/skills/openspec-* ~/.claude/commands/opsx ~/.agents/skills/openspec-*
  mkdir -p ~/.claude/skills ~/.claude/commands ~/.agents/skills
  cp -R "$tmp"/.claude/skills/openspec-* ~/.claude/skills/
  cp -R "$tmp"/.claude/commands/opsx ~/.claude/commands/
  cp -R "$tmp"/.agents/skills/openspec-* ~/.agents/skills/
  ```

  Удаление прежних `openspec-*` нужно, чтобы не остался навык, исчезнувший из новой версии.
  Варианты для Claude и Codex отличаются только подсказками вызова следующего шага.

### Схема и config

Из клона Spydell (нужен Python 3.10+ и PyYAML):

```bash
gh repo clone sv-kozlov/spydell
cd spydell
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Схему держите тоже в одном месте — выберите вариант.

**Один раз на уровне пользователя** (удобно для нескольких проектов на одной машине):
схема ставится в каталог схем пользователя OpenSpec (`$XDG_DATA_HOME/openspec/schemas`,
по умолчанию `~/.local/share/openspec/schemas`, в Windows — `%LOCALAPPDATA%\openspec\schemas`),
а в проект пишется только config:

```bash
.venv/bin/python install.py --user-schema --project "/path/to/project" --project-only --dry-run
.venv/bin/python install.py --user-schema --project "/path/to/project" --project-only
```

Для следующих проектов схема уже стоит; повторный запуск только объединяет их config.
Если в проекте осталась копия `openspec/schemas/spydell`, она перекрывает общую — удалите её.
Разработчик Spydell может вместо копии сослаться на клон, чтобы правки действовали сразу;
установщик такую ссылку не трогает:

```bash
ln -s "$PWD/openspec/schemas/spydell" ~/.local/share/openspec/schemas/spydell
```

**В каждом проекте** (когда репозиторий должен быть самодостаточным — команда, CI):

```bash
.venv/bin/python install.py --project "/path/to/project" --project-only --dry-run
.venv/bin/python install.py --project "/path/to/project" --project-only
```

В Windows используйте `.venv\Scripts\python.exe`.
Установщик ставит `openspec/schemas/spydell` (в проект или на уровень пользователя)
и добавляет context/rules/operations в config проекта.
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

`schema which` показывает источник: `user` или `project`.
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

Схему обновляет повторный запуск `install.py` из свежего клона с тем же вариантом размещения;
схема-ссылка на клон обновляется вместе с ним. Совпадающие файлы пропускаются.
Context, rules и guidance объединяются по точному совпадению строк. Переформулированные Spydell правила
установщик вытесняет сам: замещённая запись удаляется из проектного config и выводится строкой
`Superseded entry removed from ...`. Правила самого проекта не затрагиваются.
Если skill или schema отличается, сначала выполните dry-run, а для сознательной замены укажите `--replace`:

```bash
.venv/bin/python install.py --user-schema --project-only --replace
```
```bash
.venv/bin/python install.py --project "/path/to/project" --project-only --replace
```

После обновления OpenSpec CLI перегенерируйте его навыки тем же способом, каким они ставились (раздел 4).

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
