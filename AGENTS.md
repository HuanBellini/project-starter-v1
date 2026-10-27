# AGENTS.md - Safe Agent Entry

STATUS: PROPOSTA / INITIAL DRAFT. Not adopted as project policy.

## 1. Purpose and adoption

This proposed document defines operational guidance for agents entering a project. It must be adapted, reviewed and approved by the responsible human before normative use. Its presence does not replace human authorization, applicable project policies or tool/platform access controls. It does not amend the host project's existing protocols.

## 2. Context and sources of truth

Use the authorized project files, documented decisions and actual Git state to reconstruct context. Do not assume that remembered conversations, another agent's claims or an old report are current project evidence. A current human instruction defines task authorization; record important decisions durably through the authorized workflow.

For the adopting project, read this file, PROJECT_STATE.md, applicable execution/review protocols and decisions before mutations. Read architecture, handoffs and recovery documentation when relevant. PROJECT_STATE.md is the proposed single operational state source; historical documents do not override it. Verify its recorded facts against the actual environment. Placeholders, missing permissions and stale evidence are not approval.

## 3. Safe entry before any change

Check and report:

1. Exact authorized workspace. Identify execution checkouts separately from audit copies, backups and external artifacts; do not inspect those locations without authorization.
2. Repository identity, Git root and configured remote. Do not assume the current terminal directory is the correct checkout. A remote URL alone does not prove access or the remote state.
3. Current branch and full HEAD, compared with the authorized baseline.
4. Working tree, staging and relevant untracked files. Preserve existing work; distinguish pre-existing changes from the proposed task.
5. Authorized objective, allowed files/actions, exclusions and acceptance criteria.
6. Required evidence, validation method and applicable permissions before proceeding.

Read-only local inspection is separate from editing or network access. Do not infer remote-operation permission from permission to inspect local Git.

If workspace, baseline, documents or permissions conflict, or critical information is missing: STOP the dependent action, report the discrepancy and request the missing decision. Do not silently switch branches, reset, discard changes, move files, recreate backups or rewrite documentation to make the discrepancy disappear. Independent, authorized read-only investigation may continue.

## 4. Roles and authority

### Executor

Implement only authorized changes, run appropriate authorized validations and report evidence and limits. Create commits, publish branches or execute a merge only when that specific action is explicitly authorized. The executor does not decide scope expansions, grant itself exceptions or approve its own important changes as the sole reviewer. Merge decision authority remains human; technical execution of an authorized merge does not transfer that authority.

### Independent reviewer

Examine the actual change and relevant criteria, run authorized checks and attempt negative cases without substituting the executor's report for evidence. Record perspective, reviewed HEAD or content hash, findings and limitations. Do not repair findings without a separately authorized execution scope, and do not approve changes you implemented as an independent reviewer. Review requirements should be proportionate to risk under the adopted review protocol.

### Responsible human

Decide scope changes, exceptions, irreversible actions and final merge authorization. Technical reviewer approval and CI success do not replace that decision. Authorizations remain bound to their stated action, scope and version; permission to edit is not permission to commit, push, deploy or merge.

## 5. Git workflow and change limits

Use an isolated working branch for changes; do not edit, commit or push directly to main or the designated integration branch outside a specifically authorized exception. Do not infer such an exception from ordinary task approval or merge authorization.

Proposed normal flow: isolated branch -> scoped change and validation -> reviewed, authorized commit -> authorized publication and PR -> review/checks on the exact published HEAD -> explicit human merge authorization -> verified integration. Review may begin before commit, but evidence must remain bound to the version actually integrated.

Before an authorized commit, verify the branch, staging contents and exact file allowlist. Before publication or merge, verify the relevant remote state and reviewed version; stop on unexpected divergence. Do not force push, rewrite history, discard work or delete unique data without specific authorization and the required recovery evidence. Never include secrets or temporary/private artifacts merely because they are present in the workspace.

After authorized work, report actual files/actions, tests and omissions, Git state, remaining risks and the next permitted step. Update operational state and handoff through the allowed file scope; if those updates are outside scope, report them as pending rather than editing silently. A Git recovery reference is not proof of a recoverable backup.

## 6. Operational rules versus technical protection

These are proposed operational controls, not technical enforcement. Provider branch protections, required reviews/checks, permissions and effective bypass settings must be evaluated separately. Do not claim that main is protected from these instructions alone. Any unavailable control or proposed exception requires documented assessment and responsible human approval; no provider configuration or paid service change is implied.

## 7. Limits of this draft

No project workspace, repository, baseline, risk classification, completed test, approval or certification is supplied by this template. No production readiness, budget spend, external auditor use or new milestone is authorized. The adopting project must complete its state and approve applicable procedures before operational use.
