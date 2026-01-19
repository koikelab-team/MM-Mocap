#!/usr/bin/env python3
"""
Orchestrator to run numbered scripts (00-99) in sequence:
- runs each numbered `*.py` in the workspace root sorted by prefix
- passes `--duration` to the recorder script when possible
- passes output path to the copy script when possible
- runs the gopro sync script (cameras remain on after recording)

Usage example:
  python main.py --duration 60 --output outputs/session1
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_PREFIX_RE = re.compile(r"^(\d{2})\..*\.py$")


def find_numbered_scripts(directory: Path) -> list[Path]:
    scripts = []
    for p in directory.iterdir():
        if p.is_file() and p.suffix == ".py":
            m = SCRIPT_PREFIX_RE.match(p.name)
            if m:
                scripts.append((int(m.group(1)), p))
    scripts.sort(key=lambda x: x[0])
    return [p for _, p in scripts]


def run_script(python_exe: str, script_path: Path, args: list[str] | None = None) -> int:
    args = args or []
    cmd = [python_exe, str(script_path)] + args
    print(f"-> Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(f"   WARNING: script {script_path.name} returned code {proc.returncode}")
    return proc.returncode


def try_with_variants(python_exe: str, script_path: Path, duration: int | None, output: str | None) -> None:
    name = script_path.name
    if name.startswith("04"):
        # This script expects a positional <destination_root>
        tried = []
        if output:
            tried.append([output])
        tried.append([])
        for args in tried:
            rc = run_script(python_exe, script_path, args)
            if rc == 0:
                return
        print(f"   WARNING: copy script {name} failed with common arg variants.")
        return



def main() -> int:
    parser = argparse.ArgumentParser(description="Run 00-99 GoPro orchestration scripts in sequence")
    parser.add_argument("--duration", "-t", type=int, required=True, help="Recording duration in seconds")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output path to copy recordings to")
    parser.add_argument("--python", type=str, default=sys.executable, help="Python executable to run scripts (default: this interpreter)")
    parser.add_argument("--dir", type=str, default=".", help="Directory containing the numbered scripts (default: repo root)")
    args = parser.parse_args()

    repo_dir = Path(args.dir).resolve()
    if not repo_dir.exists():
        print(f"Error: scripts directory does not exist: {repo_dir}")
        return 2

    out_path = Path(args.output)
    out_path.mkdir(parents=True, exist_ok=True)

    scripts = find_numbered_scripts(repo_dir)
    if not scripts:
        print("No numbered scripts found in directory.")
        return 3

    print(f"Found {len(scripts)} numbered scripts. Running in order...")

    # Track the Take_XXXXXX directory created during this run
    take_base_path: Path | None = None
    
    # Iterate and run with some targeted arg handling
    already_run: set[str] = set()
    for s in scripts:
        name = s.name
        # Skip this orchestrator if it matches the pattern
        if s.resolve() == Path(__file__).resolve():
            continue

        # If this is the recorder (02), start it, wait, then stop via 03
        if name.startswith("02"):
            run_script(args.python, s)
            print(f"Recording for {args.duration} seconds...")
            time.sleep(args.duration)
            # Find and run the stop script (03.*)

        # If this is the copy script (04), pass destination as positional arg
        # After running, find the newly created Take_XXXXXX directory
        if name.startswith("04"):
            # Record existing directories before running
            existing_dirs = {d.name for d in out_path.iterdir() if d.is_dir()} if out_path.exists() else set()
            try_with_variants(args.python, s, None, str(out_path))
            # Find newly created Take_XXXXXX directory (only check once, not iterate all)
            if out_path.exists():
                for d in out_path.iterdir():
                    if d.is_dir() and d.name.startswith("Take_") and d.name not in existing_dirs:
                        take_base_path = d
                        break
            continue

        # If this is the sync script (06), use the Take_XXXXXX/videos directory
        if name.startswith("06"):
            if take_base_path is None:
                # Fallback: try to find latest Take_ directory (only if not found after 04)
                if out_path.exists():
                    take_dirs = [d for d in out_path.iterdir() if d.is_dir() and d.name.startswith("Take_")]
                    if take_dirs:
                        take_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        take_base_path = take_dirs[0]
            
            if take_base_path:
                video_dir = take_base_path / "videos"
                if video_dir.exists() and video_dir.is_dir():
                    run_script(args.python, s, [str(video_dir)])
                else:
                    print(f"   WARNING: Videos directory not found: {video_dir}. Skipping {name}")
            else:
                print(f"   WARNING: No Take_XXXXXX directory found. Skipping {name}")
            continue

        # Skip turn off cameras script (99) - only stop recording, don't power off
        if name.startswith("99"):
            print(f"   Skipping {name} (cameras will remain on)")
            continue

        # Default: just run
        run_script(args.python, s)

    print("Orchestration complete. Recommended: inspect logs and outputs in the output folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
