# PROJECT_STARTER_V1 - reusable package

STATUS: PROPOSTA / REUSABLE PACKAGE. Project adoption and execution remain separately authorized.

Adoption-Status: NOT_ADOPTED
Initialization-Status: INITIALIZATION_REQUIRED
Execution-Authorization: NONE

## Purpose and entry

External project memory, scoped execution, separate review, human decisions and recoverable handoffs for AI-assisted projects. The design derives from a validated controlled exercise; copying its design does not transfer any previous authorization, identity, evidence or acceptance.

COPYING TEMPLATE != ADOPTION

ADOPTION != EXECUTION AUTHORIZATION

Package validation and project adoption are separate scopes. PROPOSTA, UNBORN and unverified test/recovery fields in the reusable governance/state templates describe the future adopting project, not the validation history of this package. Populate them only for that project under its own authorization.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), [AI_EXECUTOR_PROTOCOL.md](AI_EXECUTOR_PROTOCOL.md), [AI_REVIEW_PROTOCOL.md](AI_REVIEW_PROTOCOL.md) and [AUTOMATION_CONTRACT_V1.md](docs/AUTOMATION_CONTRACT_V1.md). Use [AI_DECISION_LOG.md](AI_DECISION_LOG.md) for decisions and [RECOVERY.md](docs/RECOVERY.md) for resumption. Handoffs describe a dated delivery, not competing current state.

## Supported V1 profile

Only WINDOWS_LOCAL_SHA1_TEXT_LF_V1: Windows, local Python and Git, SHA-1 repository, explicit local core.filemode=false, conventional independent .git directory, direct loose branch ref, text LF, no CR bytes or Git filters, and remote_policy=NONE. Worktrees, gitdir files, shallow history, alternates, arbitrary binary files, POSIX and other remote policies are unsupported. Unsupported configuration blocks; no automatic conversion or persistent Git configuration change is implemented.

Python >= 3.13 is required, including APIs such as ntpath.isreserved. Validation used Python 3.14.6 and Git for Windows 2.54.0.windows.1; other versions satisfying the minimum are not individually qualified by that run. Python standard library is the only Python dependency; Git must be installed and trusted. No external service or provider is required.

## Bootstrap / Adoption is separate

COPY TEMPLATE -> INSPECT -> INITIALIZE PROJECT STATE -> configure profile -> generate PROJECT_MANIFEST -> HUMAN ADOPTION DECISION -> ESTABLISH BASELINE -> specifically authorized operations.

Every mutating bootstrap step needs its own authorization. Human acceptance does not automatically grant the first staging/commit. The operational CLI requires an existing HEAD, a versioned parent contract and an operational manifest. It does not initialize a repository or create its first baseline. This package intentionally contains no operational project manifest or adopted-project baseline. Package Git provenance is separate from the adopting project's operational history; PROJECT_STATE.md retains UNBORN as a new-project template value.

Adapt the state/configuration only after authorization. Record actual adoption evidence; setting an ADOPTED string is not proof of human identity or a decision. After acceptance, the state and explicit configuration must consistently record ADOPTED / INITIALIZED. Reconcile the manifest after any authorized bootstrap edit before claiming inventory correspondence. Git remains authoritative for current HEAD/branch/staging; never chase a containing future commit by recursively editing the state.

## Explicit configuration, no destination fallback

[starter-config.example.json](starter-config.example.json) is intentionally incomplete. The CLI does not search for it, open a supplied configuration path, inspect the current directory as a default workspace or infer values from Git configuration. Supply initialized JSON text through --config-json. It is data, not permission.

Required configuration: project_name, workspace, repository, work_branch, default_branch, human_authority, manifest_path, contract_path, supported_profile, remote_policy, backup_location, adoption_status and initialization_status. In this local-only profile repository is the absolute local Git root and must have the same lexical identity as workspace. backup_location may explicitly be NOT_CONFIGURED; this records missing recovery protection, not approval. Work branch must differ from integration branch. Profile is WINDOWS_LOCAL_SHA1_TEXT_LF_V1; remote_policy is only NONE; manifest_path is evidence/PROJECT_MANIFEST.json and contract_path is docs/AUTOMATION_CONTRACT_V1.md. These fixed relative conventions are checked rather than accepting arbitrary contract selectors.

Missing configuration/placeholders, unsupported policy, mismatched workspace/repository/project/branch or absent expected HEAD/count return BLOCKED before destination filesystem access. Documentary paths are untrusted: lexical Windows validation/confinement precedes destination access. UNC, device namespaces, drive-relative/relative roots and foreign roots cannot be used to discover another project.

## CLI and authority gates

The CLI has separate commands: observe (default), prepare, execute-stage, commit-plan and execute-commit. Default means read-only observation, not automatic workspace selection. All commands require explicit initialized configuration, expected existing parent and positive expected manifest count. Optional --workspace/--expected-workspace/--expected-project/--expected-branch assertions must agree with configuration. Missing data blocks instead of falling back.

Illustrative syntax only; placeholders are not executable permission:

```text
python -B starter_cli.py observe --config-json <INITIALIZED_CONFIG_JSON> --expected-head <EXPECTED_HEAD> --expected-count <EXPECTED_COUNT> --json
python -B starter_cli.py prepare --config-json <INITIALIZED_CONFIG_JSON> --expected-head <EXPECTED_HEAD> --expected-count <EXPECTED_COUNT> --path <CHANGED_PATH>
```

