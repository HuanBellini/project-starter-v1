# AUTOMATION CONTRACT V1 - reusable local profile

STATUS: PROPOSTA / VALIDATED LOCAL PROFILE. Not adopted as project policy.

No adoption or execution authorization is granted. This contract specifies the boundaries of the reusable local CLI validated within the supported profile. Package validation is separate from an adopting project's qualification, production acceptance and human permissions; no formal certification is claimed. Release/version identity belongs to Git commit/tag/release metadata, not to an automatic adoption state.

## Supported boundary

WINDOWS_LOCAL_SHA1_TEXT_LF_V1 only: Windows, Python >= 3.13 standard library plus trusted local Git, SHA-1, explicit core.filemode=false, conventional independent .git directory, direct loose branch, text LF/no CR, no filters and remote_policy=NONE. No worktrees, gitdir-file layout, shallow repositories, alternates, arbitrary binaries or POSIX claim. Unsupported local Git configuration is BLOCKED, not interpreted permissively. Global/system settings are disabled; their external values are not asserted.

Python 3.14.6 and Git for Windows 2.54.0.windows.1 were used in validation. The minimum is required by APIs including ntpath.isreserved; Python 3.12 is unsupported. Meeting the minimum does not prove every runtime combination has been tested.

## Bootstrap versus operation

Copy -> inspect -> authorized identity/state/profile initialization -> generate the project manifest -> human adoption decision -> separately authorized first baseline -> scoped operational actions. The CLI requires HEAD, a versioned parent contract and a generated operational manifest; it does not initialize an empty repository. PROJECT_STATE.md is the documentary state; Git supplies actual current HEAD/branch/tree/index. Historical handoffs do not override current evidence. No self-referential HEAD update loop is allowed.

## Input and preflight

No historical workspace/project/branch/HEAD/count defaults exist. CLI configuration is explicit JSON text, never an automatically opened file path. Missing/placeholder critical fields, unsupported profile or remote policy, or disagreement with explicit expectations yields BLOCKED before inspecting a destination. The profile fixes manifest/contract relative paths; a value cannot turn a permitted Git argument into an arbitrary selector or command.

Validate lexical identity before filesystem access. The authorized local drive root is the reference; reject UNC/device namespaces, relative and drive-relative roots, invalid components and foreign paths without resolving/statting/opening their destinations. Reject symlink/reparse/hard-linked metadata and unsupported layouts. Check actual Git root, project, branch, parent, flags/modes, index/worktree bytes, manifest, attributes, remotes, relevant locks and scope before dependent actions. Never correct a mismatch automatically.

## State and authority separation

OBSERVE -> VALIDATE -> PREPARE -> HUMAN AUTHORIZE STAGE -> EXECUTE-STAGE -> COMMIT-PLAN -> HUMAN AUTHORIZE COMMIT -> EXECUTE-COMMIT -> POSTCHECK.

Each is a separate command/decision boundary. A result, test pass, reviewer approval or existing commit does not authorize another action. Executor checks do not approve its own implementation. Human authority remains final; contextual agent review is not institutional independence. Important evidence must have an authorized durable record, not only chat memory. Text fields and hash bindings do not authenticate a human cryptographically. Bindings detect/reject content drift in the checked flow, but an executor with terminal access can technically provide its own bindings. External governance must preserve the human/executor separation. COMMIT_EXECUTED_AUTHORIZED does not prove the identity of the person authorizing an action.

## Canonical payloads and exact content

Schemas are starter-candidate-v1, starter-stage-receipt-v1, starter-commit-intent-v1 and starter-commit-receipt-v1. The coordinated namespace change intentionally invalidates prior digests and authorizations. No legacy schema/receipt is accepted as current permission.

Canonical payload bytes: UTF-8 json.dumps with sorted keys, compact separators, ensure_ascii=True, allow_nan=False, no newline; SHA-256 over those bytes. Candidate binds identity/workspace/branch/parent, exact sorted A/M/D paths, modes/blob OIDs, sizes/hashes and parent contract/attributes/manifest policy. Hashes do not prove trusted origin or permission. Git blob/tree IDs use SHA-1 framing, distinct from SHA-256 of raw file bytes.

The staged diff method is exactly:

```text
git diff --cached --no-ext-diff --no-textconv --binary --full-index --no-color
```

Hash raw stdout bytes with SHA-256; record exact byte length and command. Do not decode/reencode/normalize for hashing. Supported Git/runtime behavior must be qualified before new operational acceptance. A raw index hash alone does not establish historical semantic identity; paths, stages, modes, relevant flags, blobs, tree and diff bindings also matter.

## Read-only and mutable guards

OBSERVE/VALIDATE and PREPARE never stage, write objects or refs, change configuration or call arbitrary Git verbs. Read-only argv forms are narrowly allowlisted, including exact variable shapes. Unrecognized flags/verbs, filters, includes, output destinations or redirections cannot enlarge scope. Default output is stdout only; output-file creation needs separate permission.

EXECUTE-STAGE requires explicit authorized Candidate hash, parent, paths and STAGE_ONLY scope. Reconstruct the Candidate before mutation; bracket index validation with the same bytes, acquire index.lock exclusively, revalidate under lock and use a private transaction index. Only authorized blob writes/update-index/write-tree are admitted. Publish only the exact authorized entries, verify live/private index/diff and preserve working tree, parent/refs/config. A failure must preserve concurrent data; rollback only owned changes under the existing transaction boundaries. Authorized unreferenced objects can remain. Stage-Receipt never grants commit permission.

