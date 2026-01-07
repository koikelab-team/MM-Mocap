import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from open_gopro import WiredGoPro
from open_gopro import constants, proto


def gopro(id):
    gopro_instance = WiredGoPro(id)
    return gopro_instance

async def setup_camera(gopro_id: str):
    """Setup a single camera: open it and load video preset"""
    gopro_instance = WiredGoPro(gopro_id)
    await gopro_instance.open()
    print(f"Camera {gopro_instance._serial} is connected via USB, opened, and ready!")
    
    # Load video preset group
    assert (await gopro_instance.http_command.load_preset_group(group=proto.EnumPresetGroup.PRESET_GROUP_ID_VIDEO)).ok
    
    return gopro_instance

async def download_latest_video(gopro_instance, gopro_id: str, media_set_before: set, output_dir: Path):
    """Download the latest video captured by a camera"""
    # Get the media set after recording
    media_set_after = set((await gopro_instance.http_command.get_media_list()).data.files)
    
    # Find the new video (difference between before and after)
    new_videos = media_set_after.difference(media_set_before)
    
    if not new_videos:
        print(f"Warning: No new video found for camera {gopro_id}")
        return None
    
    # Get the latest video (assuming it's the one we just recorded)
    video = new_videos.pop()
    
    # Create output file path: outputs/Take_YYYYMMDDHHMMSS/videos/cam_ID.mp4
    output_file = output_dir / "videos" / f"cam_{gopro_id}.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Download the video
    print(f"Downloading {video.filename} from camera {gopro_id} to {output_file}...")
    result = await gopro_instance.http_command.download_file(
        camera_file=video.filename,
        local_file=output_file
    )
    
    if result.ok:
        print(f"Successfully downloaded video from camera {gopro_id} to {output_file}")
        return output_file
    else:
        print(f"Failed to download video from camera {gopro_id}")
        return None

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Record video on multiple GoPro cameras simultaneously')
    parser.add_argument('--ids', nargs='+', required=True, help='GoPro camera IDs (e.g., 2028 2029 2030)')
    parser.add_argument('-t', '--time', type=float, default=3.0, help='Recording duration in seconds (default: 3.0)')
    
    args = parser.parse_args()
    
    gopro_ids = args.ids
    record_duration = args.time
    
    print(f"Opening {len(gopro_ids)} GoPro camera(s): {', '.join(gopro_ids)}")
    print(f"Recording duration: {record_duration} seconds")
    
    # Setup all cameras in parallel (open and load presets)
    gopros = await asyncio.gather(*[setup_camera(gopro_id) for gopro_id in gopro_ids])
    
    print(f"\nAll {len(gopros)} cameras are ready!")
    
    # Get media list before recording for each camera
    print("\nGetting media list before recording...")
    media_sets_before = await asyncio.gather(*[gopro.http_command.get_media_list() for gopro in gopros])
    media_sets_before = [set(media_list.data.files) for media_list in media_sets_before]
    
    # Create output directory with timestamp: outputs/Take_YYYYMMDDHHMMSS/
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = Path("outputs") / f"Take_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    try:
        # Start recording on all cameras simultaneously
        print("\nStarting recording on all cameras simultaneously...")
        await asyncio.gather(*[gopro.http_command.set_shutter(shutter=constants.Toggle.ENABLE) for gopro in gopros])
        print("All cameras are now recording!")
        
        # Wait for the specified duration
        print(f"Recording for {record_duration} seconds...")
        await asyncio.sleep(record_duration)
        
        # Stop recording on all cameras simultaneously
        print("Stopping recording on all cameras simultaneously...")
        await asyncio.gather(*[gopro.http_command.set_shutter(shutter=constants.Toggle.DISABLE) for gopro in gopros])
        print("All cameras have stopped recording!")
        
        # Download videos from all cameras in parallel
        print("\nDownloading videos from all cameras...")
        download_tasks = [
            download_latest_video(gopro, gopro_id, media_set_before, output_dir)
            for gopro, gopro_id, media_set_before in zip(gopros, gopro_ids, media_sets_before)
        ]
        downloaded_files = await asyncio.gather(*download_tasks)
        
        print(f"\nDownload complete! Files saved to {output_dir}")
        for gopro_id, file_path in zip(gopro_ids, downloaded_files):
            if file_path:
                print(f"  Camera {gopro_id}: {file_path}")
    finally:
        # Close all cameras
        await asyncio.gather(*[gopro.close() for gopro in gopros])
        print(f"\nAll {len(gopros)} GoPro camera(s) are closed!")
 
if __name__ == "__main__":
    asyncio.run(main())