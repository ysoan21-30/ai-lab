"""Tests for tools/data_science.py — load_dataset profiling and python_exec sandboxed
execution. No Claude/Voyage API calls involved; python_exec really spawns a subprocess."""
import asyncio

import pytest


@pytest.fixture()
def ds_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    import importlib
    import tools.files as files_mod
    import tools.data_science as ds_mod

    importlib.reload(files_mod)
    importlib.reload(ds_mod)
    yield ds_mod, tmp_path
    importlib.reload(files_mod)
    importlib.reload(ds_mod)


class TestLoadDataset:
    def test_profiles_csv(self, ds_tools):
        ds_mod, tmp_path = ds_tools
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("a,b,c\n1,x,10\n2,y,20\n3,,30\n2,y,20\n")

        result = asyncio.run(ds_mod.load_dataset.handler({"path": "sample.csv", "sample_rows": 3}))
        text = result["content"][0]["text"]
        assert result.get("is_error") is not True
        assert "4 rows x 3 cols" in text
        assert "Duplicate rows: 1" in text  # row (2,y,20) appears twice
        assert "nulls=1" in text and "- b:" in text

    def test_missing_file_is_error(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(ds_mod.load_dataset.handler({"path": "nope.csv"}))
        assert result.get("is_error") is True

    def test_escape_attempt_is_error(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(ds_mod.load_dataset.handler({"path": "../../etc/passwd"}))
        assert result.get("is_error") is True

    def test_unsupported_extension_is_error(self, ds_tools):
        ds_mod, tmp_path = ds_tools
        bad = tmp_path / "file.exe"
        bad.write_bytes(b"not a dataset")
        result = asyncio.run(ds_mod.load_dataset.handler({"path": "file.exe"}))
        assert result.get("is_error") is True

    def test_tsv_loads(self, ds_tools):
        ds_mod, tmp_path = ds_tools
        tsv_path = tmp_path / "sample.tsv"
        tsv_path.write_text("a\tb\n1\t2\n3\t4\n")
        result = asyncio.run(ds_mod.load_dataset.handler({"path": "sample.tsv"}))
        assert result.get("is_error") is not True
        assert "2 rows x 2 cols" in result["content"][0]["text"]


class TestPythonExec:
    def test_prints_output(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(ds_mod.python_exec.handler({"code": "print(1 + 1)"}))
        assert result.get("is_error") is not True
        assert "2" in result["content"][0]["text"]

    def test_pandas_preimported(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(
            ds_mod.python_exec.handler({"code": "print(pd.DataFrame({'x':[1,2]}).shape)"})
        )
        assert result.get("is_error") is not True
        assert "(2, 1)" in result["content"][0]["text"]

    def test_no_print_gives_placeholder(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(ds_mod.python_exec.handler({"code": "x = 1 + 1"}))
        assert "forget to print" in result["content"][0]["text"]

    def test_syntax_error_is_reported(self, ds_tools):
        ds_mod, _ = ds_tools
        result = asyncio.run(ds_mod.python_exec.handler({"code": "def bad(:"}))
        assert result.get("is_error") is True

    def test_runs_in_workspace_cwd(self, ds_tools):
        ds_mod, tmp_path = ds_tools
        (tmp_path / "marker.txt").write_text("hi")
        result = asyncio.run(
            ds_mod.python_exec.handler({"code": "import os; print(os.path.exists('marker.txt'))"})
        )
        assert "True" in result["content"][0]["text"]

    def test_timeout_is_enforced(self, ds_tools, monkeypatch):
        import config

        monkeypatch.setattr(config, "DS_EXEC_TIMEOUT_SECONDS", 1)
        ds_mod, _ = ds_tools
        monkeypatch.setattr(ds_mod, "DS_EXEC_TIMEOUT_SECONDS", 1)
        result = asyncio.run(ds_mod.python_exec.handler({"code": "import time; time.sleep(5)"}))
        assert result.get("is_error") is True
        assert "timed out" in result["content"][0]["text"].lower()
