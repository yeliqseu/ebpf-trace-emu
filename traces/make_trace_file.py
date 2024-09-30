#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 30 2024
author: yeli , Weibiao Tian
"""

import json
import numpy as np
import os
import pandas as pd
import shutil
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置常量
DATE = "2024-09-10"
ABBR = DATE[2:4] + DATE[5:7] + DATE[8:10]
START = "000001"
CURRENT_DIR = os.getcwd()
JSON_FILENAME = os.path.join(CURRENT_DIR, f"{ABBR}-{START}-12h.json")
SAVEPATH = CURRENT_DIR
SAVEPATH_ALL = os.path.join(CURRENT_DIR, "Starlink_Data")
SEND_INTERVAL_NS = 10 * 1_000_000  # 发送间隔（纳秒）

def read_json_file(json_filename):
    '''读取JSON文件并返回数据'''
    try:
        with open(json_filename, "r") as f:
            data = json.loads(f.read())
        return data
    except Exception as e:
        logging.error(f"读取JSON文件时发生错误: {e}")
        raise

def process_data(data):
    """
    处理JSON数据，提取往返时间(RTT)、接收时间、发送时间和数据包丢失信息。
    
    参数:
    - data: 解析后的JSON数据

    return:
    - rtt: RTT时间列表（以秒为单位）。
    - receive: 接收时间列表（以秒为单位）。
    - send: 发送时间列表（以秒为单位）。
    - loss_down: 下行链路丢包列表（1表示丢包，否则为0）。
    - loss_up: 上行链路丢包列表（1表示丢包，否则为0）。
    - loss_round: 往返丢包列表（1表示丢包，否则为0）。
    """
    rtt, receive, send, loss_down, loss_up, loss_round = [], [], [], [], [], []
    
    for round in data["round_trips"]:
        if round["lost"] == "false":
            rtt.append(float(round["delay"]["rtt"]) / 1000000)
            receive.append(float(round["delay"]["receive"]) / 1000000)
            send.append(float(round["delay"]["send"]) / 1000000)
            loss_down.append(0)
            loss_up.append(0)
            loss_round.append(0)
        else:
            rtt.append(0)
            loss_round.append(1)
            if round["lost"] == "true_down":
                loss_down.append(1)
                loss_up.append(0)
                receive.append(0)
            if round["lost"] == "true_up":
                loss_up.append(1)
                loss_down.append(0)
                send.append(0)
    return rtt, receive, send, loss_down, loss_up, loss_round

def save_processed_data(savepath, date, start, receive, send, rtt, loss_down=None, loss_up=None, loss_round=None):
    '''将处理后的数据保存到指定目录'''
    try:
        os.makedirs(os.path.join(savepath, date), exist_ok=True)

        delay_filename_d = os.path.join(savepath, date, f'LEO_downlink_delay-{start}-12h.txt')
        delay_filename_u = os.path.join(savepath, date, f'LEO_uplink_delay-{start}-12h.txt')
        delay_filename_r = os.path.join(savepath, date, f'LEO_round_delay-{start}-12h.txt')

        np.savetxt(delay_filename_d, receive)
        np.savetxt(delay_filename_u, send)
        np.savetxt(delay_filename_r, rtt)

        if loss_down is not None and loss_up is not None and loss_round is not None:
            loss_filename_d = os.path.join(savepath, date, f'LEO_downlink_loss-{start}-12h.txt')
            loss_filename_u = os.path.join(savepath, date, f'LEO_uplink_loss-{start}-12h.txt')
            loss_filename_r = os.path.join(savepath, date, f'LEO_round_loss-{start}-12h.txt')

            np.savetxt(loss_filename_d, loss_down)
            np.savetxt(loss_filename_u, loss_up)
            np.savetxt(loss_filename_r, loss_round)
    except Exception as e:
        logging.error(f"保存处理数据时发生错误: {e}")
        raise

def read_data(input_file):
    '''从文本文件中读取数据并转换为浮点数列表'''

    try:
        with open(input_file, 'r') as file:
            data = file.readlines()
        data = [float(line.strip()) for line in data]
        return data
    except Exception as e:
        logging.error(f"读取数据文件时发生错误: {e}")
        raise


def convert_to_ns(data):
    '''将数据从毫秒转换为纳秒'''

    return [value * 1_000_000 for value in data]


def write_data(output_file, data):
    '''将数据写入文本文件，并附带packet_id和值'''

    try:
        with open(output_file, 'w') as file:
            for packet_id, value in enumerate(data):
                file.write(f"{packet_id},{value:.0f}\n")
    except Exception as e:
        logging.error(f"写入数据文件时发生错误: {e}")
        raise

def process_delay_trace(file_path):
    '''处理延迟跟踪文件，通过读取数据，转换为纳秒并写入处理结果'''
    input_file = file_path
    output_file = 'trace_temp.log'

    data = read_data(input_file)
    data_ns = convert_to_ns(data)
    write_data(output_file, data_ns)

    logging.info(f"数据成功从 {input_file} 读取并转换为 ns 写入到 {output_file}")

def process_loss_trace(delay_trace_name):
    '''处理延迟跟踪以计算到达时间和数据包丢失'''

    delay_trace = pd.read_csv('trace_temp.log', header=None, names=['packet_id', 'delay'])
    delay_trace['send_time'] = delay_trace['packet_id'] * SEND_INTERVAL_NS

    arrival_times, original_times = [], []

    for i, row in delay_trace.iterrows():
        if row['delay'] > 0:
            arrival_time = row['send_time'] + row['delay']
            original_times.append(row['delay'])
        else:
            previous_delay = arrival_times[-1] - delay_trace.loc[i-1, 'send_time'] if i > 0 else SEND_INTERVAL_NS
            arrival_time = row['send_time'] + previous_delay
            original_times.append(previous_delay)

        arrival_times.append(arrival_time)
    
    delay_trace['arrival_time'] = arrival_times
    delay_trace['original_time'] = original_times

    sorted_trace = delay_trace.sort_values(by='arrival_time')
    sorted_trace['lost'] = sorted_trace['delay'] == 0
    loss_trace = sorted_trace[['packet_id', 'lost']]
    loss_trace['lost'] = loss_trace['lost'].astype(int)  # 将True/False转换为1/0

    loss_trace.to_csv('loss_temp.log', index=False, header=True)
    sorted_trace[['original_time']].to_csv(delay_trace_name, index=False, header=False)

def transform_log(input_file, output_file):
    '''转换日志文件, 提取必要的信息并写入输出文件'''

    try:
        with open(input_file, 'r') as infile:
            lines = infile.readlines()

        with open(output_file, 'w') as outfile:
            skipped_first_lost = False
            for line in lines:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    if parts[1] == '1' and not skipped_first_lost:
                        skipped_first_lost = True
                        continue
                    outfile.write(parts[1] + '\n')
    except Exception as e:
        logging.error(f"转换日志文件时发生错误: {e}")

def main():
    '''主函数，执行从读取JSON文件、处理数据、保存处理文件到生成跟踪文件的整个过程'''
    try:
        data = read_json_file(JSON_FILENAME)
        rtt, receive, send, loss_down, loss_up, loss_round = process_data(data)
        
        # 保存原始数据文件
        save_processed_data(SAVEPATH_ALL, DATE, START, receive, send, rtt, loss_down, loss_up, loss_round)
        
        # 保存trace数据文件
        save_processed_data(SAVEPATH, DATE, START, receive, send, rtt)
        
        round_delay = 'LEO_round_delay-000001-12h.txt'
        round_loss = 'LEO_round_loss-000001-12h.txt'
        uplink_delay = 'LEO_uplink_delay-000001-12h.txt'
        downlink_delay = 'LEO_downlink_delay-000001-12h.txt'
        uplink_loss = 'LEO_uplink_loss-000001-12h.txt'
        downlink_loss = 'LEO_downlink_loss-000001-12h.txt'

        # 处理并转换日志
        process_delay_trace(os.path.join(CURRENT_DIR, DATE, round_delay))
        process_loss_trace(round_delay)
        transform_log('loss_temp.log', round_loss)

        process_delay_trace(os.path.join(CURRENT_DIR, DATE, downlink_delay))
        process_loss_trace(downlink_delay)
        transform_log('loss_temp.log', downlink_loss)

        process_delay_trace(os.path.join(CURRENT_DIR, DATE, uplink_delay))
        process_loss_trace(uplink_delay)
        transform_log('loss_temp.log', uplink_loss)

    finally:
        # 删除临时文件和目录
        if os.path.exists('loss_temp.log'):
            os.remove('loss_temp.log')
        if os.path.exists('trace_temp.log'):
            os.remove('trace_temp.log')
        if os.path.exists(DATE):
            shutil.rmtree(DATE)
        logging.info("数据处理完毕。")

if __name__ == "__main__":
    main()