# Данные дашборда: формат `spydell-dashboard`, версия 1

`scripts/dashboard.py` пишет `dashboard.json` и встраивает тот же объект в `dashboard.html`. Страница только рисует
готовые поля; всё вычисляемое — статусы, этапы, проценты, счётчики — считает скрипт. Новое поле добавляется без смены
версии; переименование или изменение смысла поля повышает `version`.

## Источник: roadmap

Срезы читаются из таблицы раздела `## Срезы` в `roadmap.md`; карточки `### <ID> — название` дают описание и поля,
которых нет в таблице. Без таблицы работает разбор карточек (строки `Предшественник:`, `Состояние:`, `Волна:`,
`Change:`), а волна берётся из ID вида `W3`.

| ID | Срез | Волна | Состояние | Предшественники | Change | Репозиторий |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | Модель счёта | 1 | ready-for-build | — | `pay-w1` | `backend` |

## Верхний уровень

| Поле | Значение |
| --- | --- |
| `format`, `version` | `"spydell-dashboard"`, `1` |
| `generated` | Время сборки, ISO 8601 с часовым поясом |
| `initiative`, `set` | Заголовок карты; путь комплекта |
| `summary` | `state`, `next`, `verdict`, `contract` — тексты разделов карты (markdown) |
| `kpis` | `slices`, `accepted`, `wavesTotal`, `wavesDone`, `tasksTotal`, `tasksComplete`, `tasksPct`, `frontier`, `decisions`, `issues`; отменённые срезы в задачи не входят |
| `statusCounts` | Число срезов по статусам |
| `waves` | Слои по порядку: `id`, `title`, `status` (`done`, `active`, `upcoming`), `slices` (ID), `closed`, `total`, `progressPct`, `counts` |
| `slices` | Срезы, поля ниже |
| `frontier`, `recentDecisions` | `{code, text}` — открытые вопросы и последние решения карты |
| `team`, `sessions`, `runLog` | Строки таблиц карты и журнала прогона, ключи — заголовки столбцов в нижнем регистре |
| `issues` | Замечания `check.py` по карте и roadmap: `{code, message, location}` |
| `openspec` | `roots`, `cli` — где искались changes и вызывался ли CLI |

## Срез

| Поле | Значение |
| --- | --- |
| `id`, `title`, `wave`, `repo` | Из roadmap; волна без значения — `"—"` |
| `status` | `planned`, `candidate`, `needs-decision`, `ready-for-spec`, `specifying`, `ready-for-build`, `in-progress`, `implemented`, `accepted`, `archived`, `dropped` |
| `stage` | Этап 0–5: план, спека, задачи, код, приёмка, архив; `-1` — отменён |
| `planState` | Состояние из roadmap как записано |
| `deps`, `dependents` | ID предшественников и зависящих срезов |
| `openDecisions` | Коды открытых решений карты, упомянутые у среза |
| `summary` | Описание из карточки roadmap |
| `tasks` | `{total, complete, pct}` или `null` |
| `gates` | `proposal`, `specs`, `qaPlan`, `design`, `tasks`: `done`, `ready`, `blocked`, `missing` или `""` |
| `acceptance` | `ok`, `issues` или `none` |
| `qa` | `{passed, failed, blocked}` или `null` |
| `change` | `{name, found, archived, path, acceptanceIssues}` или `null` |
