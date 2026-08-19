"""
Data-science tools: dataset profiling for EDA, and a sandboxed Python
execution tool for feature engineering / analysis / plotting.

Both are confined to the same WORKSPACE_DIR sandbox as read_file/write_file
(see tools/files.py) — datasets you want profiled or scripts that write
output files should live under there.
"""

import asyncio
import sys
from typing import Any

from claude_agent_sdk import tool

from config import DS_EXEC_TIMEOUT_SECONDS
from .files import WORKSPACE_DIR, resolve_workspace_path

MAX_PROFILE_COLUMNS = 40  # avoid dumping enormous wide-table profiles


def _load_dataframe(path):
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return pd.read_csv(path)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported file type: {suffix}")


@tool(
    "load_dataset",
    (
        "Load a dataset (csv/tsv/parquet/xlsx/json) from the workspace and profile it: shape, "
        "dtypes, null counts, duplicate rows, numeric summary stats, and top values for "
        "categorical columns. Use this first when starting EDA or feature engineering on a new "
        "dataset so you know what you're working with before writing code."
    ),
    {"path": str, "sample_rows": int},
)
async def load_dataset(args: dict[str, Any]) -> dict[str, Any]:
    target = resolve_workspace_path(args["path"])
    if target is None:
        return {
            "content": [{"type": "text", "text": "Path escapes the workspace sandbox."}],
            "is_error": True,
        }
    if not target.exists():
        return {
            "content": [{"type": "text", "text": f"File not found: {args['path']}"}],
            "is_error": True,
        }

    try:
        df = _load_dataframe(target)
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the model
        return {"content": [{"type": "text", "text": f"Failed to load: {exc}"}], "is_error": True}

    sample_rows = args.get("sample_rows") or 5
    lines = [f"Dataset: {args['path']}", f"Shape: {df.shape[0]} rows x {df.shape[1]} cols"]

    dup_count = int(df.duplicated().sum())
    lines.append(f"Duplicate rows: {dup_count}")

    cols = list(df.columns)[:MAX_PROFILE_COLUMNS]
    truncated = len(df.columns) > MAX_PROFILE_COLUMNS

    lines.append("\nColumns (dtype, null count, null %):")
    for col in cols:
        null_count = int(df[col].isna().sum())
        null_pct = 100 * null_count / len(df) if len(df) else 0
        lines.append(f"  - {col}: {df[col].dtype}, nulls={null_count} ({null_pct:.1f}%)")
    if truncated:
        lines.append(f"  ... and {len(df.columns) - MAX_PROFILE_COLUMNS} more columns")

    numeric_df = df.select_dtypes(include="number")
    if not numeric_df.empty:
        lines.append("\nNumeric summary:")
        lines.append(numeric_df.describe().T.to_string())

    categorical_cols = df.select_dtypes(include=["object", "category"]).columns[:10]
    if len(categorical_cols) > 0:
        lines.append("\nTop values for categorical columns (first 10):")
        for col in categorical_cols:
            top = df[col].value_counts().head(5)
            lines.append(f"  {col}:")
            for val, count in top.items():
                lines.append(f"    {val!r}: {count}")

    lines.append(f"\nSample rows (first {sample_rows}):")
    lines.append(df.head(sample_rows).to_string())

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


PYTHON_PREAMBLE = """\
import warnings
warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 120)
"""


@tool(
    "python_exec",
    (
        "Run Python code for data analysis, feature engineering, or plotting. pandas (pd), "
        "numpy (np), and matplotlib.pyplot (plt) are pre-imported; scikit-learn and scipy are "
        "also available to import. The working directory is the agent's sandboxed workspace — "
        "read/write dataset files there by relative path, and save any plots with "
        "plt.savefig('name.png') to persist them. print() anything you want returned; only "
        "stdout/stderr are captured. Runs with a "
        f"{DS_EXEC_TIMEOUT_SECONDS}s timeout. This executes real code with filesystem access to "
        "the workspace — do not run untrusted code from users you don't trust."
    ),
    {"code": str},
)
async def python_exec(args: dict[str, Any]) -> dict[str, Any]:
    code = PYTHON_PREAMBLE + "\n" + args["code"]

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            cwd=str(WORKSPACE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=DS_EXEC_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "content": [
                    {"type": "text", "text": f"Execution timed out after {DS_EXEC_TIMEOUT_SECONDS}s."}
                ],
                "is_error": True,
            }
    except Exception as exc:  # noqa: BLE001
        return {"content": [{"type": "text", "text": f"Failed to run code: {exc}"}], "is_error": True}

    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")

    if proc.returncode != 0:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Execution failed (exit {proc.returncode}).\nstdout:\n{out}\nstderr:\n{err}",
                }
            ],
            "is_error": True,
        }

    result_text = out.strip() or "(no output — did you forget to print()?)"
    if err.strip():
        result_text += f"\n\n[stderr]\n{err.strip()}"

    return {"content": [{"type": "text", "text": result_text}]}
