import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_support_ticket_runs_offline():
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "support_ticket.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Served by: s1" in result.stdout
    assert "Served by: s2" in result.stdout
    assert "low_confidence" in result.stdout
    assert "out_of_answer_space" in result.stdout
    assert "Total cost:" in result.stdout
    assert "Trace store:" in result.stdout


def test_compile_from_traces_runs_offline():
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "compile_from_traces.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"traces": 1000' in result.stdout
    assert "Lifecycle: candidate -> shadow -> promoted" in result.stdout
    assert "Healthy traffic: served=" in result.stdout
    assert " -> demoted;" in result.stdout
    assert "Promotion S5 record" in result.stdout
    assert "Demotion meta record" in result.stdout
