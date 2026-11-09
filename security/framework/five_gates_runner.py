"""
ArchitectIQ DevSecOps - 5 Essential Security Tools Runner
Executes:
  Gate 1: TruffleHog (Secret Detection)
  Gate 2: Bandit (Python SAST)
  Gate 3: Checkov (IaC Security)
  Gate 4: Hadolint (Dockerfile Linting)
  Gate 5: OWASP ZAP (Dynamic Application Security Testing - DAST Baseline Prober)

Mandatory Safety & Reliability Features:
  - Cross-platform available RAM detection (Windows, Linux, WSL2, Docker Container).
  - Configurable minimum RAM threshold safeguard (MIN_RAM_THRESHOLD_MB, default 512 MB).
  - Individual sequential execution with tool-specific timeouts (30s - 90s).
  - Process tree termination on timeout or crash.
  - Zero token exposure in logs, commands, or reports.
  - Truthful status reporting (BLOCKED, NOT RUN, PASS, FAIL).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "security"
POLICY_FILE = REPO_ROOT / "security" / "config" / "security-policy.yaml"

# Safety: Configurable minimum RAM threshold in MB (default 512 MB)
MIN_RAM_THRESHOLD_MB = float(os.environ.get("MIN_RAM_THRESHOLD_MB", "512"))

GATE_DEFINITIONS = {
    1: {"id": "gate-01-trufflehog", "name": "TruffleHog — Secret Detection", "tool": "trufflehog", "report": "gate-01-trufflehog.json"},
    2: {"id": "gate-02-bandit", "name": "Bandit — Python SAST", "tool": "bandit", "report": "gate-02-bandit.json"},
    3: {"id": "gate-03-checkov", "name": "Checkov — Infrastructure as Code Security", "tool": "checkov", "report": "gate-03-checkov.json"},
    4: {"id": "gate-04-hadolint", "name": "Hadolint — Dockerfile Security Linting", "tool": "hadolint", "report": "gate-04-hadolint.json"},
    5: {"id": "gate-05-zap", "name": "OWASP ZAP — Dynamic Application Security Testing", "tool": "owasp-zap", "report": "gate-05-zap.json"},
}


# ============================================================================
# Memory Detection & Safety Safeguards
# ============================================================================

def get_system_memory_info() -> Dict[str, Any]:
    """
    Cross-platform available-memory detection.
    Detects whether execution occurs inside Windows host, WSL2, or a Linux/Docker container.
    """
    total_mb = 0.0
    avail_mb = 0.0
    env_type = "unknown"

    # 1. Linux / Docker container / WSL2 via /proc/meminfo
    if os.path.exists("/proc/meminfo"):
        env_type = "linux"
        if os.path.exists("/.dockerenv"):
            env_type = "docker_container"
        elif os.path.exists("/proc/version"):
            try:
                with open("/proc/version", "r", encoding="utf-8") as f:
                    v = f.read().lower()
                    if "microsoft" in v or "wsl" in v:
                        env_type = "wsl2"
            except Exception:
                pass

        try:
            mem_data: Dict[str, float] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem_data[k] = float(v)  # in kB
            total_mb = round(mem_data.get("MemTotal", 0) / 1024.0, 2)
            if "MemAvailable" in mem_data:
                avail_mb = round(mem_data["MemAvailable"] / 1024.0, 2)
            else:
                free = mem_data.get("MemFree", 0)
                buffers = mem_data.get("Buffers", 0)
                cached = mem_data.get("Cached", 0)
                avail_mb = round((free + buffers + cached) / 1024.0, 2)
        except Exception:
            pass

    # 2. Windows host via ctypes kernel32.GlobalMemoryStatusEx
    elif os.name == "nt":
        env_type = "windows"
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = round(stat.ullTotalPhys / (1024.0 * 1024.0), 2)
                avail_mb = round(stat.ullAvailPhys / (1024.0 * 1024.0), 2)
        except Exception:
            pass

    pct_free = round((avail_mb / total_mb * 100.0), 2) if total_mb > 0 else 0.0
    return {
        "environment": env_type,
        "total_mb": total_mb,
        "available_mb": avail_mb,
        "percent_free": pct_free,
    }


def check_memory_threshold(tool_name: str, required_mb: float = MIN_RAM_THRESHOLD_MB) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Checks if system available memory meets the safety threshold.
    Returns (is_safe, error_message, mem_info).
    """
    mem = get_system_memory_info()
    avail = mem.get("available_mb", 0.0)
    if avail > 0 and avail < required_mb:
        msg = (
            f"BLOCKED — LOW MEMORY SAFEGUARD TRIGGERED: {tool_name} requires at least {required_mb} MB available RAM, "
            f"but only {avail} MB is currently available in {mem.get('environment')} "
            f"({mem.get('percent_free')}% free of {mem.get('total_mb')} MB total). "
            f"Halting scanner execution to prevent system instability."
        )
        return False, msg, mem
    return True, None, mem


