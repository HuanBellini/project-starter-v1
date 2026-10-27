"""Windows local OBSERVE/VALIDATE/PREPARE and separately authorized execution."""
import sys
sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import ntpath
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import time

MANIFEST = "evidence/PROJECT_MANIFEST.json"
CONTRACT = "docs/AUTOMATION_CONTRACT_V1.md"
PROFILE = "WINDOWS_LOCAL_SHA1_TEXT_LF_V1"
MANIFEST_SCOPE = "All project files except declared exclusions and this manifest"
MANIFEST_EXCLUSIONS = [".git/**", "__pycache__/**", "*.py[cod]", "*.lock",
                       "*.tmp", "*.temp", ".test-sandbox/**", MANIFEST]


class Blocked(Exception):
    pass


def windows_identity(value):
    """Pure lexical identity; never query a destination supplied as data."""
    value = os.fspath(value)
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise Blocked("Invalid Windows path value")
    value = value.replace("/", "\\")
    drive, tail = ntpath.splitdrive(value)
    if not re.fullmatch(r"[A-Za-z]:", drive) or not tail.startswith("\\"):
        raise Blocked("Only absolute local drive paths supported; UNC/device/relative paths blocked")
    for part in tail.split("\\"):
        if part in ("", ".", ".."):
            continue
        if (any(c in part for c in '<>:"|?*') or part.endswith((" ", "."))
                or ntpath.isreserved(part)):
            raise Blocked("Invalid or unsupported Windows path component")
    return ntpath.normcase(ntpath.normpath(value))


def no_links(path):
    """Reject links/reparse points rather than reading outside the intended root."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise Blocked("Link/reparse point is outside supported scope: " + path.name)


def walk_error(error):
    raise Blocked("Cannot inspect directory: " + str(error))


def excluded_file(path):
    parts = PurePosixPath(path).parts
    return ("__pycache__" in parts or ".test-sandbox" in parts
            or path.endswith((".pyc", ".pyo", ".pyd", ".lock", ".tmp", ".temp")))


def inventory(root):
    found = set()
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".test-sandbox"))
        files = sorted(f for f in files if not excluded_file((base / f).relative_to(root).as_posix()))
        for name in dirs + files:
            if base == root and name == ".git":
                continue
            no_links(base / name)
        if base == root:
            dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            path = base / name
            if not path.is_file():
                raise Blocked("Unsupported file type: " + path.name)
            found.add(path.relative_to(root).as_posix())
    return found


def confined_target(root, base, value, label):
    """Validate metadata pointer confinement lexically, without following it."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise Blocked("Invalid " + label)
    drive, tail = ntpath.splitdrive(value)
    if not drive and not value.startswith(("/", "\\")):
        value = ntpath.join(str(base), value)
    identity = windows_identity(value)
    trusted = windows_identity(root)
    if ntpath.commonpath([trusted, identity]) != trusted:
        raise Blocked(label + " escapes authorized workspace")
    return Path(identity)


def scan_metadata(gitdir):
    """No Git, include traversal or external paths are used by this scanner."""
    for directory, dirs, files in os.walk(gitdir, followlinks=False, onerror=walk_error):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            no_links(path)
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise Blocked("Unsupported Git metadata file type")
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise Blocked("Hard-linked Git metadata unsupported")


def safe_local_config(path):
    # Conservative subset, not an attempt to implement all Git config syntax.
    # Unsupported syntax/keys/includes block before Git can interpret them.
    section = None
    local_autocrlf = "unset"
    seen = set()
    core = {"repositoryformatversion": {"0"}, "filemode": {"true", "false"},
            "bare": {"false"}, "logallrefupdates": {"true", "false"},
            "symlinks": {"true", "false"}, "ignorecase": {"true", "false"},
            "autocrlf": {"true", "false", "input"},
            "fsmonitor": {"false"}, "untrackedcache": {"false"}}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            if line.lower() == "[core]":
                section = "core"
            elif re.fullmatch(r'\[remote "[A-Za-z0-9_.-]+"\]', line):
                section = line
            else:
                raise Blocked("Unsafe or unsupported Git config section (includes/filters blocked): " + line)
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*)\s*=\s*([^\r\n]*)", line)
        if not match or section is None:
            raise Blocked("Unsupported local Git config syntax")
        key, value = match[1].lower(), match[2].strip()
        if (section, key) in seen or any(c in value for c in ('\\', '"', "#", ";")):
            raise Blocked("Ambiguous or unsupported local Git config value")
        seen.add((section, key))
        if section == "core":
            if key not in core or value.lower() not in core[key]:
                raise Blocked("Unsafe or unsupported core configuration: " + key)
            if key == "autocrlf":
                local_autocrlf = value.lower()
        elif key not in ("url", "fetch"):
            raise Blocked("Unsupported remote configuration key")
    return local_autocrlf


def bootstrap(root):
    # Network-only/pager variables are discarded: no network/pager command exists.
    inert = {"GIT_HTTP_PROXY", "GIT_HTTPS_PROXY", "GIT_SSH_COMMAND", "GIT_PAGER"}
    overrides = sorted(k for k, v in os.environ.items()
                       if k.upper().startswith("GIT_") and v and k.upper() not in inert)
    if overrides:
        raise Blocked("Git environment redirection/override blocked: " + ", ".join(overrides))
    gitdir = root / ".git"
    no_links(gitdir)
    if gitdir.is_file():
        text = gitdir.read_text(encoding="utf-8").strip()
        if not text.startswith("gitdir: "):
            raise Blocked("Invalid gitdir file")
        confined_target(root, root, text[8:], "gitdir")
        raise Blocked("gitdir-file layouts unsupported in V1, even when confined")
    if not gitdir.is_dir():
        raise Blocked("Independent local .git directory required")
    scan_metadata(gitdir)
    common = gitdir / "commondir"
    if common.exists():
        confined_target(root, gitdir, common.read_text(encoding="utf-8").strip(), "commondir")
        raise Blocked("commondir layouts unsupported in V1")
    objects = gitdir / "objects"
    no_links(objects)
    if not objects.is_dir():
        raise Blocked("Git objects directory missing")
    for name in ("alternates", "http-alternates"):
        alternate = objects / "info" / name
        if alternate.exists():
            for value in alternate.read_text(encoding="utf-8").splitlines():
                confined_target(root, objects, value, "object alternate")
            raise Blocked("Object alternates unsupported in V1")
    for name in ("config.worktree", "shallow"):
        if (gitdir / name).exists():
            raise Blocked("Unsupported Git metadata: " + name)
    config = gitdir / "config"
    no_links(config)
    if not config.is_file():
        raise Blocked("Missing local Git configuration")
    return safe_local_config(config)


READ_ONLY_GIT_FORMS = frozenset({
    ("rev-parse", "--show-object-format"),
    ("rev-parse", "--show-toplevel"),
    ("rev-parse", "--verify", "HEAD"),
    ("symbolic-ref", "--quiet", "--short", "HEAD"),
    ("ls-files", "-v", "-z"),
    ("ls-files", "--stage", "-z"),
    ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
    ("diff", "--cached", "--name-only", "-z", "--no-ext-diff", "--no-textconv"),
    ("remote",),
    ("config", "--local", "--get", "core.filemode"),
})


def validate_git_argv(args, attribute_paths=None):
    """Deny by default; variable positions cannot become options or targets."""
    if not all(isinstance(a, str) for a in args):
        raise Blocked("Git argv must contain strings")
    if args in READ_ONLY_GIT_FORMS or args == STAGE_DIFF_ARGV:
        return
    if (len(args) == 4 and args[:3] == ("ls-tree", "-r", "-z")
            and re.fullmatch(r"[0-9a-f]{40}", args[3])):
        return
    if (len(args) == 8 and args[:6] == ("diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", "--no-color")
            and all(re.fullmatch(r"[0-9a-f]{40}", value) for value in args[6:])):
        return
    if (len(args) == 3 and args[:2] == ("cat-file", "commit")
            and re.fullmatch(r"[0-9a-f]{40}", args[2])):
        return
    if (len(args) == 3 and args[:2] == ("cat-file", "blob")
            and re.fullmatch(r"[0-9a-f]{40}(?::docs/AUTOMATION_CONTRACT_V1\.md)?", args[2])):
        return
    if args[:6] == ("check-attr", "-z", "text", "eol", "filter", "--") and attribute_paths is not None:
        # Bind the complete variadic tail to the inventory already checked by
        # the caller. No filesystem access occurs in this argument validator.
        if not isinstance(attribute_paths, (set, frozenset, list, tuple)) or not all(isinstance(p, str) for p in attribute_paths):
            raise Blocked("Invalid checked attribute inventory")
        expected = tuple(sorted(attribute_paths))
        if not expected or len(set(expected)) != len(expected) or args[6:] != expected:
            raise Blocked("Attribute argv differs from the checked inventory")
        for path in expected:
            parts = PurePosixPath(path)
            if (not path or parts.is_absolute() or parts.as_posix() != path
                    or ".." in parts.parts or path.lower() in (".", ".git")
                    or path.lower().startswith(".git/") or "\\" in path
                    or any(ord(c) < 32 or c in '<>:"|?*' for c in path)
                    or any(ntpath.isreserved(part) for part in parts.parts)):
                raise Blocked("Unsafe attribute path")
        return
    raise Blocked("Git argv is not an explicitly allowed read-only form")


