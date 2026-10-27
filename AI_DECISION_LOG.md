# AI Decision Log

STATUS: PROPOSTA / REUSABLE TEMPLATE. Not adopted; no actual project decision is recorded here.

## 1. Purpose and limits

Provide an index and concise summaries explaining what was decided, why, by whom and on what evidence. Adapt and approve this proposal before normative use. It does not replace specific execution authorization, applicable project policies or official detailed records.

PROJECT_STATE.md records the current operational snapshot. This log preserves decision traceability, not a second task state or a transcript of conversations. An AI recommendation is a proposal until accepted by the appropriate human authority; technical review alone is not that acceptance.

## 2. Decision states

| Status | Meaning | Required traceability |
|---|---|---|
| PROPOSTA | Suggested direction, not accepted | Proposer, context, rationale and open questions |
| APROVADA | Accepted decision within a stated scope | Identified authorizer, dated acceptance evidence, conditions and scope |
| REJEITADA | Proposal explicitly declined | Identified decision-maker, dated evidence and reason |
| SUPERADA | Previously applicable decision replaced or retired by an authorized decision | Replacement/retirement reference, authorizer, effective context and preserved history |

Do not infer acceptance from silence, a merged unrelated PR, executor claims or an empty field. APROVADA records decision acceptance; it does not prove implementation, production readiness or permission to commit, publish, deploy or merge. SUPERADA preserves the previous decision and does not mean it was always wrong.

## 3. Index and detailed source

Assign a stable project-specific ID and maintain one identifiable detailed source for each decision when details are needed. That source may be an ADR, technical document, PR, issue or reviewed report, according to the adopting project's policy. A log entry can be the complete source for a simple decision; do not create a second copy solely for formality.

When a detailed source exists, the log contains a summary and link to it. Do not maintain independently editable competing rationales, authorization or statuses. Any mirrored summary identifies the source revision/date and must remain consistent with it. A template is not a completed decision record.

Record related PRs, issues, documents and commits as relationships, not automatic proof of acceptance. Identify the specific comment, revision, commit or dated evidence supporting the decision. Missing or inaccessible evidence remains explicitly unverified.

## 4. Reusable entry structure

```text
ID: [pending]
Date / timezone: [pending]
Status: [PROPOSTA | APROVADA | REJEITADA | SUPERADA; select for an actual entry]
Decision: [pending; concise scope]
Context: [pending]
Reason: [pending]
Alternatives considered: [pending]
Impact / risks / conditions: [pending]
Proposer / recorder: [pending]
Authorizer or decision-maker: [pending; do not invent approval for a proposal]
Acceptance, rejection or supersession evidence: [pending]
Detailed source and revision/date, when applicable: [pending]
Related references:
- PR: [pending or not applicable]
- Issue: [pending or not applicable]
- Document/report: [pending or not applicable]
- Commit/content version: [pending or not applicable]
Supersedes / superseded by: [pending or not applicable]
```

All fields above are placeholders, not project facts. Use [DECISION_TEMPLATE.md](templates/DECISION_TEMPLATE.md) as a drafting aid where applicable; its current placeholder is not an adopted source of authority. No actual ID, date, decision or authorization is supplied by this reusable template.

## 5. High-impact decisions

For architecture changes, supplier changes, security changes, data deletion or other irreversible effects, record the concrete affected scope, alternatives, dependencies, risks, review evidence and explicit human decision. Distinguish reversible source changes from irreversible external effects.

Record recovery or mitigation plans and their verified limits where relevant. A Git SHA or a claimed backup is not proof of restore capability. Do not treat acceptance of a design as permission to delete data, change providers, incur costs or operate in production. Apply the adopting project's risk and authorization requirements before execution.

## 6. Recording and history

Add or update entries only within an authorized documentation scope. An agent may record an authorized proposal or faithfully transcribe an evidenced human decision; it may not invent the authorizer, silently grant itself approval or change policy through the index.

When a decision changes, preserve the prior record and identify the dated transition and relationship rather than rewriting the past as if the new decision had always applied. Correct factual transcription errors transparently, retaining the relevant historical evidence. Report inconsistent sources and stop dependent execution until resolved; do not silently choose a convenient interpretation.

This log creates no universal approval authority, vendor requirement or project-specific exception. Publication and adoption remain separately authorized actions.