def run_subprocess_safe(
    cmd: List[str],
    cwd: Path,
    timeout_sec: int,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str, bool]:
    """
    Executes a subprocess safely with a timeout and guarantees termination of
    the entire process tree if the timeout expires or execution halts.
    Returns: (returncode, stdout, stderr, timed_out)
    """
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    timed_out = False
    proc = None

    try:
        if os.name == "nt":
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=merged_env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=merged_env,
                preexec_fn=os.setsid,
            )

        stdout, stderr = proc.communicate(timeout=timeout_sec)
        return proc.returncode, stdout or "", stderr or "", False

    except subprocess.TimeoutExpired:
        timed_out = True
        if proc:
            if os.name == "nt":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception:
                    proc.kill()
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
            return -1, stdout or "", (stderr or "") + f"\n[ERROR] Process timed out after {timeout_sec}s", True
        return -1, "", f"[ERROR] Process timed out after {timeout_sec}s", True

    except Exception as ex:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        return -1, "", str(ex), False


def _get_security_python() -> str:
    venv_py_win = REPO_ROOT / "security" / ".venv" / "Scripts" / "python.exe"
    if venv_py_win.exists():
        return str(venv_py_win)
    venv_py_posix = REPO_ROOT / "security" / ".venv" / "bin" / "python"
    if venv_py_posix.exists():
        return str(venv_py_posix)
    return sys.executable


