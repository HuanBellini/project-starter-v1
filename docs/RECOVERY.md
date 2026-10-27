# Recovery and Safe Resumption

STATUS: PROPOSTA / INITIAL DRAFT. Not adopted as project policy.

## 1. Purpose and limits

Propose safe context resumption, Git investigation and separately authorized data recovery. Adapt and approve this procedure before normative use. It does not guarantee recoverability, authorize access to backups or grant permission to change project state.

Never assume that an old document, conversation, local remote-tracking ref or discovered copy represents the current accepted state. Verify the relevant files, Git facts, evidence and permissions before dependent actions. Do not invent missing content or declare recovery from an untested assumption.

## 2. Three different activities

| Activity | Goal | Limit |
|---|---|---|
| Context resumption | Understand the project and the next permitted action | Does not restore lost files or authorize implementation |
| Git investigation/recovery | Identify branches, commits and differences; propose an approved source recovery if needed | Reading history is different from changing refs or files; Git does not preserve all untracked data or external systems |
| Backup/restore | Validate a recovery copy and restore explicitly scoped data | Finding a copy is not proof it is complete, compatible or restorable |

Completing one activity does not prove success of the other two.

## 3. Context resumption

1. Establish the exact authorized workspace and repository identity before using their contents. Do not search unrelated directories, audit copies or backups without permission.
2. Read the adopting project's AGENTS.md, [PROJECT_STATE.md](../PROJECT_STATE.md), applicable protocols, decisions and latest relevant handoff. Historical handoffs explain prior work; PROJECT_STATE.md provides the proposed operational snapshot.
3. Verify the actual Git root, configured remote, branch, full HEAD, working tree, staging and relevant untracked artifacts. Compare expected and observed values; a local tracking ref does not prove server state.
4. Identify completed, in-progress and blocked work with its evidence, scope and verification date. Check what remains unverified and which permissions apply now.
5. Report the reconstructed context and next permitted action. Missing critical fields or inconsistent evidence block the dependent action, even if other checks passed.

Do not infer permission to edit, commit, publish or merge from merely recovering context. Read-only investigation may continue only within its authorized scope.

## 4. Git investigation versus mutation

Examples below classify operations; they are not commands to run automatically.

| Read-only local investigation | State-changing operation requiring specific authorization |
|---|---|
| Inspect status, log, diff, commit objects and local branch/ref lists | Switch/create branches or worktrees; checkout/restore files |
| Compare recorded commits and inspect tracked file history | Reset, revert, cherry-pick, rebase, merge or ref updates |
| Inspect configured remote and local tracking refs | Fetch/pull updating local metadata; push or remote changes |

Network queries need the applicable network/access scope even when they do not mutate the server. Some Git commands have both read and write modes; classify the intended effect, not the command name alone. Never treat permission to inspect history as permission to execute a recovery command.

Before an authorized source recovery, verify the selected commit/branch, affected paths, working tree and staging, potential overwrite/loss and recovery evidence for existing unique data. Preserve pre-existing work. Do not automatically choose a newer branch, switch to an audit checkout, reset to a convenient commit or discard uncommitted files to resolve a mismatch.

Report a proposed recovery plan and its limits when mutation is needed. A commit existing locally is not proof that it is approved, published or includes lost untracked files. Reverting source does not necessarily reverse external side effects.

## 5. Backup validation and restore

Inspect only explicitly authorized backup locations and artifacts. Do not presume a reported backup still exists, that a deleted copy can be recovered or that permission to resume a project authorizes recreating a backup.

Before calling a copy suitable for recovery, assess and record:

- Origin, creator/source and custody evidence.
- Creation date, intended recovery point and subsequent changes.
- Integrity checks and the trusted reference used for comparison.
- Content inventory, completeness and required dependent data/configuration.
- Compatibility with the target environment, versions and data format.
- Restore evidence or an explicitly authorized isolated restore test, with result and limits.

A matching hash establishes content correspondence with its reference, not trusted origin, completeness or restore capability. A Git reference is not a backup of untracked files, databases, credentials or external services. Record owner reports separately from independent verification; expose no secrets in logs or reports.

Restore is a state-changing operation. Require explicit authorization for source, destination, affected data and permitted method. Assess overwrite risks, protect existing unique data and define rollback/containment limits before execution. Do not restore over the execution workspace or production simply to test whether a copy works. If testing or protection requires additional access, data copies or costs, obtain that specific authorization first.

After an authorized restore, validate the recovered content and relevant behavior against the stated criteria. Report partial recovery, omissions and unverified areas; do not claim full recovery from file presence alone.

## 6. Blockers and reporting

Examples:

- BLOCKED - required evidence or information absent.
- BLOCKED - workspace, Git baseline or documents diverge.
- BLOCKED - access or mutation authorization absent.
- BLOCKED - recovery not demonstrated.

State the observed facts, owner-reported claims, unknowns, stopped action and what evidence or decision would unblock it. Do not reconstruct missing authoritative records from guesses, silently overwrite conflicts or label an untested restore successful. Preserve available evidence and report the smallest next authorized investigation step.

## 7. Handoff after investigation or authorized recovery

Record the activity actually performed, examined workspace/repository and version, commands/checks, evidence, mutations if any, final Git/data state, limitations, remaining risks and next permitted action. Update PROJECT_STATE.md and the historical handoff only within the authorized file scope; otherwise report those updates as pending.

No real backup, path, supplier, restore result, certification or project authorization is supplied by this reusable proposal.
