# Operational evidence lifecycle

STATUS: PROPOSTA / INITIALIZATION_REQUIRED

The initial package does not contain evidence/PROJECT_MANIFEST.json. Generate it only during explicitly authorized bootstrap in the adopting project from its actual authorized file bytes. Use templates/PROJECT_MANIFEST_TEMPLATE.json as structural guidance, not operational evidence.

PILOT_MANIFEST != PROJECT_MANIFEST

SOURCE_MANIFEST != PROJECT_MANIFEST

Copying or renaming historical inventories is prohibited. No old paths, dates, hashes, Candidates, receipts, decisions or permissions establish new-project evidence.

Operational format: schema starter-project-manifest-v1, version 1, status GENERATED, profile WINDOWS_LOCAL_SHA1_TEXT_LF_V1, scope "All project files except declared exclusions and this manifest", exact exclusions from the template and entries sorted by normalized relative path with size and SHA-256 of raw bytes. Validate confinement and the closed inventory. Exclude .git, __pycache__, bytecode, locks, temporaries, .test-sandbox and this manifest itself. No self hash, authorization inference or recursive HEAD update.

Generation is not implemented as a CLI command. It needs its own authorized bootstrap procedure; later changes to state/config/acceptance records require authorized inventory reconciliation. Record evidence separately from interpretation, and compare the actual expected snapshot before operational use. Baseline establishment is separate from adoption and from each future action.
