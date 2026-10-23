# Происхождение адаптированных методов

Источник — авторская коллекция пользователя `specialist-profiles`, изученная 9 октября 2026 года.
Ниже пути относительно её корня; коллекция не является обязательной runtime-зависимостью Spydell.
Полезные методы адаптированы внутри семейства; исходные ролевые prompts и схемы установки не импортируются.
При повторном исследовании найди указанный пользователем checkout, а не предполагай фиксированный абсолютный путь.

## Концепция, аспекты, требования

- `business-analyst/subagent/skills/business-problem-framing/SKILL.md`:
  симптом, гипотеза причины, потребность, результат и решение.
- `business-analyst/subagent/skills/stakeholder-analysis/SKILL.md`:
  затронутые люди, знания, полномочия решения и пропущенные точки зрения.
- `business-analyst/subagent/skills/user-story-and-use-case-modeling/SKILL.md`:
  актор, триггер, основной/альтернативный путь, исключения и постусловия.
- `shared-skills/shared-requirements-analysis/SKILL.md`, `shared-business-rules/SKILL.md` в том же каталоге skills:
  классификация кандидатов, нормализация, правила, контрпримеры и конфликты.
- `shared-skills/shared-facilitation/SKILL.md`:
  вопрос решения, исходный материал, запись результата и следующий адресат.
- `system-analyst/subagent/skills/non-functional-requirements/SKILL.md`:
  область качественного требования, условия, наблюдение и непроверяемое обязательство как открытый риск.

## Roadmap и готовность

- `product-manager/subagent/skills/roadmap-management/SKILL.md` и `prioritization-and-tradeoffs/SKILL.md`:
  ценность, основания выбора, горизонт и trade-offs; пути второго файла относительны тому же каталогу skills.
- `product-owner/subagent/skills/scope-and-mvp-management/SKILL.md` и `backlog-refinement/SKILL.md`:
  границы, отложенное, срезы и готовность; второй файл находится в том же каталоге skills.
- `project-manager/subagent/skills/dependency-management/SKILL.md`, `project-planning/SKILL.md`:
  результат зависимости, владелец, доказательство, реальный ресурс и подтверждённый срок.
- `system-architect/subagent/skills/target-and-transition-architecture/SKILL.md`:
  baseline, target, промежуточные состояния, критерии выхода и обратимость.

## Review, QA и документы

- `shared-skills/shared-quality-gates-review/SKILL.md`, `shared-impact-analysis/SKILL.md`,
  `shared-documentation-management/SKILL.md`, `shared-acceptance-criteria/SKILL.md`:
  готовность для следующего шага, следствия изменения, актуальность источников и разные виды приёмки.
  Сокращённые пути здесь относительны `shared-skills/`.
- `system-analyst/subagent/skills/functional-specification/SKILL.md`:
  сценарии, валидации, состояния, права, данные и граничные случаи после продуктового прояснения.
- `ui-ux-designer/subagent/skills/interaction-states-and-edge-cases/SKILL.md`:
  триггер, видимый результат, действие и восстановление.
- `ui-ux-designer/subagent/skills/forms-and-complex-workflows/SKILL.md`, `usability-review/SKILL.md`:
  границы многошагового пути, валидация и разделение наблюдаемого препятствия и гипотезы.
  Второй файл находится в том же каталоге skills.
- `ui-ux-designer/subagent/skills/accessibility-and-inclusive-design/SKILL.md`:
  клавиатурный путь, фокус, подписи и ошибки; checklist не сертифицирует соответствие стандарту.
- `system-architect/subagent/skills/architecture-review-and-governance/SKILL.md`:
  значимые отклонения, условия пересмотра и проверка соответствия принятому решению.

## Оценка и системные ограничения

- `product-analyst/subagent/skills/product-hypothesis-analysis/SKILL.md`, `analytics-methodology/SKILL.md`:
  решение, метод, достаточное свидетельство и исход «неопределённо».
- `product-analyst/subagent/skills/product-metrics/SKILL.md`, `data-quality-and-tracking/SKILL.md`:
  смысл метрики, знаменатель, сегмент, момент события, идентичность, дедупликация и сопоставимость.
- `system-architect/subagent/skills/non-functional-architecture/SKILL.md`:
  качество конкретного потока, условия нагрузки/отказа, компромисс и проверка.
Сокращённые пути второй части пунктов относительны тому же каталогу skills.

## Что добавлено под процесс Spydell

Полный wave loop, проверяемые ревизии, findings с устойчивыми ID и перепроверка следующих волн по фактической реализации
задаются требованиями пользователя. Исходные навыки дают методы, но не готовую реализацию этого протокола.
Фронтир grilling и карта решений остаются у Matt; CLI lifecycle — у OpenSpec.
Исходные Role Modes преобразованы в уровни/области проверки без отдельной оргструктуры агентов.
Ссылки Sources исходных навыков не означают, что внешние публикации повторно проверены в этом локальном исследовании.
