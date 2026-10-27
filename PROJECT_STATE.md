# Project State

STATUS: PROPOSTA / UNINITIALIZED PROJECT TEMPLATE

Adoption-Status: NOT_ADOPTED
Initialization-Status: INITIALIZATION_REQUIRED
Execution-Authorization: NONE

## Identity - placeholders are not verified facts

- Project: <PROJECT_NAME>
- Workspace / Git root: <WORKSPACE> (NOT VERIFIED).
- Repository: <REPOSITORY>
- Work branch: <WORK_BRANCH>
- Integration branch: <DEFAULT_BRANCH>
- Human authority: <HUMAN_AUTHORITY>
- Last verification date/time/timezone: <DATE>
- Remote policy: <REMOTE_POLICY>
- Backup location: <BACKUP_LOCATION>

## Git snapshot

- Baseline commit: UNBORN
- Baseline field to establish after specific authorization: <BASELINE_COMMIT>
- Observed HEAD: NOT VERIFIED; read actual Git at session entry.
- Working tree: NOT VERIFIED.
- Staging: NOT VERIFIED.
- Remotes: NOT VERIFIED.
- Locks: NOT VERIFIED.

Do not replace UNBORN with an inferred or source-project commit. A recorded baseline is historical evidence, not the future HEAD of its containing document.

## Work and evidence

- Completed: NONE.
- In progress: NONE.
- Blocked: initialization, adoption decision and baseline are missing.
- Tests: NOT RUN.
- Reviews: NOT PERFORMED.
- Recovery / restore: NOT DEMONSTRATED.
- Backup: NOT VERIFIED.
- Adoption evidence: NONE.

## Next authorized action

NONE. Copying this template grants no task scope. Request a human decision specifying identity, destination, initialization edits, evidence, profile and acceptance criteria. Adoption and execution permissions are separate; no automatic staging/commit is implied.

## Authorized initialization notes

After verifying the actual root under explicit permission, populate this snapshot and configuration with real values and references. The operational identity parser expects exactly one '- Project: <actual name>' and one '- Workspace / Git root: <actual authorized absolute root> (verified).' line. Only after an evidenced human adoption decision may Adoption-Status become ADOPTED and Initialization-Status become INITIALIZED. Those strings are consistency checks, not authentication. Regenerate/reconcile the operational manifest within an authorized scope after relevant edits. Until required fields, actual Git and evidence agree, dependent operational automation remains BLOCKED.

Historical handoffs and decision records link here rather than maintaining a second current state. Update this snapshot only within the allowed scope and reconfirm reality before execution.
