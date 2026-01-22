# Copyright (c) 2024 Andrii Shramko
# Contact: zmei116@gmail.com
# LinkedIn: https://www.linkedin.com/in/andrii-shramko/
# Tags: #ShramkoVR #ShramkoCamera #ShramkoSoft
# License: This code is free to use for non-commercial projects.
# For commercial use, please contact Andrii Shramko at the above email or LinkedIn.

import requests
import json
import time
import socket
from concurrent.futures import ThreadPoolExecutor

def send_stop_signal(target_ip="192.168.100.66", port=9998):
    """Send stop signal to specified IP and port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tc = time.strftime("%H:%M:%S", time.localtime())
    payload = f"STOP {tc} {time.time_ns()}".encode("utf-8")
    
    # Send 5 times with 10ms interval for reliability
    for i in range(5):
        sock.sendto(payload, (target_ip, port))
        time.sleep(0.01)
    
    print(f"Sent stop signal to {target_ip}:{port}: {payload.decode('utf-8')}")

def stop_recording(camera_ip):
    try:
        response = requests.get(f"http://{camera_ip}:8080/gopro/camera/shutter/stop")
        if response.status_code == 200:
            print(f"Recording stopped successfully on camera {camera_ip}.")
        else:
            print(f"Failed to stop recording on camera {camera_ip}. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"An error occurred while stopping recording on camera {camera_ip}: {e}")

if __name__ == "__main__":
    # Load devices from cache
    try:
        with open("camera_cache.json", "r") as cache_file:
            devices = json.load(cache_file)
        print("Loaded cached camera devices:")
        for device in devices:
            print(f"Name: {device['name']}, IP: {device['ip']}")
    except FileNotFoundError:
        print("Camera cache not found. Cannot stop recording.")
        exit()

    # Stop recording on all cameras and send stop signal
    print("Stopping recording on all cameras...")
    with ThreadPoolExecutor() as executor:
        # Stop recording on all cameras and send stop signal simultaneously
        stop_futures = [executor.submit(stop_recording, d["ip"]) for d in devices]
        stop_signal_future = executor.submit(send_stop_signal)
        # Wait for all tasks to complete
        for future in stop_futures:
            future.result()
        stop_signal_future.result()