PREPARE requires the complete exact set of real changes. It writes no files, index or Git objects and returns PREPARED_NOT_AUTHORIZED. Explicit candidate/parent/path binding and STAGE_ONLY scope are required by execute-stage; a separate invocation can return STAGED_AWAITING_COMMIT_AUTHORIZATION. It does not commit.

COMMIT-PLAN requires full Candidate and Stage-Receipt JSON objects and hashes, exact paths, subject, full UTF-8 LF message and explicit author/committer name/email with COMMIT_ONLY scope. Message bytes, including a final newline if supplied, are bound without normalization. The output COMMIT_PLANNED_NOT_AUTHORIZED is not permission. execute-commit additionally requires a separately authorized intent hash and parent. No command chains to the next or generates human approval.

Schemas have been deliberately renamed together: starter-candidate-v1, starter-stage-receipt-v1, starter-commit-intent-v1 and starter-commit-receipt-v1. This changes canonical digests and invalidates all previous Candidate/receipt/intent permissions. There is no legacy authorization migration or fallback. JSON canonicalization remains UTF-8, sorted keys, compact separators, ensure_ascii=True, allow_nan=False, no newline; SHA-256 hashes its raw bytes. Git blob/tree identities retain SHA-1 object framing. Message, raw files, Git blobs and canonical payloads are distinct byte domains.

## Manifest lifecycles

[evidence/README.md](evidence/README.md) describes the operational manifest generated during authorized bootstrap. [templates/PROJECT_MANIFEST_TEMPLATE.json](templates/PROJECT_MANIFEST_TEMPLATE.json) is TEMPLATE_ONLY and cannot validate as a generated manifest. Operational schema is starter-project-manifest-v1, version 1, status GENERATED and the supported profile; entries are ordered path/size/sha256 records. The closed inventory excludes .git, known caches/bytecode, locks, temporaries, .test-sandbox and the manifest itself under the exact declared policy. Its expected count is supplied independently for the authorized snapshot, not trusted from the same manifest to waive a mismatch.

[release/README.md](release/README.md) describes the existing package manifest, generated from the actual distributed bytes and reconciled for authorized package changes. It is not operational project state or adoption evidence. No manifest may require its own hash. Updating an adopting project manifest does not regenerate the package provenance manifest or create a cycle of HEAD/hash updates. MANIFEST GENERATION = BOOTSTRAP RESPONSIBILITY, NOT OPERATIONAL CLI: the CLI does not implement a PROJECT_MANIFEST generator.

## Package maturity and validation evidence

PROJECT_STARTER_V1 is a reusable package validated within its declared profile. Release/version identity is represented by Git commit/tag/release metadata; this preparation does not assert that a V1.0 tag or promotion already exists. Copying this package does not adopt it into a project and does not authorize execution. Package validation is not formal certification or production acceptance.

Historical RC validation recorded 173 tests: 172 PASS, 0 FAIL, 0 ERROR and 1 SKIP. The skipped real-symlink test could not create a symlink on Windows; equivalent logical reparse guards passed, but real symlink capability remains unproved. Historical allowlist probes rejected 207 invalid combinations. These are scoped validation records, not guarantees about all environments.

The validated cold start used the composition before the final RC RELEASE_MANIFEST was added. The relevant automation code remained identical. It did not test the later manifest or this documentation patch; do not attribute those bytes to that earlier cold-start run. The historical RC subsequently passed bundle verification and isolated restore with 26/26 byte-identical files. That proves logical recovery of that RC, not a new recovery run for later compositions or an independent physical backup.

Derived regressions are in tests/test_starter_cli.py. Tests create disposable repositories under the test copy's .test-sandbox when separately authorized; import alone does not create it. Run tests preferably in a disposable copy/fixture, not a frozen distributed release. .test-sandbox/ is ignored for hygiene; ignoring it is not evidence that package contents remained unchanged. Test identities, remote URLs and foreign Windows/UNC/device paths are isolated fixtures, never operational destinations. Documentation/metadata edits require their own inventory validation and appropriate regression checks. No test outcome, technical review or commit creates permission.

## Known operational limits

Authorization fields check binding/scope and reject snapshot drift within the validated flow; they do not authenticate a human cryptographically or prove civil identity. An executor with terminal access can technically supply its own bindings. Separation of authority therefore also depends on external governance and human decisions. COMMIT_EXECUTED_AUTHORIZED reports successful checks against supplied bindings, not proof of human identity. Separate-context review is not institutional independence. Git/config/attribute guard allowlists remain conservative; global/system configuration is disabled without claiming its ambient values. Git settings unsupported by the local parser block, including ordinary local sections outside its subset. No remote support is implied.

Exclusive index locking coordinates conventional writers; it is not an absolute filesystem/ref transaction. Preserve semantic paths/stages/modes/blobs/flags/tree/diff bindings; raw index bytes also detect in-operation races but are not a historical snapshot identity alone. Crash/timeouts may leave unreferenced objects, uncertain updates or COMMITTED_POSTCHECK_FAILED; do not retry or roll back a committed ref automatically. Execution dates are observed metadata outside Commit-Intent V1. A same-volume bundle is not independent physical-loss protection. Recovery remains a separately authorized procedure, not a new CLI capability.

External tools, including agent environments, can create auxiliary Git refs. Unexpected external refs can cause BLOCKED or postcheck failure; reconcile them through a human decision rather than silently deleting or accepting them. Distribution bundles must name explicit refs; never use --all automatically.

Package evidence and Git provenance grant no adoption, staging, commit, tag, remote, publication, bundle, restore or autonomy expansion. Future publication has a separate human privacy decision described in [release/README.md](release/README.md).
