# Tasks

<!-- Each implementation group links to scenarios/dependencies and includes its own tests and docs.
     Every task states its completion evidence. Adapt numbering and scope; do not retain placeholder tasks.
     Each group heading ends with an execution hint: — <class>/<effort>, group <letter>; same letter = may run in parallel. -->

## 1. <!-- Task Group Name --> — <!-- class/effort -->, group A

- [ ] 1.1 <!-- Task description -->
- [ ] 1.2 <!-- Task description -->

## 2. <!-- Task Group Name --> — <!-- class/effort -->, group B

- [ ] 2.1 <!-- Task description -->
- [ ] 2.2 <!-- Task description -->

## 3. Integrated Wave Acceptance

<!-- Keep this group in the change that closes a wave; for multi-change waves, in one coordinator change, with the
     same acceptance report linked from every change. A single-capability change that closes no wave keeps only 3.1,
     3.3 when qa-plan has user-interaction cases, and 3.5 when the proposal flags notable risk — drop the rest,
     never tick a step that was not performed. Individual change completion does not close the wave. -->

- [ ] 3.1 Run integrated checks and independent code review; fix findings and record the verified revision.
- [ ] 3.2 Extend acceptance/qa-plan.md with regression cases from the actual diff, or keep its non-applicability line.
- [ ] 3.3 Execute required user interactions; save case results, build/plan revisions, evidence and defects.
- [ ] 3.4 Re-review code with the QA plan/report; fix findings and rerun affected checks until resolved.
- [ ] 3.5 Independently review specs, decisions, docs and next-wave prerequisites against the verified implementation.
- [ ] 3.6 Reconcile changes, repeat affected reviews/tests and link final evidence before closing the wave.

<!-- If user QA is not applicable, record the reason against its tasks; do not claim a test was executed.
     Missing tools, failures or unresolved findings block closure. With no next wave, reconcile final docs. -->

## Workflow Follow-up

- Archive only after the shared wave acceptance is complete; archive is not a pre-archive task.
