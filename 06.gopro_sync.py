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
    print(f"\nExporting 3x3 grid preview for {n} videos (video only)...")
    if n == 0:
        raise ValueError("No files provided for grid export")

    # Fixed 3x3 grid (9 positions)
    cols = 3
    rows = 3
    total_positions = 9

    # Compute per-tile size (use 1920 width for overall canvas)
    total_width = 1920
    tile_w = total_width // cols  # 640 pixels per tile
    tile_h = int(tile_w * 9 / 16)  # 16:9 aspect ratio, 360 pixels

    # Get duration of first video for black filler
    first_video_info = ffprobe_info(pre_synced_files[0])
    duration = get_video_duration_seconds(first_video_info)
    if duration <= 0:
        duration = 10.0  # fallback duration

    cmd = ['ffmpeg', '-y']
    # Add all video inputs
    for f in pre_synced_files:
        cmd += ['-i', f]
    
    # Add black video inputs for empty positions (need total_positions - n black videos)
    num_black_videos = total_positions - n
    if num_black_videos > 0:
        # Create black video using color filter
        for i in range(num_black_videos):
            # Use color source for black video
            cmd += ['-f', 'lavfi', '-i', f'color=c=black:s={tile_w}x{tile_h}:d={duration}']

    # Scale each input video to tile_w x tile_h
    fc_parts = []
    for i in range(n):
        fc_parts.append(f"[{i}:v]scale={tile_w}:{tile_h}[v{i}]")
    
    # Scale black videos (they start at index n)
    for i in range(num_black_videos):
        black_idx = n + i
        fc_parts.append(f"[{black_idx}:v]scale={tile_w}:{tile_h}[v{black_idx}]")

    # Create hstack for each row (3 videos per row)
    row_labels = []
    full_row_width = tile_w * cols
    for r in range(rows):
        row_videos = []
        for c in range(cols):
            pos = r * cols + c
            if pos < n:
                # Real video
                row_videos.append(f"[v{pos}]")
            else:
                # Black video (index starts from n)
                black_idx = n + (pos - n)
                row_videos.append(f"[v{black_idx}]")
        
        row_label = f"row{r}"
        # Always hstack 3 inputs
        fc_parts.append(f"{''.join(row_videos)}hstack=inputs=3[{row_label}]")
        row_labels.append(f"[{row_label}]")

    # vstack all 3 rows
    fc_parts.append(f"{''.join(row_labels)}vstack=inputs=3[out]")
    final_label = '[out]'

    filter_complex = ';'.join(fc_parts)

    cmd += [
        '-filter_complex', filter_complex,
        '-map', final_label,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-pix_fmt', 'yuv420p',
        '-t', str(duration),  # Set output duration
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


