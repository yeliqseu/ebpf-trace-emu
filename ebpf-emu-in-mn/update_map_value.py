'''
bpf map update script
Created on Mon Sep 30 2024
author: yeli , Weibiao Tian
'''
import struct
import subprocess
import argparse

def int_to_little_endian_bytes(value, byte_length=4):
    # 使用 struct.pack 将整数转换为小端序字节
    return struct.pack('<I', value)

def generate_bpftool_update_command(map_id, key, value):
    # 将 key 和 value 转换为小端序字节表示
    key_bytes = int_to_little_endian_bytes(key)
    value_bytes = int_to_little_endian_bytes(value)
    
    # 将字节转换为十进制表示，适用于 bpftool 命令行格式
    key_list = ' '.join([str(b) for b in key_bytes])
    value_list = ' '.join([str(b) for b in value_bytes])
    
    # 生成 bpftool update 命令
    command = f"sudo bpftool map update id {map_id} key {key_list} value {value_list}"
    return command

def get_map_id(keyword):
    try:
        # 获取bpftool map show的输出
        result = subprocess.run(['bpftool', 'map', 'show'], capture_output=True, text=True, check=True)
        
        # 在输出中查找包含关键字的行，并提取ID
        for line in result.stdout.splitlines():
            if keyword in line:
                # 行格式: "<id>: <type>  name <name>  flags <flags>"
                # 提取行的第一个字段
                parts = line.split()
                map_id = parts[0][:-1]  # 移除冒号
                return int(map_id)
                
    except subprocess.CalledProcessError as e:
        print(f"Error in running bpftool: {e}")
    return None

def update_bpf_map_from_file(map_id, file_path):
    try:
        with open(file_path, 'r') as file:
            for key, line in enumerate(file):
                value = int(line.strip())
                command = generate_bpftool_update_command(map_id, key, value)
                subprocess.run(command, shell=True, check=True)
                
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    # 创建解析器
    parser = argparse.ArgumentParser(description='Update BPF map with values from a given file.')
    
    # 添加参数
    parser.add_argument('--keyword', required=True, help='The keyword to identify the BPF map.')
    parser.add_argument('--file_path', required=True, help='The file path from which to read values.')

    # 解析参数
    args = parser.parse_args()

    keyword = args.keyword
    file_path = args.file_path
    
    map_id = get_map_id(keyword)
    if map_id is not None:
        update_bpf_map_from_file(map_id, file_path)
    else:
        print(f"Map with keyword '{keyword}' not found.")