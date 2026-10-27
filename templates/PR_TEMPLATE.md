# Pull Request Template

STATUS: PROPOSTA / REUSABLE TEMPLATE. Not adopted; empty fields record no approval or permission.

Adapt to the project's scope and risk. Fill only with actual changes and evidence. Use PENDING, NOT RUN, NOT VERIFIED or NOT APPLICABLE with a reason when appropriate. This template is not a requirement for three universal approvals and does not replace the adopted project workflow.

## 1. Identification

- Project / repository: [pending]
- PR reference: [pending or not created]
- Source branch: [pending]
- Target branch and verified base SHA: [pending]
- Current published full HEAD: [pending or not yet published]
- Local content hashes / reviewed version, when different: [pending or not applicable]
- Included commits / comparison range: [pending]

A branch name alone does not identify content. Distinguish local changes from the published PR HEAD and the actual reviewed version.

## 2. Change summary

- Objective and resulting behavior: [pending]
- Motivation / problem addressed: [pending]
- Acceptance criteria: [pending]

Describe the final change for a reader without the execution conversation. Include a concrete before/after example when useful.

## 3. Scope

- Included: [pending]
- Not included / explicit exclusions: [pending]
- Related task, specification or decision: [pending]

## 4. Changes and impact

- Added / modified / removed files and purpose: [pending]
- Technical or documentary impact: [pending]
- Dependency, configuration, data or architecture impact: [pending or none with justification]
- Decision record required / referenced, where applicable: [pending or not applicable with reason]

Do not imply that a design proposal has been adopted or that external services were changed merely because documentation was added.

## 5. Validation and evidence

| Check | Command / evidence link | Version tested | Actual result and limitations |
|---|---|---|---|
| Local tests / validators | [pending] | [pending] | [pending] |
| CI workflows / checks | [pending] | [published HEAD; pending] | [pending] |
| Diff / content verification | [pending] | [pending] | [pending] |

- Relevant regression coverage: [pending]
- Omitted, unavailable or incomplete checks, with reasons: [pending]
- Evidence/artifact references and hashes where useful: [pending]

Keep local test results distinct from CI. Record what each workflow actually executes; green checks do not prove omitted tests, semantic consistency or whole-project certification. Do not report a new test run from an older version without verified applicability.

## 6. Reviews according to applicability

| Perspective | Applicable? / reason | Reviewer / record | Verdict, examined version and limits |
|---|---|---|---|
| Engineering | [pending] | [pending] | [pending] |
| Architecture | [pending] | [pending] | [pending] |
| Adversarial | [pending] | [pending] | [pending] |

- Risk classification and applicable review requirements: [pending]
- Unresolved blocking findings or missing review evidence: [pending]
- Revalidation required after subsequent changes: [pending]

Select review depth under the adopting project's risk policy. NOT APPLICABLE is a reasoned classification, not a waiver of a required perspective. Executor checks are not independent approval. Review records, comments and formal provider approvals are distinct evidence.

## 7. Risks, limitations and pending work

- Known risks and mitigations: [pending]
- Analysis / environment limitations: [pending]
- Recovery reference and rollback limits: [pending]
- Outstanding work within this PR: [pending]
- Related work outside this PR: [pending]

A Git recovery reference does not demonstrate backup/restore capability. Keep pending production, recovery or certification acceptance explicitly pending unless separately evidenced.

## 8. Authorization and integration boundary

- Technical review outcome and scoped evidence: [pending]
- Explicit human merge authorization: [PENDING unless actually granted]
- Authorizer, decision reference and authorized exact HEAD: [pending]
- Required checks and pre-merge prerequisites still to verify: [pending]

Technical approval does not authorize merge. Creating, publishing or reviewing a PR does not itself authorize integration, deployment, releases, scope changes or irreversible actions. Record an actual human decision only when evidenced; filling this template cannot grant it.

Before a specifically authorized merge, reconfirm the approved content, actual PR/base state and applicable checks/reviews. Stop dependent integration on unexpected divergence or an unresolved blocker. Do not infer automatic approval from a mergeable status.

## 9. Next step

- Next requested action and remaining authorization: [pending]

No actual project, vendor, completed validation, production acceptance or permission is supplied by this reusable proposal.
