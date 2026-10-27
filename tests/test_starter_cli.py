"""Tests mutate only disposable fixture repos under the authorized test sandbox."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import shlex
import builtins
import io
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from starter_cli import observe, prepare, main as command_main
import starter_cli as cli_module

HOST = Path(__file__).resolve().parents[1]
SANDBOX = HOST / ".test-sandbox"


def manifest_data(entries):
    return {"schema": "starter-project-manifest-v1", "version": 1, "status": "GENERATED",
            "profile": cli_module.PROFILE, "scope": cli_module.MANIFEST_SCOPE,
            "exclusions": list(cli_module.MANIFEST_EXCLUSIONS), "entries": entries}


def fixture_config(workspace):
    return {"project_name": "FIXTURE", "workspace": str(workspace), "repository": str(workspace),
            "work_branch": "codex/test", "default_branch": "main", "human_authority": "Fixture",
            "manifest_path": cli_module.MANIFEST, "contract_path": cli_module.CONTRACT,
            "supported_profile": cli_module.PROFILE, "remote_policy": "NONE",
            "backup_location": "NOT_CONFIGURED", "adoption_status": "ADOPTED",
            "initialization_status": "INITIALIZED"}


def main(argv=None):
    # Old CLI regressions get explicit fixture-only config, never runtime defaults.
    args = list(argv or [])
    if "--config-json" not in args and "--workspace" in args:
        workspace = args[args.index("--workspace") + 1]
        args += ["--config-json", json.dumps(fixture_config(workspace))]
    return command_main(args)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        SANDBOX.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix=".observe-test-", dir=SANDBOX)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.g("init", "-b", "codex/test")
        self.g("config", "core.autocrlf", "false")
        (self.root / "evidence").mkdir()
        (self.root / ".gitattributes").write_text("* text eol=lf\n", newline="\n")
        (self.root / "PROJECT_STATE.md").write_text(
            "Adoption-Status: ADOPTED\nInitialization-Status: INITIALIZED\n- Project: FIXTURE - controlled test\n- Workspace / Git root: "
            + str(self.root) + " (verified).\n", newline="\n")
        (self.root / "sample.txt").write_text("sample\n", newline="\n")
        self.refresh_manifest()
        self.commit_fixture()
        self.head = self.g("rev-parse", "HEAD").decode().strip()

    def g(self, *args, data=None):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                   GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
                   GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", *args], cwd=self.root, env=env,
                              input=data, capture_output=True, check=True).stdout

    def refresh_manifest(self):
        entries = []
        for path in (".gitattributes", "PROJECT_STATE.md", "sample.txt"):
            raw = (self.root / path).read_bytes()
            entries.append(dict(path=path, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        (self.root / "evidence/PROJECT_MANIFEST.json").write_text(
            json.dumps(manifest_data(entries), indent=2) + "\n", newline="\n")

    def commit_fixture(self):
        # Plumbing builds isolated test history, never the real project index/refs.
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or ".git" in p.relative_to(self.root).parts:
                continue
            oid = self.g("hash-object", "-w", "--stdin", data=p.read_bytes()).decode().strip()
            self.g("update-index", "--add", "--cacheinfo", "100644", oid,
                   p.relative_to(self.root).as_posix())
        tree = self.g("write-tree").decode().strip()
        commit = self.g("commit-tree", tree, data=b"fixture baseline\n").decode().strip()
        self.g("update-ref", "refs/heads/codex/test", commit)

    def run_observer(self, **overrides):
        args = dict(workspace=self.root, expected_workspace=self.root,
                    expected_project="FIXTURE", expected_branch="codex/test",
                    expected_head=self.head, expected_count=3)
        args.update(overrides)
        return observe(**args)

    def check_status(self, report, name):
        return next(c["status"] for c in report["checks"] if c["check"] == name)

    def test_valid_clean_and_manifest(self):
        result = self.run_observer()
        self.assertEqual(result["status"], "WARNING", result)
        self.assertEqual(self.check_status(result, "identity"), "PASS")
        self.assertEqual(self.check_status(result, "working_tree"), "PASS")
        self.assertEqual(self.check_status(result, "index_bytes"), "PASS")
        self.assertEqual(result["manifest"]["validated"], 3)
        self.assertEqual(result["head"], self.head)

    def test_not_git(self):
        other = self.root / "not-git"
        other.mkdir()
        self.assertEqual(self.run_observer(workspace=other, expected_workspace=other)["status"], "BLOCKED")

    def test_wrong_workspace(self):
        self.assertEqual(self.run_observer(expected_workspace=HOST)["status"], "BLOCKED")

    def test_unexpected_branch(self):
        result = self.run_observer(expected_branch="other")
        self.assertEqual(self.check_status(result, "branch"), "BLOCKED")

    def test_unexpected_head(self):
        self.assertEqual(self.check_status(self.run_observer(expected_head="0" * 40), "head"), "BLOCKED")

    def test_dirty_working_tree(self):
        (self.root / "sample.txt").write_text("changed\n", newline="\n")
        self.assertEqual(self.check_status(self.run_observer(), "working_tree"), "BLOCKED")

    def test_nonempty_staging(self):
        oid = self.g("hash-object", "-w", "--stdin", data=b"staged\n").decode().strip()
        self.g("update-index", "--cacheinfo", "100644", oid, "sample.txt")
        self.assertEqual(self.check_status(self.run_observer(), "staging"), "BLOCKED")

    def test_manifest_bad_hash(self):
        p = self.root / "evidence/PROJECT_MANIFEST.json"
        data = json.loads(p.read_text()); data["entries"][0]["sha256"] = "0" * 64
        p.write_text(json.dumps(data))
        result = self.run_observer()
        self.assertEqual(self.check_status(result, "manifest"), "BLOCKED")
        self.assertEqual(result["manifest"]["validated"], 2)

    def test_missing_file(self):
        (self.root / "sample.txt").unlink()
        result = self.run_observer()
        self.assertTrue(any("Missing file" in e for e in result["manifest"]["errors"]))

    def test_extra_untracked_file(self):
        (self.root / "extra.txt").write_text("extra")
        result = self.run_observer()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("Extra file" in e for e in result["manifest"]["errors"]))

    def test_missing_attributes(self):
        (self.root / ".gitattributes").unlink()
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_incompatible_attributes(self):
        (self.root / ".gitattributes").write_text("* text eol=crlf\n")
        self.assertEqual(self.check_status(self.run_observer(), "attributes_lf"), "BLOCKED")

    def test_autocrlf_true_explicit_lf(self):
        self.g("config", "core.autocrlf", "true")
        result = self.run_observer()
        self.assertEqual(result["status"], "WARNING", result)
        self.assertEqual(self.check_status(result, "attributes_lf"), "PASS")

    def test_unexpected_remote(self):
        self.g("config", "remote.fixture.url", "https://example.invalid/fixture.git")
        result = self.run_observer()
        self.assertEqual(self.check_status(result, "remotes"), "BLOCKED")

    def test_context_project_contamination(self):
        p = self.root / "PROJECT_STATE.md"
        p.write_text(p.read_text().replace("FIXTURE", "FOREIGN"))
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_context_workspace_contamination(self):
        p = self.root / "PROJECT_STATE.md"
        p.write_text(p.read_text().replace(str(self.root), str(HOST)))
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_duplicate_manifest_path(self):
        p = self.root / "evidence/PROJECT_MANIFEST.json"
        data = json.loads(p.read_text()); data["entries"][1] = data["entries"][0]
        p.write_text(json.dumps(data))
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_manifest_path_escape(self):
        p = self.root / "evidence/PROJECT_MANIFEST.json"
        data = json.loads(p.read_text()); data["entries"][0]["path"] = "../outside"
        p.write_text(json.dumps(data))
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_manifest_unsupported_scope(self):
        p = self.root / "evidence/PROJECT_MANIFEST.json"
        data = json.loads(p.read_text()); data["scope"] = "ignore extras"
        p.write_text(json.dumps(data))
        result = self.run_observer()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Unsupported manifest scope", result["checks"][-1]["message"])

    def test_manifest_invalid_json(self):
        (self.root / "evidence/PROJECT_MANIFEST.json").write_text("{")
        self.assertEqual(self.run_observer()["status"], "BLOCKED")

    def test_crlf_bytes_rejected(self):
        (self.root / "sample.txt").write_bytes(b"sample\r\n")
        self.assertEqual(self.check_status(self.run_observer(), "attributes_lf"), "BLOCKED")

    def test_filter_rejected_without_execution(self):
        (self.root / ".gitattributes").write_text("* text eol=lf filter=unknown\n")
        self.assertEqual(self.check_status(self.run_observer(), "attributes_lf"), "BLOCKED")

    def sentinel_command(self):
        # Must never execute during inspection. Dirty bytes ensure a conversion
        # would be relevant if status ran before the protective gate.
        marker = self.root / "EXECUTED_SENTINEL"
        script = self.root / "sentinel.py"
        script.write_text("from pathlib import Path; Path(" + repr(str(marker))
                          + ").write_text('unsafe process executed')\n")
        command = shlex.quote(sys.executable) + " " + shlex.quote(str(script))
        return marker, command

    def assert_bootstrap_blocked(self, marker=None):
        # Proves that no Git subprocess is reached; sentinel provides a second
        # real-execution guard independently of the mocked call counter.
        with patch("starter_cli.subprocess.run", wraps=subprocess.run) as calls:
            result = self.run_observer()
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(calls.call_count, 0, result)
        if marker is not None:
            self.assertFalse(marker.exists())
        return result

    def test_clean_filter_sentinel_blocked_before_git(self):
        marker, command = self.sentinel_command()
        self.g("config", "filter.attack.clean", command)
        (self.root / ".gitattributes").write_text("* text eol=lf filter=attack\n")
        (self.root / "sample.txt").write_text("dirty for filter\n")
        self.assert_bootstrap_blocked(marker)
        # Real unmocked inspection also must not trigger the configured program.
        self.assertEqual(self.run_observer()["status"], "BLOCKED")
        self.assertFalse(marker.exists())

    def test_process_filter_sentinel_blocked_before_git(self):
        marker, command = self.sentinel_command()
        self.g("config", "filter.attack.process", command)
        (self.root / ".gitattributes").write_text("* text eol=lf filter=attack\n")
        (self.root / "sample.txt").write_text("dirty for process\n")
        self.assert_bootstrap_blocked(marker)
        self.assertEqual(self.run_observer()["status"], "BLOCKED")
        self.assertFalse(marker.exists())

    def test_smudge_filter_sentinel_blocked_before_git(self):
        marker, command = self.sentinel_command()
        self.g("config", "filter.attack.smudge", command)
        self.assert_bootstrap_blocked(marker)

    def test_fsmonitor_sentinel_blocked_before_git(self):
        marker, command = self.sentinel_command()
        self.g("config", "core.fsmonitor", command)
        self.assert_bootstrap_blocked(marker)
        self.assertEqual(self.run_observer()["status"], "BLOCKED")
        self.assertFalse(marker.exists())

    def test_external_include_not_followed(self):
        marker, command = self.sentinel_command()
        # 'external' means outside fixture repository, still inside the
        # explicitly authorized disposable sandbox of this test.
        with tempfile.TemporaryDirectory(prefix=".outside-fixture-", dir=SANDBOX) as external:
            config = Path(external) / "danger.config"
            config.write_text('[filter "attack"]\n clean = ' + command + "\n")
            self.g("config", "include.path", str(config))
            with patch("pathlib.Path.read_text", autospec=True, wraps=Path.read_text) as read:
                # Record accesses with a side effect to retain ordinary behavior.
                reads = []
                def read_text(path, *args, **kwargs):
                    reads.append(path.resolve())
                    return Path.read_bytes(path).decode(kwargs.get("encoding", "utf-8"))
                read.side_effect = read_text
                self.assert_bootstrap_blocked(marker)
            self.assertNotIn(config.resolve(), reads)

    def test_internal_include_conservatively_blocked(self):
        config = self.root / ".git" / "included.config"
        config.write_text("[core]\n autocrlf = false\n")
        self.g("config", "include.path", str(config))
        self.assert_bootstrap_blocked()

    def test_external_commondir_blocked(self):
        with tempfile.TemporaryDirectory(prefix=".outside-fixture-", dir=SANDBOX) as external:
            (self.root / ".git/commondir").write_text(external + "\n")
            self.assert_bootstrap_blocked()

    def test_external_alternate_blocked(self):
        with tempfile.TemporaryDirectory(prefix=".outside-fixture-", dir=SANDBOX) as external:
            (self.root / ".git/objects/info/alternates").write_text(external + "\n")
            self.assert_bootstrap_blocked()

    def test_gitdir_file_escape_blocked(self):
        dotgit = self.root / ".git"
        dotgit.rename(self.root / "original-git")
        dotgit.write_text("gitdir: ../outside\n")
        self.assert_bootstrap_blocked()

    def test_git_env_redirections_blocked(self):
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                     "GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS",
                     "GIT_EXEC_PATH"):
            with self.subTest(variable=name), patch.dict(os.environ, {name: "not-authorized"}):
                self.assert_bootstrap_blocked()

    def test_diff_external_sentinel_blocked(self):
        marker, command = self.sentinel_command()
        self.g("config", "diff.external", command)
        self.assert_bootstrap_blocked(marker)

    def test_textconv_sentinel_blocked(self):
        marker, command = self.sentinel_command()
        self.g("config", "diff.attack.textconv", command)
        self.assert_bootstrap_blocked(marker)

    def test_assume_unchanged_hidden_modification_detected(self):
        self.g("update-index", "--assume-unchanged", "sample.txt")
        (self.root / "sample.txt").write_text("hidden difference\n", newline="\n")
        status = self.g("status", "--porcelain")
        self.assertNotIn(b"sample.txt", status)
        result = self.run_observer()
        self.assertEqual(self.check_status(result, "index_bytes"), "BLOCKED")
        errors = result["index_comparison"]["errors"]
        self.assertTrue(any("assume-unchanged" in e for e in errors))
        self.assertTrue(any("blob mismatch" in e for e in errors))

    def test_skip_worktree_hidden_modification_detected(self):
        self.g("update-index", "--skip-worktree", "sample.txt")
        (self.root / "sample.txt").write_text("hidden difference\n", newline="\n")
        self.assertNotIn(b"sample.txt", self.g("status", "--porcelain"))
        result = self.run_observer()
        self.assertEqual(self.check_status(result, "index_bytes"), "BLOCKED")
        errors = result["index_comparison"]["errors"]
        self.assertTrue(any("skip-worktree" in e for e in errors))
        self.assertTrue(any("blob mismatch" in e for e in errors))

    def test_local_autocrlf_reported_without_global_read(self):
        result = self.run_observer()
        self.assertEqual(result["core.autocrlf"], "false")
        self.assertEqual(self.check_status(result, "config_sources"), "WARNING")

    def test_global_config_sentinel_not_read_or_executed(self):
        marker, command = self.sentinel_command()
        home = self.root / "external-home"
        home.mkdir()
        (home / ".gitconfig").write_text("[core]\n fsmonitor = " + command + "\n")
        # HOME points at an unauthorized config source but is not followed by Git.
        with patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home),
                                     "XDG_CONFIG_HOME": str(home)}):
            result = self.run_observer()
        self.assertFalse(marker.exists())
        self.assertEqual(self.check_status(result, "bootstrap"), "PASS")

    def test_symlink_objects_blocked_before_git(self):
        objects = self.root / ".git/objects"
        moved = self.root / "object-copy"
        objects.rename(moved)
        try:
            objects.symlink_to(moved, target_is_directory=True)
        except OSError:
            moved.rename(objects)
            self.skipTest("OS does not permit creating symlink in test environment")
        self.assert_bootstrap_blocked()

    def test_confined_gitdir_layout_still_blocked(self):
        dotgit = self.root / ".git"
        dotgit.rename(self.root / "local-git")
        dotgit.write_text("gitdir: local-git\n")
        self.assert_bootstrap_blocked()

    def test_unsupported_index_mode_blocked(self):
        oid = self.g("hash-object", "-w", "--stdin", data=b"target").decode().strip()
        self.g("update-index", "--cacheinfo", "120000", oid, "sample.txt")
        result = self.run_observer()
        self.assertEqual(self.check_status(result, "index_bytes"), "BLOCKED")
        self.assertTrue(any("Unsupported index mode" in e for e in result["index_comparison"]["errors"]))

    def assert_rejected_without_destination_access(self, value, field="document"):
        attempts = []
        foreign = str(Path(value)).replace("\\", "/").casefold().rstrip("/")
        original_read = Path.read_text
        original_git = __import__("starter_cli").git

        def reject_foreign(path):
            if isinstance(path, (str, bytes, os.PathLike)):
                text = os.fsdecode(path).replace("\\", "/").casefold().rstrip("/")
                if text == foreign or text.startswith(foreign + "/"):
                    attempts.append(text)
                    raise AssertionError("Foreign destination inspection: " + repr(text))

        def guarded(fn):
            def call(path, *args, **kwargs):
                reject_foreign(path)
                return fn(path, *args, **kwargs)
            return call

        def read_text(path, *args, **kwargs):
            reject_foreign(path)
            text = original_read(path, *args, **kwargs)
            if field == "document" and path == self.root / "PROJECT_STATE.md":
                return text.replace(str(self.root), value)
            if field == "manifest" and path == self.root / "evidence/PROJECT_MANIFEST.json":
                data = json.loads(text)
                data["entries"][0]["path"] = value
                return json.dumps(data)
            return text

        def read_git(root, *args, **kwargs):
            if field == "git_root" and args == ("rev-parse", "--show-toplevel"):
                return value.encode()
            return original_git(root, *args, **kwargs)

        with ExitStack() as stack:
            for name in ("resolve", "absolute", "stat", "lstat", "exists", "is_file", "is_dir",
                         "is_symlink", "open", "iterdir", "glob", "rglob", "read_bytes"):
                stack.enter_context(patch.object(Path, name, guarded(getattr(Path, name))))
            for obj, names in ((os, ("stat", "lstat", "open", "scandir", "listdir", "walk")),
                               (builtins, ("open",)), (io, ("open",))):
                for name in names:
                    stack.enter_context(patch.object(obj, name, guarded(getattr(obj, name))))
            stack.enter_context(patch.object(Path, "read_text", read_text))
            stack.enter_context(patch("starter_cli.git", side_effect=read_git))
            overrides = {field: value} if field in ("workspace", "expected_workspace") else {}
            result = self.run_observer(**overrides)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(attempts, [])
        return result

    def test_document_unc_zero_destination_access(self):
        self.assert_rejected_without_destination_access(r"\\foreign.invalid\share\OTHER_PROJECT")

    def test_document_extended_device_zero_destination_access(self):
        self.assert_rejected_without_destination_access(r"\\?\D:\OTHER_PROJECT")

    def test_document_dot_device_zero_destination_access(self):
        self.assert_rejected_without_destination_access(r"\\.\D:\OTHER_PROJECT")

    def test_document_relative_zero_destination_access(self):
        self.assert_rejected_without_destination_access("foreign-project")

    def test_document_drive_relative_zero_destination_access(self):
        self.assert_rejected_without_destination_access("D:foo")

    def test_document_foreign_local_zero_destination_access(self):
        self.assert_rejected_without_destination_access(str(self.root.parent / "FOREIGN_PROJECT"))

    def test_document_invalid_forms_zero_destination_access(self):
        for value in ("D:\\bad\x00name", "D:\\bad?name", "D:\\bad:name", "D:\\trailing. ",
                      "D:\\NUL", "D:\\COM1.txt", "D:\\bad\nname", "\\rooted-relative",
                      "//foreign.invalid/share/OTHER_PROJECT", "C:/OTHER_PROJECT"):
            with self.subTest(value=repr(value)):
                self.assert_rejected_without_destination_access(value)

    def test_expectation_paths_zero_destination_access(self):
        for value in (r"\\foreign.invalid\share\OTHER_PROJECT", r"\\?\D:\OTHER_PROJECT",
                      r"\\.\D:\OTHER_PROJECT", "relative", "D:foo",
                      str(self.root.parent / "FOREIGN_PROJECT")):
            for field in ("expected_workspace", "workspace", "git_root", "manifest"):
                with self.subTest(value=value, field=field):
                    self.assert_rejected_without_destination_access(value, field)

    def test_document_safe_lexical_equivalence(self):
        original_read = Path.read_text
        root = str(self.root)
        values = [root.upper(), root.replace("\\", "/") + "/", root + "\\.\\",
                  root + "\\not-inspected\\..\\", root + "\\..\\" + self.root.name]
        for value in values:
            with self.subTest(value=value):
                def read(path, *args, **kwargs):
                    text = original_read(path, *args, **kwargs)
                    return text.replace(root, value) if path == self.root / "PROJECT_STATE.md" else text
                with patch.object(Path, "read_text", read):
                    result = self.run_observer()
                self.assertEqual(self.check_status(result, "identity"), "PASS", result)
                self.assertEqual(result["status"], "WARNING", result)

    def test_expectation_safe_lexical_equivalence(self):
        value = str(self.root).upper().replace("\\", "/") + "/unused/../"
        result = self.run_observer(expected_workspace=value)
        self.assertEqual(result["status"], "WARNING", result)
        self.assertEqual(self.check_status(result, "identity"), "PASS")

    def test_mock_reparse_objects_blocked_before_git(self):
        original = Path.lstat
        seen = []
        def lstat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == self.root / ".git/objects":
                seen.append(str(path))
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        with patch.object(Path, "lstat", lstat):
            self.assert_bootstrap_blocked()
        self.assertTrue(seen)

    def test_readonly_and_deterministic(self):
        def snapshot():
            return {p.relative_to(self.root).as_posix(): p.read_bytes()
                    for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        first, second = self.run_observer(), self.run_observer()
        self.assertEqual(first, second)
        self.assertEqual(snapshot(), before)  # includes index, refs and config

    def test_git_failure_understandable(self):
        with patch("starter_cli.subprocess.run", side_effect=FileNotFoundError):
            result = self.run_observer()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Git unavailable", result["checks"][-1]["message"])

    def test_cli_blocked_exit_code_and_json(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--workspace", str(self.root), "--expected-workspace", str(self.root),
                         "--expected-project", "FOREIGN", "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED")


class PrepareTests(unittest.TestCase):
    g = ObserverTests.g
    commit_fixture = ObserverTests.commit_fixture

    def refresh_manifest(self):
        import starter_cli as module
        entries = []
        for name in sorted(module.inventory(self.root) - {"evidence/PROJECT_MANIFEST.json"}):
            raw = (self.root / name).read_bytes()
            entries.append(dict(path=name, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        (self.root / "evidence/PROJECT_MANIFEST.json").write_text(json.dumps(manifest_data(entries), indent=2) + "\n", newline="\n")
        self.count = len(entries)

    def setUp(self):
        ObserverTests.setUp(self)
        (self.root / "docs").mkdir()
        (self.root / "docs/AUTOMATION_CONTRACT_V1.md").write_text("Fixture policy, no authority.\n", newline="\n")
        self.refresh_manifest()
        self.commit_fixture()
        self.head = self.g("rev-parse", "HEAD").decode().strip()

    def run_prepare(self, paths, **overrides):
        args = dict(workspace=self.root, expected_workspace=self.root,
                    expected_project="FIXTURE", expected_branch="codex/test",
                    expected_head=self.head, expected_count=self.count, paths=paths)
        args.update(overrides)
        return prepare(**args)

    def modify(self, text="modified\n"):
        (self.root / "sample.txt").write_text(text, newline="\n")
        self.refresh_manifest()
        return ["sample.txt", "evidence/PROJECT_MANIFEST.json"]

    def assert_prepared(self, result):
        self.assertEqual(result["status"], "PREPARED_NOT_AUTHORIZED", result)
        self.assertIn("does not authorize", result["authorization"])
        payload = result["payload"]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), result["Candidate-SHA256"])
        self.assertEqual(payload["expected_parent"], self.head)
        self.assertEqual(payload["expected_staging"], [])
        self.assertEqual(payload["paths"], sorted(payload["paths"]))
        return payload

    def test_modified_selected(self):
        paths = self.modify()
        payload = self.assert_prepared(self.run_prepare(paths))
        entry = next(c for c in payload["changes"] if c["path"] == "sample.txt")
        self.assertEqual(entry["change"], "M")
        self.assertEqual(entry["sha256"], hashlib.sha256(b"modified\n").hexdigest())
        expected_oid = self.g("hash-object", "--stdin", data=b"modified\n").decode().strip()
        self.assertEqual(entry["blob_oid"], expected_oid)
        self.assertNotEqual(entry["previous_blob_oid"], expected_oid)
        self.assertEqual(payload["preflight"]["observer_status"], "BLOCKED")

    def test_new_selected(self):
        (self.root / "new.txt").write_text("new\n", newline="\n")
        self.refresh_manifest()
        payload = self.assert_prepared(self.run_prepare(["new.txt", "evidence/PROJECT_MANIFEST.json"]))
        entry = next(c for c in payload["changes"] if c["path"] == "new.txt")
        self.assertEqual((entry["change"], entry["mode"], entry["previous_blob_oid"]), ("A", "100644", None))

    def test_deleted_selected(self):
        (self.root / "sample.txt").unlink()
        self.refresh_manifest()
        payload = self.assert_prepared(self.run_prepare(["sample.txt", "evidence/PROJECT_MANIFEST.json"]))
        entry = next(c for c in payload["changes"] if c["path"] == "sample.txt")
        self.assertEqual(entry["change"], "D")
        self.assertIsNone(entry["blob_oid"])
        self.assertIsNone(entry["sha256"])
        self.assertIsNone(entry["bytes"])
        self.assertEqual(len(entry["previous_blob_oid"]), 40)

    def test_multiple_order_and_determinism(self):
        paths = self.modify()
        (self.root / "new.txt").write_text("new\n", newline="\n")
        self.refresh_manifest(); paths.append("new.txt")
        first, second = self.run_prepare(paths), self.run_prepare(list(reversed(paths)))
        self.assert_prepared(first)
        self.assertEqual(first, second)

    def test_unselected_change_blocked(self):
        self.modify()
        self.assertEqual(self.run_prepare(["sample.txt"])["status"], "BLOCKED")

    def test_selected_unchanged_blocked(self):
        paths = self.modify() + ["PROJECT_STATE.md"]
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_empty_selection_blocked(self):
        self.assertEqual(self.run_prepare([])["status"], "BLOCKED")

    def test_duplicate_selection_blocked(self):
        paths = self.modify() + ["./sample.txt"]
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_nonempty_staging_blocked(self):
        paths = self.modify()
        oid = self.g("hash-object", "-w", "--stdin", data=b"staged\n").decode().strip()
        self.g("update-index", "--cacheinfo", "100644", oid, "sample.txt")
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_foreign_paths_blocked_before_any_inspection(self):
        values = [str(self.root.parent / "FOREIGN"), "../FOREIGN/file.txt",
                  r"\\foreign.invalid\share\file.txt", r"\\?\D:\file.txt", r"\\.\D:\file.txt",
                  "D:foo", "bad\x00path", ".git/config"]
        for value in values:
            with self.subTest(value=repr(value)), patch("starter_cli.observe") as observer, \
                    patch.object(Path, "resolve", side_effect=AssertionError("resolve")), \
                    patch.object(Path, "stat", side_effect=AssertionError("stat")), \
                    patch.object(Path, "lstat", side_effect=AssertionError("lstat")), \
                    patch.object(Path, "exists", side_effect=AssertionError("exists")), \
                    patch.object(Path, "open", side_effect=AssertionError("open")), \
                    patch("os.scandir", side_effect=AssertionError("scandir")):
                result = self.run_prepare([value])
                self.assertEqual(result["status"], "BLOCKED", result)
                observer.assert_not_called()

    def test_reparse_point_blocked(self):
        paths = self.modify()
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == self.root / "sample.txt":
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        with patch.object(Path, "lstat", lstat):
            self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_index_flags_blocked(self):
        paths = self.modify()
        for flag, undo in (("--assume-unchanged", "--no-assume-unchanged"),
                           ("--skip-worktree", "--no-skip-worktree")):
            with self.subTest(flag=flag):
                self.g("update-index", flag, "sample.txt")
                result = self.run_prepare(paths)
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertIn("Index safety failure", result["error"])
                self.g("update-index", undo, "sample.txt")

    def test_invalid_manifest_blocked(self):
        paths = self.modify()
        p = self.root / "evidence/PROJECT_MANIFEST.json"
        d = json.loads(p.read_text()); d["entries"][0]["sha256"] = "0" * 64
        p.write_text(json.dumps(d), newline="\n")
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_byte_change_changes_candidate(self):
        paths = self.modify("A\n"); first = self.run_prepare(paths)
        self.modify("B\n"); second = self.run_prepare(paths)
        self.assert_prepared(first); self.assert_prepared(second)
        self.assertNotEqual(first["Candidate-SHA256"], second["Candidate-SHA256"])

    def test_head_change_invalidates_expectation(self):
        paths = self.modify(); first = self.run_prepare(paths)
        self.assert_prepared(first)
        tree = self.g("rev-parse", "HEAD^{tree}").decode().strip()
        new = self.g("commit-tree", tree, "-p", self.head, data=b"fixture HEAD change\n").decode().strip()
        self.g("update-ref", "refs/heads/codex/test", new)
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")
        newer = self.run_prepare(paths, expected_head=new)
        self.assertEqual(newer["status"], "PREPARED_NOT_AUTHORIZED", newer)
        self.assertNotEqual(first["Candidate-SHA256"], newer["Candidate-SHA256"])
        self.assertNotEqual(first["payload"]["expected_parent"], newer["payload"]["expected_parent"])

    def test_prepare_readonly_with_command_guard(self):
        paths = self.modify()
        def snapshot():
            return {p.relative_to(self.root).as_posix(): p.read_bytes()
                    for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        real_run = subprocess.run
        commands = []
        forbidden = {"add", "commit", "commit-tree", "write-tree", "hash-object", "update-index",
                     "checkout", "reset", "restore", "update-ref", "mktree", "read-tree",
                     "clean", "apply", "bundle", "push", "tag", "fetch", "pull", "init", "clone"}
        def run(command, *args, **kwargs):
            commands.append(command)
            self.assertFalse(set(command) & forbidden, command)
            self.assertFalse(any(str(a).startswith("--output") for a in command), command)
            return real_run(command, *args, **kwargs)
        with patch("starter_cli.subprocess.run", side_effect=run):
            self.assert_prepared(self.run_prepare(paths))
            self.assert_prepared(self.run_prepare(list(reversed(paths))))
        self.assertTrue(commands)
        self.assertEqual(snapshot(), before)  # includes index, objects, refs, config

    def test_case_only_rename_blocked_as_ambiguous(self):
        (self.root / "sample.txt").rename(self.root / "SAMPLE.txt")
        self.refresh_manifest()
        result = self.run_prepare(["sample.txt", "evidence/PROJECT_MANIFEST.json"])
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("Case-colliding", result["error"])

    def test_mutable_git_verbs_rejected_before_subprocess(self):
        import starter_cli as module
        cases = [(verb,) for verb in ("add", "commit", "commit-tree", "write-tree", "update-index",
                 "checkout", "reset", "restore", "update-ref", "mktree", "read-tree", "clean",
                 "apply", "bundle", "push", "tag", "fetch", "pull", "init", "clone")]
        cases += [("hash-object", "-w", "--stdin"), ("remote", "add", "x", "url"),
                  ("config", "core.autocrlf", "true"), ("diff", "--output=bad")]
        with patch("starter_cli.subprocess.run", side_effect=AssertionError("Mutable Git call")):
            for args in cases:
                with self.subTest(args=args), self.assertRaises(module.Blocked):
                    module.git(self.root, *args)

    def test_crlf_candidate_blocked(self):
        paths = self.modify()
        (self.root / "sample.txt").write_bytes(b"bad\r\n")
        self.refresh_manifest()
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_executable_filemode_not_claimed(self):
        paths = self.modify()
        self.g("config", "core.filemode", "true")
        self.assertEqual(self.run_prepare(paths)["status"], "BLOCKED")

    def test_cli_prepare_stdout_only(self):
        paths = self.modify()
        out = io.StringIO()
        args = ["prepare", "--workspace", str(self.root), "--expected-workspace", str(self.root),
                "--expected-project", "FIXTURE", "--expected-branch", "codex/test",
                "--expected-head", self.head, "--expected-count", str(self.count)]
        for path in paths:
            args += ["--path", path]
        from contextlib import redirect_stdout
        with redirect_stdout(out):
            code = main(args)
        self.assertEqual(code, 0)
        self.assert_prepared(json.loads(out.getvalue()))


class GitArgvGuardTests(unittest.TestCase):
    FIXED = {
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
    }

    def known_forms(self):
        return [(args, {}) for args in sorted(self.FIXED)] + [
            (("cat-file", "blob", "a" * 40), {}),
            (("cat-file", "blob", "b" * 40 + ":docs/AUTOMATION_CONTRACT_V1.md"), {}),
            (("check-attr", "-z", "text", "eol", "filter", "--", "README.md", "sample.txt"),
             {"attribute_paths": {"README.md", "sample.txt"}})]

    def assert_blocked_before_subprocess(self, args, **kwargs):
        import starter_cli as module
        with patch("starter_cli.subprocess.run") as run:
            with self.assertRaises(module.Blocked):
                module.git(HOST, *args, **kwargs)
            run.assert_not_called()

    def test_symbolic_ref_exact_readonly_form_accepted(self):
        import starter_cli as module
        args = ("symbolic-ref", "--quiet", "--short", "HEAD")
        with patch("starter_cli.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"branch\n")) as run:
            self.assertEqual(module.git(HOST, *args), b"branch\n")
            run.assert_called_once()
            self.assertEqual(tuple(run.call_args.args[0][-len(args):]), args)

    def test_symbolic_ref_write_delete_variants_blocked(self):
        cases = [
            ("symbolic-ref", "HEAD", "refs/heads/other"),
            ("symbolic-ref", "--delete", "HEAD"),
            ("symbolic-ref", "-d", "HEAD"),
            ("symbolic-ref", "HEAD", "--delete"),
            ("symbolic-ref", "--quiet", "--delete", "HEAD"),
            ("symbolic-ref", "--delete", "--quiet", "HEAD"),
            ("symbolic-ref", "--short", "HEAD", "refs/heads/other"),
            ("symbolic-ref", "--quiet", "--short", "HEAD", "refs/heads/other"),
            ("symbolic-ref", "-m", "message", "HEAD", "refs/heads/other"),
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assert_blocked_before_subprocess(args)

    def test_symbolic_ref_other_reference_options_and_extra_blocked(self):
        for args in [("symbolic-ref", "--quiet", "--short", "refs/heads/other"),
                     ("symbolic-ref", "--quiet", "--short", "HEAD", "extra"),
                     ("symbolic-ref", "--short", "--quiet", "HEAD"),
                     ("symbolic-ref", "--unknown", "HEAD"), ("symbolic-ref",)]:
            with self.subTest(args=args):
                self.assert_blocked_before_subprocess(args)

    def test_all_known_forms_accepted_without_argument_rewrite(self):
        import starter_cli as module
        self.assertEqual(module.READ_ONLY_GIT_FORMS, self.FIXED)
        for args, kwargs in self.known_forms():
            with self.subTest(args=args), patch("starter_cli.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"ok")) as run:
                self.assertEqual(module.git(HOST, *args, **kwargs), b"ok")
                run.assert_called_once()
                self.assertEqual(tuple(run.call_args.args[0][-len(args):]), args)

    def test_every_known_form_rejects_arbitrary_extensions(self):
        for args, kwargs in self.known_forms():
            for extension in (("--unexpected",), ("unexpected-extra",), ("--", "extra")):
                with self.subTest(args=args, extension=extension):
                    self.assert_blocked_before_subprocess(args + extension, **kwargs)

    def test_other_verbs_are_not_sufficient_and_unknown_blocked(self):
        cases = [(), ("unknown-command",), ("rev-parse", "--git-path", "../foreign"),
                 ("ls-files", "--stage", "-z", "--debug"),
                 ("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored"),
                 ("diff", "--no-index", "foreign-a", "foreign-b"),
                 ("diff", "--out=forbidden-file"), ("diff", "--output", "forbidden-file"),
                 ("config", "--local", "core.autocrlf", "true"),
                 ("remote", "add", "x", "https://invalid.invalid/repo")]
        cases += [(verb,) for verb in ("add", "commit", "update-index", "write-tree", "reset", "restore",
                  "checkout", "update-ref", "read-tree", "mktree", "clean", "apply", "fetch", "pull",
                  "push", "tag", "bundle", "init", "clone", "commit-tree")]
        cases.append(("hash-object", "-w", "--stdin"))
        for args in cases:
            with self.subTest(args=args):
                self.assert_blocked_before_subprocess(args)

    def test_cat_file_only_hex_blob_or_exact_parent_contract(self):
        for value in ("HEAD", "HEAD:README.md", "--textconv", "--filters", "a" * 39,
                      "g" * 40, "a" * 40 + ":README.md", "a" * 40 + ":docs/../foreign",
                      "a" * 40 + ":docs/AUTOMATION_CONTRACT_V1.md/extra"):
            with self.subTest(value=value):
                self.assert_blocked_before_subprocess(("cat-file", "blob", value))

    def test_attribute_tail_must_match_checked_inventory(self):
        prefix = ("check-attr", "-z", "text", "eol", "filter", "--")
        self.assert_blocked_before_subprocess(prefix + ("sample.txt",))
        self.assert_blocked_before_subprocess(prefix + ("sample.txt", "extra.txt"), attribute_paths={"sample.txt"})
        for path in ("../foreign", "/foreign", "D:/foreign", r"\\foreign.invalid\share\x",
                     r"\\?\D:\x", ".GIT/config", "bad\x00name", "NUL", "sample.txt."):
            with self.subTest(path=repr(path)):
                self.assert_blocked_before_subprocess(prefix + (path,), attribute_paths={path})


class StageTests(unittest.TestCase):
    setUp = PrepareTests.setUp
    commit_fixture = ObserverTests.commit_fixture
    refresh_manifest = PrepareTests.refresh_manifest
    modify = PrepareTests.modify
    run_prepare = PrepareTests.run_prepare

    def g(self, *args, data=None):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                   GIT_AUTHOR_DATE="2000-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2000-01-01T00:00:00+00:00",
                   GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", *args], cwd=self.root, env=env, input=data,
                              capture_output=True, check=True).stdout

    def authorization(self, paths):
        candidate = self.run_prepare(paths)
        self.assertEqual(candidate["status"], "PREPARED_NOT_AUTHORIZED", candidate)
        return dict(authorized_candidate=candidate["Candidate-SHA256"], authorized_parent=self.head,
                    authorized_paths=paths, scope="STAGE_ONLY")

    def execute(self, authorization):
        from starter_cli import execute_stage
        return execute_stage(self.root, self.root, "FIXTURE", "codex/test", self.head,
                             self.count, **authorization)

    def refs_config(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root / ".git").rglob("*")
                if p.is_file() and ("refs" in p.parts or p.name in ("HEAD", "config", "packed-refs"))}

    def assert_success(self, result):
        import starter_cli as module
        self.assertEqual(result["status"], "STAGED_AWAITING_COMMIT_AUTHORIZATION", result)
        receipt = result["receipt"]
        self.assertEqual(hashlib.sha256(module.canonical_bytes(receipt)).hexdigest(), result["Stage-Receipt-SHA256"])
        self.assertEqual(receipt["parent"], self.head)
        self.assertEqual(receipt["scope"], "STAGE_ONLY")
        tree = self.g("write-tree").decode().strip()
        self.assertEqual(receipt["tree_sha"], tree)
        raw = self.g(*module.STAGE_DIFF_ARGV)
        self.assertEqual(len(raw), receipt["staged_diff_bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt["staged_diff_sha256"])
        actual = module.index_entries(self.g("ls-files", "--stage", "-z"))
        for path, oid in receipt["staged_blobs"].items():
            self.assertEqual(actual.get(path, {}).get("oid"), oid)
        self.assertFalse((self.root / ".git/index.lock").exists())
        self.assertFalse((self.root / ".git/index.lock.lock").exists())
        self.assertFalse(list((self.root / ".git").glob("starter-stage-*")))
        return receipt

    def test_authorized_exact_stage_and_receipt_no_ref_change(self):
        paths = self.modify(); auth = self.authorization(paths)
        refs = self.refs_config(); result = self.execute(auth)
        self.assert_success(result)
        self.assertEqual(self.refs_config(), refs)
        self.assertEqual(self.g("rev-parse", "HEAD").decode().strip(), self.head)
        self.assertEqual(self.g("remote"), b"")
        self.assertEqual(self.g("rev-list", "--count", "HEAD").strip(), b"1")

    def test_wrong_candidate_parent_scope_and_missing_fields(self):
        paths = self.modify(); auth = self.authorization(paths)
        before = (self.root / ".git/index").read_bytes()
        all_before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        variants = [dict(auth, authorized_candidate="0" * 64), dict(auth, authorized_parent="0" * 40),
                    dict(auth, scope="COMMIT"), {}, dict(auth, scope=None),
                    {k: v for k, v in auth.items() if k != "authorized_candidate"},
                    {k: v for k, v in auth.items() if k != "authorized_parent"},
                    {k: v for k, v in auth.items() if k != "authorized_paths"}]
        for variant in variants:
            with self.subTest(fields=list(variant)):
                result = self.execute(variant)
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertEqual((self.root / ".git/index").read_bytes(), before)
                self.assertFalse((self.root / ".git/index.lock").exists())
                self.assertEqual({p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, all_before)

    def test_paths_omitted_or_extra_blocked(self):
        paths = self.modify(); auth = self.authorization(paths)
        for selected in (["sample.txt"], paths + ["PROJECT_STATE.md"], paths + ["sample.txt"]):
            with self.subTest(selected=selected):
                self.assertEqual(self.execute(dict(auth, authorized_paths=selected))["status"], "BLOCKED")

    def test_byte_change_and_other_candidate_authorization_blocked(self):
        paths = self.modify("A\n"); old = self.authorization(paths)
        self.modify("B\n")
        new = self.authorization(paths)
        self.assertNotEqual(old["authorized_candidate"], new["authorized_candidate"])
        self.assertEqual(self.execute(old)["status"], "BLOCKED")

    def test_staging_nonempty_and_replay_blocked(self):
        paths = self.modify(); auth = self.authorization(paths)
        first = self.execute(auth); self.assert_success(first)
        original = (self.root / ".git/index").read_bytes()
        second = self.execute(auth)
        self.assertEqual(second["status"], "BLOCKED")
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_branch_head_or_manifest_change_blocked(self):
        paths = self.modify(); auth = self.authorization(paths)
        self.g("symbolic-ref", "HEAD", "refs/heads/other")
        self.g("update-ref", "refs/heads/other", self.head)
        self.assertEqual(self.execute(auth)["status"], "BLOCKED")
        self.g("symbolic-ref", "HEAD", "refs/heads/codex/test")
        tree = self.g("rev-parse", "HEAD^{tree}").decode().strip()
        changed = self.g("commit-tree", tree, "-p", self.head, data=b"external HEAD change\n").decode().strip()
        self.g("update-ref", "refs/heads/codex/test", changed)
        self.assertEqual(self.execute(auth)["status"], "BLOCKED")
        self.g("update-ref", "refs/heads/codex/test", self.head)
        (self.root / "evidence/PROJECT_MANIFEST.json").write_text("{}")
        self.assertEqual(self.execute(auth)["status"], "BLOCKED")

    def test_add_modify_delete_exact_blobs(self):
        (self.root / "new.txt").write_text("new\n", newline="\n")
        (self.root / "sample.txt").unlink()
        self.refresh_manifest()
        paths = ["new.txt", "sample.txt", "evidence/PROJECT_MANIFEST.json"]
        auth = self.authorization(paths)
        result = self.execute(auth);receipt = self.assert_success(result)
        self.assertIsNone(receipt["staged_blobs"]["sample.txt"])
        self.assertEqual(self.g("cat-file", "blob", receipt["staged_blobs"]["new.txt"]), b"new\n")

    def test_no_filter_executed(self):
        paths = self.modify();auth = self.authorization(paths)
        marker, command = ObserverTests.sentinel_command(self)
        self.g("config", "filter.attack.clean", command)
        self.g("config", "filter.attack.process", command)
        (self.root / ".gitattributes").write_text("* text eol=lf filter=attack\n", newline="\n")
        original = (self.root / ".git/index").read_bytes()
        with patch("starter_cli.subprocess.run", side_effect=AssertionError("Unsafe config reached Git")):
            self.assertEqual(self.execute(auth)["status"], "BLOCKED")
        self.assertFalse(marker.exists())
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_transaction_disables_hooks_without_changing_config(self):
        paths = self.modify(); auth = self.authorization(paths)
        marker = self.root / "HOOK_EXECUTED"
        hook = self.root / ".git/hooks/post-index-change"
        hook.write_text("#!/bin/sh\nprintf unsafe > " + shlex.quote(str(marker)) + "\n", newline="\n")
        hook.chmod(0o755)
        before = (self.root / ".git/config").read_bytes()
        real = subprocess.run
        stage_commands = []
        def run(command, *args, **kwargs):
            if any(verb in command for verb in ("hash-object", "update-index", "write-tree")):
                stage_commands.append(command)
                self.assertIn("core.hooksPath=" + os.devnull, command)
            return real(command, *args, **kwargs)
        with patch("starter_cli.subprocess.run", side_effect=run):
            result = self.execute(auth)
        self.assertEqual(result["status"], "STAGED_AWAITING_COMMIT_AUTHORIZATION", result)
        self.assertTrue(stage_commands)
        self.assertFalse(marker.exists())
        self.assertEqual((self.root / ".git/config").read_bytes(), before)

    def test_existing_index_lock_untouched(self):
        paths = self.modify();auth = self.authorization(paths)
        lock = self.root / ".git/index.lock";lock.write_bytes(b"OTHER OWNER")
        self.assertEqual(self.execute(auth)["status"], "BLOCKED")
        self.assertEqual(lock.read_bytes(), b"OTHER OWNER")

    def test_failure_after_private_update_restores_original_index(self):
        import starter_cli as module
        paths = self.modify();auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        run = module._StageTransaction._run
        def fail(tx, args, data=None, live=False):
            result = run(tx, args, data, live)
            if args == ("update-index", "-z", "--index-info"):
                raise RuntimeError("injected after update")
            return result
        with patch.object(module._StageTransaction, "_run", fail):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)
        self.assertFalse((self.root / ".git/index.lock").exists())

    def test_failure_after_publish_restores_original_index(self):
        import starter_cli as module
        paths = self.modify();auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        publish = module._StageTransaction.publish
        def fail(tx):
            publish(tx)
            raise RuntimeError("injected after live index publication")
        with patch.object(module._StageTransaction, "publish", fail):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_receipt_serialization_failure_rolls_back_before_unlock(self):
        paths = self.modify(); auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        with patch("starter_cli.canonical_bytes", side_effect=RuntimeError("receipt serialization failure")):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)
        self.assertFalse((self.root / ".git/index.lock").exists())

    def test_head_change_during_execution_rolls_back(self):
        import starter_cli as module
        paths = self.modify();auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        tree = self.g("rev-parse", "HEAD^{tree}").decode().strip()
        new = self.g("commit-tree", tree, "-p", self.head, data=b"concurrent actor\n").decode().strip()
        publish = module._StageTransaction.publish
        def change(tx):
            publish(tx)
            self.g("update-ref", "refs/heads/codex/test", new)
        with patch.object(module._StageTransaction, "publish", change):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)
        self.assertEqual(self.g("rev-parse", "HEAD").decode().strip(), new)  # never repair refs

    def test_working_tree_change_during_execution_rolls_back(self):
        import starter_cli as module
        paths = self.modify();auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        publish = module._StageTransaction.publish
        def change(tx):
            publish(tx)
            (self.root / "sample.txt").write_text("concurrent byte change\n", newline="\n")
        with patch.object(module._StageTransaction, "publish", change):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_blob_result_mismatch_blocks_and_restores(self):
        import starter_cli as module
        paths = self.modify();auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        run = module._StageTransaction._run
        def wrong(tx, args, data=None, live=False):
            result = run(tx, args, data, live)
            return b"0" * 40 + b"\n" if args[0] == "hash-object" else result
        with patch.object(module._StageTransaction, "_run", wrong):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_mutable_executor_guard_has_no_commit_path(self):
        import starter_cli as module
        paths = self.modify();candidate = self.run_prepare(paths)
        original = (self.root / ".git/index").read_bytes()
        entries = module.index_entries(self.g("ls-files", "--stage", "-z"))
        tx = module._StageTransaction(self.root, original, candidate["payload"]["changes"], {"sample.txt": b"modified\n"}, entries)
        tx.acquire()
        try:
            cases = [("commit",), ("update-ref", "HEAD", "a" * 40), ("add", "--", "sample.txt"),
                     ("hash-object", "-w", "--stdin"), ("update-index", "--add", "sample.txt"),
                     ("write-tree", "extra"), ("symbolic-ref", "HEAD", "refs/heads/evil")]
            with patch("starter_cli.subprocess.run", side_effect=AssertionError("prohibited mutation")):
                for args in cases:
                    with self.subTest(args=args), self.assertRaises(module.Blocked):
                        tx._run(args)
                with self.assertRaises(module.Blocked):
                    tx._run(("hash-object", "-w", "--no-filters", "--stdin"), b"UNAUTHORIZED")
        finally:
            tx.close()
        import ast
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_run":
                self.assertFalse(node.args and isinstance(node.args[0], ast.Tuple) and any(isinstance(e, ast.Constant) and e.value == "commit" for e in node.args[0].elts))

    def test_index_replacement_requires_active_transaction_and_exact_bytes(self):
        import starter_cli as module
        paths = self.modify(); candidate = self.run_prepare(paths)
        original = (self.root / ".git/index").read_bytes()
        entries = module.index_entries(self.g("ls-files", "--stage", "-z"))
        tx = module._StageTransaction(self.root, original, candidate["payload"]["changes"], {}, entries)
        with self.assertRaises(module.Blocked):
            tx.replace_index(original)
        tx.acquire()
        try:
            with self.assertRaises(module.Blocked):
                tx.replace_index(b"UNAUTHORIZED INDEX")
        finally:
            tx.close()
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_prepare_cannot_chain_or_authorize_execute(self):
        paths = self.modify();auth = self.authorization(paths)
        out = io.StringIO()
        from contextlib import redirect_stdout
        with patch("starter_cli.execute_stage", side_effect=AssertionError("auto-execute")), redirect_stdout(out):
            code = main(["prepare", "--authorized-candidate", auth["authorized_candidate"],
                         "--authorized-parent", self.head, "--authorized-path", "sample.txt", "--scope", "STAGE_ONLY"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED")

    def test_cli_execute_requires_separate_explicit_authorization(self):
        from contextlib import redirect_stdout
        paths = self.modify(); auth = self.authorization(paths)
        args = ["execute-stage", "--workspace", str(self.root), "--expected-workspace", str(self.root),
                "--expected-project", "FIXTURE", "--expected-branch", "codex/test",
                "--expected-head", self.head, "--expected-count", str(self.count),
                "--authorized-candidate", auth["authorized_candidate"], "--authorized-parent", self.head,
                "--scope", "STAGE_ONLY"]
        for path in paths:
            args += ["--authorized-path", path]
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(args)
        self.assertEqual(code, 0)
        self.assert_success(json.loads(out.getvalue()))

    def assert_blocked_without_own_mutation(self, auth, injected, boundary="prepare"):
        import starter_cli as module
        real_prepare, real_acquire = module.prepare, module._StageTransaction.acquire
        calls = 0
        captured = {}
        def inject():
            injected()
            captured["index"] = (self.root / ".git/index").read_bytes()
            captured["objects"] = {p.relative_to(self.root).as_posix(): p.read_bytes()
                                   for p in (self.root / ".git/objects").rglob("*") if p.is_file()}
        def revalidate(*args, **kwargs):
            nonlocal calls
            result = real_prepare(*args, **kwargs)
            calls += 1
            if calls == 2 and boundary == "prepare":
                inject()
            return result
        def acquire(tx):
            if boundary == "acquire":
                inject()
            return real_acquire(tx)
        with patch.object(module, "prepare", revalidate), patch.object(module._StageTransaction, "acquire", acquire), \
             patch.object(module._StageTransaction, "_run", side_effect=AssertionError("own Git before validated lock")) as own, \
             patch.object(module._StageTransaction, "rollback", side_effect=AssertionError("rollback before own mutation")) as rollback:
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertNotIn("receipt", result)
        self.assertNotIn("Stage-Receipt-SHA256", result)
        own.assert_not_called(); rollback.assert_not_called()
        self.assertEqual((self.root / ".git/index").read_bytes(), captured["index"])
        self.assertEqual({p.relative_to(self.root).as_posix(): p.read_bytes()
                          for p in (self.root / ".git/objects").rglob("*") if p.is_file()}, captured["objects"])
        self.assertFalse((self.root / ".git/index.lock").exists())
        return result

    def concurrent_stage(self, path):
        original = (self.root / path).read_bytes()
        try:
            (self.root / path).write_bytes(b"different concurrent staged bytes\n")
            self.g("add", "--", path)
        finally:
            (self.root / path).write_bytes(original)

    def test_conventional_stage_after_second_prepare_preserved_authorized_path(self):
        paths = self.modify(); auth = self.authorization(paths)
        result = self.assert_blocked_without_own_mutation(auth, lambda: self.concurrent_stage("sample.txt"))
        self.assertIn("Index changed", result["error"])
        self.assertEqual(self.g("show", ":sample.txt"), b"different concurrent staged bytes\n")

    def test_conventional_stage_before_acquire_preserved_authorized_path(self):
        paths = self.modify(); auth = self.authorization(paths)
        result = self.assert_blocked_without_own_mutation(auth, lambda: self.concurrent_stage("sample.txt"), "acquire")
        self.assertEqual(result["validated_index_sha256"], result["original_index"]["sha256"])
        self.assertEqual(self.g("show", ":sample.txt"), b"different concurrent staged bytes\n")

    def test_conventional_stage_after_second_prepare_preserved_unselected_path(self):
        paths = self.modify(); auth = self.authorization(paths)
        self.assert_blocked_without_own_mutation(auth, lambda: self.concurrent_stage("PROJECT_STATE.md"))
        self.assertEqual(self.g("show", ":PROJECT_STATE.md"), b"different concurrent staged bytes\n")

    def test_conventional_stage_before_acquire_preserved_unselected_path(self):
        paths = self.modify(); auth = self.authorization(paths)
        self.assert_blocked_without_own_mutation(auth, lambda: self.concurrent_stage("PROJECT_STATE.md"), "acquire")

    def test_unstaged_index_encoding_drift_under_lock_preserved(self):
        paths = self.modify(); auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        def change():
            self.g("update-index", "--index-version=4")
            self.assertEqual(self.g("diff", "--cached", "--name-only"), b"")
            self.assertNotEqual((self.root / ".git/index").read_bytes(), original)
        self.assert_blocked_without_own_mutation(auth, change, "acquire")

    def test_head_changed_between_validation_and_lock_blocks_before_objects(self):
        paths = self.modify(); auth = self.authorization(paths)
        tree = self.g("rev-parse", "HEAD^{tree}").decode().strip()
        other = self.g("commit-tree", tree, "-p", self.head, data=b"concurrent ref\n").decode().strip()
        self.assert_blocked_without_own_mutation(auth, lambda: self.g("update-ref", "refs/heads/codex/test", other), "acquire")
        self.assertEqual(self.g("rev-parse", "HEAD").decode().strip(), other)

    def test_worktree_changed_between_validation_and_lock_blocks_before_objects(self):
        paths = self.modify(); auth = self.authorization(paths)
        self.assert_blocked_without_own_mutation(auth, lambda: (self.root / "sample.txt").write_bytes(b"concurrent worktree\n"), "acquire")
        self.assertEqual((self.root / "sample.txt").read_bytes(), b"concurrent worktree\n")

    def test_existing_lock_blocks_without_objects_or_rollback(self):
        import starter_cli as module
        paths = self.modify(); auth = self.authorization(paths)
        lock = self.root / ".git/index.lock"; lock.write_bytes(b"OTHER OWNER")
        original = (self.root / ".git/index").read_bytes()
        with patch.object(module._StageTransaction, "_run", side_effect=AssertionError("own Git")) as own, \
             patch.object(module._StageTransaction, "rollback", side_effect=AssertionError("rollback")) as rollback:
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        own.assert_not_called(); rollback.assert_not_called()
        self.assertEqual(lock.read_bytes(), b"OTHER OWNER")
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_validated_index_identity_used_for_success_and_rollback(self):
        import starter_cli as module
        paths = self.modify(); auth = self.authorization(paths)
        original = (self.root / ".git/index").read_bytes()
        real_run = module._StageTransaction._run
        def fail(tx, args, data=None, live=False):
            self.assertTrue(tx.baseline_validated)
            self.assertEqual(tx.original, original)
            self.assertTrue(tx.lock.exists())
            output = real_run(tx, args, data, live)
            if args[0] == "update-index":
                raise RuntimeError("failure after own mutation")
            return output
        with patch.object(module._StageTransaction, "_run", fail):
            result = self.execute(auth)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["index_rollback_verified"])
        self.assertEqual(result["validated_index_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual((self.root / ".git/index").read_bytes(), original)
        successful = self.execute(auth); self.assert_success(successful)
        self.assertEqual(successful["validated_index_sha256"], hashlib.sha256(original).hexdigest())

    def test_mutable_commands_require_validated_lock(self):
        import starter_cli as module
        paths = self.modify(); candidate = self.run_prepare(paths)
        original = (self.root / ".git/index").read_bytes()
        tx = module._StageTransaction(self.root, original, candidate["payload"]["changes"], {"sample.txt": b"modified\n"}, {})
        tx.acquire()
        try:
            with patch("starter_cli.subprocess.run", side_effect=AssertionError("premature subprocess")) as run:
                for args, data in [(("hash-object", "-w", "--no-filters", "--stdin"), b"modified\n"),
                                   (("update-index", "-z", "--index-info"), tx.batch), (("write-tree",), None)]:
                    with self.subTest(args=args), self.assertRaises(module.Blocked):
                        tx._run(args, data)
                run.assert_not_called()
            with self.assertRaises(module.Blocked):
                tx.replace_index(original)
        finally:
            tx.close()
        self.assertEqual((self.root / ".git/index").read_bytes(), original)

    def test_receipt_deterministic_across_independent_repository_recreation(self):
        import tempfile
        paths = self.modify();auth = self.authorization(paths)
        baseline = {}
        for row in self.g("ls-files", "--stage", "-z").split(b"\0"):
            if row:
                meta, path = row.split(b"\t", 1);oid = meta.decode().split()[1]
                baseline[path.decode()] = self.g("cat-file", "blob", oid)
        first = self.execute(auth);self.assert_success(first)
        with tempfile.TemporaryDirectory(prefix=".stage-independent-", dir=SANDBOX) as archive:
            source = (self.root / ".git").absolute();target = (Path(archive) / "old-metadata").absolute()
            self.assertTrue(source.is_relative_to(SANDBOX) and target.is_relative_to(SANDBOX))
            source.rename(target)
            for p, raw in baseline.items():
                (self.root / p).write_bytes(raw)
            self.g("init", "-b", "codex/test");self.g("config", "core.autocrlf", "false")
            self.commit_fixture()
            self.assertEqual(self.g("rev-parse", "HEAD").decode().strip(), self.head)
            self.modify();second = self.execute(self.authorization(paths));self.assert_success(second)
            self.assertEqual(first["receipt"], second["receipt"])
            self.assertEqual(first["Stage-Receipt-SHA256"], second["Stage-Receipt-SHA256"])
            # Raw stat-cache identities remain diagnostic, outside receipt hash.


class CommitPlanTests(unittest.TestCase):
    g = StageTests.g
    commit_fixture = ObserverTests.commit_fixture
    refresh_manifest = PrepareTests.refresh_manifest
    modify = PrepareTests.modify
    run_prepare = PrepareTests.run_prepare
    authorization = StageTests.authorization
    execute = StageTests.execute

    def setUp(self):
        PrepareTests.setUp(self)
        paths = self.modify()
        candidate = self.run_prepare(paths)
        staged = self.execute(self.authorization(paths))
        self.assertEqual(staged["status"], "STAGED_AWAITING_COMMIT_AUTHORIZATION", staged)
        self.inputs = dict(candidate=candidate["payload"], candidate_sha256=candidate["Candidate-SHA256"],
                           stage_receipt=staged["receipt"], stage_receipt_sha256=staged["Stage-Receipt-SHA256"],
                           paths=paths, scope="COMMIT_ONLY", subject="feat: fixture", message="feat: fixture\n\nFixture body.\n",
                           author_name="Fixture Author", author_email="author@example.invalid",
                           committer_name="Fixture Committer", committer_email="committer@example.invalid")

    def plan(self, **overrides):
        from starter_cli import commit_plan
        inputs = dict(self.inputs, **overrides)
        return commit_plan(self.root, self.root, "FIXTURE", "codex/test", self.head, self.count, **inputs)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def assert_planned(self, result):
        import starter_cli as module
        self.assertEqual(result["status"], "COMMIT_PLANNED_NOT_AUTHORIZED", result)
        self.assertEqual(result["authorization"], "Commit-Intent-SHA256 is a binding identifier, not human authorization.")
        intent = result["intent"]
        self.assertEqual(result["Commit-Intent-SHA256"], hashlib.sha256(module.canonical_bytes(intent)).hexdigest())
        self.assertEqual(result["Commit-Message-SHA256"], hashlib.sha256(bytes.fromhex(intent["message_utf8_hex"])).hexdigest())
        self.assertEqual(intent["tree_sha"], self.inputs["stage_receipt"]["tree_sha"])
        self.assertEqual(intent["scope"], "COMMIT_ONLY")
        self.assertFalse(any(key in intent for key in ("timestamp", "pid", "commit_oid")))
        return result["Commit-Intent-SHA256"]

    def receipt_variant(self, **changes):
        from starter_cli import canonical_bytes
        receipt = dict(self.inputs["stage_receipt"], **changes)
        return dict(stage_receipt=receipt, stage_receipt_sha256=hashlib.sha256(canonical_bytes(receipt)).hexdigest())

    def test_valid_plan_no_mutation_and_deterministic(self):
        before = self.snapshot()
        first = self.plan(); second = self.plan(paths=list(reversed(self.inputs["paths"])))
        self.assert_planned(first); self.assertEqual(first, second)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.g("rev-parse", "HEAD").decode().strip(), self.head)

    def test_wrong_candidate_and_receipt_hashes_block(self):
        for fields in (dict(candidate_sha256="0" * 64), dict(stage_receipt_sha256="0" * 64),
                       dict(candidate_sha256=None), dict(stage_receipt_sha256=None)):
            with self.subTest(fields=fields):
                self.assertEqual(self.plan(**fields)["status"], "BLOCKED")

    def test_receipt_parent_tree_diff_blob_and_paths_revalidated(self):
        actual = self.inputs["stage_receipt"]
        variants = [dict(parent="0" * 40), dict(tree_sha="0" * 40),
                    dict(staged_diff_sha256="0" * 64), dict(staged_diff_bytes=actual["staged_diff_bytes"]+1),
                    dict(staged_diff_bytes=True), dict(paths=actual["paths"][:-1]),
                    dict(paths=actual["paths"]+["extra.txt"]), dict(staged_blobs=dict(actual["staged_blobs"], **{"sample.txt":"0"*40})),
                    {"Candidate-SHA256":"0"*64}, dict(branch="codex/other")]
        before = self.snapshot()
        for fields in variants:
            with self.subTest(fields=fields):
                result = self.plan(**self.receipt_variant(**fields))
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertNotIn("Commit-Intent-SHA256", result)
        self.assertEqual(self.snapshot(), before)

    def test_wrong_expected_parent_blocks(self):
        import starter_cli as module
        result = module.commit_plan(self.root,self.root,"FIXTURE","codex/test","0"*40,self.count,**self.inputs)
        self.assertEqual(result["status"], "BLOCKED")

    def test_selection_omitted_extra_duplicate_blocked(self):
        for paths in (None, [], self.inputs["paths"][:-1], self.inputs["paths"]+["extra.txt"],
                      self.inputs["paths"]+[self.inputs["paths"][0]]):
            with self.subTest(paths=paths):
                self.assertEqual(self.plan(paths=paths)["status"], "BLOCKED")

    def test_candidate_payload_and_policy_revalidated(self):
        from copy import deepcopy
        from starter_cli import canonical_bytes
        for key, value in (("changes", []), ("manifest_sha256", "0"*64), ("workspace", "D:/foreign")):
            candidate = deepcopy(self.inputs["candidate"]); candidate[key]=value
            digest=hashlib.sha256(canonical_bytes(candidate)).hexdigest()
            receipt=self.receipt_variant(**{"Candidate-SHA256":digest})
            self.assertEqual(self.plan(candidate=candidate,candidate_sha256=digest,**receipt)["status"],"BLOCKED")

    def test_unstaged_bytes_blocked_without_repair(self):
        (self.root/"sample.txt").write_bytes(b"unstaged change\n")
        before=self.snapshot(); result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result);self.assertEqual(before,self.snapshot())

    def test_untracked_file_blocked_without_repair(self):
        (self.root/"extra.txt").write_bytes(b"extra\n")
        before=self.snapshot();self.assertEqual(self.plan()["status"],"BLOCKED");self.assertEqual(before,self.snapshot())

    def test_message_one_byte_and_trailing_newline_are_bound(self):
        first=self.assert_planned(self.plan())
        for message in ("feat: fixture\n\nFixture body!\n", "feat: fixture\n\nFixture body.",
                        "feat: fixture\n\nFixture body.\n\n", "feat: fixture\n\nFixture b\u00f3dy.\n"):
            with self.subTest(message=message):
                result=self.plan(message=message)
                self.assertNotEqual(self.assert_planned(result),first)
                self.assertEqual(bytes.fromhex(result["intent"]["message_utf8_hex"]),message.encode("utf-8"))

    def test_subject_changed_with_message_changes_intent(self):
        original=self.assert_planned(self.plan())
        result=self.plan(subject="fix: fixture",message="fix: fixture\n\nFixture body.\n")
        self.assertNotEqual(self.assert_planned(result),original)
        self.assertEqual(self.plan(subject="fix: fixture")["status"],"BLOCKED")

    def test_all_explicit_identity_fields_are_bound(self):
        original=self.assert_planned(self.plan())
        for fields in (dict(author_name="Other Author"),dict(author_email="other@example.invalid"),
                       dict(committer_name="Other Committer"),dict(committer_email="other@example.invalid")):
            with self.subTest(fields=fields):
                self.assertNotEqual(self.assert_planned(self.plan(**fields)),original)

    def test_missing_and_unsupported_identity_fields_rejected(self):
        for field in ("author_name","author_email","committer_name","committer_email"):
            for value in (None,""," bad ","bad\0identity","bad\nidentity","a<b>"):
                with self.subTest(field=field,value=repr(value)):
                    self.assertEqual(self.plan(**{field:value})["status"],"BLOCKED")
        for email in ("x", "a@@example.invalid", "a@-bad.invalid", "a@example..invalid", ".a@example.invalid"):
            self.assertEqual(self.plan(author_email=email)["status"],"BLOCKED")

    def test_no_silent_message_normalization(self):
        for fields in (dict(message=None),dict(subject=None),dict(message="feat: fixture"),
                       dict(message="feat: fixture\n\n"),dict(message="feat: fixture\r\n\r\nbody\r\n"),
                       dict(message="feat: fixture\n\nbody\0"),dict(subject=" feat: fixture")):
            self.assertEqual(self.plan(**fields)["status"],"BLOCKED")

    def test_scope_is_not_permission(self):
        for scope in (None,"STAGE_ONLY","EXECUTE_COMMIT",""):
            self.assertEqual(self.plan(scope=scope)["status"],"BLOCKED")
        result=self.plan();self.assert_planned(result)
        self.assertIn("not human authorization",result["authorization"])

    def test_json_arguments_do_not_open_files_and_reject_duplicates(self):
        for value in ('D:/foreign/receipt.json','{"schema":"a","schema":"b"}','{"x":NaN}', '[]'):
            self.assertEqual(self.plan(stage_receipt=value)["status"],"BLOCKED")

    def test_ambient_identity_is_not_consulted_or_used(self):
        import starter_cli as module
        real_run=subprocess.run
        def run(command,*args,**kwargs):
            self.assertFalse(any(x in command for x in ("user.name","user.email","--global","--system","var")))
            if command[0]=="git":
                self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"],os.devnull)
                self.assertEqual(kwargs["env"]["GIT_CONFIG_SYSTEM"],os.devnull)
            return real_run(command,*args,**kwargs)
        with patch("starter_cli.subprocess.run",side_effect=run):
            self.assert_planned(self.plan())
            self.assertEqual(self.plan(author_name=None)["status"],"BLOCKED")
        with patch.dict(os.environ,{"GIT_AUTHOR_NAME":"unexpected ambient identity"}):
            self.assertEqual(self.plan()["status"],"BLOCKED")

    def test_index_drift_during_plan_blocked_without_restore(self):
        import starter_cli as module
        real=module.plan_snapshot; calls=0; concurrent={}
        def snapshot(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==1:
                self.g("update-index","--index-version=4")
                concurrent["index"]=(self.root/".git/index").read_bytes()
            return result
        with patch.object(module,"plan_snapshot",snapshot):result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertNotIn("Commit-Intent-SHA256",result)
        self.assertEqual((self.root/".git/index").read_bytes(),concurrent["index"])

    def test_head_drift_during_plan_blocked_without_restore(self):
        import starter_cli as module
        tree=self.g("rev-parse","HEAD^{tree}").decode().strip()
        other=self.g("commit-tree",tree,"-p",self.head,data=b"external writer\n").decode().strip()
        real=module.plan_snapshot;calls=0
        def snapshot(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==1:self.g("update-ref","refs/heads/codex/test",other)
            return result
        with patch.object(module,"plan_snapshot",snapshot):result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),other)

    def test_worktree_drift_during_plan_blocked(self):
        import starter_cli as module
        real=module.plan_snapshot;calls=0
        def snapshot(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==1:(self.root/"sample.txt").write_bytes(b"external bytes\n")
            return result
        with patch.object(module,"plan_snapshot",snapshot):result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertEqual((self.root/"sample.txt").read_bytes(),b"external bytes\n")

    def test_late_same_tree_head_change_before_intent_blocked(self):
        import starter_cli as module
        tree=self.g("rev-parse","HEAD^{tree}").decode().strip()
        other=self.g("commit-tree",tree,"-p",self.head,data=b"late external ref\n").decode().strip()
        real=module.plan_snapshot;calls=0
        def snapshot(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==2:self.g("update-ref","refs/heads/codex/test",other)
            return result
        with patch.object(module,"plan_snapshot",snapshot):result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),other)

    def test_late_worktree_change_before_intent_blocked(self):
        import starter_cli as module
        real=module.plan_snapshot;calls=0
        def snapshot(*args,**kwargs):
            nonlocal calls
            result=real(*args,**kwargs);calls+=1
            if calls==2:(self.root/"sample.txt").write_bytes(b"late external bytes\n")
            return result
        with patch.object(module,"plan_snapshot",snapshot):result=self.plan()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertEqual((self.root/"sample.txt").read_bytes(),b"late external bytes\n")

    def test_plan_cannot_reach_mutable_executor(self):
        import starter_cli as module
        before=self.snapshot()
        with patch.object(module,"execute_stage",side_effect=AssertionError("auto execution")), \
             patch.object(module._StageTransaction,"_run",side_effect=AssertionError("mutable executor")), \
             patch.object(module._StageTransaction,"replace_index",side_effect=AssertionError("index write")):
            self.assert_planned(self.plan())
        self.assertEqual(before,self.snapshot())

    def test_new_readonly_forms_are_exact_and_mutable_forms_rejected(self):
        import starter_cli as module
        forms=[module.STAGE_DIFF_ARGV,("ls-tree","-r","-z",self.head)]
        for args in forms:
            with patch("starter_cli.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=b"ok")) as run:
                self.assertEqual(module.git(self.root,*args),b"ok");run.assert_called_once()
            for invalid in (args+("extra",),args+("--output=bad",)):
                with patch("starter_cli.subprocess.run") as run,self.assertRaises(module.Blocked):
                    module.git(self.root,*invalid)
                run.assert_not_called()
        bad=[("commit",),("commit-tree",self.head),("update-ref","HEAD",self.head),
             ("symbolic-ref","HEAD","refs/heads/other"),("hash-object","-w","--stdin"),
             ("write-tree",),("update-index","--refresh"),("add","."),("reset",),("restore","x"),
             ("checkout","x"),("config","user.name","x"),("ls-tree","-r","-z","HEAD"),
             ("ls-tree","-r","-z",self.head+":foreign")]
        for args in bad:
            with patch("starter_cli.subprocess.run") as run,self.assertRaises(module.Blocked):
                module.git(self.root,*args)
            run.assert_not_called()

    def test_plan_accepts_authorized_add_and_delete(self):
        self.g("reset","--mixed","HEAD")  # Disposable fixture only.
        (self.root/"sample.txt").unlink()
        (self.root/"new.txt").write_bytes(b"new planned file\n")
        self.refresh_manifest()
        paths=["new.txt","sample.txt","evidence/PROJECT_MANIFEST.json"]
        candidate=self.run_prepare(paths);staged=self.execute(self.authorization(paths))
        self.assertEqual(staged["status"],"STAGED_AWAITING_COMMIT_AUTHORIZATION",staged)
        before=self.snapshot()
        result=self.plan(candidate=candidate["payload"],candidate_sha256=candidate["Candidate-SHA256"],
                         stage_receipt=staged["receipt"],stage_receipt_sha256=staged["Stage-Receipt-SHA256"],paths=paths)
        self.assertEqual(result["status"],"COMMIT_PLANNED_NOT_AUTHORIZED",result)
        self.assertIsNone(result["intent"]["staged_blobs"]["sample.txt"])
        self.assertEqual(self.snapshot(),before)

    def test_tree_hash_matches_git_for_nested_directories(self):
        from starter_cli import git_tree_oid,index_entries
        self.assertEqual(git_tree_oid(index_entries(self.g("ls-files","--stage","-z"))),self.inputs["stage_receipt"]["tree_sha"])

    def test_cli_plan_is_separate_and_json_inputs_are_explicit(self):
        from contextlib import redirect_stdout
        inputs=self.inputs
        args=["commit-plan","--workspace",str(self.root),"--expected-workspace",str(self.root),
              "--expected-project","FIXTURE","--expected-branch","codex/test","--expected-head",self.head,
              "--expected-count",str(self.count),"--candidate-json",json.dumps(inputs["candidate"]),
              "--stage-receipt-json",json.dumps(inputs["stage_receipt"])]
        for field in ("candidate_sha256","stage_receipt_sha256","subject","message","author_name","author_email","committer_name","committer_email","scope"):
            args += ["--"+field.replace("_","-"),inputs[field]]
        for path in reversed(inputs["paths"]):args += ["--plan-path",path]
        out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(main(args),0)
        self.assertEqual(json.loads(out.getvalue()),self.plan())
        for command in ("observe","prepare","execute-stage"):
            out=io.StringIO()
            with patch("starter_cli.execute_stage",side_effect=AssertionError("auto stage")),redirect_stdout(out):
                self.assertEqual(main([command,"--message","x"]),2)
            self.assertEqual(json.loads(out.getvalue())["status"],"BLOCKED")


class CommitExecutionTests(unittest.TestCase):
    g = StageTests.g
    commit_fixture = ObserverTests.commit_fixture
    refresh_manifest = PrepareTests.refresh_manifest
    modify = PrepareTests.modify
    run_prepare = PrepareTests.run_prepare
    authorization = StageTests.authorization
    execute = StageTests.execute
    plan = CommitPlanTests.plan
    snapshot = CommitPlanTests.snapshot

    def setUp(self):
        CommitPlanTests.setUp(self)
        self.inputs["message"] = "feat: fixture\n\nExact body without final newline"
        planned = self.plan()
        self.assertEqual(planned["status"], "COMMIT_PLANNED_NOT_AUTHORIZED", planned)
        self.intent = planned["intent"]
        self.commit_authorization = {"authorized_intent": planned["Commit-Intent-SHA256"], "authorized_parent": self.head}
        self.epoch = 946684800

    def run_commit(self, **overrides):
        from starter_cli import execute_commit
        fields = dict(self.inputs, **self.commit_authorization, clock=lambda: self.epoch)
        fields.update(overrides)
        return execute_commit(self.root, self.root, "FIXTURE", "codex/test", self.head, self.count, **fields)

    def assert_zero_mutation(self, **fields):
        before = self.snapshot()
        result = self.run_commit(**fields)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertFalse(result.get("commit_object_attempted", False), result)
        self.assertNotIn("Commit-Receipt-SHA256", result)
        self.assertEqual(self.snapshot(), before)
        return result

    def other_commit(self):
        tree = self.g("rev-parse", "HEAD^{tree}").decode().strip()
        return self.g("commit-tree", tree, "-p", self.head, data=b"other actor\n").decode().strip()

    def assert_success(self, result):
        import starter_cli as module
        self.assertEqual(result["status"], "COMMIT_EXECUTED_AUTHORIZED", result)
        receipt = result["receipt"]
        self.assertEqual(result["Commit-Receipt-SHA256"],hashlib.sha256(module.canonical_bytes(receipt)).hexdigest())
        oid = self.g("rev-parse","HEAD").decode().strip()
        self.assertEqual(receipt["commit_oid"],oid)
        raw = self.g("cat-file","commit",oid)
        headers,message=raw.split(b"\n\n",1)
        self.assertEqual(message,self.inputs["message"].encode())
        self.assertFalse(message.endswith(b"\n"))
        self.assertIn(b"parent "+self.head.encode(),headers.split(b"\n"))
        self.assertIn(b"tree "+self.intent["tree_sha"].encode(),headers.split(b"\n"))
        for role in ("author","committer"):
            who=self.intent[role]
            expected=(role+" "+who["name"]+" <"+who["email"]+"> "+str(self.epoch)+" +0000").encode()
            self.assertIn(expected,headers.split(b"\n"))
            self.assertEqual(receipt[role]["unix_seconds"],self.epoch)
        self.assertEqual(self.g("rev-list",self.head+"..HEAD").decode().split(),[oid])
        diff=self.g("diff",self.head,oid,"--no-ext-diff","--no-textconv","--binary","--full-index","--no-color")
        self.assertEqual(len(diff),receipt["source_staged_diff_bytes"])
        self.assertEqual(hashlib.sha256(diff).hexdigest(),receipt["source_staged_diff_sha256"])
        self.assertFalse((self.root/".git/index.lock").exists())
        return receipt

    def test_valid_exactly_one_commit_raw_metadata_receipt_and_coherence(self):
        import starter_cli as module
        index=(self.root/".git/index").read_bytes()
        files={p:(self.root/p).read_bytes() for p in module.inventory(self.root)}
        before_refs=module.commit_refs(self.root)
        result=self.run_commit();receipt=self.assert_success(result)
        self.assertEqual((self.root/".git/index").read_bytes(),index)
        self.assertEqual({p:(self.root/p).read_bytes() for p in module.inventory(self.root)},files)
        expected=dict(before_refs,**{"refs/heads/codex/test":(receipt["commit_oid"]+"\n").encode()})
        self.assertEqual(module.commit_refs(self.root),expected)
        observation=module.observe(self.root,self.root,"FIXTURE","codex/test",receipt["commit_oid"],self.count)
        self.assertIn(observation["status"],("PASS","WARNING"),observation)
        self.assertFalse(observation["staging"])
        self.assertFalse(observation["working_tree"])

    def test_wrong_or_missing_authorization_message_identity_candidate_receipt_zero_mutations(self):
        variants=[{"authorized_intent":None},{"authorized_intent":"0"*64},{"authorized_parent":"0"*40},
                  {"scope":"STAGE_ONLY"},{"message":self.inputs["message"]+"!"},
                  {"author_name":"Different Author"},{"committer_email":"different@example.invalid"},
                  {"candidate_sha256":"0"*64},{"stage_receipt_sha256":"0"*64}]
        for fields in variants:
            with self.subTest(fields=fields):
                self.assert_zero_mutation(**fields)

    def test_tree_blob_diff_binding_drift_zero_mutations(self):
        import starter_cli as module
        old=self.inputs["stage_receipt"]
        for changes in ({"tree_sha":"0"*40},{"staged_diff_sha256":"0"*64},
                        {"staged_diff_bytes":old["staged_diff_bytes"]+1},
                        {"staged_blobs":dict(old["staged_blobs"],**{"sample.txt":"0"*40})}):
            receipt=dict(old,**changes)
            with self.subTest(changes=changes):
                self.assert_zero_mutation(stage_receipt=receipt,
                    stage_receipt_sha256=hashlib.sha256(module.canonical_bytes(receipt)).hexdigest())

    def test_wrong_expected_parent_branch_and_detached_head_zero_mutations(self):
        import starter_cli as module
        for branch,parent in (("codex/other",self.head),("codex/test","0"*40)):
            before=self.snapshot()
            fields=dict(self.inputs,**self.commit_authorization,clock=lambda:self.epoch)
            result=module.execute_commit(self.root,self.root,"FIXTURE",branch,parent,self.count,**fields)
            self.assertEqual(result["status"],"BLOCKED",result);self.assertEqual(before,self.snapshot())
        self.g("update-ref","--no-deref","HEAD",self.head)
        self.assert_zero_mutation()

    def test_staging_changed_after_plan_zero_mutations(self):
        oid=self.g("hash-object","-w","--stdin",data=b"other staged bytes\n").decode().strip()
        self.g("update-index","--cacheinfo","100644",oid,"sample.txt")
        self.assert_zero_mutation()

    def test_unstaged_untracked_remote_manifest_zero_mutations(self):
        sample=(self.root/"sample.txt").read_bytes()
        manifest=(self.root/"evidence/PROJECT_MANIFEST.json").read_bytes()
        cases=[(lambda:(self.root/"sample.txt").write_bytes(b"unstaged\n"),
                lambda:(self.root/"sample.txt").write_bytes(sample)),
               (lambda:(self.root/"extra.txt").write_bytes(b"extra\n"),
                lambda:(self.root/"extra.txt").unlink()),
               (lambda:self.g("remote","add","unexpected","https://invalid.invalid/repo"),
                lambda:self.g("remote","remove","unexpected")),
               (lambda:(self.root/"evidence/PROJECT_MANIFEST.json").write_bytes(b"{}"),
                lambda:(self.root/"evidence/PROJECT_MANIFEST.json").write_bytes(manifest))]
        for change,cleanup in cases:
            change()
            try:self.assert_zero_mutation()
            finally:cleanup()

    def test_existing_index_or_other_lock_preserved(self):
        for name in ("index.lock","HEAD.lock","packed-refs.lock"):
            lock=self.root/".git"/name;lock.write_bytes(b"OTHER OWNER")
            try:self.assert_zero_mutation();self.assertEqual(lock.read_bytes(),b"OTHER OWNER")
            finally:lock.unlink()

    def test_index_bytes_race_before_acquire_preserves_concurrent_index(self):
        import starter_cli as module
        real=module._CommitExecution.acquire;concurrent={}
        def acquire(tx):
            self.g("update-index","--index-version=4")
            concurrent["snapshot"]=self.snapshot()
            return real(tx)
        with patch.object(module._CommitExecution,"acquire",acquire):
            result=self.run_commit()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertFalse(result["commit_object_attempted"])
        self.assertEqual(self.snapshot(),concurrent["snapshot"])

    def test_staging_race_before_acquire_preserves_concurrent_bytes(self):
        import starter_cli as module
        real=module._CommitExecution.acquire;concurrent={}
        def acquire(tx):
            oid=self.g("hash-object","-w","--stdin",data=b"concurrent staged bytes\n").decode().strip()
            self.g("update-index","--cacheinfo","100644",oid,"sample.txt")
            concurrent["snapshot"]=self.snapshot()
            return real(tx)
        with patch.object(module._CommitExecution,"acquire",acquire):result=self.run_commit()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertFalse(result["commit_object_attempted"])
        self.assertEqual(self.snapshot(),concurrent["snapshot"])

    def test_head_race_before_object_zero_own_mutation(self):
        import starter_cli as module
        other=self.other_commit();real=module._CommitExecution._run;concurrent={}
        def run(tx,args,data=None):
            if args[0]=="commit-tree":
                self.g("update-ref","refs/heads/codex/test",other)
                concurrent["snapshot"]=self.snapshot()
            return real(tx,args,data)
        with patch.object(module._CommitExecution,"_run",run):result=self.run_commit()
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertFalse(result["commit_object_attempted"])
        # The owned index.lock is removed; no other concurrent bytes are restored.
        concurrent["snapshot"].pop(".git/index.lock")
        self.assertEqual(self.snapshot(),concurrent["snapshot"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),other)

    def test_head_race_after_object_preserves_external_ref_and_reports_orphan(self):
        import starter_cli as module
        other=self.other_commit();real=module._CommitExecution._run;calls=[]
        def run(tx,args,data=None):
            calls.append(args[0]);out=real(tx,args,data)
            if args[0]=="commit-tree":self.g("update-ref","refs/heads/codex/test",other)
            return out
        with patch.object(module._CommitExecution,"_run",run):result=self.run_commit()
        self.assertEqual(result["status"],"COMMIT_OBJECT_CREATED_REF_NOT_UPDATED",result)
        self.assertEqual(calls,["commit-tree"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),other)
        self.assertEqual(self.g("cat-file","-t",result["commit_object_oid"]).strip(),b"commit")
        self.assertIn("unreferenced",result["object_database_limit"])

    def test_atomic_old_oid_failure_preserves_concurrent_branch(self):
        other=self.other_commit();real=subprocess.run;calls=[]
        def run(command,*args,**kwargs):
            if "update-ref" in command and "--no-deref" in command:
                calls.append("CAS")
                self.g("update-ref","refs/heads/codex/test",other)
            return real(command,*args,**kwargs)
        with patch("starter_cli.subprocess.run",side_effect=run):result=self.run_commit()
        self.assertEqual(result["status"],"COMMIT_OBJECT_CREATED_REF_NOT_UPDATED",result)
        self.assertEqual(calls,["CAS"])
        self.assertFalse(result["ref_update_confirmed"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),other)
        self.assertEqual(self.g("cat-file","-t",result["commit_object_oid"]).strip(),b"commit")

    def test_wrong_created_message_identity_tree_or_parent_never_updates_ref(self):
        real=subprocess.run;other=self.other_commit()
        wrong_tree=self.g("rev-parse","HEAD^{tree}").decode().strip()
        for variant in ("message","author","committer","date","tree","parent","merge"):
            def run(command,*args,**kwargs):
                if "commit-tree" in command and "commit.gpgsign=false" in command:
                    command=list(command);kwargs=dict(kwargs)
                    if variant=="message":kwargs["input"]+=b"!"
                    elif variant in ("author","committer","date"):
                        values=dict(kwargs["env"])
                        key={"author":"GIT_AUTHOR_NAME","committer":"GIT_COMMITTER_EMAIL","date":"GIT_AUTHOR_DATE"}[variant]
                        values[key]={"author":"Wrong Author","committer":"wrong@example.invalid","date":"@946684801 +0000"}[variant]
                        kwargs["env"]=values
                    elif variant=="tree":command[command.index("commit-tree")+1]=wrong_tree
                    elif variant=="parent":command[-1]=other
                    elif variant=="merge":command.extend(["-p",other])
                return real(command,*args,**kwargs)
            with self.subTest(variant=variant),patch("starter_cli.subprocess.run",side_effect=run):
                result=self.run_commit()
            self.assertEqual(result["status"],"COMMIT_OBJECT_CREATED_REF_NOT_UPDATED",result)
            self.assertFalse(result["ref_update_attempted"])
            self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),self.head)

    def test_postcheck_failure_does_not_undo_commit(self):
        import starter_cli as module
        real=module.observe
        def observe(*args,**kwargs):
            if args[4]!=self.head:raise RuntimeError("injected postcheck failure")
            return real(*args,**kwargs)
        with patch.object(module,"observe",observe):result=self.run_commit()
        self.assertEqual(result["status"],"COMMITTED_POSTCHECK_FAILED",result)
        self.assertTrue(result["ref_update_confirmed"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),result["commit_object_oid"])
        self.assertFalse((self.root/".git/index.lock").exists())

    def test_receipt_failure_after_commit_is_not_hidden_as_blocked(self):
        import starter_cli as module
        real=module.canonical_bytes
        def canonical(payload):
            if payload.get("schema")=="starter-commit-receipt-v1":raise RuntimeError("receipt failure")
            return real(payload)
        with patch.object(module,"canonical_bytes",canonical):result=self.run_commit()
        self.assertEqual(result["status"],"COMMITTED_POSTCHECK_FAILED",result)
        self.assertTrue(result["ref_update_confirmed"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),result["commit_object_oid"])

    def test_timeout_after_ref_success_is_reported_as_committed_failure(self):
        real=subprocess.run
        def run(command,*args,**kwargs):
            output=real(command,*args,**kwargs)
            if "update-ref" in command and "--no-deref" in command:raise subprocess.TimeoutExpired(command,30)
            return output
        with patch("starter_cli.subprocess.run",side_effect=run):result=self.run_commit()
        self.assertEqual(result["status"],"COMMITTED_POSTCHECK_FAILED",result)
        self.assertTrue(result["ref_update_confirmed"])
        self.assertEqual(self.g("rev-parse","HEAD").decode().strip(),result["commit_object_oid"])

    def test_exact_mutable_guard_rejects_other_refs_verbs_and_extra_arguments(self):
        import starter_cli as module
        snapshot=module.plan_snapshot(self.root,self.root,"FIXTURE","codex/test",self.head,self.count)
        tx=module._CommitExecution(self.root,snapshot,self.intent)
        tx.acquire();tx.ready=True;tx.timestamp=self.epoch
        tx.object_oid=tx.verified_oid="a"*40
        bad=[("add","."),("reset",),("restore","x"),("checkout","x"),("merge","x"),("rebase","x"),
             ("tag","x"),("push",),("config","user.name","x"),
             ("update-ref","--no-deref","refs/heads/other","a"*40,self.head),
             ("update-ref","--no-deref","refs/tags/tag","a"*40,self.head),
             ("update-ref","--no-deref",tx.ref,"a"*40),
             ("update-ref","--no-deref",tx.ref,"a"*40,"0"*40),
             ("commit-tree",self.intent["tree_sha"],"-p",self.head,"-p",self.head),
             ("commit-tree",self.intent["tree_sha"],"-p",self.head,"-S")]
        try:
            with patch("starter_cli.subprocess.run",side_effect=AssertionError("guard reached subprocess")) as run:
                for args in bad:
                    with self.subTest(args=args),self.assertRaises(module.Blocked):tx._run(args)
                with self.assertRaises(module.Blocked):tx._run(("commit-tree",self.intent["tree_sha"],"-p",self.head),b"wrong message")
                run.assert_not_called()
        finally:tx.close()

    def test_hooks_signing_and_ambient_identity_are_disabled(self):
        marker=self.root/"HOOK_EXECUTED"
        for name in ("pre-commit","prepare-commit-msg","commit-msg","post-commit","reference-transaction"):
            hook=self.root/".git/hooks"/name
            hook.write_text("#!/bin/sh\nprintf unsafe > "+shlex.quote(str(marker))+"\n",newline="\n")
            hook.chmod(0o755)
        real=subprocess.run;mutations=[]
        def run(command,*args,**kwargs):
            self.assertFalse(any(x in command for x in ("user.name","user.email","--global","--system")))
            if "commit-tree" in command or "update-ref" in command:
                mutations.append(command)
                self.assertIn("core.hooksPath="+os.devnull,command)
                self.assertIn("commit.gpgsign=false",command)
                values=kwargs["env"]
                self.assertEqual(values["GIT_AUTHOR_NAME"],self.intent["author"]["name"])
                self.assertEqual(values["GIT_COMMITTER_EMAIL"],self.intent["committer"]["email"])
                self.assertEqual(values["GIT_AUTHOR_DATE"],"@946684800 +0000")
                self.assertEqual(values["GIT_COMMITTER_DATE"],"@946684800 +0000")
                self.assertEqual(values["GIT_CONFIG_GLOBAL"],os.devnull)
            return real(command,*args,**kwargs)
        before=(self.root/".git/config").read_bytes()
        with patch("starter_cli.subprocess.run",side_effect=run):result=self.run_commit()
        self.assert_success(result)
        self.assertEqual(len(mutations),2);self.assertFalse(marker.exists())
        self.assertEqual((self.root/".git/config").read_bytes(),before)

    def test_no_automatic_retry_or_replay(self):
        import starter_cli as module
        real=module._CommitExecution._run;calls=[]
        def run(tx,args,data=None):calls.append(args[0]);return real(tx,args,data)
        with patch.object(module._CommitExecution,"_run",run):result=self.run_commit()
        self.assert_success(result);self.assertEqual(calls,["commit-tree","update-ref"])
        self.assert_zero_mutation()

    def test_new_readonly_forms_exact_and_mutable_commands_not_added(self):
        import starter_cli as module
        forms=[("cat-file","commit",self.head),
               ("diff","--no-ext-diff","--no-textconv","--binary","--full-index","--no-color",self.head,"a"*40)]
        for args in forms:
            with patch("starter_cli.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=b"ok")):
                self.assertEqual(module.git(self.root,*args),b"ok")
            for invalid in (args+("extra",),args[:-1]+("HEAD",),args[:-1]+("--output=x",)):
                with patch("starter_cli.subprocess.run") as run,self.assertRaises(module.Blocked):module.git(self.root,*invalid)
                run.assert_not_called()
        for verb in ("commit-tree","update-ref","commit","add","push","config"):
            with patch("starter_cli.subprocess.run") as run,self.assertRaises(module.Blocked):module.git(self.root,verb)
            run.assert_not_called()

    def test_invalid_execution_clock_zero_mutations(self):
        for value in (None,True,-1,float("nan"),float("inf"),"946684800"):
            with self.subTest(value=value):self.assert_zero_mutation(clock=lambda:value)

    def test_cli_execute_is_explicit_and_other_operations_cannot_chain(self):
        from contextlib import redirect_stdout
        import starter_cli as module
        inputs=self.inputs
        args=["execute-commit","--workspace",str(self.root),"--expected-workspace",str(self.root),
              "--expected-project","FIXTURE","--expected-branch","codex/test","--expected-head",self.head,
              "--expected-count",str(self.count),"--candidate-json",json.dumps(inputs["candidate"]),
              "--stage-receipt-json",json.dumps(inputs["stage_receipt"]),
              "--authorized-intent",self.commit_authorization["authorized_intent"],"--authorized-parent",self.head]
        for field in ("candidate_sha256","stage_receipt_sha256","subject","message","author_name","author_email","committer_name","committer_email","scope"):
            args+=["--"+field.replace("_","-"),inputs[field]]
        for path in inputs["paths"]:args+=["--plan-path",path]
        out=io.StringIO()
        with patch("starter_cli.time.time",return_value=self.epoch),redirect_stdout(out):self.assertEqual(main(args),0)
        self.assert_success(json.loads(out.getvalue()))
        for command in ("observe","prepare","execute-stage","commit-plan"):
            out=io.StringIO()
            with patch.object(module,"execute_commit",side_effect=AssertionError("auto execute")),redirect_stdout(out):
                self.assertEqual(main([command,"--authorized-intent","a"*64]),2)
            self.assertEqual(json.loads(out.getvalue())["status"],"BLOCKED")


class ConfigurationTests(unittest.TestCase):
    def assert_blocked_before_inspection(self, argv):
        from contextlib import redirect_stdout
        out = io.StringIO()
        with ExitStack() as stack:
            checks = [stack.enter_context(patch.object(Path, name, side_effect=AssertionError("filesystem inspection")))
                      for name in ("resolve", "stat", "lstat", "exists", "open", "read_bytes", "read_text", "iterdir")]
            checks.append(stack.enter_context(patch("starter_cli.subprocess.run", side_effect=AssertionError("Git called"))))
            with redirect_stdout(out):
                self.assertEqual(command_main(argv), 2)
            for check in checks:
                check.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED")

    def arguments(self, config):
        return ["--config-json", json.dumps(config), "--expected-head", "a" * 40, "--expected-count", "1"]

    def test_missing_configuration_blocks_before_filesystem(self):
        self.assert_blocked_before_inspection([])

    def test_each_required_configuration_field_is_required(self):
        config = fixture_config("Z:/FIXTURE_UNACCESSED")
        for key in config:
            with self.subTest(key=key):
                value = dict(config); del value[key]
                self.assert_blocked_before_inspection(self.arguments(value))

    def test_placeholders_are_not_defaults(self):
        config = fixture_config("Z:/FIXTURE_UNACCESSED")
        for key in config:
            with self.subTest(key=key):
                self.assert_blocked_before_inspection(self.arguments(dict(config, **{key: "<PENDING>"})))

    def test_unadopted_or_uninitialized_configuration_blocks(self):
        config = fixture_config("Z:/FIXTURE_UNACCESSED")
        for fields in ({"adoption_status": "NOT_ADOPTED"}, {"initialization_status": "INITIALIZATION_REQUIRED"}):
            self.assert_blocked_before_inspection(self.arguments(dict(config, **fields)))

    def test_unsupported_remote_profile_and_paths_block_before_inspection(self):
        config = fixture_config("Z:/FIXTURE_UNACCESSED")
        for fields in ({"remote_policy": "ALLOW"}, {"supported_profile": "POSIX"},
                       {"manifest_path": "other.json"}, {"contract_path": "other.md"},
                       {"repository": "Y:/FOREIGN_UNACCESSED"}, {"work_branch": "main"}):
            self.assert_blocked_before_inspection(self.arguments(dict(config, **fields)))

    def test_configuration_roots_rejected_without_destination_access(self):
        for root in (r"\\foreign.invalid\share\OTHER", r"\\?\Z:\OTHER",
                     r"\\.\Z:\OTHER", "relative", "Z:relative"):
            self.assert_blocked_before_inspection(self.arguments(fixture_config(root)))

    def test_head_and_count_are_explicit(self):
        config = fixture_config("Z:/FIXTURE_UNACCESSED")
        for args in (["--config-json", json.dumps(config)],
                     ["--config-json", json.dumps(config), "--expected-head", "a" * 40],
                     self.arguments(config) + ["--expected-count", "0"]):
            self.assert_blocked_before_inspection(args)

    def test_explicit_config_is_lexical_data_not_permission(self):
        args = SimpleNamespace(config_json=json.dumps(fixture_config("Z:/FIXTURE_UNACCESSED")),
                               workspace=None, expected_workspace=None, expected_project=None,
                               expected_branch=None, expected_head="a" * 40, expected_count=1)
        with patch.object(Path, "lstat", side_effect=AssertionError("filesystem")):
            values = cli_module.configured_values(args)
        self.assertEqual(values, ("Z:/FIXTURE_UNACCESSED", "Z:/FIXTURE_UNACCESSED", "FIXTURE", "codex/test", "a" * 40, 1))



class InitializationTests(unittest.TestCase):
    setUp = ObserverTests.setUp
    g = ObserverTests.g
    refresh_manifest = ObserverTests.refresh_manifest
    commit_fixture = ObserverTests.commit_fixture
    run_observer = ObserverTests.run_observer
    def test_template_manifest_rejected(self):
        path = self.root / cli_module.MANIFEST
        data = json.loads(path.read_text(encoding="utf-8")); data["status"] = "TEMPLATE_ONLY"
        path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        result = self.run_observer()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("Generated project manifest" in c["message"] for c in result["checks"]))

    def test_unadopted_document_rejected(self):
        path = self.root / "PROJECT_STATE.md"
        path.write_text(path.read_text(encoding="utf-8").replace("Adoption-Status: ADOPTED", "Adoption-Status: NOT_ADOPTED"), encoding="utf-8", newline="\n")
        self.refresh_manifest()
        self.assertEqual(self.run_observer()["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
