# AI Review Protocol

STATUS: PROPOSTA / INITIAL DRAFT. Not adopted as project policy.

## 1. Purpose and applicability

Propose independent review of technical correctness, scope compliance, risk, failure paths and unintended effects. Review is more than confirming that a happy-path test passes. Adapt and approve this model before normative use; it does not replace project-specific requirements, human authorization or provider controls.

No AI vendor is required. Choose reviewers appropriate to the task and disclose their role and provenance. External strategic review is optional under explicit authorization and applicable cost limits; this proposal does not authorize paid use.

## 2. Independence and evidence

A reviewer needs enough context to understand the objective, acceptance criteria, applicable decisions and baseline, but must not rely only on the executor's report. Examine the actual diff and relevant surrounding implementation or documents, inspect evidence and perform independent checks or reproduction where needed and authorized.

For AI review, use a separate review context with task evidence and criteria. A separate context or a different model alone does not prove real-world independence; disclose shared inputs, limitations and reliance on others. Executor claims remain claims until checked. Existing tests and green CI do not substitute for analysis of what they actually cover.

Begin with read-only review. Any tests must respect authorized file, service and cost boundaries. Report unavailable checks rather than fabricate results. Do not modify the implementation or publish comments/approvals merely because review was authorized.

Bind the review to an exact HEAD or content hash and scope. If review precedes commit, verify content equivalence before attributing it to a published version; do not claim a new run. Later changes require impact assessment and proportionate revalidation of affected perspectives. Identify partial evidence and unreviewed files explicitly.

## 3. Review perspectives

| Perspective | Questions and evidence |
|---|---|
| Engineering | Does the implementation satisfy the criteria? Are meaningful tests and regressions covered? Are errors, maintenance or performance concerns present? |
| Architecture | Does the change preserve accepted boundaries, contracts and design decisions? Does it introduce structural impact, coupling or a decision needing approval? |
| Adversarial | What inputs, bypasses, inconsistent states or fragile assumptions could break the change? Can negative cases reproduce a violation? |

These perspectives describe analytical coverage, not fixed suppliers or automatic approval authority.

## 4. Proportional review by risk

Use actual impact and the adopting project's risk criteria, not filenames alone. Suggested minimum depth:

| Risk | Proposed review model |
|---|---|
| Low | A focused, simple review of scope, correctness and evidence; avoid three full audits for an ordinary text correction. |
| Medium | Engineering assessment plus independent scrutiny of the relevant failure risks; no automatic requirement for three separate full audits. |
| High | Engineering, Architecture and Adversarial perspectives, with separately attributable evidence and the required human decisions. |

For medium risk, an independent reviewer may perform the Engineering assessment and the additional scrutiny in one review. This is not two independent approvals. For high risk, plan reviewers and their independence explicitly under the adopted project policy; do not count executor self-checks as an independent perspective.

All levels retain the no-self-approval rule. Focused review can be performed by an independent human or agent; executor verification remains distinct. Normative documentation, security-sensitive dependencies, production effects or irreversible changes can raise risk. Do not downgrade classification or omit a required perspective merely to obtain approval. Resolve material uncertainty about applicable review requirements before advancing.

## 5. Findings and re-review

Record each finding with severity, affected location, observed behavior, reproduction or evidence, expected behavior and recommended correction where applicable. Distinguish verified defects, unresolved questions and suggestions. Do not invent reproduction when access or evidence is insufficient.

Return REQUEST CHANGES for verified blocking defects or unmet criteria; return BLOCKED when critical evidence or prerequisites prevent a conclusion. After an authorized correction, review the changed content and relevant regressions. A reviewer who implements a correction becomes an executor for that change and cannot independently approve it; another reviewer is needed. Merely discovering the original defect does not prevent the reviewer from rechecking a correction implemented by someone else.

## 6. Review result format

```text
REVIEW RESULT
Status: APPROVED | REQUEST CHANGES | BLOCKED
Reviewer / role / provenance:
Perspective and risk classification:
Reviewed scope and acceptance criteria:
Baseline and exact HEAD or content hashes:
Evidence and checks actually performed:
Findings, severity and reproduction:
Residual risks:
Limitations, omissions and unreviewed scope:
Recommendation and next prerequisites:
```

APPROVED means the reviewed scope satisfies the assessed criteria within the stated evidence and limitations. It does not certify the whole project or prove absent production risks. REQUEST CHANGES identifies corrections required before advancement. BLOCKED identifies missing evidence or prerequisites without pretending a complete technical verdict.

Record important results using the authorized project evidence workflow. A conversation, local draft, PR comment and formal provider review submission are different records; do not misrepresent one as another. No publication is authorized by producing the result.

## 7. Human decision and merge boundary

The reviewer informs; the responsible human decides exceptions, scope changes, irreversible actions and final merge authorization. Technical approval, a provider APPROVED review or successful CI is not that authorization. The executor cannot grant it to itself.

Before a permitted merge, the applicable review requirements and required checks must refer to the exact version to be integrated, with explicit human authorization for that action. An unresolved blocking finding or missing required evidence prevents claiming readiness. Any exception requires the authorized human decision and the project's documented exception process; it cannot silently relabel a failed or incomplete review as APPROVED.

This initial proposal grants no merge, deployment, certification or milestone permission and does not amend the host project's review policy.
