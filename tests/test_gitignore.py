"""Repository hygiene assertions for generated evaluation output."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_generated_pilot_directory_is_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "outputs/evaluation/pilots/example/trials_public.jsonl"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
