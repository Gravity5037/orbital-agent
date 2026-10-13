"""Install Orbital to start automatically, correctly.

Replaces setup_silent_autostart.py, which could not run at all: it built a
PowerShell script inside an unescaped f-string, so Python raised
    SyntaxError: f-string: expecting a valid expression after '{'
at line 33 and nothing was ever written.

This version:
  * uses a normal string with placeholders, not an f-string, so braces in
    PowerShell are literal
  * offers three mechanisms and tells you which one it used
  * is reversible with --uninstall

Usage (run from C:\\Orbital):
    python install_autostart.py                    # Startup folder shortcut
    python install_autostart.py --mode task        # Task Scheduler, at logon
    python install_autostart.py --mode registry    # HKCU\\...\\Run
    python install_autostart.py --uninstall
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("autostart")

SHORTCUT_NAME = "Orbital OS.lnk"
TASK_NAME = "OrbitalOS"
RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"


def _is_windows():
    return os.name == "nt"


def _target_argv():
    """What autostart should actually launch."""
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return exe, os.path.join(config.BASE_DIR, "start.py")


def _startup_dir():
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def install_startup_folder():
    exe, script = _target_argv()
    startup = _startup_dir()
    if not os.path.isdir(startup):
        return False, f"Startup folder not found: {startup}"

    link = os.path.join(startup, SHORTCUT_NAME)
    icon = os.path.join(config.BASE_DIR, "orbital_logo.ico")

    # Braces below are literal PowerShell, which is why this is not an f-string.
    ps = """
$WshShell = New-Object -ComObject WScript.Shell
$link = $WshShell.CreateShortcut(__LINK__)
$link.TargetPath = __EXE__
$link.Arguments = __ARGS__
$link.WorkingDirectory = __CWD__
if (Test-Path __ICON__) { $link.IconLocation = __ICON__ }
$link.Save()
Write-Output "created"
""".replace("__LINK__", _ps_quote(link)) \
   .replace("__EXE__", _ps_quote(exe)) \
   .replace("__ARGS__", _ps_quote(f'"{script}" --background')) \
   .replace("__CWD__", _ps_quote(config.BASE_DIR)) \
   .replace("__ICON__", _ps_quote(icon))

    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, timeout=60,
    )
    if "created" in (res.stdout or ""):
        return True, link
    return False, (res.stderr or res.stdout or "unknown error").strip()


def install_task():
    exe, script = _target_argv()
    cmd = f'"{exe}" "{script}" --background'
    res = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "ONLOGON",
         "/TR", cmd, "/F"],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode == 0:
        return True, f"scheduled task '{TASK_NAME}' (at logon)"
    return False, (res.stderr or res.stdout or "unknown error").strip()


def install_registry():
    exe, script = _target_argv()
    value = f'"{exe}" "{script}" --background'
    res = subprocess.run(
        ["reg", "add", RUN_KEY, "/v", "OrbitalOS", "/t", "REG_SZ",
         "/d", value, "/f"],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode == 0:
        return True, f"{RUN_KEY}\\OrbitalOS"
    return False, (res.stderr or res.stdout or "unknown error").strip()


def uninstall():
    removed = []

    link = os.path.join(_startup_dir(), SHORTCUT_NAME)
    if os.path.exists(link):
        try:
            os.remove(link)
            removed.append(link)
        except OSError as exc:
            log.warn(f"could not remove {link}: {exc}")

    res = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        removed.append(f"task {TASK_NAME}")

    res = subprocess.run(
        ["reg", "delete", RUN_KEY, "/v", "OrbitalOS", "/f"],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        removed.append(f"registry {RUN_KEY}\\OrbitalOS")

    return removed


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser(description="Install or remove Orbital autostart.")
    ap.add_argument("--mode", choices=["startup", "task", "registry"],
                    default="startup")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log.info(f"Base directory: {config.BASE_DIR}")

    if not _is_windows():
        log.warn("Not running on Windows — nothing to install.")
        log.info("On Linux, add a systemd unit or a desktop autostart entry.")
        return 1

    exe, script = _target_argv()
    log.info(f"Would launch: {exe} {script} --background")

    if args.dry_run:
        log.info("Dry run only; no changes made.")
        return 0

    if args.uninstall:
        removed = uninstall()
        if removed:
            for item in removed:
                log.info(f"removed: {item}")
        else:
            log.info("nothing to remove")
        return 0

    installers = {
        "startup": install_startup_folder,
        "task": install_task,
        "registry": install_registry,
    }
    ok, detail = installers[args.mode]()
    if ok:
        log.info(f"Autostart installed via {args.mode}: {detail}")
        log.info("Remove it later with:  python install_autostart.py --uninstall")
        return 0
    log.error(f"Failed to install via {args.mode}: {detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
