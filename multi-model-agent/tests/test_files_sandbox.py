"""Tests for the workspace sandboxing in tools/files.py — the security-critical
path-escape logic shared by read_file/write_file/load_dataset/python_exec."""
import asyncio
import os

import pytest


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Point AGENT_WORKSPACE_DIR at a throwaway tmp dir and reload the module
    so WORKSPACE_DIR picks up the new value."""
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    import importlib
    import tools.files as files_mod

    importlib.reload(files_mod)
    yield files_mod
    importlib.reload(files_mod)  # restore default state for other tests


class TestResolveWorkspacePath:
    def test_normal_relative_path_resolves_inside(self, workspace):
        result = workspace.resolve_workspace_path("data.csv")
        assert result is not None
        assert result.parent == workspace.WORKSPACE_DIR

    def test_nested_relative_path_resolves_inside(self, workspace):
        result = workspace.resolve_workspace_path("sub/dir/data.csv")
        assert result is not None
        assert workspace.WORKSPACE_DIR in result.parents

    def test_dotdot_escape_is_rejected(self, workspace):
        result = workspace.resolve_workspace_path("../../../etc/passwd")
        assert result is None

    def test_single_dotdot_escape_is_rejected(self, workspace):
        result = workspace.resolve_workspace_path("../outside.txt")
        assert result is None

    def test_absolute_path_escape_is_rejected(self, workspace):
        result = workspace.resolve_workspace_path("/etc/passwd")
        assert result is None

    def test_workspace_root_itself_is_allowed(self, workspace):
        result = workspace.resolve_workspace_path(".")
        assert result == workspace.WORKSPACE_DIR

    def test_sneaky_dotdot_that_stays_inside_is_allowed(self, workspace):
        # sub/../data.csv normalizes to just data.csv, which is inside — should be allowed
        result = workspace.resolve_workspace_path("sub/../data.csv")
        assert result is not None
        assert result.parent == workspace.WORKSPACE_DIR


class TestReadWriteFile:
    def test_write_then_read_roundtrip(self, workspace):
        result = asyncio.run(workspace.write_file.handler({"path": "note.txt", "content": "hello world"}))
        assert result.get("is_error") is not True

        result = asyncio.run(workspace.read_file.handler({"path": "note.txt"}))
        assert result["content"][0]["text"] == "hello world"

    def test_read_missing_file_is_error(self, workspace):
        result = asyncio.run(workspace.read_file.handler({"path": "does-not-exist.txt"}))
        assert result.get("is_error") is True

    def test_read_escape_attempt_is_error(self, workspace):
        result = asyncio.run(workspace.read_file.handler({"path": "../../../etc/passwd"}))
        assert result.get("is_error") is True
        assert "sandbox" in result["content"][0]["text"].lower()

    def test_write_escape_attempt_is_error(self, workspace):
        result = asyncio.run(workspace.write_file.handler({"path": "../evil.txt", "content": "pwned"}))
        assert result.get("is_error") is True

    def test_write_creates_parent_dirs(self, workspace):
        result = asyncio.run(
            workspace.write_file.handler({"path": "a/b/c/deep.txt", "content": "deep"})
        )
        assert result.get("is_error") is not True
        assert (workspace.WORKSPACE_DIR / "a" / "b" / "c" / "deep.txt").read_text() == "deep"
