# Audit Record

STATUS: PROPOSTA / REUSABLE TEMPLATE. Not adopted; no actual audit result or certification is supplied.

Fill only from the audit actually performed under its authorized scope. Empty fields are not evidence of conformity. Use NOT VERIFIED, NOT RUN or NOT APPLICABLE with reasons where relevant. This template does not replace the adopting project's audit criteria or review protocol.

## Audit and technical review

Audit and technical review have distinct, complementary objectives. Audit verifies evidence against defined criteria; technical review assesses implementation, changes and their possible effects. Neither process substitutes for human authorization of execution, publication or merge. A recommendation to act outside the existing scope requires a separately authorized scope; it does not itself permit execution.

## 1. Identification

- Project: [pending]
- Repository: [pending]
- Audited object / behavior / document: [pending]
- Branch: [pending]
- Exact HEAD or content hashes and their scope: [pending]
- Baseline / comparison range: [pending or not applicable]
- Date, time and timezone: [pending]
- Auditor identity, role and provenance: [pending]
- Independence, shared inputs and authorized methods: [pending]

For uncommitted content or external artifacts, record the examined version and hashes where appropriate. A branch name alone does not identify the audited content. Later publication requires verified equivalence; do not claim a new audit run merely because identical content was committed.

## 2. Scope and criteria

- Audit objective: [pending]
- Criteria and their authoritative source/revision: [pending]
- Included files, behaviors or controls: [pending]
- Excluded items: [pending]
- Access, environment and method boundaries: [pending]

No finding or conclusion may silently expand this scope. Criteria not evaluated must remain explicitly outside the conclusion or unverified.

## 3. Evidence register

| ID | Source / file / version | Check or test actually performed | Observed result | Limits and verification status |
|---|---|---|---|---|
| [pending] | [pending] | [pending] | [pending] | [pending] |

- Sources consulted and evidence origin: [pending]
- Files and surrounding context inspected: [pending]
- Test commands, tested version, dates and exact results: [pending]
- Reproductions / negative probes, inputs and expected versus observed behavior: [pending]
- Evidence supplied by others and not independently checked: [pending]
- Missing, inaccessible or outdated evidence: [pending]
- Checks omitted or incomplete and reasons: [pending]

Separate recorded observations from interpretation. Distinguish local tests from CI on its exact HEAD. A content hash does not prove trusted origin or completeness; unavailable evidence is not a successful check.

## 4. Assessment

- Conformities supported by evidence, mapped to criteria: [pending]
- Nonconformities, mapped to criteria and evidence: [pending]
- Documentary / implementation / baseline divergences: [pending]
- Risks and fragile assumptions: [pending]
- Unassessed or inconclusive criteria: [pending]

For each finding, record:

- ID and classification: [verified nonconformity / divergence / unresolved question / risk / suggestion]
- Description and affected location: [pending]
- Criterion and expected behavior: [pending]
- Observed facts and evidence references: [pending]
- Reproduction, when applicable: [pending or not reproduced with reason]
- Interpretation, impact and severity rationale: [pending]
- Recommended correction or investigation: [pending]

Suggestions and risks are not automatically proven violations. State when no findings were identified within the assessed scope; do not infer that unexamined areas are safe.

## 5. Audit result

- Result: [PASS / PASS WITH LIMITATIONS / FAIL / BLOCKED; select after assessment]
- Justification and criteria covered: [pending]
- Blocking nonconformities or missing prerequisites: [pending]
- Limitations and residual risks: [pending]

| Result | Meaning within the stated scope |
|---|---|
| PASS | Sufficient evidence supports the assessed criteria, with no identified blocking nonconformity. Not whole-project certification. |
| PASS WITH LIMITATIONS | The clearly bounded assessed portion passes, while declared exclusions or non-blocking limitations restrict the conclusion. No missing mandatory criterion or blocking defect is waived. |
| FAIL | Verified nonconformities prevent meeting the assessed criteria. |
| BLOCKED | Critical evidence, access or prerequisites are insufficient to reach a reliable conclusion. |

Do not use PASS WITH LIMITATIONS to conceal a failed mandatory check, a blocking defect or missing evidence needed for the claimed conclusion. An auditor cannot grant an exception by changing the result label.

## 6. Conclusion and next steps

- Summary of findings: [pending]
- Recommendations and priority: [pending]
- Required corrective work or additional evidence: [pending]
- Reaudit scope after changes: [pending]
- Next steps and authorization still needed: [pending]

This record documents findings; it does not authorize their correction, publication, deployment or merge. Any remediation remains subject to a separately authorized scope and applicable revalidation. An auditor who implements a correction cannot independently approve that implementation.

## 7. Limits of authority

Audit evidence and interpretation remain distinct. The conclusion applies only to the object, version, criteria and scope actually assessed. Do not declare production readiness, recovery guarantees or certification beyond that evidence. Technical audit results do not replace the responsible human's decisions or effective provider controls.

Completing this template does not authorize execution, external access, paid services, remote comments or formal review submissions. No real project data, supplier requirement, completed audit or approval is included here.