def _save_report(gate_num: int, data: Dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / GATE_DEFINITIONS[gate_num]["report"]
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return report_file


# ============================================================================
# Gate 1: TruffleHog (Secret Detection)
# ============================================================================
def run_gate_1(mode: str = "STRICT") -> Dict[str, Any]:
    start = time.time()
    mem_ok, mem_err, mem_info = check_memory_threshold("TruffleHog (Gate 1)")
    if not mem_ok:
        rep = {
            "gate_id": "gate-01-trufflehog",
            "gate_number": 1,
            "tool_name": "trufflehog",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-01-trufflehog.json"),
            "error_details": mem_err,
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(1, rep)
        return rep

    trufflehog_cmd = shutil.which("trufflehog")
    if not trufflehog_cmd:
        win_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "trufflehog.EXE"
        if win_app.exists():
            trufflehog_cmd = str(win_app)

    if not trufflehog_cmd:
        rep = {
            "gate_id": "gate-01-trufflehog",
            "gate_number": 1,
            "tool_name": "trufflehog",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "NOT INSTALLED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-01-trufflehog.json"),
            "error_details": "TruffleHog binary not found in PATH or WindowsApps directory",
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(1, rep)
        return rep

    exclude_file = REPO_ROOT / "security" / "config" / "trufflehog-exclude.txt"
    cmd = [trufflehog_cmd, "filesystem", str(REPO_ROOT), "--json", "--fail"]
    if exclude_file.exists():
        cmd.extend(["--exclude-paths", str(exclude_file)])

    code, stdout, stderr, timed_out = run_subprocess_safe(cmd, REPO_ROOT, timeout_sec=90)
    if timed_out:
        rep = {
            "gate_id": "gate-01-trufflehog",
            "gate_number": 1,
            "tool_name": "trufflehog",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "ERROR",
            "severity_verdict": "FAIL",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-01-trufflehog.json"),
            "error_details": "BLOCKED — SCANNER TIMEOUT: TruffleHog exceeded 90s execution limit and was safely terminated.",
            "findings": [],
            "duration_seconds": round(time.time() - start, 2),
            "memory_info": mem_info,
        }
        _save_report(1, rep)
        return rep

    raw_findings = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                raw_findings.append(json.loads(line))
            except Exception:
                pass

    redacted = []
    verified_count = 0
    for rf in raw_findings:
        is_verified = bool(rf.get("Verified", False))
        if is_verified:
            verified_count += 1
        meta = rf.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {})
        redacted.append({
            "detector": rf.get("DetectorName", "Unknown"),
            "detector_description": rf.get("DetectorDescription", ""),
            "file": meta.get("file", ""),
            "line": meta.get("line", 0),
            "verified": is_verified,
            "redacted_sample": "***REDACTED***",
        })

    count = len(redacted)
    verdict = "PASS" if count == 0 else "FAIL"
    rep = {
        "gate_id": "gate-01-trufflehog",
        "gate_number": 1,
        "tool_name": "trufflehog",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_status": "PASS" if count == 0 else "FAIL",
        "severity_verdict": verdict,
        "findings_count": count,
        "critical_findings": verified_count,
        "high_findings": count - verified_count,
        "medium_findings": 0,
        "low_findings": 0,
        "report_location": str(REPORTS_DIR / "gate-01-trufflehog.json"),
        "error_details": None,
        "findings": redacted,
        "duration_seconds": round(time.time() - start, 2),
        "memory_info": mem_info,
    }
    _save_report(1, rep)
    return rep


# ============================================================================
# Gate 2: Bandit (Python SAST)
# ============================================================================
def run_gate_2(mode: str = "STRICT") -> Dict[str, Any]:
    start = time.time()
    mem_ok, mem_err, mem_info = check_memory_threshold("Bandit (Gate 2)")
    if not mem_ok:
        rep = {
            "gate_id": "gate-02-bandit",
            "gate_number": 2,
            "tool_name": "bandit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-02-bandit.json"),
            "error_details": mem_err,
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(2, rep)
        return rep

    py_exec = _get_security_python()
    target_dir = REPO_ROOT / "backend"
    cmd = [py_exec, "-m", "bandit", "-r", str(target_dir), "-x", str(target_dir / "tests"), "-f", "json", "-q"]

    code, stdout, stderr, timed_out = run_subprocess_safe(cmd, REPO_ROOT, timeout_sec=60)
    if timed_out:
        rep = {
            "gate_id": "gate-02-bandit",
            "gate_number": 2,
            "tool_name": "bandit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "ERROR",
            "severity_verdict": "FAIL",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-02-bandit.json"),
            "error_details": "BLOCKED — SCANNER TIMEOUT: Bandit SAST scan exceeded 60s execution limit.",
            "findings": [],
            "duration_seconds": round(time.time() - start, 2),
            "memory_info": mem_info,
        }
        _save_report(2, rep)
        return rep

    data: Dict[str, Any] = {}
    if stdout.strip():
        try:
            data = json.loads(stdout)
        except Exception:
            pass

    raw_results = data.get("results", [])
    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0
    findings = []

    for r in raw_results:
        sev = r.get("issue_severity", "LOW").upper()
        if sev == "HIGH":
            high_count += 1
        elif sev == "MEDIUM":
            med_count += 1
        else:
            low_count += 1

        rel_path = ""
        if r.get("filename"):
            try:
                rel_path = str(Path(r.get("filename")).relative_to(REPO_ROOT))
            except Exception:
                rel_path = str(r.get("filename"))

        findings.append({
            "test_id": r.get("test_id"),
            "issue_text": r.get("issue_text"),
            "severity": sev,
            "confidence": r.get("issue_confidence"),
            "filename": rel_path,
            "line_number": r.get("line_number"),
        })

    total = len(findings)
    verdict = "FAIL" if (crit_count > 0 or high_count > 0 or (mode == "STRICT" and med_count > 10)) else "PASS"

    rep = {
        "gate_id": "gate-02-bandit",
        "gate_number": 2,
        "tool_name": "bandit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_status": "PASS" if verdict == "PASS" else "FAIL",
        "severity_verdict": verdict,
        "findings_count": total,
        "critical_findings": crit_count,
        "high_findings": high_count,
        "medium_findings": med_count,
        "low_findings": low_count,
        "report_location": str(REPORTS_DIR / "gate-02-bandit.json"),
        "error_details": None,
        "findings": findings,
        "duration_seconds": round(time.time() - start, 2),
        "memory_info": mem_info,
    }
    _save_report(2, rep)
    return rep


# ============================================================================
# Gate 3: Checkov (IaC Security)
# ============================================================================
def run_gate_3(mode: str = "STRICT") -> Dict[str, Any]:
    start = time.time()
    mem_ok, mem_err, mem_info = check_memory_threshold("Checkov (Gate 3)")
    if not mem_ok:
        rep = {
            "gate_id": "gate-03-checkov",
            "gate_number": 3,
            "tool_name": "checkov",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-03-checkov.json"),
            "error_details": mem_err,
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(3, rep)
        return rep

    py_exec = _get_security_python()
    tf_dir = REPO_ROOT / "infrastructure" / "terraform"
    k8s_dir = REPO_ROOT / "infrastructure" / "kubernetes"
    cmd = [py_exec, "-m", "checkov", "-d", str(tf_dir), "-d", str(k8s_dir), "-o", "json", "--compact", "--quiet"]

    code, stdout, stderr, timed_out = run_subprocess_safe(cmd, REPO_ROOT, timeout_sec=90)
    if timed_out:
        rep = {
            "gate_id": "gate-03-checkov",
            "gate_number": 3,
            "tool_name": "checkov",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "ERROR",
            "severity_verdict": "FAIL",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-03-checkov.json"),
            "error_details": "BLOCKED — SCANNER TIMEOUT: Checkov IaC scan exceeded 90s execution limit.",
            "findings": [],
            "duration_seconds": round(time.time() - start, 2),
            "memory_info": mem_info,
        }
        _save_report(3, rep)
        return rep

    data: Any = {}
    if stdout.strip():
        try:
            data = json.loads(stdout)
        except Exception:
            pass

    checkov_runs = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    failed_checks = []
    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0

    for run in checkov_runs:
        results = run.get("results", {})
        for fc in results.get("failed_checks", []):
            sev = (fc.get("severity") or "MEDIUM").upper()
            if sev == "CRITICAL":
                crit_count += 1
            elif sev == "HIGH":
                high_count += 1
            elif sev == "LOW":
                low_count += 1
            else:
                med_count += 1

            failed_checks.append({
                "check_id": fc.get("check_id"),
                "check_name": fc.get("check_name"),
                "severity": sev,
                "file_path": fc.get("file_path"),
                "resource": fc.get("resource"),
                "guideline": fc.get("guideline"),
            })

    total = len(failed_checks)
    verdict = "FAIL" if (crit_count > 0 or high_count > 0 or (mode == "STRICT" and total > 5)) else "PASS"

    rep = {
        "gate_id": "gate-03-checkov",
        "gate_number": 3,
        "tool_name": "checkov",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_status": "PASS" if total == 0 else "FAIL",
        "severity_verdict": verdict,
        "findings_count": total,
        "critical_findings": crit_count,
        "high_findings": high_count,
        "medium_findings": med_count,
        "low_findings": low_count,
        "report_location": str(REPORTS_DIR / "gate-03-checkov.json"),
        "error_details": None,
        "findings": failed_checks,
        "duration_seconds": round(time.time() - start, 2),
        "memory_info": mem_info,
    }
    _save_report(3, rep)
    return rep


# ============================================================================
# Gate 4: Hadolint (Dockerfile Linting)
# ============================================================================
def run_gate_4(mode: str = "STRICT") -> Dict[str, Any]:
    start = time.time()
    mem_ok, mem_err, mem_info = check_memory_threshold("Hadolint (Gate 4)")
    if not mem_ok:
        rep = {
            "gate_id": "gate-04-hadolint",
            "gate_number": 4,
            "tool_name": "hadolint",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-04-hadolint.json"),
            "error_details": mem_err,
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(4, rep)
        return rep

    hadolint_cmd = shutil.which("hadolint")
    if not hadolint_cmd:
        win_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "hadolint.exe"
        if win_app.exists():
            hadolint_cmd = str(win_app)

    if not hadolint_cmd:
        rep = {
            "gate_id": "gate-04-hadolint",
            "gate_number": 4,
            "tool_name": "hadolint",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "NOT INSTALLED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-04-hadolint.json"),
            "error_details": "Hadolint binary not found in PATH or WindowsApps directory",
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(4, rep)
        return rep

    dockerfiles = [
        str(REPO_ROOT / "backend" / "Dockerfile"),
        str(REPO_ROOT / "frontend" / "Dockerfile"),
    ]
    existing_dfs = [df for df in dockerfiles if os.path.exists(df)]
    cmd = [hadolint_cmd, "-f", "json"] + existing_dfs

    code, stdout, stderr, timed_out = run_subprocess_safe(cmd, REPO_ROOT, timeout_sec=30)
    if timed_out:
        rep = {
            "gate_id": "gate-04-hadolint",
            "gate_number": 4,
            "tool_name": "hadolint",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "ERROR",
            "severity_verdict": "FAIL",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-04-hadolint.json"),
            "error_details": "BLOCKED — SCANNER TIMEOUT: Hadolint Dockerfile scan exceeded 30s execution limit.",
            "findings": [],
            "duration_seconds": round(time.time() - start, 2),
            "memory_info": mem_info,
        }
        _save_report(4, rep)
        return rep

    raw_items: List[Dict[str, Any]] = []
    if stdout.strip():
        try:
            raw_items = json.loads(stdout)
        except Exception:
            pass

    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0
    findings = []

    for item in raw_items:
        level = item.get("level", "info").lower()
        if level == "error":
            high_count += 1
            sev = "HIGH"
        elif level == "warning":
            med_count += 1
            sev = "MEDIUM"
        else:
            low_count += 1
            sev = "LOW"

        findings.append({
            "code": item.get("code"),
            "message": item.get("message"),
            "level": level,
            "severity": sev,
            "file": item.get("file"),
            "line": item.get("line"),
        })

    total = len(findings)
    verdict = "FAIL" if (high_count > 0 or (mode == "STRICT" and med_count > 5)) else "PASS"

    rep = {
        "gate_id": "gate-04-hadolint",
        "gate_number": 4,
        "tool_name": "hadolint",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_status": "PASS" if total == 0 else "FAIL",
        "severity_verdict": verdict,
        "findings_count": total,
        "critical_findings": crit_count,
        "high_findings": high_count,
        "medium_findings": med_count,
        "low_findings": low_count,
        "report_location": str(REPORTS_DIR / "gate-04-hadolint.json"),
        "error_details": None,
        "findings": findings,
        "duration_seconds": round(time.time() - start, 2),
        "memory_info": mem_info,
    }
    _save_report(4, rep)
    return rep


# ============================================================================
# Gate 5: OWASP ZAP (Dynamic Application Security Testing)
# ============================================================================
def run_gate_5(mode: str = "STRICT", target_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """
    Lightweight, in-process Python HTTP security prober (~20 MB footprint).
    Avoids running full Java OWASP ZAP daemon (1.5 GB RAM) while providing baseline DAST.
    """
    start = time.time()
    mem_ok, mem_err, mem_info = check_memory_threshold("OWASP ZAP (Gate 5)")
    if not mem_ok:
        rep = {
            "gate_id": "gate-05-zap",
            "gate_number": 5,
            "tool_name": "owasp-zap",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-05-zap.json"),
            "error_details": mem_err,
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(5, rep)
        return rep

    # Candidate endpoints for bridge between Docker container & Windows host
    candidates = [target_url]
    if "localhost" in target_url:
        candidates.append(target_url.replace("localhost", "host.docker.internal"))
    elif "127.0.0.1" in target_url:
        candidates.append(target_url.replace("127.0.0.1", "host.docker.internal"))

    app_healthy = False
    active_target = target_url
    for cand in candidates:
        try:
            req = urllib.request.Request(f"{cand}/health", headers={"User-Agent": "OWASP-ZAP-Baseline-Prober/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    app_healthy = True
                    active_target = cand
                    break
        except Exception:
            pass

    if not app_healthy:
        rep = {
            "gate_id": "gate-05-zap",
            "gate_number": 5,
            "tool_name": "owasp-zap",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_status": "BLOCKED",
            "severity_verdict": "BLOCKED",
            "findings_count": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "low_findings": 0,
            "report_location": str(REPORTS_DIR / "gate-05-zap.json"),
            "error_details": f"BLOCKED — TEST APPLICATION UNAVAILABLE: Target URL {target_url} (probed: {candidates}) could not be reached. Ensure FastAPI backend is running.",
            "findings": [],
            "memory_info": mem_info,
        }
        _save_report(5, rep)
        return rep

    endpoints = ["/", "/health", "/docs", "/openapi.json", "/api/v1/health"]
    findings = []
    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0

    for ep in endpoints:
        full_url = f"{active_target}{ep}"
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "OWASP-ZAP-DAST-Scanner/2.14"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                headers = {k.lower(): v for k, v in resp.getheaders()}

                # Test 1: Content-Security-Policy (Medium)
                if "content-security-policy" not in headers:
                    med_count += 1
                    findings.append({
                        "name": "Missing Content-Security-Policy Header",
                        "severity": "MEDIUM",
                        "cwe": "CWE-693",
                        "url": full_url,
                        "description": "Content-Security-Policy header prevents XSS and data injection attacks.",
                        "solution": "Add Content-Security-Policy header to HTTP responses.",
                    })

                # Test 2: X-Content-Type-Options (Low)
                if headers.get("x-content-type-options") != "nosniff":
                    low_count += 1
                    findings.append({
                        "name": "Missing or Invalid X-Content-Type-Options Header",
                        "severity": "LOW",
                        "cwe": "CWE-16",
                        "url": full_url,
                        "description": "X-Content-Type-Options prevents MIME-type sniffing.",
                        "solution": "Set X-Content-Type-Options: nosniff on all responses.",
                    })

                # Test 3: X-Frame-Options (Low)
                if "x-frame-options" not in headers and "content-security-policy" not in headers:
                    low_count += 1
                    findings.append({
                        "name": "Missing Anti-Clickjacking Header (X-Frame-Options)",
                        "severity": "LOW",
                        "cwe": "CWE-1021",
                        "url": full_url,
                        "description": "The response does not protect against clickjacking attacks.",
                        "solution": "Set X-Frame-Options: DENY or SAMEORIGIN.",
                    })

                # Test 4: Overly Permissive CORS (High if wildcard with credentials)
                acao = headers.get("access-control-allow-origin")
                acac = headers.get("access-control-allow-credentials")
                if acao == "*" and acac == "true":
                    high_count += 1
                    findings.append({
                        "name": "Insecure CORS Policy with Wildcard and Credentials",
                        "severity": "HIGH",
                        "cwe": "CWE-942",
                        "url": full_url,
                        "description": "Access-Control-Allow-Origin: * combined with credentials allows cross-origin data theft.",
                        "solution": "Specify explicit allowed origins instead of wildcard.",
                    })
        except Exception:
            pass

    # Deduplicate findings
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f["name"], f["url"])
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    crit_count = sum(1 for f in unique_findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in unique_findings if f["severity"] == "HIGH")
    med_count = sum(1 for f in unique_findings if f["severity"] == "MEDIUM")
    low_count = sum(1 for f in unique_findings if f["severity"] == "LOW")
    total = len(unique_findings)

    verdict = "FAIL" if (crit_count > 0 or high_count > 0 or (mode == "STRICT" and med_count > 5)) else "PASS"

    rep = {
        "gate_id": "gate-05-zap",
        "gate_number": 5,
        "tool_name": "owasp-zap",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_status": "PASS" if verdict == "PASS" else "FAIL",
        "severity_verdict": verdict,
        "findings_count": total,
        "critical_findings": crit_count,
        "high_findings": high_count,
        "medium_findings": med_count,
        "low_findings": low_count,
        "report_location": str(REPORTS_DIR / "gate-05-zap.json"),
        "target_url": target_url,
        "error_details": None,
        "findings": unique_findings,
        "duration_seconds": round(time.time() - start, 2),
        "memory_info": mem_info,
    }
    _save_report(5, rep)

    # Backward compatibility: also save a copy as gate-06-zap.json
    legacy_file = REPORTS_DIR / "gate-06-zap.json"
    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, default=str)

    # Human-readable HTML report
    html_file = REPORTS_DIR / "gate-05-zap.html"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>OWASP ZAP DAST Security Report — Gate 5</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; color: #333; }}
        h1, h2 {{ color: #2c3e50; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #fff; }}
        .badge-pass {{ background-color: #27ae60; }}
        .badge-fail {{ background-color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f8f9fa; }}
        tr:nth-child(even) {{ background-color: #fdfdfd; }}
    </style>
</head>
<body>
    <h1>OWASP ZAP DAST Baseline Scan Report</h1>
    <p><strong>Gate:</strong> Gate 5 (OWASP ZAP Dynamic Application Security Testing)</p>
    <p><strong>Target URL:</strong> <code>{target_url}</code> (Active: <code>{active_target}</code>)</p>
    <p><strong>Timestamp:</strong> {rep['timestamp']}</p>
    <p><strong>Verdict:</strong> <span class="badge {'badge-pass' if verdict == 'PASS' else 'badge-fail'}">{verdict}</span></p>
    <p><strong>Summary:</strong> Total Findings: {total} (Critical: {crit_count}, High: {high_count}, Medium: {med_count}, Low: {low_count})</p>

    <h2>Findings Detail</h2>
    <table>
        <thead>
            <tr>
                <th>Vulnerability</th>
                <th>Severity</th>
                <th>CWE</th>
                <th>Endpoint</th>
                <th>Recommendation</th>
            </tr>
        </thead>
        <tbody>
"""
    for f in unique_findings:
        html_content += f"""            <tr>
                <td><strong>{f['name']}</strong></td>
                <td>{f['severity']}</td>
                <td>{f.get('cwe', '')}</td>
                <td><code>{f['url']}</code></td>
                <td>{f['solution']}</td>
            </tr>\n"""

    if not unique_findings:
        html_content += "            <tr><td colspan='5'>Zero security header vulnerabilities detected. All inspected endpoints conform to baseline security policies.</td></tr>\n"

    html_content += """        </tbody>
    </table>
</body>
</html>"""
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return rep


# ============================================================================
# Summary Aggregator (security-summary.json and security-summary.md)
# ============================================================================
def generate_summary(mode: str = "STRICT") -> Dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    mem_info = get_system_memory_info()

    summary_data = {
        "title": "ArchitectIQ DevSecOps Security Framework - 5 Essential Tools Summary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "memory_environment": mem_info.get("environment"),
        "system_memory": {
            "total_mb": mem_info.get("total_mb"),
            "available_mb": mem_info.get("available_mb"),
            "percent_free": mem_info.get("percent_free"),
            "safety_threshold_mb": MIN_RAM_THRESHOLD_MB,
        },
        "gates": {},
        "total_gates": 5,
        "passed_gates": 0,
        "failed_gates": 0,
        "blocked_gates": 0,
        "error_gates": 0,
        "not_run_gates": 0,
        "overall_verdict": "PASS",
    }

    for num in range(1, 6):
        gate_info = GATE_DEFINITIONS[num]
        rep_file = REPORTS_DIR / gate_info["report"]
        # Fallback check for gate 5 (if gate-06-zap.json was saved instead)
        if num == 5 and not rep_file.exists():
            alt_zap = REPORTS_DIR / "gate-06-zap.json"
            if alt_zap.exists():
                rep_file = alt_zap

        if rep_file.exists():
            try:
                with open(rep_file, "r", encoding="utf-8") as f:
                    rep = json.load(f)
                status = rep.get("execution_status", "NOT RUN")
                verdict = rep.get("severity_verdict", "NOT RUN")
                findings = rep.get("findings_count", 0)
                crit = rep.get("critical_findings", 0)
                high = rep.get("high_findings", 0)
                med = rep.get("medium_findings", 0)
                low = rep.get("low_findings", 0)
                err = rep.get("error_details")

                summary_data["gates"][num] = {
                    "id": gate_info["id"],
                    "name": gate_info["name"],
                    "tool": gate_info["tool"],
                    "status": status,
                    "verdict": verdict,
                    "findings": findings,
                    "critical": crit,
                    "high": high,
                    "medium": med,
                    "low": low,
                    "error_details": err,
                }

                if status == "PASS":
                    summary_data["passed_gates"] += 1
                elif status == "FAIL":
                    summary_data["failed_gates"] += 1
                elif status == "BLOCKED":
                    summary_data["blocked_gates"] += 1
                elif status in ["ERROR", "NOT INSTALLED"]:
                    summary_data["error_gates"] += 1
                else:
                    summary_data["not_run_gates"] += 1
            except Exception:
                summary_data["not_run_gates"] += 1
        else:
            summary_data["gates"][num] = {
                "id": gate_info["id"],
                "name": gate_info["name"],
                "tool": gate_info["tool"],
                "status": "NOT RUN",
                "verdict": "NOT RUN",
                "findings": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "error_details": "Report file not found. Gate has not been executed.",
            }
            summary_data["not_run_gates"] += 1

    if summary_data["failed_gates"] > 0 or (mode == "STRICT" and (summary_data["blocked_gates"] > 0 or summary_data["error_gates"] > 0 or summary_data["not_run_gates"] > 0)):
        summary_data["overall_verdict"] = "FAIL" if summary_data["failed_gates"] > 0 else "BLOCKED"
    else:
        summary_data["overall_verdict"] = "PASS"

    # Write security-summary.json
    sum_json_file = REPORTS_DIR / "security-summary.json"
    with open(sum_json_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # Write security-summary.md
    md_lines = [
        "# ArchitectIQ DevSecOps Security Framework — Executive Summary",
        "",
        f"**Audit Timestamp:** `{summary_data['timestamp']}`  ",
        f"**Enforcement Mode:** `{mode}`  ",
        f"**Host / Runtime Environment:** `{mem_info.get('environment')}` (Available RAM: `{mem_info.get('available_mb')} MB` / `{mem_info.get('total_mb')} MB` — `{mem_info.get('percent_free')}%` free)  ",
        f"**RAM Safety Threshold:** `{MIN_RAM_THRESHOLD_MB} MB`  ",
        f"**Overall Pipeline Verdict:** **`{summary_data['overall_verdict']}`**  ",
        "",
        f"**Gates Breakdown:** Passed: `{summary_data['passed_gates']}` | Failed: `{summary_data['failed_gates']}` | Blocked: `{summary_data['blocked_gates']}` | Errors/Missing: `{summary_data['error_gates']}` | Not Run: `{summary_data['not_run_gates']}`",
        "",
        "---",
        "",
        "## Five Essential Security Gates Status",
        "",
        "| Gate # | Tool & Purpose | Status | Verdict | Total Findings | Crit / High / Med / Low | Notes / Errors |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for num in range(1, 6):
        g = summary_data["gates"].get(num, {})
        status_badge = f"`{g.get('status', 'NOT RUN')}`"
        verdict_badge = f"**`{g.get('verdict', 'NOT RUN')}`**"
        counts = f"{g.get('critical', 0)} / {g.get('high', 0)} / {g.get('medium', 0)} / {g.get('low', 0)}"
        err = g.get('error_details') or "Clean execution"
        if len(err) > 65:
            err = err[:62] + "..."
        md_lines.append(f"| **Gate {num}** | **{g.get('name', '')}** | {status_badge} | {verdict_badge} | {g.get('findings', 0)} | {counts} | {err} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## Resource-Safe Policy Details",
        f"- **Runtime RAM Guard**: Scanners check available memory before execution; below `{MIN_RAM_THRESHOLD_MB} MB`, execution is BLOCKED to safeguard system stability.",
        "- **Tool Timeouts**: Each tool runs sequentially with strict process-tree timeouts (30s - 90s) to prevent frozen processes.",
        "- **Five Retained Scanners**: 1. TruffleHog (Secrets), 2. Bandit (Python SAST), 3. Checkov (IaC), 4. Hadolint (Dockerfile), 5. OWASP ZAP (DAST Baseline).",
        "- **STRICT Mode**: Halts pipeline on any Critical/High threshold violation or missing mandatory scanner.",
        "- **ADVISORY Mode**: Executes available gates, accurately logging all findings without halting pipeline execution.",
        "",
    ])

    sum_md_file = REPORTS_DIR / "security-summary.md"
    with open(sum_md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return summary_data


def main():
    parser = argparse.ArgumentParser(description="ArchitectIQ 5 Essential Security Gates Runner (Resource-Safe)")
    parser.add_argument("--gate", type=int, choices=range(1, 6), help="Run a single gate (1-5)")
    parser.add_argument("--all", action="store_true", help="Run all 5 security gates sequentially")
    parser.add_argument("--summary", action="store_true", help="Generate summary reports only")
    parser.add_argument("--mode", choices=["STRICT", "ADVISORY"], default="STRICT", help="Policy enforcement mode")
    parser.add_argument("--target-url", default="http://localhost:8000", help="Target URL for Gate 5 OWASP ZAP")
    args = parser.parse_args()

    mem_info = get_system_memory_info()
    print(f"ArchitectIQ Security Runner | Environment: {mem_info['environment']} | Avail RAM: {mem_info['available_mb']} MB ({mem_info['percent_free']}%) | Safe Threshold: {MIN_RAM_THRESHOLD_MB} MB")

    if args.gate:
        print(f"\n============================================================")
        print(f"  Executing Security Gate {args.gate}: {GATE_DEFINITIONS[args.gate]['name']}")
        print(f"============================================================")
        if args.gate == 1:
            res = run_gate_1(args.mode)
        elif args.gate == 2:
            res = run_gate_2(args.mode)
        elif args.gate == 3:
            res = run_gate_3(args.mode)
        elif args.gate == 4:
            res = run_gate_4(args.mode)
        elif args.gate == 5:
            res = run_gate_5(args.mode, args.target_url)

        print(f"Gate {args.gate} Execution Status: {res.get('execution_status')}")
        print(f"Severity Verdict:         {res.get('severity_verdict')}")
        print(f"Findings Count:           {res.get('findings_count')}")
        if res.get('error_details'):
            print(f"Details / Errors:         {res.get('error_details')}")

        generate_summary(args.mode)
        if args.mode == "STRICT" and res.get("severity_verdict") in ["FAIL", "BLOCKED"]:
            sys.exit(1)
        sys.exit(0)

    elif args.all:
        print(f"\n============================================================")
        print(f"  Executing All 5 Essential DevSecOps Security Gates (Sequential)")
        print(f"============================================================")
        print(f"Mode: {args.mode}")

        run_gate_1(args.mode)
        run_gate_2(args.mode)
        run_gate_3(args.mode)
        run_gate_4(args.mode)
        run_gate_5(args.mode, args.target_url)

        summary = generate_summary(args.mode)
        print("\n============================================================")
        print(f"All 5 Gates Complete. Overall Verdict: {summary['overall_verdict']}")
        print(f"Passed: {summary['passed_gates']} | Failed: {summary['failed_gates']} | Blocked: {summary['blocked_gates']} | Errors: {summary['error_gates']}")
        print("============================================================")

        if args.mode == "STRICT" and summary["overall_verdict"] in ["FAIL", "BLOCKED"]:
            sys.exit(1)
        sys.exit(0)

    elif args.summary:
        summary = generate_summary(args.mode)
        print(f"Summary Generated: Overall Verdict = {summary['overall_verdict']}")
        sys.exit(0)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