def git(root, *args, allowed=(0,), attribute_paths=None):
    validate_git_argv(args, attribute_paths)
    # Suppress optional index refresh, fsmonitor and automatic maintenance.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1",
               GIT_NO_REPLACE_OBJECTS="1")
    command = ["git", "--no-pager", "--no-optional-locks",
               "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
               "-c", "core.attributesFile=" + os.devnull,
               "-c", "core.excludesFile=" + os.devnull,
               "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args]
    try:
        result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Blocked("Git unavailable or timed out") from error
    if result.returncode not in allowed:
        raise Blocked("Git inspection failed: " + " ".join(args[:2]))
    return result.stdout


def blob_oid(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def compare_index(root, files):
    errors, safety_errors, differences, compared = [], [], [], 0
    flags = git(root, "ls-files", "-v", "-z").split(b"\0")
    for record in flags:
        if not record:
            continue
        tag, path = os.fsdecode(record[:1]), os.fsdecode(record[2:])
        if tag.islower():
            safety_errors.append("assume-unchanged flag: " + path)
        if tag.upper() == "S":
            safety_errors.append("skip-worktree flag: " + path)
    records = git(root, "ls-files", "--stage", "-z").split(b"\0")
    if git(root, "rev-parse", "--show-object-format").decode().strip() != "sha1":
        raise Blocked("Only SHA-1 Git repositories supported in this milestone")
    tracked = set()
    for record in records:
        if not record:
            continue
        meta, encoded_path = record.split(b"\t", 1)
        mode, oid, stage = meta.decode("ascii").split()
        path = os.fsdecode(encoded_path)
        tracked.add(path)
        if mode not in ("100644", "100755") or stage != "0":
            safety_errors.append("Unsupported index mode/stage: " + path)
            continue
        blob = git(root, "cat-file", "blob", oid)
        if b"\r" in blob:
            safety_errors.append("Index blob contains CR bytes: " + path)
        if path not in files:
            errors.append("Tracked file missing from working tree: " + path)
            differences.append({"path": path, "change": "D", "mode": mode,
                                "previous_blob_oid": oid, "blob_oid": None,
                                "bytes": None, "sha256": None})
            continue
        raw = (root / path).read_bytes()
        observed = blob_oid(raw)
        if observed != oid:
            errors.append("Working-tree/index blob mismatch: " + path)
            differences.append({"path": path, "change": "M", "mode": mode,
                                "previous_blob_oid": oid, "blob_oid": observed,
                                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        compared += 1
    for path in sorted(files - tracked):
        raw = (root / path).read_bytes()
        errors.append("New working-tree file: " + path)
        differences.append({"path": path, "change": "A", "mode": "100644",
                            "previous_blob_oid": None, "blob_oid": blob_oid(raw),
                            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return {"compared": compared, "errors": sorted(errors + safety_errors),
            "safety_errors": sorted(safety_errors),
            "differences": sorted(differences, key=lambda d: d["path"]),
            "method": "SHA1(blob header + raw bytes), not filters or status"}


def validate_manifest(root, files, expected_count):
    no_links(root / "evidence")
    no_links(root / MANIFEST)
    data = plan_json((root / MANIFEST).read_text(encoding="utf-8"))
    if (data.get("schema") != "starter-project-manifest-v1"
            or type(data.get("version")) is not int or data["version"] != 1
            or data.get("status") != "GENERATED" or data.get("profile") != PROFILE
            or not isinstance(data.get("entries"), list)):
        raise Blocked("Generated project manifest schema/version/status/profile required; template is not operational")
    if data.get("scope") != MANIFEST_SCOPE or data.get("exclusions") != MANIFEST_EXCLUSIONS:
        raise Blocked("Unsupported manifest scope/exclusions; closed inventory policy required")
    entries = data["entries"]
    paths, validated = set(), 0
    errors = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise Blocked("Manifest entry must be an object")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise Blocked("Manifest path must be a nonempty string")
        parts = PurePosixPath(path)
        if (parts.is_absolute() or ".." in parts.parts or "\\" in path
                or ":" in path or parts.as_posix() != path or path.startswith(".git/")
                or path in (".git", MANIFEST) or path in paths):
            raise Blocked("Unsafe, duplicate or self-referential manifest path")
        paths.add(path)
        if (type(entry.get("size")) is not int or entry["size"] < 0
                or not isinstance(entry.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            raise Blocked("Invalid manifest size/hash fields: " + path)
        if path not in files:
            errors.append("Missing file: " + path)
            continue
        raw = (root / path).read_bytes()
        if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            errors.append("Manifest size/hash mismatch: " + path)
        else:
            validated += 1
    if [e["path"] for e in entries] != sorted(paths):
        errors.append("Manifest entries must use deterministic path ordering")
    extras = sorted(files - paths - {MANIFEST})
    errors.extend("Extra file in closed inventory: " + p for p in extras)
    if len(entries) != expected_count:
        errors.append("Manifest entry count differs from expected count")
    return {"expected": expected_count, "declared": len(entries),
            "validated": validated, "errors": errors}


def validate_expectations(workspace, expected_workspace, project, branch, head, count):
    # Pure lexical checks precede all destination filesystem access.
    if windows_identity(workspace) != windows_identity(expected_workspace):
        raise Blocked("Workspace differs from expected workspace; no destination inspection")
    if (not isinstance(project, str) or not project.strip() or project != project.strip()
            or any(ord(c) < 32 or c in "<>" for c in project)):
        raise Blocked("Explicit project identity required; placeholders are not values")
    commit_branch_ref(branch)
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise Blocked("Existing explicit SHA-1 HEAD required; bootstrap is separate")
    if type(count) is not int or count < 1:
        raise Blocked("Explicit positive manifest entry count required")


def observe(workspace, expected_workspace, expected_project, expected_branch,
            expected_head, expected_count):
    report = {"mode": "OBSERVE+VALIDATE", "status": "BLOCKED", "checks": [],
              "authorization": "NONE: results do not authorize any action"}

    def check(name, status, message):
        report["checks"].append({"check": name, "status": status, "message": message})

    try:
        validate_expectations(workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
        entered_id = windows_identity(workspace)
        if entered_id != windows_identity(expected_workspace):
            raise Blocked("Workspace differs from expected workspace; no destination inspection")
        entered = Path(entered_id)
        for part in [entered, *entered.parents]:
            no_links(part)
        root = entered.resolve(strict=True)
        if windows_identity(root) != entered_id:
            raise Blocked("Resolved workspace differs from approved lexical identity")
        report["workspace"] = str(root)
        local_autocrlf = bootstrap(root)
        check("bootstrap", "PASS", "Python-only metadata/config/environment checks passed before Git")
        check("config_sources", "WARNING", "Global/system config and attributes disabled without reading them; effective external core.autocrlf unknown")
        gitroot = windows_identity(os.fsdecode(git(root, "rev-parse", "--show-toplevel").strip()))
        report["git_root"] = str(root)
        if gitroot != windows_identity(root):
            raise Blocked("Git root differs from authorized workspace")
        # Scan safe paths before consuming project/manifest content.
        files = inventory(root)
        state = (root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        for label, value in (("Adoption-Status", "ADOPTED"), ("Initialization-Status", "INITIALIZED")):
            if re.findall(r"^" + label + r": (.+)$", state, re.M) != [value]:
                raise Blocked("Operational project is not adopted/initialized; bootstrap requires human decision")
        projects = re.findall(r"^- Project: (.+)$", state, re.M)
        workspaces = re.findall(r"^- Workspace / Git root: (.+?) \(verified\)\.$", state, re.M)
        if (len(projects) != 1 or not (projects[0] == expected_project
                or projects[0].startswith(expected_project + " - "))):
            raise Blocked("Project identity mismatch or ambiguous operational context")
        if len(workspaces) != 1 or windows_identity(workspaces[0]) != windows_identity(root):
            raise Blocked("Operational workspace context mismatch")
        report["project"] = expected_project
        check("identity", "PASS", "Expected workspace, Git root and project match")
        branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).decode().strip()
        head = git(root, "rev-parse", "--verify", "HEAD").decode().strip()
        report.update(branch=branch, head=head)
        check("branch", "PASS" if branch == expected_branch else "BLOCKED", "Expected: " + expected_branch)
        check("head", "PASS" if head == expected_head else "BLOCKED", "Expected: " + expected_head)
        if ".gitattributes" not in files:
            raise Blocked("Missing .gitattributes")
        # Check effective attributes without executing clean/smudge filters.
        args = ["check-attr", "-z", "text", "eol", "filter", "--", *sorted(files)]
        attributes = git(root, *args, attribute_paths=files).split(b"\0")
        policy_errors = []
        for i in range(0, len(attributes) - 1, 3):
            path, attribute, value = map(os.fsdecode, attributes[i:i + 3])
            if ((attribute == "text" and value != "set")
                    or (attribute == "eol" and value != "lf")
                    or (attribute == "filter" and value not in ("unspecified", "unset"))):
                policy_errors.append(path + ": " + attribute + "=" + value)
        cr_files = sorted(p for p in files if b"\r" in (root / p).read_bytes())
        policy_errors.extend(p + ": CR byte violates LF policy" for p in cr_files)
        report["line_endings"] = {"errors": policy_errors, "policy": "text set; eol=lf; no filter; no CR bytes"}
        check("attributes_lf", "BLOCKED" if policy_errors else "PASS", "Effective attributes and working-tree bytes checked")
        if policy_errors:
            return finish(report)
        index_result = compare_index(root, files)
        report["index_comparison"] = index_result
        check("index_bytes", "BLOCKED" if index_result["errors"] else "PASS",
              "Raw working-tree bytes compared with staged blob identities; flags/modes checked")
        records = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
        changes = [os.fsdecode(r) for r in records if r]
        report["working_tree"] = sorted(changes)
        check("working_tree", "BLOCKED" if changes else "PASS", "Clean working tree required")
        staged = git(root, "diff", "--cached", "--name-only", "-z", "--no-ext-diff", "--no-textconv").split(b"\0")
        report["staging"] = sorted(os.fsdecode(p) for p in staged if p)
        check("staging", "BLOCKED" if report["staging"] else "PASS", "Empty staging required")
        remotes = sorted(git(root, "remote").decode().splitlines())
        report["remotes"] = remotes
        check("remotes", "BLOCKED" if remotes else "PASS", "No remotes permitted by the LOCAL_NO_REMOTE profile")
        manifest = validate_manifest(root, files, expected_count)
        report["manifest"] = manifest
        check("manifest", "BLOCKED" if manifest["errors"] else "PASS", "Closed inventory of working-tree bytes")
        autocrlf = local_autocrlf
        report["core.autocrlf"] = autocrlf
        check("autocrlf", "WARNING" if autocrlf == "true" else "PASS",
              "core.autocrlf=" + autocrlf + "; explicit eol=lf remains required")
    except (Blocked, OSError, ValueError, TypeError, KeyError) as error:
        check("inspection", "BLOCKED", str(error))
    return finish(report)


def candidate_paths(paths, root_identity):
    """Canonical comparison keys only; no inspection of input destinations."""
    if not paths:
        raise Blocked("Explicit nonempty candidate paths required")
    keys = []
    for value in paths:
        value = os.fspath(value)
        if not isinstance(value, str) or not value or ntpath.splitdrive(value)[0] or value.startswith(("/", "\\")):
            raise Blocked("Candidate path must be relative; absolute/UNC/device paths blocked")
        identity = windows_identity(ntpath.join(root_identity, value))
        if ntpath.commonpath([root_identity, identity]) != root_identity or identity == root_identity:
            raise Blocked("Candidate path escapes workspace or selects its root")
        key = ntpath.relpath(identity, root_identity).replace("\\", "/")
        if key == ".git" or key.startswith(".git/"):
            raise Blocked("Git metadata cannot be a candidate")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise Blocked("Duplicate candidate paths")
    return set(keys)


def prepare(workspace, expected_workspace, expected_project, expected_branch,
            expected_head, expected_count, paths):
    result = {"mode": "PREPARE", "status": "BLOCKED",
              "authorization": "NONE: preparation does not authorize staging or commit"}
    try:
        selected = candidate_paths(paths, windows_identity(expected_workspace))
        observed = observe(workspace, expected_workspace, expected_project,
                           expected_branch, expected_head, expected_count)
        result["observation"] = observed
        # Only ordinary content differences may be candidates. OBSERVE itself
        # still reports BLOCKED for any dirty working tree/index byte mismatch.
        excluded = {"index_bytes", "working_tree"}
        required = {"bootstrap", "identity", "branch", "head", "attributes_lf",
                    "index_bytes", "working_tree", "staging", "remotes", "manifest"}
        checks = observed["checks"]
        if not required.issubset({c["check"] for c in checks}):
            raise Blocked("Incomplete OBSERVE preflight")
        if any(c["status"] == "BLOCKED" and c["check"] not in excluded for c in checks):
            raise Blocked("Safety preflight failed")
        comparison = observed["index_comparison"]
        if comparison["safety_errors"]:
            raise Blocked("Index safety failure: " + "; ".join(comparison["safety_errors"]))
        changes = comparison["differences"]
        actual = {ntpath.normcase(c["path"]).replace("\\", "/") for c in changes}
        if len(actual) != len(changes):
            raise Blocked("Case-colliding candidate paths unsupported on Windows")
        if selected != actual:
            raise Blocked("Selection must exactly match all real changes; missing="
                          + repr(sorted(actual - selected)) + "; invalid=" + repr(sorted(selected - actual)))
        root = Path(observed["workspace"])
        # Windows filemode=false preserves tracked modes; new ordinary files
        # use 100644. Do not pretend to model executable-bit changes here.
        if git(root, "config", "--local", "--get", "core.filemode", allowed=(0, 1)).strip().lower() != b"false":
            raise Blocked("PREPARE requires explicit local core.filemode=false")
        contract = CONTRACT
        contract_blob = git(root, "cat-file", "blob", observed["head"] + ":" + contract)
        payload = {
            "schema": "starter-candidate-v1", "workspace": observed["workspace"],
            "project": observed["project"], "branch": observed["branch"],
            "expected_parent": observed["head"],
            "policy": {"contract_path": contract,
                       "parent_contract_sha256": hashlib.sha256(contract_blob).hexdigest(),
                       "attributes_sha256": hashlib.sha256((root / ".gitattributes").read_bytes()).hexdigest(),
                       "content": "explicit text/eol=lf; no filters; no CR; SHA-1 Git; filemode=false",
                       "blob_method": "SHA1(b'blob ' + decimal_byte_length + NUL + raw_LF_bytes); no Git object writes"},
            "paths": [c["path"] for c in changes], "path_count": len(changes), "changes": changes,
            "manifest": observed["manifest"],
            "manifest_sha256": hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest(),
            "expected_staging": [], "expected_remotes": [],
            "preflight": {"safety_status": "WARNING" if any(c["status"] == "WARNING" for c in checks) else "PASS",
                          "checks": [c for c in checks if c["check"] not in excluded],
                          "observer_status": observed["status"],
                          "candidate_differences": "EXACT_SELECTION; OBSERVE clean-tree gates remain unchanged"},
            "limitations": ["Not authorization, staging, a staged tree or a staged diff",
                            "No transactional protection against concurrent changes; revalidate before any separately authorized action",
                            "Global/system configuration not read; trusted Git/Python runtime required",
                            "Candidate blob OIDs describe supported LF bytes, not written objects"]}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
        result.update(status="PREPARED_NOT_AUTHORIZED", payload=payload,
                      **{"Candidate-SHA256": hashlib.sha256(canonical).hexdigest(),
                         "canonicalization": "UTF-8 json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False); no newline"})
    except (Blocked, OSError, ValueError, TypeError, KeyError) as error:
        result["error"] = str(error)
    return result


STAGE_DIFF_ARGV = ("diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", "--no-color")
STAGE_DIFF_COMMAND = "git " + " ".join(STAGE_DIFF_ARGV)


def canonical_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def index_entries(raw):
    entries = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, oid, stage = meta.decode("ascii").split()
        if stage != "0" or mode not in ("100644", "100755") or not re.fullmatch(r"[0-9a-f]{40}", oid):
            raise Blocked("Unsupported stage index entry")
        name = os.fsdecode(path)
        if name in entries:
            raise Blocked("Duplicate index entry")
        entries[name] = {"mode": mode, "oid": oid}
    return entries


class _StageTransaction:
    """Private index transaction; instantiated only after authorization binding."""
    def __init__(self, root, original, changes, content, expected_entries):
        self.root, self.original = root, original
        self.index = root / ".git/index"
        self.lock = root / ".git/index.lock"
        self.nested_lock = root / ".git/index.lock.lock"
        self.content = content
        self.expected_entries = expected_entries
        self.active = self.published = self.baseline_validated = False
        self.batch = b"".join((("0 " + "0" * 40 if c["change"] == "D" else c["mode"] + " " + c["blob_oid"])
                               + "\t" + c["path"] + "\0").encode("utf-8") for c in changes)

    def acquire(self):
        if self.lock.exists() or self.nested_lock.exists():
            raise Blocked("Existing index lock; no mutation permitted")
        # Exclusive create also closes the check/create race for Git writers.
        with self.lock.open("xb") as handle:
            self.active = True
        if self.index.read_bytes() != self.original:
            raise Blocked("Index differs from validated baseline under lock")

    def validate_baseline(self):
        if not self.active or self.index.read_bytes() != self.original:
            raise Blocked("Index differs from validated baseline before mutation")
        # Initialize only our private index after semantic revalidation under lock.
        with self.lock.open("wb") as handle:
            handle.write(self.original)
            handle.flush()
            os.fsync(handle.fileno())
        self.baseline_validated = True

    def _run(self, args, data=None, live=False):
        reads = {("ls-files", "--stage", "-z"), STAGE_DIFF_ARGV}
        valid = (args in reads and data is None)
        valid |= (not live and args == ("hash-object", "-w", "--no-filters", "--stdin")
                  and isinstance(data, bytes) and data in self.content.values())
        valid |= (not live and args == ("update-index", "-z", "--index-info") and data == self.batch)
        valid |= (not live and args == ("write-tree",) and data is None)
        if not self.active or not valid or (args not in reads and not self.baseline_validated):
            raise Blocked("Executor Git argv/data outside STAGE_ONLY transaction")
        bootstrap(self.root)
        no_links(self.lock)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_ATTR_NOSYSTEM="1", GIT_NO_REPLACE_OBJECTS="1")
        if not live:
            env["GIT_INDEX_FILE"] = str(self.lock)
        command = ["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
                   "-c", "core.untrackedCache=false", "-c", "core.attributesFile=" + os.devnull,
                   "-c", "core.excludesFile=" + os.devnull, "-c", "gc.auto=0",
                   "-c", "maintenance.auto=false", "-c", "core.hooksPath=" + os.devnull, *args]
        try:
            result = subprocess.run(command, cwd=self.root, env=env, input=data,
                                    capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Blocked("Stage Git unavailable/timed out; objects may remain") from error
        if result.returncode:
            raise Blocked("Stage Git failed: " + " ".join(args))
        return result.stdout

    def entries(self, live=False):
        return index_entries(self._run(("ls-files", "--stage", "-z"), live=live))

    def replace_index(self, raw):
        if not self.active or not self.baseline_validated:
            raise Blocked("No active STAGE_ONLY index transaction")
        no_links(self.lock)
        if raw != self.original and raw != self.lock.read_bytes():
            raise Blocked("Unauthorized index replacement bytes")
        # Keep index.lock present while publishing/verifying/rolling back, so
        # ordinary Git writers remain excluded throughout the transaction.
        no_links(self.root / ".git")
        no_links(self.index)
        fd, name = tempfile.mkstemp(prefix="starter-stage-", dir=self.root / ".git")
        temp = Path(name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.index)
        finally:
            if temp.exists():
                temp.unlink()

    def publish(self):
        if self.index.read_bytes() != self.original:
            raise Blocked("Original index changed despite lock")
        if self.entries() != self.expected_entries:
            raise Blocked("Transaction index contains unauthorized changes")
        self.published = True
        self.replace_index(self.lock.read_bytes())

    def rollback(self):
        if self.published:
            self.replace_index(self.original)
        return self.index.read_bytes() == self.original

    def close(self):
        if self.nested_lock.exists():
            raise Blocked("Nested Git lock remains; manual inspection required")
        if self.active:
            no_links(self.lock)
            self.lock.unlink()
            self.active = False


def execute_stage(workspace, expected_workspace, expected_project, expected_branch,
                  expected_head, expected_count, authorized_candidate=None,
                  authorized_parent=None, authorized_paths=None, scope=None):
    result = {"mode": "EXECUTE-STAGE", "status": "BLOCKED",
              "authorization_limit": "Checks external value binding/scope only; cannot authenticate the human or cryptographic single-use; no commit authorization"}
    transaction = None
    try:
        if (scope != "STAGE_ONLY" or not isinstance(authorized_candidate, str)
                or not re.fullmatch(r"[0-9a-f]{64}", authorized_candidate)
                or not isinstance(authorized_parent, str)
                or not re.fullmatch(r"[0-9a-f]{40}", authorized_parent)
                or authorized_parent != expected_head):
            raise Blocked("Missing/invalid external authorization or parent/scope mismatch")
        candidate_paths(authorized_paths, windows_identity(expected_workspace))
        candidate = prepare(workspace, expected_workspace, expected_project, expected_branch,
                            expected_head, expected_count, authorized_paths)
        if candidate["status"] != "PREPARED_NOT_AUTHORIZED" or candidate["Candidate-SHA256"] != authorized_candidate:
            raise Blocked("Current candidate does not match external authorization")
        payload = candidate["payload"]
        root = Path(payload["workspace"])
        if payload["expected_parent"] != authorized_parent or payload["branch"] != expected_branch:
            raise Blocked("Authorized parent/branch mismatch")
        snapshot = {p: (root / p).read_bytes() for p in inventory(root)}
        content = {}
        initial_entries = index_entries(git(root, "ls-files", "--stage", "-z"))
        expected_entries = {p: dict(v) for p, v in initial_entries.items()}
        for change in payload["changes"]:
            path = change["path"]
            if change["change"] == "D":
                if path in snapshot or expected_entries[path]["oid"] != change["previous_blob_oid"]:
                    raise Blocked("Deletion drift")
                del expected_entries[path]
            else:
                raw = snapshot[path]
                if (b"\r" in raw or len(raw) != change["bytes"]
                        or hashlib.sha256(raw).hexdigest() != change["sha256"]
                        or blob_oid(raw) != change["blob_oid"]):
                    raise Blocked("Authorized byte/OID drift")
                content[path] = raw
                expected_entries[path] = {"mode": change["mode"], "oid": change["blob_oid"]}
        # Bracket semantic validation with the exact same index bytes. Never
        # adopt a later capture as the baseline after PREPARE has passed.
        index_path = root / ".git/index"
        no_links(index_path)
        original = index_path.read_bytes()
        recheck = prepare(workspace, expected_workspace, expected_project, expected_branch,
                          expected_head, expected_count, authorized_paths)
        if recheck["status"] != "PREPARED_NOT_AUTHORIZED" or recheck["Candidate-SHA256"] != authorized_candidate:
            raise Blocked("Candidate changed immediately before execution")
        if index_path.read_bytes() != original:
            raise Blocked("Index changed during candidate revalidation")
        result["validated_index_sha256"] = hashlib.sha256(original).hexdigest()
        config_snapshot = (root / ".git/config").read_bytes()
        identity = index_path.lstat()
        result["original_index"] = {"sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original),
                                    "device": identity.st_dev, "inode": identity.st_ino}
        transaction = _StageTransaction(root, original, payload["changes"], content, expected_entries)
        if transaction.lock.exists() or transaction.nested_lock.exists():
            raise Blocked("Existing index lock")
        if git(root, "rev-parse", "--verify", "HEAD").decode().strip() != authorized_parent:
            raise Blocked("HEAD changed before first mutation")
        transaction.acquire()
        if git(root, "rev-parse", "--verify", "HEAD").decode().strip() != authorized_parent:
            raise Blocked("HEAD changed after lock acquisition")
        locked = prepare(workspace, expected_workspace, expected_project, expected_branch,
                         expected_head, expected_count, authorized_paths)
        if (locked["status"] != "PREPARED_NOT_AUTHORIZED"
                or locked["Candidate-SHA256"] != authorized_candidate
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot):
            raise Blocked("Candidate/HEAD/branch changed before mutation under lock")
        transaction.validate_baseline()
        for change in payload["changes"]:
            if change["change"] != "D":
                oid = transaction._run(("hash-object", "-w", "--no-filters", "--stdin"), content[change["path"]]).decode().strip()
                if oid != change["blob_oid"]:
                    raise Blocked("Git returned an unauthorized blob OID")
        transaction._run(("update-index", "-z", "--index-info"), transaction.batch)
        if transaction.entries() != expected_entries:
            raise Blocked("Private index mismatch")
        tree = transaction._run(("write-tree",)).decode().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", tree):
            raise Blocked("Invalid staged tree OID")
        before_diff = transaction._run(STAGE_DIFF_ARGV)
        if git(root, "rev-parse", "--verify", "HEAD").decode().strip() != authorized_parent:
            raise Blocked("HEAD changed before index publication")
        if {p: (root / p).read_bytes() for p in inventory(root)} != snapshot:
            raise Blocked("Working tree changed before index publication")
        transaction.publish()
        post = observe(workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
        blocked = {c["check"] for c in post["checks"] if c["status"] == "BLOCKED"}
        if (blocked != {"staging", "working_tree"} or post.get("head") != authorized_parent
                or post.get("branch") != expected_branch or post.get("index_comparison", {}).get("errors")):
            raise Blocked("Post-stage safety/HEAD/branch verification failed")
        if {p: (root / p).read_bytes() for p in inventory(root)} != snapshot:
            raise Blocked("Working tree changed during execution")
        if transaction.entries(live=True) != expected_entries:
            raise Blocked("Live index differs from authorized entries")
        diff = transaction._run(STAGE_DIFF_ARGV, live=True)
        if diff != before_diff or index_path.read_bytes() != transaction.lock.read_bytes():
            raise Blocked("Live/private index or diff mismatch")
        receipt = {"schema": "starter-stage-receipt-v1", "scope": "STAGE_ONLY",
                   "Candidate-SHA256": authorized_candidate, "parent": authorized_parent,
                   "branch": expected_branch, "paths": payload["paths"],
                   "staged_blobs": {c["path"]: (None if c["change"] == "D" else c["blob_oid"]) for c in payload["changes"]},
                   "tree_sha": tree, "staged_diff_bytes": len(diff),
                   "staged_diff_sha256": hashlib.sha256(diff).hexdigest(),
                   "staged_diff_command": STAGE_DIFF_COMMAND,
                   "diff_hash_method": "SHA-256 of raw stdout bytes; no decoding/newline conversion",
                   "index_scope": "Complete live index equals original entries plus exactly authorized A/M/D changes",
                   "authorization_limit": "No commit permission; human origin and absolute single-use not authenticated"}
        if (git(root, "rev-parse", "--verify", "HEAD").decode().strip() != authorized_parent
                or git(root, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip() != expected_branch):
            raise Blocked("HEAD/branch changed before receipt completion")
        if (root / ".git/config").read_bytes() != config_snapshot:
            raise Blocked("Repository configuration changed during execution")
        if {p: (root / p).read_bytes() for p in inventory(root)} != snapshot:
            raise Blocked("Working tree changed before receipt completion")
        receipt_hash = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
        transaction.close()
        result.update(status="STAGED_AWAITING_COMMIT_AUTHORIZATION", receipt=receipt,
                      **{"Stage-Receipt-SHA256": receipt_hash,
                         "receipt_canonicalization": "UTF-8 json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False); no newline"})
    except Exception as error:
        result["error"] = str(error)
        if transaction is not None and transaction.active:
            if transaction.baseline_validated:
                try:
                    result["index_rollback_verified"] = transaction.rollback()
                except Exception as rollback_error:
                    result["index_rollback_verified"] = False
                    result["rollback_error"] = str(rollback_error)
            else:
                result["index_rollback"] = "Not attempted: no own mutation; concurrent index preserved"
            try:
                transaction.close()
            except Exception as cleanup_error:
                result["cleanup_error"] = str(cleanup_error)
            result["object_database_rollback"] = "Not guaranteed; unreferenced authorized blobs/trees may remain"
    return result


def plan_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise Blocked("Duplicate JSON key")
            result[key] = item
        return result
    if isinstance(value, str):
        value = json.loads(value, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(Blocked("Nonfinite JSON")))
    if not isinstance(value, dict):
        raise Blocked("Candidate/receipt must be explicit JSON objects, not file paths")
    return value


def git_tree_oid(entries):
    """Calculate the canonical SHA-1 tree in memory; never write Git objects."""
    directory = {}
    for path, entry in entries.items():
        node = directory
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise Blocked("Index file/directory collision")
        if parts[-1] in node:
            raise Blocked("Duplicate index tree path")
        node[parts[-1]] = (entry["mode"], entry["oid"])
    def digest(node):
        rows = []
        for name, child in node.items():
            encoded = name.encode("utf-8")
            mode, oid = ("40000", digest(child)) if isinstance(child, dict) else child
            rows.append((encoded + (b"/" if mode == "40000" else b""),
                         mode.encode("ascii") + b" " + encoded + b"\0" + bytes.fromhex(oid)))
        raw = b"".join(row for _, row in sorted(rows))
        return hashlib.sha1(b"tree " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    return digest(directory)


def plan_snapshot(workspace, expected_workspace, expected_project, expected_branch,
                  expected_head, expected_count):
    validate_expectations(workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
    identity = windows_identity(workspace)
    if identity != windows_identity(expected_workspace):
        raise Blocked("Plan workspace mismatch before filesystem access")
    entered = Path(identity)
    for path in [entered, *entered.parents]:
        no_links(path)
    root = entered.resolve(strict=True)
    if windows_identity(root) != identity:
        raise Blocked("Plan resolved workspace mismatch")
    bootstrap(root)
    index_path = root / ".git/index"
    no_links(index_path)
    original = index_path.read_bytes()
    config = (root / ".git/config").read_bytes()
    entries = index_entries(git(root, "ls-files", "--stage", "-z"))
    candidate_paths(list(entries), identity)  # Validate index names before file reads.
    files = {p: (root / p).read_bytes() for p in inventory(root)}
    observed = observe(root, expected_workspace, expected_project, expected_branch,
                       expected_head, expected_count)
    required = {"bootstrap", "identity", "branch", "head", "attributes_lf",
                "index_bytes", "working_tree", "staging", "remotes", "manifest"}
    checks = observed["checks"]
    if (not required.issubset({c["check"] for c in checks})
            or any(c["status"] == "BLOCKED" and c["check"] not in {"working_tree", "staging"} for c in checks)
            or observed["index_comparison"]["errors"] or not observed["staging"]
            or any(not r.startswith(("M  ", "A  ", "D  ")) for r in observed["working_tree"])):
        raise Blocked("COMMIT-PLAN requires an exact staged snapshot, no unstaged/untracked changes and all safety gates")
    if git(root, "config", "--local", "--get", "core.filemode", allowed=(0, 1)).strip().lower() != b"false":
        raise Blocked("COMMIT-PLAN requires core.filemode=false")
    parent_entries = {}
    for row in git(root, "ls-tree", "-r", "-z", expected_head).split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            if kind != "blob":
                raise Blocked("Unsupported parent tree entry")
            parent_entries[os.fsdecode(path)] = {"mode": mode, "oid": oid}
    candidate_paths(list(parent_entries), identity)
    changes = []
    for path in sorted(set(entries) | set(parent_entries)):
        current, previous = entries.get(path), parent_entries.get(path)
        if current == previous:
            continue
        if current is None:
            changes.append({"path": path, "change": "D", "mode": previous["mode"],
                            "previous_blob_oid": previous["oid"], "blob_oid": None,
                            "bytes": None, "sha256": None})
        else:
            raw = files[path]
            if current["mode"] != (previous["mode"] if previous else "100644") or blob_oid(raw) != current["oid"]:
                raise Blocked("Unsupported staged mode or byte drift")
            changes.append({"path": path, "change": "M" if previous else "A", "mode": current["mode"],
                            "previous_blob_oid": previous["oid"] if previous else None,
                            "blob_oid": current["oid"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    diff = git(root, *STAGE_DIFF_ARGV)
    if index_path.read_bytes() != original:
        raise Blocked("Index changed during plan inspection; no restoration attempted")
    return {"root": str(root), "index": original, "config": config, "files": files,
            "entries": entries, "changes": changes, "manifest": observed["manifest"],
            "staging": observed["staging"], "tree": git_tree_oid(entries), "diff": diff,
            "branch": observed["branch"], "head": observed["head"]}


def plan_identity(name, email):
    if (not isinstance(name, str) or not name or name != name.strip()
            or any(ord(c) < 32 or ord(c) == 127 or c in "<>" for c in name)
            or not isinstance(email, str) or not re.fullmatch(r"[A-Za-z0-9_%+.-]+@[A-Za-z0-9.-]+", email)):
        raise Blocked("Missing/unsupported explicit Git identity; no ambient fallback")
    local, domain = email.split("@")
    if (local.startswith(".") or local.endswith(".") or ".." in local
            or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in domain.split("."))):
        raise Blocked("Unsupported explicit identity email format")
    name.encode("utf-8"); email.encode("utf-8")
    return {"name": name, "email": email}


def commit_plan(workspace, expected_workspace, expected_project, expected_branch,
                expected_head, expected_count, candidate=None, candidate_sha256=None,
                stage_receipt=None, stage_receipt_sha256=None, paths=None,
                message=None, subject=None, author_name=None, author_email=None,
                committer_name=None, committer_email=None, scope=None):
    result = {"mode": "COMMIT-PLAN", "status": "BLOCKED",
              "authorization": "Commit-Intent-SHA256 is a binding identifier, not human authorization."}
    try:
        if scope != "COMMIT_ONLY" or not re.fullmatch(r"[0-9a-f]{40}", expected_head):
            raise Blocked("Explicit COMMIT_ONLY scope and full parent required")
        author, committer = plan_identity(author_name, author_email), plan_identity(committer_name, committer_email)
        if (not isinstance(subject, str) or not subject or subject != subject.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in subject)
                or not isinstance(message, str) or "\0" in message or "\r" in message
                or not message.startswith(subject + "\n\n") or not message[len(subject) + 2:].strip()):
            raise Blocked("Explicit subject and exact UTF-8 LF message with body required; no normalization")
        message_bytes = message.encode("utf-8")
        candidate, receipt = plan_json(candidate), plan_json(stage_receipt)
        for value in (candidate_sha256, stage_receipt_sha256):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise Blocked("Explicit Candidate/Stage-Receipt SHA-256 required")
        if (hashlib.sha256(canonical_bytes(candidate)).hexdigest() != candidate_sha256
                or hashlib.sha256(canonical_bytes(receipt)).hexdigest() != stage_receipt_sha256):
            raise Blocked("Candidate/Stage-Receipt hash mismatch")
        required = {"schema", "scope", "Candidate-SHA256", "parent", "branch", "paths", "staged_blobs", "tree_sha",
                    "staged_diff_bytes", "staged_diff_sha256", "staged_diff_command", "diff_hash_method", "index_scope", "authorization_limit"}
        if (set(receipt) != required or receipt["schema"] != "starter-stage-receipt-v1"
                or receipt["scope"] != "STAGE_ONLY" or receipt["Candidate-SHA256"] != candidate_sha256
                or receipt["parent"] != expected_head or receipt["branch"] != expected_branch
                or receipt["staged_diff_command"] != STAGE_DIFF_COMMAND
                or type(receipt["staged_diff_bytes"]) is not int):
            raise Blocked("Unsupported Stage-Receipt or parent/branch/candidate binding")
        selected = candidate_paths(paths, windows_identity(expected_workspace))
        snapshot = plan_snapshot(workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
        actual = [c["path"] for c in snapshot["changes"]]
        if (receipt["paths"] != sorted(actual) or candidate["paths"] != actual
                or selected != candidate_paths(actual, windows_identity(expected_workspace))
                or snapshot["staging"] != sorted(actual) or candidate["changes"] != snapshot["changes"]
                or candidate["schema"] != "starter-candidate-v1" or candidate["expected_parent"] != expected_head
                or candidate["branch"] != expected_branch or candidate["project"] != expected_project
                or candidate["workspace"] != snapshot["root"] or candidate["path_count"] != len(actual)
                or candidate["expected_staging"] != [] or candidate["expected_remotes"] != []):
            raise Blocked("Candidate/receipt path, blob or parent snapshot mismatch")
        staged_blobs = {c["path"]: c["blob_oid"] for c in snapshot["changes"]}
        if (receipt["tree_sha"] != snapshot["tree"] or receipt["staged_blobs"] != staged_blobs
                or receipt["staged_diff_bytes"] != len(snapshot["diff"])
                or receipt["staged_diff_sha256"] != hashlib.sha256(snapshot["diff"]).hexdigest()):
            raise Blocked("Stage-Receipt tree/blob/diff binding mismatch")
        files = snapshot["files"]
        attributes_hash = hashlib.sha256(files[".gitattributes"]).hexdigest()
        manifest_hash = hashlib.sha256(files[MANIFEST]).hexdigest()
        contract = CONTRACT
        parent_contract = git(Path(snapshot["root"]), "cat-file", "blob", expected_head + ":" + contract)
        parent_contract_hash = hashlib.sha256(parent_contract).hexdigest()
        if (candidate["manifest"] != snapshot["manifest"] or candidate["manifest_sha256"] != manifest_hash
                or candidate["policy"]["attributes_sha256"] != attributes_hash
                or candidate["policy"]["contract_path"] != contract
                or candidate["policy"]["parent_contract_sha256"] != parent_contract_hash):
            raise Blocked("Candidate manifest/attributes/contract policy mismatch")
        intent = {"schema": "starter-commit-intent-v1", "scope": "COMMIT_ONLY",
                  "workspace": snapshot["root"], "project": expected_project,
                  "branch": expected_branch, "parent": expected_head,
                  "Candidate-SHA256": candidate_sha256, "Stage-Receipt-SHA256": stage_receipt_sha256,
                  "tree_sha": snapshot["tree"], "staged_diff_sha256": receipt["staged_diff_sha256"],
                  "staged_diff_bytes": len(snapshot["diff"]), "paths": sorted(actual), "staged_blobs": staged_blobs,
                  "message_utf8_hex": message_bytes.hex(), "message_bytes": len(message_bytes),
                  "Commit-Message-SHA256": hashlib.sha256(message_bytes).hexdigest(), "subject": subject,
                  "author": author, "committer": committer,
                  "policy": {"contract_path": contract, "parent_contract_sha256": parent_contract_hash,
                             "staged_contract_sha256": hashlib.sha256(files[contract]).hexdigest(),
                             "attributes_sha256": attributes_hash, "manifest_sha256": manifest_hash,
                             "staged_diff_command": STAGE_DIFF_COMMAND}}
        intent_hash = hashlib.sha256(canonical_bytes(intent)).hexdigest()
        final = plan_snapshot(workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
        root = Path(snapshot["root"])
        if (final != snapshot
                or git(root, "rev-parse", "--verify", "HEAD").decode().strip() != expected_head
                or git(root, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip() != expected_branch
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot["files"]
                or (root / ".git/config").read_bytes() != snapshot["config"]
                or (root / ".git/index").read_bytes() != snapshot["index"]):
            raise Blocked("Snapshot changed during COMMIT-PLAN; no restoration attempted")
        result.update(status="COMMIT_PLANNED_NOT_AUTHORIZED", intent=intent,
                      **{"Commit-Message-SHA256": intent["Commit-Message-SHA256"], "Commit-Intent-SHA256": intent_hash,
                         "canonicalization": "SHA-256 of UTF-8 json.dumps(intent, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False); no newline",
                         "limitations": ["Identity strings do not prove civil identity or authenticate human authorization",
                                         "No timestamp or future commit OID; future execution time metadata can change the Git OID",
                                         "Read-only repeated observations detect drift; no absolute transactional protection",
                                         "Stage-Receipt, technical approval and tests do not authorize a commit"]})
    except (Blocked, OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        result["error"] = str(error)
    return result


def commit_branch_ref(branch):
    if (not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)
            or ".." in branch or "//" in branch
            or any(not part or part.startswith(".") or (part.endswith(".") or part.lower().endswith(".lock"))
                   or ntpath.isreserved(part) for part in branch.split("/"))):
        raise Blocked("Unsupported explicit branch name")
    return "refs/heads/" + branch


def commit_refs(root):
    refs = {"HEAD": (root / ".git/HEAD").read_bytes()}
    for path in (root / ".git/refs").rglob("*"):
        no_links(path)
        if path.is_file():
            refs[path.relative_to(root / ".git").as_posix()] = path.read_bytes()
    packed = root / ".git/packed-refs"
    if packed.exists():
        no_links(packed)
        refs["packed-refs"] = packed.read_bytes()
    return refs


def commit_locks(root):
    return sorted(p.relative_to(root / ".git").as_posix()
                  for p in (root / ".git").rglob("*.lock"))


def verify_commit_object(raw, oid, intent, timestamp):
    if hashlib.sha1(b"commit " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() != oid:
        raise Blocked("Created commit object OID mismatch")
    header, message = raw.split(b"\n\n", 1)
    rows = header.split(b"\n")
    fields = {}
    for row in rows:
        key, value = row.split(b" ", 1)
        if key in fields or key not in (b"tree", b"parent", b"author", b"committer"):
            raise Blocked("Unsupported/duplicate commit header or additional parent/signature")
        fields[key] = value
    if (set(fields) != {b"tree", b"parent", b"author", b"committer"}
            or fields[b"tree"] != intent["tree_sha"].encode("ascii")
            or fields[b"parent"] != intent["parent"].encode("ascii")
            or message != bytes.fromhex(intent["message_utf8_hex"])
            or hashlib.sha256(message).hexdigest() != intent["Commit-Message-SHA256"]):
        raise Blocked("Created commit tree/parent/message differs from authorized intent")
    identities = {}
    for role in ("author", "committer"):
        who = intent[role]
        expected = (who["name"] + " <" + who["email"] + "> " + str(timestamp) + " +0000").encode("utf-8")
        if fields[role.encode("ascii")] != expected:
            raise Blocked("Created commit identity/date differs from explicit execution metadata")
        identities[role] = dict(who, unix_seconds=timestamp, utc_offset="+0000",
                                git_date="@" + str(timestamp) + " +0000")
    return {"tree": intent["tree_sha"], "parent": intent["parent"],
            "message_sha256": hashlib.sha256(message).hexdigest(),
            "message_bytes": len(message), **identities}


class _CommitExecution:
    """Only commit-tree plus one verified-ref CAS; never changes the index."""
    def __init__(self, root, snapshot, intent):
        self.root, self.snapshot, self.intent = root, snapshot, intent
        self.parent = intent["parent"]
        self.ref = commit_branch_ref(intent["branch"])
        self.ref_path = root / ".git" / self.ref
        self.index, self.lock = root / ".git/index", root / ".git/index.lock"
        self.active = self.ready = self.object_attempted = self.ref_attempted = self.ref_updated = False
        self.object_oid = self.verified_oid = self.ref_returncode = self.lock_identity = None
        self.timestamp = None

    def read_ref(self):
        for path in [self.ref_path, *self.ref_path.parents]:
            if path == self.root:
                break
            no_links(path)
        raw = self.ref_path.read_bytes()
        if not re.fullmatch(rb"[0-9a-f]{40}\n", raw):
            raise Blocked("Only direct loose branch refs supported; no silent ref indirection")
        return raw[:-1].decode("ascii")

    def check_parent(self):
        if (git(self.root, "rev-parse", "--verify", "HEAD").decode().strip() != self.parent
                or git(self.root, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip() != self.intent["branch"]
                or self.read_ref() != self.parent):
            raise Blocked("HEAD/branch/ref changed before mutation")

    def acquire(self):
        if commit_locks(self.root):
            raise Blocked("Unexpected Git lock before execution")
        with self.lock.open("xb") as handle:
            self.active = True
            identity = os.fstat(handle.fileno())
            self.lock_identity = (identity.st_dev, identity.st_ino)
        if self.index.read_bytes() != self.snapshot["index"]:
            raise Blocked("Index differs from validated bytes under exclusive lock")

    def close(self):
        if self.active:
            no_links(self.lock)
            identity = self.lock.lstat()
            if (identity.st_dev, identity.st_ino) != self.lock_identity or self.lock.read_bytes() != b"":
                raise Blocked("Owned lock replaced/changed; manual inspection required")
            self.lock.unlink()
            self.active = False

    def _run(self, args, data=None):
        create = (args == ("commit-tree", self.intent["tree_sha"], "-p", self.parent)
                  and isinstance(data, bytes) and data == bytes.fromhex(self.intent["message_utf8_hex"])
                  and not self.object_attempted)
        update = (self.verified_oid is not None and self.verified_oid == self.object_oid
                  and args == ("update-ref", "--no-deref", self.ref, self.verified_oid, self.parent)
                  and data is None and not self.ref_attempted)
        if not self.active or not self.ready or not (create or update):
            raise Blocked("Commit executor argv/data outside exact COMMIT_ONLY allowlist")
        if type(self.timestamp) is not int or not 0 <= self.timestamp <= 253402300799:
            raise Blocked("Explicit execution timestamp required before mutation")
        bootstrap(self.root)
        if commit_locks(self.root) != ["index.lock"] or self.index.read_bytes() != self.snapshot["index"]:
            raise Blocked("Unexpected lock or index drift before mutation")
        self.check_parent()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_ATTR_NOSYSTEM="1", GIT_NO_REPLACE_OBJECTS="1",
                   GIT_AUTHOR_NAME=self.intent["author"]["name"], GIT_AUTHOR_EMAIL=self.intent["author"]["email"],
                   GIT_COMMITTER_NAME=self.intent["committer"]["name"], GIT_COMMITTER_EMAIL=self.intent["committer"]["email"],
                   GIT_AUTHOR_DATE="@" + str(self.timestamp) + " +0000",
                   GIT_COMMITTER_DATE="@" + str(self.timestamp) + " +0000")
        command = ["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
                   "-c", "core.untrackedCache=false", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                   "-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgsign=false", *args]
        if create:
            self.object_attempted = True
        else:
            self.ref_attempted = True
        try:
            output = subprocess.run(command, cwd=self.root, env=env, input=data,
                                    capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Blocked("Commit subprocess failed/timed out; mutation may have occurred") from error
        if update:
            self.ref_returncode = output.returncode
            self.ref_updated = output.returncode == 0
        if output.returncode:
            raise Blocked("Commit executor Git command failed: " + args[0])
        if create:
            oid = output.stdout.decode("ascii").strip()
            if not re.fullmatch(r"[0-9a-f]{40}", oid):
                raise Blocked("Commit-tree returned no verifiable object OID")
            self.object_oid = oid
        return output.stdout


def execute_commit(workspace, expected_workspace, expected_project, expected_branch,
                   expected_head, expected_count, authorized_intent=None, authorized_parent=None,
                   clock=None, **plan_inputs):
    result = {"mode": "EXECUTE-COMMIT", "status": "BLOCKED",
              "authorization_limit": "External fields bind execution to intent; they do not authenticate civil identity or cryptographically prove human authorization"}
    execution = None
    try:
        if (not isinstance(authorized_intent, str) or not re.fullmatch(r"[0-9a-f]{64}", authorized_intent)
                or authorized_parent != expected_head or plan_inputs.get("scope") != "COMMIT_ONLY"):
            raise Blocked("Explicit intent authorization, parent and COMMIT_ONLY scope required")
        commit_branch_ref(expected_branch)
        values = (workspace, expected_workspace, expected_project, expected_branch, expected_head, expected_count)
        snapshot = plan_snapshot(*values)
        root = Path(snapshot["root"])
        if commit_locks(root):
            raise Blocked("Unexpected Git lock")
        def rebuild():
            planned = commit_plan(*values, **plan_inputs)
            if (planned["status"] != "COMMIT_PLANNED_NOT_AUTHORIZED"
                    or planned["Commit-Intent-SHA256"] != authorized_intent):
                raise Blocked("Reconstructed intent differs from external authorization")
            return planned["intent"]
        intent = rebuild()
        if (root / ".git/index").read_bytes() != snapshot["index"]:
            raise Blocked("Index changed during intent validation")
        refs_before = commit_refs(root)
        result["validated_index_sha256"] = hashlib.sha256(snapshot["index"]).hexdigest()
        execution = _CommitExecution(root, snapshot, intent)
        execution.check_parent()
        execution.acquire()
        if (rebuild() != intent or execution.index.read_bytes() != snapshot["index"]
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot["files"]
                or commit_refs(root) != refs_before):
            raise Blocked("Snapshot/refs drift under lock; no baseline refresh permitted")
        execution.check_parent()
        execution.ready = True
        observed_time = (clock or time.time)()
        if type(observed_time) not in (int, float) or not 0 <= observed_time <= 253402300799:
            raise Blocked("Unsupported execution clock value")
        execution.timestamp = int(observed_time)
        execution._run(("commit-tree", intent["tree_sha"], "-p", expected_head),
                       bytes.fromhex(intent["message_utf8_hex"]))
        oid = execution.object_oid
        actual = verify_commit_object(git(root, "cat-file", "commit", oid), oid, intent, execution.timestamp)
        execution.verified_oid = oid
        # Revalidate after object creation, before the old-OID guarded ref update.
        if (rebuild() != intent or commit_refs(root) != refs_before
                or execution.index.read_bytes() != snapshot["index"]
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot["files"]):
            raise Blocked("Snapshot/HEAD/ref drift after object creation; branch not updated")
        execution._run(("update-ref", "--no-deref", execution.ref, oid, expected_head))
        result["status"] = "COMMITTED_AWAITING_POSTCHECK"
        post = observe(workspace, expected_workspace, expected_project, expected_branch, oid, expected_count)
        expected_refs = dict(refs_before, **{execution.ref: (oid + "\n").encode("ascii")})
        if (post["status"] not in ("PASS", "WARNING") or post.get("head") != oid
                or post.get("branch") != expected_branch or post.get("working_tree") or post.get("staging")
                or post.get("remotes") or post.get("manifest", {}).get("errors")
                or execution.index.read_bytes() != snapshot["index"]
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot["files"]
                or (root / ".git/config").read_bytes() != snapshot["config"]
                or commit_refs(root) != expected_refs or commit_locks(root) != ["index.lock"]):
            raise Blocked("Commit ref updated but postchecks failed; no rollback")
        committed_diff = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", "--no-color", expected_head, oid)
        if committed_diff != snapshot["diff"]:
            raise Blocked("Committed diff differs from authorized staged diff; no rollback")
        if verify_commit_object(git(root, "cat-file", "commit", oid), oid, intent, execution.timestamp) != actual:
            raise Blocked("Commit object changed after ref update")
        execution.close()
        if (commit_locks(root) or commit_refs(root) != expected_refs
                or execution.index.read_bytes() != snapshot["index"]
                or (root / ".git/config").read_bytes() != snapshot["config"]
                or {p: (root / p).read_bytes() for p in inventory(root)} != snapshot["files"]
                or git(root, "rev-parse", "--verify", "HEAD").decode().strip() != oid
                or git(root, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip() != expected_branch):
            raise Blocked("Post-unlock drift; commit is not rolled back")
        receipt = {"schema": "starter-commit-receipt-v1", "status": "COMMIT_EXECUTED_AUTHORIZED",
                   "Commit-Intent-SHA256": authorized_intent, "Candidate-SHA256": intent["Candidate-SHA256"],
                   "Stage-Receipt-SHA256": intent["Stage-Receipt-SHA256"], "scope": "COMMIT_ONLY",
                   "parent": expected_head, "commit_oid": oid, "tree_sha": intent["tree_sha"],
                   "branch": expected_branch, "updated_ref": execution.ref,
                   "Commit-Message-SHA256": actual["message_sha256"], "message_bytes": actual["message_bytes"],
                   "author": actual["author"], "committer": actual["committer"],
                   "dates_authority": "Execution timestamps were explicitly supplied to Git; not previously bound by Commit-Intent V1",
                   "paths": intent["paths"], "blobs": intent["staged_blobs"],
                   "source_staged_diff_sha256": intent["staged_diff_sha256"],
                   "source_staged_diff_bytes": intent["staged_diff_bytes"],
                   "ref_update_method": "git update-ref --no-deref " + execution.ref + " " + oid + " " + expected_head,
                   "postchecks": {"head_branch_parent_tree_message_identity": "PASS", "working_tree_index_manifest": "PASS",
                                  "other_refs_config_remotes": "PASS", "locks_removed": "PASS"}}
        result.update(status="COMMIT_EXECUTED_AUTHORIZED", receipt=receipt,
                      **{"Commit-Receipt-SHA256": hashlib.sha256(canonical_bytes(receipt)).hexdigest(),
                         "canonicalization": "SHA-256 of UTF-8 json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False); no newline",
                         "limitations": ["Dates are execution metadata, not part of authorized Commit-Intent V1",
                                         "Different execution times can produce different commit OIDs and receipts",
                                         "Fields do not authenticate human identity or absolute single-use",
                                         "Index lock coordinates ordinary writers, not arbitrary filesystem/ref writers; no crash-proof transaction"]})
    except Exception as error:
        result["error"] = str(error)
        if execution is not None:
            if execution.ref_attempted and not execution.ref_updated and execution.object_oid:
                try:
                    execution.ref_updated = execution.read_ref() == execution.object_oid
                except Exception as ref_check_error:
                    result["ref_state_error"] = str(ref_check_error)
            result.update(commit_object_attempted=execution.object_attempted, commit_object_oid=execution.object_oid,
                          ref_update_attempted=execution.ref_attempted, ref_update_confirmed=execution.ref_updated)
            if execution.ref_updated:
                result["status"] = "COMMITTED_POSTCHECK_FAILED"
            elif execution.ref_attempted and execution.ref_returncode is None:
                result["status"] = "COMMIT_REF_UPDATE_UNCERTAIN"
            elif execution.object_oid is not None:
                result["status"] = "COMMIT_OBJECT_CREATED_REF_NOT_UPDATED"
            elif execution.object_attempted:
                result["status"] = "COMMIT_OBJECT_CREATION_UNCERTAIN"
            if execution.object_attempted:
                result["object_database_limit"] = "No automatic object removal; an unreferenced commit object may remain"
            if execution.active:
                try:
                    execution.close()
                except Exception as cleanup_error:
                    result["cleanup_error"] = str(cleanup_error)
                    if execution.ref_updated:
                        result["status"] = "COMMITTED_POSTCHECK_FAILED"
            result["recovery"] = "No index/ref/HEAD rollback or automatic retry; human inspection required on partial mutation"
    return result


def finish(report):
    statuses = {c["status"] for c in report["checks"]}
    report["status"] = "BLOCKED" if "BLOCKED" in statuses else "WARNING" if "WARNING" in statuses else "PASS"
    return report


def configured_values(args):
    # Explicit JSON input only: no file lookup or current-directory fallback.
    data = plan_json(args.config_json)
    fields = ("project_name", "workspace", "repository", "work_branch", "default_branch",
              "human_authority", "manifest_path", "contract_path", "supported_profile",
              "remote_policy", "backup_location", "adoption_status", "initialization_status")
    for field in fields:
        value = data.get(field)
        if (not isinstance(value, str) or not value or value != value.strip()
                or any(ord(c) < 32 or c in "<>" for c in value)):
            raise Blocked("Missing or placeholder configuration: " + field)
    if (data["supported_profile"] != PROFILE or data["remote_policy"] != "NONE"
            or data["manifest_path"] != MANIFEST or data["contract_path"] != CONTRACT):
        raise Blocked("Only the documented fixed Windows local profile and paths are supported")
    if data["adoption_status"] != "ADOPTED" or data["initialization_status"] != "INITIALIZED":
        raise Blocked("Configuration is not adopted/initialized; no automatic bootstrap")
    workspace = data["workspace"]
    if windows_identity(data["repository"]) != windows_identity(workspace):
        raise Blocked("Local repository identity must equal the authorized workspace root")
    commit_branch_ref(data["default_branch"])
    if data["work_branch"].casefold() == data["default_branch"].casefold():
        raise Blocked("Execution branch must differ from integration branch")
    for provided in (args.workspace, args.expected_workspace):
        if provided is not None and windows_identity(provided) != windows_identity(workspace):
            raise Blocked("Explicit workspace differs from configuration; no destination inspection")
    if args.expected_project is not None and args.expected_project != data["project_name"]:
        raise Blocked("Explicit project differs from configuration")
    if args.expected_branch is not None and args.expected_branch != data["work_branch"]:
        raise Blocked("Explicit work branch differs from configuration")
    validate_expectations(workspace, workspace, data["project_name"], data["work_branch"],
                          args.expected_head, args.expected_count)
    return (workspace, workspace, data["project_name"], data["work_branch"],
            args.expected_head, args.expected_count)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("observe", "prepare", "execute-stage", "commit-plan", "execute-commit"), default="observe")
    parser.add_argument("--path", action="append", default=[], help="Explicit candidate path; repeat for every real change")
    parser.add_argument("--authorized-candidate")
    parser.add_argument("--authorized-parent")
    parser.add_argument("--authorized-intent")
    parser.add_argument("--authorized-path", action="append", default=[])
    parser.add_argument("--scope")
    for option in ("candidate-json", "candidate-sha256", "stage-receipt-json", "stage-receipt-sha256",
                   "message", "subject", "author-name", "author-email", "committer-name", "committer-email"):
        parser.add_argument("--" + option)
    parser.add_argument("--plan-path", action="append", default=[])
    parser.add_argument("--config-json", help="Explicit initialized configuration JSON object; never a path")
    parser.add_argument("--workspace")
    parser.add_argument("--expected-workspace")
    parser.add_argument("--expected-project")
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--json", action="store_true", help="Deterministic structured report")
    args = parser.parse_args(argv)
    try:
        values = configured_values(args)
    except (Blocked, OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error), "authorization": "NONE"}, sort_keys=True))
        return 2
    auth_present = any((args.authorized_candidate, args.authorized_parent, args.authorized_path, args.scope))
    plan_present = any(getattr(args, field) is not None for field in
                       ("candidate_json", "candidate_sha256", "stage_receipt_json", "stage_receipt_sha256",
                        "message", "subject", "author_name", "author_email", "committer_name", "committer_email")) or bool(args.plan_path)
    if args.command == "execute-commit":
        result = ({"status": "BLOCKED", "error": "Commit execution cannot accept PREPARE/staging selections"}
                  if args.path or args.authorized_candidate or args.authorized_path else
                  execute_commit(*values, authorized_intent=args.authorized_intent, authorized_parent=args.authorized_parent,
                                 candidate=args.candidate_json, candidate_sha256=args.candidate_sha256,
                                 stage_receipt=args.stage_receipt_json, stage_receipt_sha256=args.stage_receipt_sha256,
                                 paths=args.plan_path, message=args.message, subject=args.subject, author_name=args.author_name,
                                 author_email=args.author_email, committer_name=args.committer_name,
                                 committer_email=args.committer_email, scope=args.scope))
    elif args.authorized_intent is not None:
        result = {"status": "BLOCKED", "error": "Intent execution authorization requires separate execute-commit invocation"}
    elif args.command == "commit-plan":
        result = ({"status": "BLOCKED", "error": "Commit planning cannot accept PREPARE/staging arguments"}
                  if args.path or args.authorized_candidate or args.authorized_parent or args.authorized_path else
                  commit_plan(*values, candidate=args.candidate_json, candidate_sha256=args.candidate_sha256,
                              stage_receipt=args.stage_receipt_json, stage_receipt_sha256=args.stage_receipt_sha256,
                              paths=args.plan_path, message=args.message, subject=args.subject, author_name=args.author_name,
                              author_email=args.author_email, committer_name=args.committer_name,
                              committer_email=args.committer_email, scope=args.scope))
    elif plan_present:
        result = {"status": "BLOCKED", "error": "Plan inputs require separate commit-plan invocation"}
    elif args.command == "execute-stage":
        result = ({"status": "BLOCKED", "error": "Use --authorized-path, not --path, for execute-stage"}
                  if args.path else execute_stage(*values, args.authorized_candidate,
                      args.authorized_parent, args.authorized_path, args.scope))
    elif auth_present:
        result = {"status": "BLOCKED", "error": "Authorization fields require a separate execute-stage invocation"}
    else:
        result = prepare(*values, args.path) if args.command == "prepare" else observe(*values)
    if args.command == "observe" and args.path:
        result = {"status": "BLOCKED", "checks": [{"check": "arguments", "status": "BLOCKED", "message": "--path requires prepare"}]}
    if args.json or args.command != "observe" or auth_present or plan_present or args.authorized_intent is not None:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print("OBSERVE + VALIDATE: " + result["status"])
        print("Authorization: NONE; no mutation is authorized by this report")
        for name in ("project", "workspace", "git_root", "branch", "head", "working_tree", "staging", "remotes", "manifest", "core.autocrlf", "index_comparison"):
            if name in result:
                print(name + ": " + json.dumps(result[name], sort_keys=True, ensure_ascii=True))
        for item in result["checks"]:
            print(item["status"] + " " + item["check"] + ": " + item["message"])
        if result.get("line_endings", {}).get("errors"):
            print(json.dumps(result["line_endings"], sort_keys=True))
    return 2 if result["status"] not in ("PASS", "WARNING", "PREPARED_NOT_AUTHORIZED", "STAGED_AWAITING_COMMIT_AUTHORIZATION", "COMMIT_PLANNED_NOT_AUTHORIZED", "COMMIT_EXECUTED_AUTHORIZED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
