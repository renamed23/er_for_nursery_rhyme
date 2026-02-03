#!/usr/bin/env python3

import os
import json
from typing import Dict, List, Tuple
from utils_tools.libs.ops_lib import EndParsing, Handler, assemble_one_op, fix_offset,  flat, h, parse_data, string, u32, u16, i32
from utils_tools.libs.translate_lib import collect_files, de, se


def end_handler(data: bytes, offset: int, ctx: Dict) -> Tuple[None, int]:
    if offset >= len(data):
        raise EndParsing()

    if data[offset] in (0xC2, 0x00, 0x81):
        raise EndParsing()

    return (None, offset)


end = Handler(end_handler)


def get_a9_indices(op: Dict) -> List[int]:
    count, _ = de(op['value'][0])
    return list(range(1, 1 + count))


FIX_OPS_MAP = {
    "10 00 00 00 00 00": [1],
    "A0 00": [0],
    "A1 00": [1],
    "A2 00": [1],
    "A4 00": [2],
    "A5 00": [3],
    "A7 00": [3],
    "A8 00": [3],
    "A9 00": get_a9_indices,
    "AE 00": [0],
}


OPCODES_MAP = flat({
    # [偏移] 对话，第二个u32是指向文本区的偏移
    h("10 00 00 00 00 00"): [u32.repeat(2)],
    h("11 00"): [],
    # [文本] 注音OP，作用于下一个`10 00 00 00 00 00`，第一个字符串是需要注音的原文，第二个字符串是注音
    h("12 00"): [string.repeat(2)],
    # [文本] 应该是和`12 00`一起使用，作用于上一个`10 00 00 00 00 00`(大概)
    h("13 00"): [string],
    # [文本] 名字OP，作用于下一个`10 00 00 00 00 00`
    h("14 00"): [string],
    h("18 00"): [u32.repeat(5)],  # 非偏移
    h("1A 00"): [u32.repeat(3)],  # 非偏移
    # [文本] 角色文本颜色定义，第一个是角色名，后面的u32代表颜色
    h("1B 00"): [string, u32.repeat(7)],
    h("1C 00"): [u32.repeat(5)],  # 非偏移
    h("1E 00"): [u32.repeat(3)],  # 非偏移
    h("1D 00"): [],
    h("20 00"): [],
    h("21 00"): [],
    h("28 00"): [string, u32],  # 非偏移
    h("29 00"): [string.repeat(2), u32],  # 非偏移
    h("2A 00"): [u32],  # 非偏移
    h("2B 00"): [string, u32],  # 非偏移
    h("2C 00"): [string, u32.repeat(8)],  # 非偏移
    h("2D 00"): [u32.repeat(5)],  # 非偏移
    h("34 00"): [u32, string, i32.repeat(5)],  # 非偏移
    h("35 00"): [u32.repeat(2)],  # 非偏移
    h("36 00"): [u32.repeat(6)],  # 非偏移
    h("3D 00"): [u32.repeat(2)],  # 非偏移
    h("40 00"): [u32.repeat(2), string, u32.repeat(2)],  # 非偏移
    h("41 00"): [u32.repeat(2), string, u32.repeat(2)],  # 非偏移
    h("42 00"): [u32.repeat(2), string, u32],  # 非偏移
    h("43 00"): [u32.repeat(2), string, u32],  # 非偏移
    h("44 00"): [u32.repeat(2), string, u32],  # 非偏移
    h("45 00"): [u32.repeat(2), string, u32],  # 非偏移
    h("46 00"): [u32, string, u32],  # 非偏移
    h("47 00"): [u32, string, u32],  # 非偏移
    h("48 00"): [u32.repeat(2)],  # 非偏移
    h("49 00"): [u32.repeat(2)],  # 非偏移
    h("50 00"): [string, u32],  # 非偏移
    h("51 00"): [string.repeat(2), u32],  # 非偏移
    h("52 00"): [u32],  # 非偏移
    h("53 00"): [string, u32],  # 非偏移
    h("66 00"): [u32.repeat(2)],  # 非偏移
    h("67 00"): [u32],  # 非偏移
    h("68 00"): [u32],  # 非偏移
    h("69 00"): [u32],  # 非偏移
    h("6A 00"): [u32],  # 非偏移
    h("6C 00"): [u32],  # 非偏移
    h("6D 00"): [u32.repeat(3)],  # 非偏移
    h("6F 00"): [u32],  # 非偏移
    h("70 00"): [u32, string, u32],  # 非偏移
    h("71 00"): [u32],  # 非偏移
    h("72 00 03 00 00 00"): [u32.repeat(2)],  # 非偏移
    h("74 00"): [u32, string, u32],  # 非偏移
    h("75 00"): [u32],  # 非偏移
    h("76 00"): [u32.repeat(3)],  # 非偏移
    h("80 00"): [string, u32],  # 非偏移
    h("82 00"): [],
    h("83 00"): [],
    h("85 00"): [string],
    h("88 00"): [string],
    h("8C 00"): [u32],  # 非偏移
    h("90 00"): [u32],  # 非偏移
    h("92 00"): [u32],  # 非偏移
    h("98 00"): [u16.repeat(2), u32],  # 非偏移
    h("99 00"): [u16.repeat(2), u32],  # 非偏移
    # [偏移] 指向OP区的偏移
    h("A0 00"): [u32],
    # [偏移] 第二个u32是指向OP区的偏移
    h("A1 00"): [u32.repeat(2)],
    # [偏移] 第二个u32是指向OP区的偏移
    h("A2 00"): [u32.repeat(2)],
    # [偏移] 第三个u32是指向OP区的偏移
    h("A4 00"): [u32.repeat(3)],
    # [偏移] 第四个u32是指向OP区的偏移
    h("A5 00"): [u16.repeat(2), u32.repeat(2)],
    # [偏移] 第四个u32是指向OP区的偏移
    h("A7 00"): [u16.repeat(2), u32.repeat(2)],
    # [偏移] 第四个u32是指向OP区的偏移
    h("A8 00"): [u16.repeat(2), u32.repeat(2)],
    # [偏移] 除了第一个u32，其他全是指向OP区的偏移
    h("A9 00"): [u32, u32.repeat_var()],
    # [偏移] 指向OP区的偏移
    h("AE 00"): [u32],
    # [文本] 第一个u32是选项数量，之后的字符串为选项
    h("B0 00"): [u32, string.repeat_var()],
    h("B8 00"): [],
    h("B9 00"): [u16, u16],
    h("BA 00"): [u32],  # 非偏移
    h("8D 00"): [u32],  # 非偏移
    h("8E 00"): [u32],  # 非偏移
    h("C0 00"): [string],
    h("C1 00"): [string],
    # OP结束标志
    h("C2 00 C2 00"): [end],
    h("C2 00"): [end],
    h("C4 00"): [u32],  # 非偏移
    # [文本] 场景的标题名
    h("C8 00"): [string],
    h("C9 00"): [],
    h("D4 00"): [u32],  # 非偏移
    h("D8 00"): [u32],  # 非偏移
    h("DA 00"): [u32],  # 非偏移
    h("DB 00"): [u32],  # 非偏移
    h("DC 00"): [u32],  # 非偏移

    h("37 01"): [u32, string, u32.repeat(3)],  # 非偏移
    h("38 01"): [u32.repeat(2)],  # 非偏移
    h("39 01"): [u32],  # 非偏移
    h("3A 01"): [u32],  # 非偏移
    h("6E 01"): [u32.repeat(6)],  # 非偏移
})


