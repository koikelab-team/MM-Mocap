# MM-Mocap — GoPro multi-camera capture utilities

This repository contains a set of small Python helper scripts and demos to discover, start/stop, copy, and synchronize multiple GoPro cameras for multi-camera motion capture workflows.

**Quick overview**
- **Purpose:** discover GoPros on the network, start/stop recording on all cameras, copy recordings to a PC, sort them into scenes, and synchronize/merge multi-camera footage.
- **Orchestrator:** [main.py](main.py) runs the numbered scripts in numeric order to perform a full capture session.

# Running seperately is recommanded.

Repository structure (root highlights):
- [00.goprolist_and_start_usb_sync_all_settings_date_time.py](00.goprolist_and_start_usb_sync_all_settings_date_time.py) — discovery and initial configuration helpers
- [01.goprolist_and_start_usb.py](01.goprolist_and_start_usb.py) — discover and prepare cameras
- [02.sync_and_record.py](02.sync_and_record.py) — start recording on all cameras (does not accept a duration)
- [03.stop_record.py](03.stop_record.py) — stop recording on all cameras
- [04.copy_to_pc_and_scene_sorting.py](04.copy_to_pc_and_scene_sorting.py) — copy media to a destination folder and sort into per-scene folders (usage: `python 04.copy_to_pc_and_scene_sorting.py <destination_root>`)
- [05.format_sd.py](05.format_sd.py) — format camera SD cards
- [06.gopro_sync.py](06.gopro_sync.py) — synchronize video files (merging/syncing tool)
- [99.Turn_Off_Cameras.py](99.Turn_Off_Cameras.py) — power off / shutdown cameras
- `OpenGoPro/` — upstream SDKs, demos, and protobufs used by several scripts

Requirements
- Python 3.10 (use the same interpreter that the scripts expect).
- `requests` library (used by the copy script). Install with:

```bash
pip install -r requirements.txt
# Or if no requirements file exists:
pip install requests
```

How to run a full capture session
1. Prepare a destination folder for copied files (e.g. `outputs/session1`).
2. Run the orchestrator with the desired recording duration (seconds) and output path:

```bash
python main.py --duration 60 --output outputs/
```

What `main.py` does
- Finds numbered scripts (files matching `NN.*.py`) and runs them in numeric order.
- Starts recording by running `02.sync_and_record.py` (note: `02` itself does not accept a duration).
- Sleeps for the `--duration` seconds you provided to `main.py` to allow cameras to record.
- Runs `03.stop_record.py` to stop recording after the wait.
- Calls `04.copy_to_pc_and_scene_sorting.py` with the destination path as a positional argument to copy and sort media into scene folders.
- Runs `06.gopro_sync.py` (if present) to synchronize/merge videos.
- Runs `99.Turn_Off_Cameras.py` at the end to power off cameras.

Important notes & tips
- `02.sync_and_record.py` does not support a `--duration` flag. `main.py` starts `02` then waits for the duration before invoking `03` to stop recordings.
- `04.copy_to_pc_and_scene_sorting.py` requires a positional `<destination_root>` argument; `main.py` passes the `--output` path as that positional parameter.
- Check the individual script top-of-file docstrings and `print` output for script-specific options and error messages.
- If you prefer to run steps manually, run scripts in this order: 01 → 02 → wait → 03 → 04 <destination> → 06 → 99.

Troubleshooting
- If cameras are not discovered, verify network connections and that camera Wi‑Fi is enabled.
- If a script exits with a non-zero code, inspect its console output; `main.py` prints warnings but does not currently abort on every non-zero exit.
- For large copies, ensure the destination drive has enough space and a stable network connection to cameras.

Want changes?
If you'd like `main.py` to be more conservative (dry-run mode, parallel execution, retries, or to abort on first error), tell me which behavior you want and I can update the orchestrator.

---
Generated README for MM-Mocap automation utilities.
# MM-Mocap
Multimodal-Mocap
