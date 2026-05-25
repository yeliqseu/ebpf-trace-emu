#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
bpf map config update script
Used to switch between Packet-Driven (0) and Time-Driven (1) modes.
'''
import argparse
import subprocess
import ctypes
import ctypes.util
import os
import sys

# === Libbpf Setup ===
libbpf_path = ctypes.util.find_library('bpf')
if not libbpf_path:
    possible_paths = [
        '/usr/lib/x86_64-linux-gnu/libbpf.so', 
        '/usr/lib64/libbpf.so', 
        '/usr/lib/libbpf.so'
    ]
    for p in possible_paths:
        if os.path.exists(p):
            libbpf_path = p
            break

if not libbpf_path:
    print("Error: libbpf.so not found. Please install libbpf-dev or ensure libbpf.so is in your library path.")
    sys.exit(1)

try:
    libbpf = ctypes.CDLL(libbpf_path)
    libbpf.bpf_map_get_fd_by_id.argtypes = [ctypes.c_uint32]
    libbpf.bpf_map_get_fd_by_id.restype = ctypes.c_int
    libbpf.bpf_map_update_elem.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
    libbpf.bpf_map_update_elem.restype = ctypes.c_int
except Exception as e:
    print(f"Error loading libbpf functions: {e}")
    sys.exit(1)

def get_map_ids(keyword):
    """Get all map IDs matching the keyword"""
    map_ids = []
    try:
        cmd = ['sudo', 'bpftool', 'map', 'show']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if keyword in line:
                parts = line.split()
                map_id = parts[0][:-1]
                map_ids.append(int(map_id))
    except Exception as e:
        print(f"Error finding map: {e}")
    return map_ids

def update_mode(map_id, mode):
    """Update config_map with the selected mode"""
    map_fd = libbpf.bpf_map_get_fd_by_id(map_id)
    if map_fd < 0:
        print(f"Failed to get FD for map ID {map_id}.")
        return False

    try:
        c_key = ctypes.c_uint32(0)
        c_value = ctypes.c_uint32(mode)
        
        ret = libbpf.bpf_map_update_elem(map_fd, ctypes.byref(c_key), ctypes.byref(c_value), 0)
        if ret != 0:
            err = ctypes.get_errno()
            print(f"Failed to update map {map_id}: errno {err}")
            return False
        return True
    finally:
        os.close(map_fd)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Error: This script must be run as root (sudo).")
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Set eBPF Emulation Mode.')
    parser.add_argument('--mode', type=int, choices=[0, 1], required=True, 
                        help='0 for Packet-Driven (irtt), 1 for Time-Driven (iperf3)')
    
    args = parser.parse_args()

    # Find all config_map instances (should be 4: delay/loss for B and C)
    map_ids = get_map_ids("config_map")
    
    if not map_ids:
        print("No config_map found. Are the eBPF programs loaded?")
        sys.exit(1)
        
    success_count = 0
    for mid in map_ids:
        if update_mode(mid, args.mode):
            success_count += 1
            
    mode_str = "Time-Driven" if args.mode == 1 else "Packet-Driven"
    print(f"Successfully updated {success_count}/{len(map_ids)} config_maps to {mode_str} Mode ({args.mode}).")
