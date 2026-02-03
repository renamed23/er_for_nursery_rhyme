#!/usr/bin/env python3

import os
import json
import argparse
import re
from typing import List, Dict, Optional, Tuple
from utils_tools.libs import translate_lib


names = dict()


def save_names() -> List[Dict]:
    results: List[Dict] = []
    for n in names.keys():
        results.append({"message": n, "is_name": True, "raw_name": n})
    return results


def load_names(text: List[Dict[str, str]],
               trans_index: int) -> int:
    global names
    while trans_index < len(text):
        item = text[trans_index]
        if "is_name" in item and item["is_name"]:
            names[item["raw_name"]] = item["message"]
            trans_index += 1
        else:
            break

    return trans_index


def extract_strings_from_file(file_path: str) -> List[Dict]:
    """
    扫描单文件，提取字符串。
    返回的 results: 每项至少包含 'message'；若该对话有角色名则包含 'name'。
    """
    results: List[Dict] = []
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    current_name = None

    for op in json_data["opcodes"]:
        if op["op"] in ("12 00", "13 00", "1B 00"):
            names[op["value"][0]] = ""

        if op["op"] == "14 00":
            assert current_name == None
            current_name = op["value"][0]
            names[current_name] = ""

        if op["op"] == "10 00 00 00 00 00":
            idx = op["target_idx"]
            item = {"message": json_data["text"][idx]["value"]}
            if item["message"].startswith("　"):
                item["need_whitespace"] = True
            if current_name:
                item["name"] = current_name
                current_name = None

            results.append(item)

        if op["op"] == "B0 00":
            for s in op["value"][1:]:
                results.append({"message": s, "is_select": True})

        if op["op"] == "C8 00":
            results.append({"message": op["value"][0], "is_title": True})

    return results


def extract_strings(path: str, output_file: str):
    files = translate_lib.collect_files(path)
    results = []
    for file in files:
        results.extend(extract_strings_from_file(file))

    final_result = save_names()
    final_result.extend(results)
    print(f"提取了 {len(final_result)} 项")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, indent=2, ensure_ascii=False)

# ========== 替换 ==========


def replace_in_file(
    file_path: str,
    text: List[Dict[str, str]],
    output_dir: str,
    trans_index: int,
    base_root: str
) -> int:
    """
    替换单文件中的字符串。返回更新后的 trans_index。
    text: 全局译文列表（每项至少有 'message'，可能还含 'name'）
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    new_opcodes = []

    for op in json_data["opcodes"]:
        if op["op"] in ("12 00", "13 00", "1B 00", "14 00"):
            op["value"][0] = names[op["value"][0]]

        if op["op"] == "10 00 00 00 00 00":
            trans_item = text[trans_index]
            trans_index += 1
            idx = op["target_idx"]
            json_data["text"][idx]["value"] = trans_item["message"]

        if op["op"] == "B0 00":
            new_value = [op["value"][0]]
            for _ in range(len(op["value"][1:])):
                trans_item = text[trans_index]
                trans_index += 1
                new_value.append(trans_item["message"])

            op["value"] = new_value

        if op["op"] == "C8 00":
            trans_item = text[trans_index]
            trans_index += 1
            op["value"][0] = trans_item["message"]

        new_opcodes.append(op)

    json_data["opcodes"] = new_opcodes

    # ---------- 保存 ----------
    rel = os.path.relpath(file_path, start=base_root)
    out_path = os.path.join(output_dir, rel)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return trans_index


def replace_strings(path: str, text_file: str, output_dir: str):
    with open(text_file, 'r', encoding='utf-8') as f:
        text = json.load(f)
    files = translate_lib.collect_files(path)
    trans_index = 0
    trans_index = load_names(text, trans_index)

    for file in files:
        trans_index = replace_in_file(
            file, text, output_dir, trans_index, base_root=path)
        print(f"已处理: {file}")
    if trans_index != len(text):
        print(f"错误: 有 {len(text)} 项译文，但只消耗了 {trans_index}。")
        exit(1)

# ---------------- main ----------------


def main():
    parser = argparse.ArgumentParser(description='文件提取和替换工具')
    subparsers = parser.add_subparsers(
        dest='command', help='功能选择', required=True)

    ep = subparsers.add_parser('extract', help='解包文件提取文本')
    ep.add_argument('--path', required=True, help='文件夹路径')
    ep.add_argument('--output', default='raw.json', help='输出JSON文件路径')

    rp = subparsers.add_parser('replace', help='替换解包文件中的文本')
    rp.add_argument('--path', required=True, help='文件夹路径')
    rp.add_argument('--text', default='translated.json', help='译文JSON文件路径')
    rp.add_argument('--output-dir', default='translated',
                    help='输出目录(默认: translated)')

    args = parser.parse_args()
    if args.command == 'extract':
        extract_strings(args.path, args.output)
        print(f"提取完成! 结果保存到 {args.output}")
    elif args.command == 'replace':
        replace_strings(args.path, args.text, args.output_dir)
        print(f"替换完成! 结果保存到 {args.output_dir} 目录")


if __name__ == '__main__':
    main()
