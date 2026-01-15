#!/usr/bin/env python3
"""
Sync N videos by embedded timecode, trim to common overlap, export per-camera clips
and a grid preview.

All input videos should be placed in a folder (for example: outputs/Take_XXXXXX/videos).

Usage:
    python gopro_sync.py /path/to/videos --num 4
"""

import argparse
import glob
import json
import os
import subprocess
from pathlib import Path


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def ffprobe_info(path):
    cmd = [
        'ffprobe', '-v', 'error', '-print_format', 'json',
        '-show_streams', '-show_format', path
    ]
    try:
        res = run_cmd(cmd)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"ffprobe failed for {path}: {e.stderr}")
        return None


def get_timecode_and_framerate(info):
    if not info or 'streams' not in info:
        return None, None
    timecode = None
    fps_str = None
    for s in info['streams']:
        if s.get('codec_type') == 'video':
            if 'tags' in s and s['tags']:
                timecode = s['tags'].get('timecode') or timecode
            fps_str = s.get('r_frame_rate') or fps_str
    return timecode, fps_str


def parse_framerate(r):
    if not r or r == '0/0':
        return 30.0
    try:
        n, d = r.split('/')
        n = float(n)
        d = float(d)
        return n / d if d != 0 else 30.0
    except Exception:
        return 30.0


def parse_timecode_to_seconds(tc, fps):
    if not tc:
        return 0.0
    t = tc.replace(';', ':')
    try:
        h, m, s, f = map(int, t.split(':'))
    except Exception:
        # Fallback if frames missing: HH:MM:SS
        parts = t.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            f = 0
        else:
            return 0.0
    return (h * 3600 + m * 60 + s) + (f / float(fps))


def get_video_duration_seconds(info):
    if not info or 'format' not in info:
        return 0.0
    try:
        return float(info['format'].get('duration', 0.0))
    except Exception:
        return 0.0


def discover_videos(directory, expected_count=None):
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    patterns = ['*.mp4', '*.MP4', '*.mov', '*.MOV', '*.mkv', '*.MKV', '*.avi', '*.AVI']
    files = []
    for pat in patterns:
        files.extend(glob.glob(str(p / pat)))
    files = sorted(files)
    # Deduplicate matches (Windows filesystems are case-insensitive and
    # the multiple glob patterns above can cause the same file to be added
    # more than once). Preserve order.
    seen = set()
    unique = []
    for f in files:
        key = os.path.normcase(os.path.abspath(f))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    files = unique
    if expected_count is not None:
        if len(files) < expected_count:
            raise ValueError(f"Found {len(files)} videos in {directory}, need at least {expected_count}")
        # return the first `expected_count` files
        return files[:expected_count]
    if not files:
        raise ValueError(f"No videos found in {directory}")
    return files


def compute_alignment(files):
    starts = {}
    durations = {}
    for f in files:
        info = ffprobe_info(f)
        if not info:
            raise RuntimeError(f"Could not read metadata for {f}")
        tc, r = get_timecode_and_framerate(info)
        fps = parse_framerate(r)
        start_sec = parse_timecode_to_seconds(tc, fps)
        dur_sec = get_video_duration_seconds(info)
        print(f"{os.path.basename(f)} -> timecode={tc} fps={fps:.3f} start={start_sec:.3f}s duration={dur_sec:.3f}s")
        starts[f] = start_sec
        durations[f] = dur_sec

    latest_start = max(starts.values())
    print(f"Latest start among videos: {latest_start:.3f}s")

    # Required front trim for each = latest_start - its_start (>=0)
    trims = {f: max(0.0, latest_start - starts[f]) for f in files}

    # Effective durations after front trim
    effective = {f: max(0.0, durations[f] - trims[f]) for f in files}
    common_duration = min(effective.values()) if effective else 0.0
    print(f"Common overlap (after front trim): {common_duration:.3f}s")

    return trims, common_duration


