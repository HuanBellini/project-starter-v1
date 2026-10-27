# Release evidence lifecycle

STATUS: PROPOSTA / RELEASE CANDIDATE METADATA. Not an adoption decision.

## Package maturity and provenance

PROJECT_STARTER_V1 is a reusable package validated within its declared profile. Release/version identity is represented by Git commit/tag/release metadata. This promotion preparation does not assert that a V1.0 tag exists. Copying this package does not adopt it into a project and does not authorize execution. No formal certification is claimed.

The package includes release/RELEASE_MANIFEST.json: schema starter-release-manifest-v1, version 1, status RELEASE_CANDIDATE, canonical profile WINDOWS_LOCAL_SHA1_TEXT_LF_V1. That is the exact profile accepted by the operational CLI, with no alias. The manifest inventories actual distributed bytes using a closed, ordered path/size/SHA-256 inventory and excludes itself. Regenerate it when authorized package edits change those bytes; retain the earlier manifest in its historical RC. Never silently relabel frozen evidence as a promoted version.

The manifest is not adoption, execution authorization, active project state or backup. evidence/PROJECT_MANIFEST.json is generated separately during an adopting project's authorized bootstrap and is not distributed as fictitious valid evidence. Its generation is a bootstrap responsibility, not an operational CLI command. Adapting a project must not recursively regenerate the package provenance manifest.

## Validation and recovery scope

Historical RC qualification recorded 173 tests: 172 PASS, 0 FAIL, 0 ERROR and 1 real-symlink SKIP on Windows. Logical reparse guards passed; real symlink capability is not established. Python >= 3.13 is required; validation used Python 3.14.6 and Git for Windows 2.54.0.windows.1. Other runtime combinations are not qualified by inference.

The successful cold start used the composition before the final RC RELEASE_MANIFEST was added. Relevant automation code remained identical, but the later manifest and promotion documentation were not tested by that cold start. The historical RC then acquired a root baseline, verified bundle and isolated restore with 26/26 byte-identical files. That evidence belongs to that RC, not automatically to the edited promotion composition. A corrected composition needs its own explicitly authorized commit and recovery validation.

Distinguish bundle created, bundle verified, isolated restore actually tested and independent physical backup. Same-volume recovery != independent physical backup. A successful logical restore does not establish physical-loss protection.

External tools, including agent environments, may create auxiliary refs. Unexpected refs can cause BLOCKED or failed postchecks; do not remove them automatically. Distribution bundles must name explicit refs; never use --all automatically. Run authorized tests in a disposable copy/fixture rather than a frozen distributed release. .test-sandbox/ is ignored, not an approved distributed artifact.

## Separate publication privacy gate

The inherited RC Git history contains personal author/committer identity metadata. Public distribution of a repository or bundle may expose that metadata and requires an explicit human privacy decision at the future Publication Gate. This does not block internal technical promotion. No publication or history rewrite is authorized here, and no history rewrite is claimed. Git identity strings do not prove civil identity or cryptographic authentication.
