"""
ArchitectIQ DevSecOps - Security Gates Runner (Compatibility Shim)
Forwards all operations to the authoritative five_gates_runner.py.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Insert parent directory for module resolution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from security.framework.five_gates_runner import (
    GATE_DEFINITIONS,
    get_system_memory_info,
    check_memory_threshold,
    run_subprocess_safe,
    run_gate_1,
    run_gate_2,
    run_gate_3,
    run_gate_4,
    run_gate_5,
    generate_summary,
    main,
)

# Compatibility aliases
run_gate_6 = run_gate_5

if __name__ == "__main__":
    main()