def disasm_mode(input_path: str, output_path: str):
    """反汇编模式：将二进制文件转换为JSON"""
    files = collect_files(input_path)

    for file in files:
        with open(file, "rb") as f:
            data = f.read()

        json_file = {}

        # parse_data 返回 opcodes 列表和 text_offset（文本区开始偏移）
        opcodes, text_offset = parse_data({
            "file_name": file,
            "offset": 0,
        }, data, OPCODES_MAP)
        text_data = data[text_offset:]

        # 确保正确解析了真正的终止OP
        assert text_data.find(b"\xC2\x00") == -1

        json_file["opcodes"] = opcodes
        json_file["text"] = []

        # 把文本区切分为以 0 结尾的字符串，记录每段文本的原始 offset
        for seg in text_data.split(b'\x00')[:-1]:
            json_file["text"].append(
                {"value": seg.decode("cp932"), "offset": text_offset})
            text_offset += len(seg) + 1

        # 为指向文本的 OP 添加 target_idx 字段（以方便后续 asm）
        for op in json_file["opcodes"]:
            if op["op"] == "10 00 00 00 00 00":
                old_offset, _type = de(op['value'][1])
                idx = next((i for i, t in enumerate(
                    json_file["text"]) if t["offset"] == old_offset), None)
                assert idx != None
                op['target_idx'] = idx

        # 保存为JSON
        rel_path = os.path.relpath(file, start=input_path)
        out_file = os.path.join(output_path, rel_path + ".json")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(json_file, f, ensure_ascii=False, indent=2)


def asm_mode(input_path: str, output_path: str):
    """汇编模式：将JSON转换回二进制文件"""
    files = collect_files(input_path, "json")

    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # ========= 第一步：assemble opcode，计算新 offset =========
        old2new = {}          # old_offset -> new_offset
        cursor = 0
        opcodes = json_data['opcodes']

        for op in opcodes:
            old_offset = op["offset"]
            b = assemble_one_op(op)
            old2new[old_offset] = cursor
            cursor += len(b)

        # ========= 第二步：处理文本区，建立文本偏移映射并构造 text_blob =========
        text_blob_parts: List[bytes] = []

        for text in json_data['text']:
            old_text_offset = text['offset']
            old2new[old_text_offset] = cursor
            seg = text['value'].encode('cp932') + b'\x00'
            text_blob_parts.append(seg)
            cursor += len(seg)

        text_blob = b"".join(text_blob_parts)

        # ========= 第三步：修复 opcodes 中偏移（包括指向 opcode 区和文本区的偏移） =========
        opcodes = fix_offset(file, opcodes, old2new, FIX_OPS_MAP)

        # ========= 第四步：assemble 修复过跳转的 opcodes 并拼接文本区生成最终二进制 =========
        new_blob = b"".join([assemble_one_op(op) for op in opcodes])
        new_blob += text_blob

        # 保存二进制文件
        rel_path = os.path.relpath(file, start=input_path)
        rel_path = rel_path[:-5]  # 移除.json扩展名
        out_file = os.path.join(output_path, rel_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        with open(out_file, 'wb') as f:
            f.write(new_blob)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='游戏脚本反汇编/汇编工具')
    parser.add_argument(
        'mode', choices=['disasm', 'asm'], help='模式: disasm(反汇编) 或 asm(汇编)')
    parser.add_argument('input', help='输入文件夹路径')
    parser.add_argument('output', help='输出文件夹路径')

    args = parser.parse_args()

    if args.mode == 'disasm':
        disasm_mode(args.input, args.output)
        print(f"反汇编完成: {args.input} -> {args.output}")
    elif args.mode == 'asm':
        asm_mode(args.input, args.output)
        print(f"汇编完成: {args.input} -> {args.output}")


if __name__ == "__main__":
    main()
