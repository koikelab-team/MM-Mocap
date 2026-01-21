# Copyright (c) 2024 Andrii Shramko
# Contact: zmei116@gmail.com
# LinkedIn: https://www.linkedin.com/in/andrii-shramko/
# Tags: #ShramkoVR #ShramkoCamera #ShramkoSoft
# License: This code is free to use for non-commercial projects.
# For commercial use, please contact Andrii Shramko at the above email or LinkedIn.

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from goprolist_and_start_usb import discover_gopro_devices
from prime_camera_sn import serial_number as prime_camera_sn  # Импортируем серийный номер основной камеры
from concurrent.futures import ThreadPoolExecutor

def create_folder_structure_and_copy_files(destination_root):
    print("Starting discovery of connected cameras...")
    devices = discover_gopro_devices()
    if not devices:
        print("No GoPro devices found.")
        return
    print(f"Discovered devices: {devices}")

    destination_root = Path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    print(f"Destination root folder: {destination_root}")

    media_data = []

    def collect_media(camera):
        ip = camera["ip"]
        serial_number = camera["name"].split("._gopro-web._tcp.local.")[0]
        media_url = f"http://{ip}:8080/gopro/media/list"
        try:
            response = requests.get(media_url)
            if response.status_code == 200:
                media_list = response.json().get("media", [])
                for media in media_list:
                    for file in media.get("fs", []):
                        file_metadata = {
                            "serial_number": serial_number,
                            "ip": ip,
                            "folder": media.get("d"),
                            "name": file.get("n"),
                            "time": datetime.fromtimestamp(int(file.get("cre")))
                        }
                        media_data.append(file_metadata)
            else:
                print(f"Failed to get media list from camera {ip}: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error connecting to camera {ip}: {e}")

    with ThreadPoolExecutor() as executor:
        executor.map(collect_media, devices)

    if not media_data:
        print("No media found on any camera.")
        return

    # Group files by camera serial number
    files_by_camera = {}
    for file in media_data:
        serial = file["serial_number"]
        if serial not in files_by_camera:
            files_by_camera[serial] = []
        files_by_camera[serial].append(file)
    
    # Sort files by time for each camera (newest first)
    for serial in files_by_camera:
        files_by_camera[serial].sort(key=lambda x: x["time"], reverse=True)
    
    print(f"Found files from {len(files_by_camera)} cameras")
    
    # Find the latest recording time across all cameras
    latest_time = None
    for serial, files in files_by_camera.items():
        if files:
            camera_latest = files[0]["time"]
            if latest_time is None or camera_latest > latest_time:
                latest_time = camera_latest
    
    if latest_time is None:
        print("No media found to copy.")
        return
    
    print(f"Latest recording time: {latest_time}")
    
    # For each camera, find the file closest to the latest time (within 5 seconds)
    take_files = []
    for serial, files in files_by_camera.items():
        if files:
            # Find the file closest to latest_time (within 5 seconds tolerance)
            closest_file = None
            min_time_diff = float('inf')
            for file in files:
                time_diff = abs((file["time"] - latest_time).total_seconds())
                if time_diff <= 5 and time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_file = file
            
            # If no file within 5 seconds, use the latest file from this camera
            if closest_file is None:
                closest_file = files[0]
                print(f"Warning: Camera {serial} has no file within 5 seconds of latest time, using latest file")
            
            take_files.append(closest_file)
            print(f"Selected file from camera {serial}: {closest_file['name']} (time: {closest_file['time']})")
    
    if not take_files:
        print("No files found to copy.")
        return
    
    print(f"Creating Take with {len(take_files)} files from all cameras")

    # Определение времени съемки с основной (прайм) камеры
    prime_file = next((f for f in take_files if f["serial_number"] == prime_camera_sn), take_files[0])
    # Use timestamp format: Take_YYYYMMDDHHMMSS (no underscores)
    timestamp = prime_file["time"].strftime("%Y%m%d%H%M%S")
    
    # Create Take_XXXXXX/videos folder structure
    take_folder_name = f"Take_{timestamp}"
    take_folder = destination_root / take_folder_name
    videos_folder = take_folder / "videos"
    videos_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"Copying {len(take_files)} files to {take_folder_name}")
    
    for file in take_files:
        source_url = f"http://{file['ip']}:8080/videos/DCIM/{file['folder']}/{file['name']}"
        # Use last 4 digits of serial number for filename: cam_XXXX.mp4
        serial_suffix = file['serial_number'][-4:] if len(file['serial_number']) >= 4 else file['serial_number']
        file_extension = Path(file['name']).suffix
        destination_file = videos_folder / f"cam_{serial_suffix}{file_extension}"
        print(f"Copying file {file['name']} from {file['ip']} to {destination_file}")
        try:
            with requests.get(source_url, stream=True) as response:
                if response.status_code == 200:
                    with open(destination_file, "wb") as out_file:
                        for chunk in response.iter_content(chunk_size=8192):
                            out_file.write(chunk)
                    print(f"File {file['name']} successfully copied.")
                else:
                    print(f"Failed to download {file['name']} from {file['ip']}. Response code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error downloading {file['name']} from {file['ip']}: {e}")

    print(f"All files copied successfully: {len(take_files)} files from all cameras.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python copy_to_pc_and_scene_sorting.py <destination_root>")
        sys.exit(1)
    destination = sys.argv[1]
    create_folder_structure_and_copy_files(destination)
