"""Validation helpers for identifiers used in artifact paths."""

import re


MAX_RUN_ID_LENGTH = 128
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\Z", re.ASCII)


def validate_run_id(run_id: str) -> str:
    """Return a safe run identifier or raise ``ValueError``.

    Run identifiers are deliberately validated rather than sanitized because
    they become artifact directory names and are also stored in run models.
    """
    if not isinstance(run_id, str):
        raise ValueError("run_id must be a string")
    if not run_id:
        raise ValueError("run_id must not be empty")
    if len(run_id) > MAX_RUN_ID_LENGTH:
        raise ValueError(
            f"run_id must be at most {MAX_RUN_ID_LENGTH} characters"
        )
    if run_id in {".", ".."} or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError(
            "run_id must begin with an ASCII letter or digit and contain "
            "only ASCII letters, digits, '.', '_' or '-'"
        )
    return run_id
