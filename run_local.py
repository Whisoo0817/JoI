"""Backward-compat shim for `from run_local import generate_joi_code, JoiGenerationError`.

The active pipeline lives at `paper.run_local_ir`. This shim re-exports the
public symbols so legacy callers (e.g. `app.py`) keep working without a deep
refactor of import paths.
"""

from paper.run_local_ir import generate_joi_code  # noqa: F401
from pipeline_helpers import JoiGenerationError  # noqa: F401

__all__ = ["generate_joi_code", "JoiGenerationError"]
