# Copyright (c) 2024 Andrii Shramko
# Contact: zmei116@gmail.com
# LinkedIn: https://www.linkedin.com/in/andrii-shramko/
# Tags: #ShramkoVR #ShramkoCamera #ShramkoSoft
# License: This code is free to use for non-commercial projects.
# For commercial use, please contact Andrii Shramko at the above email or LinkedIn.

import time
import socket
from date_time_sync import sync_time_on_cameras
from recording import discover_gopro_devices, set_video_mode, start_recording
from concurrent.futures import ThreadPoolExecutor

def send_timecode(target_ip="192.168.100.66", port=9998):
    """Send timecode to specified IP and port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tc = time.strftime("%H:%M:%S", time.localtime())
    payload = f"TC {tc} {time.time_ns()}".encode("utf-8")
    
    # Send 5 times with 10ms interval for reliability
    for i in range(5):
        sock.sendto(payload, (target_ip, port))
        time.sleep(0.01)
    
    print(f"Sent timecode to {target_ip}:{port}: {payload.decode('utf-8')}")

def sync_and_start_recording():
    # Step 1: Synchronize time on all cameras
    print("Starting time synchronization on all cameras...")
    sync_time_on_cameras()
    
    # Short pause after synchronization
    print("Waiting for 1 seconds before starting recording...")
    time.sleep(1)

    # Step 2: Discover cameras
    devices = discover_gopro_devices()
    if not devices:
        print("No GoPro devices found.")
        return

    print("Found the following GoPro devices:")
    for device in devices:
        print(f"Name: {device['name']}, IP: {device['ip']}")

    # Step 3: Set video mode
   # print("Setting video mode on all cameras...")
   # for device in devices:
   #     set_video_mode(device["ip"])

    # Step 4: Start recording and send timecode
    print("Starting recording on all cameras...")
    with ThreadPoolExecutor() as executor:
        # Start recording on all cameras and send timecode simultaneously
        recording_futures = [executor.submit(start_recording, d["ip"]) for d in devices]
        timecode_future = executor.submit(send_timecode)
        # Wait for all tasks to complete
        for future in recording_futures:
            future.result()
        timecode_future.result()

if __name__ == "__main__":
    sync_and_start_recording()