COMMIT-PLAN is read-only and requires complete Candidate/Stage-Receipt objects and digests, parent/tree/diff/paths/blobs/policy, exact UTF-8 LF message/subject and explicit author/committer strings. It recomputes the tree in memory and rechecks the snapshot. Duplicate/nonfinite JSON, unknown layouts and drift block. Commit-Intent binds message bytes, identities and scope; it neither authorizes execution nor promises a future Git OID. No ambient identity fallback or silent message cleanup exists.

EXECUTE-COMMIT separately requires exact authorized intent hash, parent and COMMIT_ONLY scope. Rebuild and revalidate under an owned exclusive index lock. Admit only exact commit-tree for the intended tree/one parent/message, then update-ref --no-deref for that branch with old-OID compare-and-swap (CAS). Verify raw object OID, tree, one parent, exact message and identities before changing the ref. Disable hooks/signing with per-command settings, never persistent configuration changes. Revalidate before CAS, compare immutable committed diff and perform postchecks. No automatic retry, further commit or ref rollback is authorized.

## Explicit post-mutation states

- BLOCKED: prerequisites fail before own object creation; no automatic repair.
- COMMIT_OBJECT_CREATION_UNCERTAIN: creation attempted, no verified result.
- COMMIT_OBJECT_CREATED_REF_NOT_UPDATED: object may remain unreferenced.
- COMMIT_REF_UPDATE_UNCERTAIN: ref outcome needs human reconciliation.
- COMMITTED_AWAITING_POSTCHECK: internal transient state.
- COMMITTED_POSTCHECK_FAILED: commit/ref may already exist; never pretend zero mutation or erase it automatically.
- COMMIT_EXECUTED_AUTHORIZED: all postchecks and receipt construction succeeded within the external authorization boundary.

Commit-Receipt records actual commit metadata, message/content bindings, CAS and postchecks. Execution dates are observed metadata, not bound by Commit-Intent V1; different dates can change OID/receipt. Replay against changed state blocks, but a caller restoring identical state is not cryptographic single-use protection. Crash/timeouts and arbitrary external writers are outside an absolute repository transaction guarantee.

## Manifest and recovery lifecycles

Operational artifact: evidence/PROJECT_MANIFEST.json, generated only in authorized adopting-project bootstrap from real bytes. MANIFEST GENERATION = BOOTSTRAP RESPONSIBILITY, NOT OPERATIONAL CLI; no generator is implemented by the operational CLI. Schema starter-project-manifest-v1/version 1/status GENERATED/profile above. Deterministically sorted entries use path, size and sha256. Paths are relative, normalized and confined. Exclusions are explicit: .git/**, __pycache__/**, *.py[cod], *.lock, *.tmp, *.temp, .test-sandbox/** and the manifest itself. No self hash or future containing HEAD is required. Complete inventory, hashes/sizes, attributes and working-tree/blob correspondence are separate checks. The structural template is TEMPLATE_ONLY and must fail operational validation.

Release artifact: the existing release/RELEASE_MANIFEST.json, generated from actual package bytes and regenerated for authorized package edits, excluding itself. Its canonical profile name is WINDOWS_LOCAL_SHA1_TEXT_LF_V1, exactly as accepted by the CLI; no alternate alias is introduced. It inventories distributed bytes, not adoption or operational permission. No circular regeneration between release and project manifests. Updating state/config or recording acceptance may change files; reconcile the project inventory under explicit authorization before claiming correspondence.

Recovery is a separately authorized procedure, not a new CLI command. Distinguish bundle created, bundle verified, isolated restore actually tested and an independent physical-loss backup. Record bundle bytes/hash/refs, verification, isolated restore comparison and limitations. A same-volume copy is not independent physical protection. ZIP remains a compatibility recommendation, not a tested capability supplied here.

## Qualification and stop boundary

Preserve all relevant derived regressions: confinement without external access, narrow Git guards, exact selection, index concurrency/lock ownership, message/identity/policy binding, CAS races, replay and partial failure states. Add explicit configuration/adoption/schema/template rejection tests. Real symlink capability can remain an environmental limitation with equivalent logical guards; never weaken protections to eliminate a skip.

Historical RC validation completed the full suite: 173 executed, 172 PASS, 0 FAIL, 0 ERROR and 1 real-symlink SKIP on Windows, with logical reparse guards passing. Symlink capability remains unproved. Historical allowlist probes rejected 207 invalid combinations. The validated cold start preceded the final RC RELEASE_MANIFEST; the relevant automation code was identical, but the later manifest and documentation patch were not part of that cold-start snapshot. The historical RC later passed bundle verification and isolated logical restore with 26/26 byte-identical files. Later package compositions require their own scoped checks and recovery evidence; prior results must not be relabeled as new runs.

Tests should run in an authorized disposable copy/fixture, not on a frozen release. External tools can create auxiliary refs; unexpected refs can cause BLOCKED or postcheck failure. Distribution bundles must use explicit refs, never --all automatically. Resolving external ref interference is a separate human decision.

No adoption, staging, commit, remote, tag, publication, bundle, restore or autonomy expansion follows from this document. Package maturity is not formal certification.