def export_synced_individuals(files, trims, duration, out_dir):
    print("\nExporting synced individual videos (with audio)...")
    os.makedirs(out_dir, exist_ok=True)
    outputs = []
    for f in files:
        base = os.path.basename(f)
        out = os.path.join(out_dir, f"sync_{base}")
        t = trims[f]
        filter_complex = (
            f"[0:v]trim=start={t}:duration={duration},setpts=PTS-STARTPTS,scale=1920:1080[v];"
            f"[0:a]atrim=start={t}:duration={duration},asetpts=PTS-STARTPTS[a]"
        )
        cmd = [
            'ffmpeg', '-y',
            '-i', f,
            '-filter_complex', filter_complex,
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k',
            out
        ]
        try:
            print(f"Creating {out} ...")
            run_cmd(cmd)
            outputs.append(out)
        except subprocess.CalledProcessError as e:
            print(f"Failed to create {out}: {e.stderr}")
            raise
    return outputs


def export_grid(pre_synced_files, out_path):
    n = len(pre_synced_files)
    print(f"\nExporting grid preview for {n} videos (video only)...")
    if n == 0:
        raise ValueError("No files provided for grid export")

    # Compute grid size: square-ish layout
    import math
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    # Compute per-tile size (use 1920 width for overall canvas)
    total_width = 1920
    tile_w = max(64, total_width // cols)
    tile_h = int(tile_w * 9 / 16)

    cmd = ['ffmpeg', '-y']
    for f in pre_synced_files:
        cmd += ['-i', f]

    # scale each input to tile_w x tile_h
    fc_parts = []
    for i in range(n):
        fc_parts.append(f"[{i}:v]scale={tile_w}:{tile_h}[v{i}]")

    # create hstack for each row
    row_labels = []
    for r in range(rows):
        start = r * cols
        end = min(start + cols, n)
        inputs = [f"[v{i}]" for i in range(start, end)]
        if len(inputs) == 1:
            row_label = f"row{r}"
            # single input, just rename
            fc_parts.append(f"{inputs[0]}[{row_label}]")
        else:
            row_label = f"row{r}"
            fc_parts.append(f"{''.join(inputs)}hstack=inputs={len(inputs)}[{row_label}]")
        row_labels.append(f"[{row_label}]")

    # if multiple rows, vstack them
    if len(row_labels) == 1:
        final_label = row_labels[0]
    else:
        # combine rows via vstack in groups if needed
        # ffmpeg vstack can take multiple inputs: vstack=inputs=R
        fc_parts.append(f"{''.join(row_labels)}vstack=inputs={len(row_labels)}[out]")
        final_label = '[out]'

    # For single-row case the existing row label will be used as the final map

    filter_complex = ';'.join(fc_parts)

    cmd += [
        '-filter_complex', filter_complex,
        '-map', final_label,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-pix_fmt', 'yuv420p',
        out_path
    ]

    try:
        run_cmd(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Failed to create grid preview: {e.stderr}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Sync N videos by timecode and export grid")
    parser.add_argument('video_directory', help='Directory containing videos (e.g. outputs/Take_XXXXXX/videos)')
    parser.add_argument('-n', '--num', type=int, default=None, help='Number of videos to sync (optional)')
    parser.add_argument('-o', '--out', default=None, help='Optional output directory for synced files')
    args = parser.parse_args()

    # Check tools
    try:
        run_cmd(['ffmpeg', '-version'])
        run_cmd(['ffprobe', '-version'])
    except subprocess.CalledProcessError:
        print('ffmpeg/ffprobe not found in PATH')
        return

    try:
        files = discover_videos(args.video_directory, expected_count=args.num)
        print(f"Found {len(files)} videos:")
        for i, f in enumerate(files, 1):
            print(f"  {i}. {os.path.basename(f)}")

        trims, common_duration = compute_alignment(files)
        if common_duration <= 0.0:
            print("No overlapping region across videos after alignment.")
            return

        base_dir = os.path.dirname(files[0])
        out_dir = args.out if args.out else os.path.join(base_dir, 'synced')
        synced_files = export_synced_individuals(files, trims, common_duration, out_dir)

        grid_out = os.path.join(out_dir, 'grid_preview.mp4')
        export_grid(synced_files, grid_out)

        print("\nDone.")
        print("Outputs:")
        for f in synced_files:
            print(f"  - {f}")
        print(f"  - {grid_out}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main()


