# AI Executor Protocol

STATUS: PROPOSTA / INITIAL DRAFT. Not adopted as project policy.

## 1. Purpose and applicability

Define a repeatable operating flow for executor agents before, during and after an authorized task. Adapt and approve this proposal before normative use. It complements AGENTS.md and does not replace human authorization, project-specific policies or tool/platform controls. No permission is granted by this document alone.

## 2. Task entry and preflight

Begin with authorized read-only inspection; before any mutation, verify:

- Exact workspace, repository identity, Git root and configured remote.
- Current branch and full HEAD against the authorized baseline.
- Working tree, staging and relevant untracked files; identify pre-existing work.
- PROJECT_STATE.md, relevant files, accepted decisions and applicable protocols.
- Objective, allowed files and actions, exclusions and acceptance criteria.
- Required evidence, validations and action-specific authorization.

Report the task, proposed files/actions, baseline, risks and validation plan. Do not treat an empty state field or an old approval as current permission.

Preflight result:

- READY: sufficient verified context and authorization for the stated next action only.
- BLOCKED: a critical prerequisite, consistent baseline or required permission is missing.

READY is not technical approval of an unimplemented change, production certification or permission for later Git/deployment actions. If blocked, report the discrepancy and request the missing information or decision. Do not silently switch checkout, reset, discard work, use a backup or rewrite records to hide a mismatch. Independently authorized read-only investigation may continue.

## 3. Risk classification

Classify the actual effect, not just the filename. The following are starting examples, subject to the adopting project's criteria:

| Level | Typical scope | Validation and review planning |
|---|---|---|
| Low | Ordinary text corrections, non-normative documentation, isolated tests without external effects | Focused checks and proportionate review |
| Medium | Bounded code changes, dependency adjustments or local refactoring | Relevant baseline/regression checks and independent review |
| High | Architecture, security, sensitive data, production or irreversible operations | Explicit risk assessment, required independent perspectives and human decisions |

Documentation that changes policy, tests that mutate services, dependency changes with security impact or broad refactoring can be high risk. Do not downgrade risk to avoid controls. If classification affects permission and remains unclear, stop the dependent action and ask for a decision. This proposal supplies no automatic review waiver or authorization.

## 4. Controlled execution

1. Establish the relevant baseline checks when required. If they fail, report the failure and stop dependent changes rather than claim a clean baseline.
2. Change only approved files and behavior. Preserve existing work, decisions, historical records and project-specific data. Use the smallest complete change that meets acceptance criteria.
3. If a new issue, architectural decision or broader fix is needed, report it without automatically expanding scope. A proposal is not an accepted decision.
4. Run meaningful, authorized checks appropriate to the risk. Do not run tests that mutate external services or incur costs without the corresponding permission. Report omitted checks and their limits.
5. Inspect the resulting diff and reconcile every changed file with the allowlist. Distinguish new work from pre-existing changes.
6. Record results and operational state only in the allowed scope. PROJECT_STATE.md is the proposed single operational state source; handoffs record the session historically. If either update is outside scope, report it as pending rather than edit silently.

Verification by the executor is evidence gathering, not independent approval of its own important change. Do not substitute the executor report for the required review.

## 5. Git flow and permission gates

Proposed normal flow:

```text
isolated branch
  -> scoped change
  -> validation
  -> authorized commit
  -> independent review
  -> authorized publication and PR
  -> review/checks on the exact published HEAD
  -> human-authorized merge
  -> verified integration
```

Review may start before commit, as described in AGENTS.md. Bind findings and approval to the examined HEAD or verified content hash; later changes require impact assessment and appropriate revalidation. Adapt review depth to risk under the adopted review protocol.

- Branch: verify it is the approved working branch; no direct integration-branch changes outside a specifically authorized exception.
- Commit: require explicit authorization; inspect staging before adding files and confirm the exact allowlist and diff before committing. Do not include secrets, temporary audit files or unrelated work.
- Publication/PR: require the relevant authorization; verify remote identity, baseline and commit content. Do not silently overwrite unexpected remote work or duplicate an existing PR.
- Merge: decision belongs to the responsible human. The executor may perform only an explicitly authorized merge of the specified version after required checks/reviews; no auto-merge or automatic acceptance is inferred.
- After integration: verify PR state, resulting main SHA and approved content. Sync, rollback, releases, tags and deployment are separate actions governed by their own authorized scope.

These are operational controls. Assess effective provider protections separately; this flow does not technically enforce them.

## 6. Failures and blockers

Use a specific result, for example:

- BLOCKED - required information absent.
- BLOCKED - workspace, baseline or documentary state diverges.
- BLOCKED - authorization for the next action absent.
- BLOCKED - required baseline/validation failed.

State what was observed, what remains unverified, which action stopped and what information or authorization would unblock it. Do not fabricate missing facts or infer a sensitive permission. Do not label owner reports as independently verified. Preserve partial work and evidence; do not apply a rollback or discard data without the applicable authorization and recovery assessment.

## 7. Executor handoff format

Each delivery should contain:

- Task, authorized scope and baseline/branch.
- Outcome: completed within scope, partial or blocked; no broader completion claim.
- Files/actions changed, including pre-existing work and exclusions.
- Commands and checks actually performed, exact results, warnings, failures and omissions.
- Evidence references and hashes where relevant; local tests distinct from CI on a named HEAD.
- Independent review status and the content/version reviewed, without inventing approvals.
- Final Git state: HEAD, staging, tracked changes and relevant untracked artifacts.
- Risks, outstanding work and state/handoff updates still pending.
- Recovery reference and its limits; a Git SHA is not verified backup/restore.
- Next action, prerequisites and authorization still needed.

Important evidence belongs in project records through an authorized versioning workflow. Local drafts and conversation reports must not be represented as already published. This initial proposal contains no completed project evidence, adopted policy or permission to begin a new milestone.
