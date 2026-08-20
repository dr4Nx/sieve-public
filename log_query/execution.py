"""Command execution helpers."""

import subprocess
import sys

from .logging_utils import Logger


def run_command(cmd: str, log: Logger) -> int:
    log.info("Executing generated command...")
    log.debug(f"Full command string: {cmd}")
    proc = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
    if proc.returncode == 0:
        if proc.stdout:
            print(proc.stdout, end="")
        if not proc.stdout:
            log.info("Command ran successfully but produced no output.")
    else:
        log.error(f"Command failed with exit code {proc.returncode}")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
    return proc.returncode
