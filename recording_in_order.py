# Copyright (c) 2024 Andrii Shramko
# Contact: zmei116@gmail.com
# LinkedIn: https://www.linkedin.com/in/andrii-shramko/
# Tags: #ShramkoVR #ShramkoCamera #ShramkoSoft
# License: This code is free to use for non-commercial projects.
# For commercial use, please contact Andrii Shramko at the above email or LinkedIn.

import time
import requests
from recording import discover_gopro_devices, start_recording

# Camera order list: last 4 digits of serial numbers in desired recording order
CAMERA_ORDER = ["2994", "7139", "4818", "4345", "6448", "3552", "9497", "0066", "9752"]

def set_external_control(camera_ip):
    """Set camera to external control mode."""
    try:
        response = requests.get(f"http://{camera_ip}:8080/gopro/camera/control/set_ui_controller?p=2", timeout=10)
        if response.status_code == 200:
            print(f"External control set on camera {camera_ip}.")
        else:
            print(f"Failed to set external control on camera {camera_ip}. Status Code: {response.status_code}")
    except requests.Timeout:
        print(f"Timeout while setting external control on camera {camera_ip}")
    except requests.RequestException as e:
        print(f"Error setting external control on camera {camera_ip}: {e}")
    except Exception as e:
        print(f"An error occurred while setting external control on camera {camera_ip}: {e}")

def get_camera_state(camera_ip):
    """Get camera state to check current status."""
    try:
        response = requests.get(f"http://{camera_ip}:8080/gopro/camera/state", timeout=10)
        if response.status_code == 200:
            state = response.json()
            recording = state.get("status", {}).get("1", 0)  # Status 1 is recording status
            return recording
        else:
            print(f"Failed to get camera state. Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error getting camera state: {e}")
        return None

def stop_recording(camera_ip):
    """Stop recording on a specific camera."""
    try:
        response = requests.get(f"http://{camera_ip}:8080/gopro/camera/shutter/stop", timeout=10)
        if response.status_code == 200:
            print(f"Recording stopped successfully on camera {camera_ip}.")
        else:
            print(f"Failed to stop recording on camera {camera_ip}. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except requests.Timeout:
        print(f"Timeout while stopping recording on camera {camera_ip}")
    except requests.RequestException as e:
        print(f"Error stopping recording on camera {camera_ip}: {e}")
    except Exception as e:
        print(f"An error occurred while stopping recording on camera {camera_ip}: {e}")

def extract_serial_last4(device_name):
    """Extract last 4 digits of serial number from device name."""
    # Device name format: C3531325189752._gopro-web._tcp.local.
    # Extract the serial number part (before the first dot)
    serial_part = device_name.split('.')[0]
    # Remove 'C' prefix if present
    if serial_part.startswith('C'):
        serial_part = serial_part[1:]
    # Get last 4 digits
    if len(serial_part) >= 4:
        return serial_part[-4:]
    return None

def sort_devices_by_order(devices, order_list):
    """Sort devices according to the order list based on last 4 digits of serial number."""
    sorted_devices = []
    device_dict = {}
    
    # Create a dictionary mapping last 4 digits to devices
    for device in devices:
        last4 = extract_serial_last4(device["name"])
        if last4:
            device_dict[last4] = device
    
    # Sort devices according to order list
    for order_item in order_list:
        if order_item in device_dict:
            sorted_devices.append(device_dict[order_item])
        else:
            print(f"Warning: Camera with last 4 digits '{order_item}' not found in discovered devices.")
    
    # Add any remaining devices not in the order list
    for device in devices:
        last4 = extract_serial_last4(device["name"])
        if last4 and last4 not in order_list:
            sorted_devices.append(device)
            print(f"Note: Camera with last 4 digits '{last4}' not in order list, added at the end.")
    
    return sorted_devices

def sequential_record_test():
    """Discover all cameras and record 5 seconds on each camera sequentially."""
    # Step 1: Discover cameras
    print("Discovering GoPro devices...")
    devices = discover_gopro_devices()
    
    if not devices:
        print("No GoPro devices found.")
        return
    
    print(f"Found {len(devices)} GoPro device(s):")
    for i, device in enumerate(devices, 1):
        last4 = extract_serial_last4(device["name"])
        print(f"  {i}. Name: {device['name']}, IP: {device['ip']}, Last4: {last4}")
    
    # Step 2: Sort devices according to order list
    print(f"\nSorting cameras according to order list: {CAMERA_ORDER}")
    sorted_devices = sort_devices_by_order(devices, CAMERA_ORDER)
    
    if not sorted_devices:
        print("No cameras matched the order list.")
        return
    
    print(f"\nRecording order:")
    for i, device in enumerate(sorted_devices, 1):
        last4 = extract_serial_last4(device["name"])
        print(f"  {i}. Camera with last 4 digits: {last4} ({device['ip']})")
    
    # Step 3: Record sequentially on each camera
    print("\nStarting sequential recording test (5 seconds per camera)...")
    for i, device in enumerate(sorted_devices, 1):
        camera_ip = device["ip"]
        camera_name = device["name"]
        
        last4 = extract_serial_last4(camera_name)
        print(f"\n[{i}/{len(sorted_devices)}] Processing camera: {camera_name} ({camera_ip}) [Last4: {last4}]")
        
        # Set external control mode
        print(f"  Setting external control mode...")
        set_external_control(camera_ip)
        time.sleep(0.5)  # Short pause after setting control
        
        # Ensure camera is not recording before starting
        print(f"  Ensuring camera is stopped...")
        stop_recording(camera_ip)
        time.sleep(0.5)  # Short pause after stopping
        
        # Start recording
        print(f"  Starting recording...")
        start_recording(camera_ip)
        
        # Wait 5 seconds
        print(f"  Recording for 5 seconds...")
        time.sleep(3)
        
        # Stop recording
        print(f"  Stopping recording...")
        stop_recording(camera_ip)
        
        print(f"  Camera {camera_name} test completed.")
    
    print("\nSequential recording test completed for all cameras.")

if __name__ == "__main__":
    sequential_record_test()

