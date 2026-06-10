"""
Script execution API.

GET  /api/scripts          — list available scripts
POST /api/scripts/{name}   — execute a script with arguments
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent.schemas import ScriptInfo, ScriptListResponse, ScriptResult, ScriptRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])

# Script directory (relative to project root)
_SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "script"

# Files to exclude from the script list (not standalone runnable scripts)
_EXCLUDE_SCRIPTS = {"main", "interactivethread", "__init__"}


def _list_script_files() -> list[Path]:
    """Return list of .py files in script/ that are standalone runnable scripts."""
    scripts = []
    for f in sorted(_SCRIPT_DIR.glob("*.py")):
        name = f.stem
        if name in _EXCLUDE_SCRIPTS or name.startswith("_"):
            continue
        if f.name == "__init__.py":
            continue
        scripts.append(f)
    return scripts


def _script_docstring(script_path: Path) -> str:
    """Extract the first line of the module docstring as a description."""
    try:
        text = script_path.read_text(encoding="utf-8")
        # Simple heuristic: first line after any shebang
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("#!"):
                continue
            if line.startswith('"""') or line.startswith("'''"):
                # Extract first line of docstring
                inner = line.strip('"').strip("'")
                if inner:
                    return inner
            if line and not line.startswith("#") and not line.startswith("import"):
                break
        return ""
    except Exception:
        return ""


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=ScriptListResponse)
async def list_scripts():
    """List all available standalone scripts in the script/ directory."""
    scripts = []
    for f in _list_script_files():
        desc = _script_docstring(f)
        scripts.append(ScriptInfo(name=f.stem, description=desc))
    return ScriptListResponse(scripts=scripts)


@router.post("/{name}", response_model=ScriptResult)
async def run_script(name: str, req: ScriptRunRequest):
    """Execute a script as a subprocess and return its output.

    The script runs in its own process with the project root as CWD.
    Stdout and stderr are captured and returned.
    """
    script_path = _SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail=f"Script '{name}' not found")

    # Security: prevent path traversal
    resolved = script_path.resolve()
    if not str(resolved).startswith(str(_SCRIPT_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Invalid script path")

    if name in _EXCLUDE_SCRIPTS:
        raise HTTPException(status_code=403, detail=f"Script '{name}' is not executable")

    cmd = [sys.executable, str(resolved), *req.args]
    project_root = str(_SCRIPT_DIR.parent)

    logger.info(f"Running script: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=req.timeout,
        )
        return ScriptResult(
            retcode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail=f"Script '{name}' timed out after {req.timeout}s",
        )
    except Exception as e:
        logger.error(f"Script '{name}' failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

