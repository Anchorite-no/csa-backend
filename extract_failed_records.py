#!/usr/bin/env python3
"""
脚本：从CSV文件中提取失败的记录
根据终端输出中的失败记录，从原始CSV中提取对应的行
"""

import csv
from pathlib import Path

# 从终端输出中提取的失败记录UID列表
failed_uids = [
    '22403047',      # 于昊文
    '3250103153',    # 周奕辰
    '3250100643',    # 竺子豪
    '3240105435',    # 韩一凯
    '3240104676',    # 马玉玺
    '3250103878',    # 白延胜
    '3240102328',    # 宫妍玉
    '3240104126',    # 乐彦彤
    '12442024',      # 梅愉婷
    '3250104691',     # 高千里
]

def extract_failed_records(input_csv: str, output_csv: str, failed_uids: list):
    """
    从输入CSV中提取失败的记录到输出CSV
    
    Args:
        input_csv: 输入CSV文件路径
        output_csv: 输出CSV文件路径
        failed_uids: 失败的UID列表
    """
    if not Path(input_csv).exists():
        print(f"错误：输入文件 '{input_csv}' 不存在")
        return False
    
    failed_uids_set = set(failed_uids)
    extracted_rows = []
    
    # 读取原始CSV
    with open(input_csv, 'r', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        for row in reader:
            uid = row.get('uid', '').strip()
            if uid in failed_uids_set:
                extracted_rows.append(row)
                print(f"找到失败记录: {uid} ({row.get('name', '')})")
    
    # 写入输出CSV
    if extracted_rows:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(extracted_rows)
        
        print(f"\n成功提取 {len(extracted_rows)} 条失败记录到: {output_csv}")
        return True
    else:
        print("未找到任何失败记录")
        return False

if __name__ == '__main__':
    input_file = 'members_export_20260103_034252.csv'
    output_file = 'failed_records.csv'
    
    # 如果文件在项目根目录，调整路径
    if not Path(input_file).exists():
        input_file = f'../{input_file}'
    
    extract_failed_records(input_file, output_file, failed_uids)

