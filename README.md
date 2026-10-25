# Spydell

Семейство навыков для ведения инициативы от замысла к реализации:
представление → прояснение аспектов → требования → roadmap → specs → design → задачи.
Существенные вопросы текущего уровня проясняются через grilling. После реализации каждой волны:
тесты → независимое code review и исправления → пользовательский QA → повторное code review →
сверка specs, решений, документов и следующей волны с фактической реализацией.

Spydell встраивается в [OpenSpec](https://github.com/Fission-AI/OpenSpec): своя схема `spydell`
(proposal → specs → design → tasks) и правила проектного `openspec/config.yaml`.
Прояснение, карта решений и review опираются на навыки [Matt Pocock](https://github.com/mattpocock/skills):
`grilling`, `wayfinder`, `research`, `domain-modeling`, `code-review` и др.

## Установка

Claude Code:

```bash
claude plugin marketplace add sv-kozlov/spydell
claude plugin install spydell@spydell
```

Codex:

```bash
codex plugin marketplace add sv-kozlov/spydell
codex plugin add spydell@spydell
```

Зависимости (навыки Matt, OpenSpec CLI и схема в проекте), обновление и установка без плагинов —
в [INSTALL.md](INSTALL.md).

## Состав

| Путь | Содержание |
| --- | --- |
| `skills/` | spydell, roadmap, spec-review, critic, evaluator, systems, ai-agents, triz — с references и metadata |
| `openspec/` | Схема `spydell` и образец проектной конфигурации |
| `.claude-plugin/`, `.codex-plugin/` | Манифесты плагина и marketplace для Claude Code и Codex |
| `install.py` | Подключение схемы к проекту OpenSpec; установка навыков без плагинов |
| `docs/` | Чем схема отличается от `spec-driven`, завершение волны, границы автоматизации |
| `licenses/` | Лицензия OpenSpec для производной схемы и шаблонов |
| `tests/` | Изолированные проверки установщика |

## Работа после установки

Начать с идеи: «Используй spydell: разверни идею в концепцию, затем обсудим открытые аспекты».
Продолжить планирование: «Используй spydell-roadmap для согласованных требований».
Проверить срез: «Используй spydell-spec-review; проверь готовность к следующему шагу».
Снять противоречие: «Используй spydell-triz: улучшаем X — ухудшается Y, компромисс не устраивает».

Срез OpenSpec создаётся в настроенном проекте:

```bash
openspec new change <change-name> --schema spydell
```

Default существующего проекта сохраняется. Завершение файла не равно успешной приёмке волны.
Независимый reviewer и реальные UI-действия требуют соответствующих возможностей агента/окружения.

Подробности настройки OpenSpec: [docs/spydell-openspec-setup.md](docs/spydell-openspec-setup.md).
Происхождение заимствований: [NOTICE.md](NOTICE.md).
