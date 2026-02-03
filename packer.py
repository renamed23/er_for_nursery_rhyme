#!/usr/bin/env python3

import argparse
import struct
from pathlib import Path


# ----------------- Decoder -----------------

class MsbBitStream:
    def __init__(self, data: bytes, pos=0):
        self.data = data
        self.pos = pos
        self.bits = 0
        self.cached_bits = 0

    def get_bits(self, count):
        while self.cached_bits < count:
            if self.pos >= len(self.data):
                return -1
            b = self.data[self.pos]
            self.pos += 1
            self.bits = (self.bits << 8) | b
            self.cached_bits += 8
        self.cached_bits -= count
        mask = (1 << count) - 1
        return (self.bits >> self.cached_bits) & mask

    def get_next_bit(self):
        return self.get_bits(1)


class BgiKey:
    def __init__(self, key, magic):
        self.key = key & 0xFFFFFFFF
        self.magic = magic & 0xFFFFFFFF

    def update(self):
        v0 = 20021 * (self.key & 0xFFFF)
        v1 = self.magic | (self.key >> 16)
        v1 = v1 * 20021 + self.key * 346
        v1 = (v1 + (v0 >> 16)) & 0xFFFF
        self.key = ((v1 << 16) + (v0 & 0xFFFF) + 1) & 0xFFFFFFFF
        return v1 & 0xFF


class HuffmanNode:
    __slots__ = ("is_parent", "code", "left", "right")

    def __init__(self):
        self.is_parent = False
        self.code = 0
        self.left = 0
        self.right = 0


def build_huffman_tree(codes):
    nodes = [HuffmanNode() for _ in range(1023)]
    index = [[0]*512 for _ in range(2)]

    next_node = 1
    depth_nodes = 1
    depth = 0
    child = 0

    index[0][0] = 0
    n = 0

    while n < len(codes):
        cur = child
        child ^= 1

        existed = 0
        while n < len(codes) and codes[n][1] == depth:
            node = nodes[index[cur][existed]]
            node.is_parent = False
            node.code = codes[n][0]
            existed += 1
            n += 1

        to_create = depth_nodes - existed
        for i in range(to_create):
            node = nodes[index[cur][existed + i]]
            node.is_parent = True
            node.left = next_node
            index[child][i*2] = next_node
            next_node += 1
            node.right = next_node
            index[child][i*2+1] = next_node
            next_node += 1

        depth += 1
        depth_nodes = to_create * 2

    return nodes


def dsc_decompress(data: bytes) -> bytes:
    magic = struct.unpack_from("<H", data, 0)[0] << 16
    key = struct.unpack_from("<I", data, 0x10)[0]
    unpacked_size = struct.unpack_from("<I", data, 0x14)[0]
    dec_count = struct.unpack_from("<I", data, 0x18)[0]

    keygen = BgiKey(key, magic)

    # 读取 Huffman depth
    pos = 0x20
    codes = []
    for i in range(512):
        d = (data[pos] - keygen.update()) & 0xFF
        pos += 1
        if d:
            codes.append((i, d))

    codes.sort(key=lambda x: (x[1], x[0]))
    hnodes = build_huffman_tree(codes)

    bs = MsbBitStream(data, pos)
    out = bytearray(unpacked_size)
    dst = 0

    for _ in range(dec_count):
        node = 0
        while hnodes[node].is_parent:
            bit = bs.get_next_bit()
            if bit < 0:
                break
            node = hnodes[node].left if bit == 0 else hnodes[node].right

        code = hnodes[node].code
        if code >= 256:
            offset = bs.get_bits(12)
            count = (code & 0xFF) + 2
            offset += 2
            for i in range(count):
                out[dst+i] = out[dst - offset + i]
            dst += count
        else:
            out[dst] = code
            dst += 1

    return bytes(out)


# ----------------- Decoder -----------------


ARC_SIGNATURE = b"PackFile    "
INDEX_ENTRY_SIZE = 0x20


def read_u32(f):
    return struct.unpack("<I", f.read(4))[0]


def write_u32(f, v):
    f.write(struct.pack("<I", v))


def unpack(input_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("rb") as f:
        sig = f.read(12)

        if sig != ARC_SIGNATURE:
            raise ValueError("不是有效的 BGI ARC 文件")

        count = read_u32(f)

        index_offset = 0x10
        data_base = index_offset + count * INDEX_ENTRY_SIZE

        entries = []

        f.seek(index_offset)
        for _ in range(count):
            name = f.read(0x10).split(b"\x00", 1)[
                0].decode("ascii")
            offset = read_u32(f)
            size = read_u32(f)
            f.read(8)  # reserved

            entries.append((name, offset, size))

        for name, offset, size in entries:
            f.seek(data_base + offset)
            data = f.read(size)

            out_path = out_dir / name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(dsc_decompress(data))

            print(f"[+] {name} ({size} bytes)")


def pack(input_dir: Path, out_path: Path):
    files = sorted(p for p in input_dir.iterdir() if p.is_file())
    count = len(files)

    with out_path.open("wb") as f:
        # header
        f.write(ARC_SIGNATURE)
        write_u32(f, count)

        index_offset = 0x10
        data_base = index_offset + count * INDEX_ENTRY_SIZE

        # 先占位索引区
        f.seek(data_base)

        file_datas = []
        for p in files:
            data = p.read_bytes()
            file_datas.append((p.name, data))

        offsets = []
        cur_offset = 0
        for _, data in file_datas:
            offsets.append(cur_offset)
            cur_offset += len(data)

        # 写文件数据
        for _, data in file_datas:
            f.write(data)

        # 回写索引
        f.seek(index_offset)
        for (name, data), offset in zip(file_datas, offsets):
            name_bytes = name.encode("ascii")[:0x0F]
            name_bytes += b"\x00" * (0x10 - len(name_bytes))

            f.write(name_bytes)
            write_u32(f, offset)
            write_u32(f, len(data))
            f.write(b"\x00" * 8)

    print(f"[+] 打包完成: {out_path}")


def main():
    ap = argparse.ArgumentParser(description="BGI ARC 解包/打包工具")
    sub = ap.add_subparsers(dest='cmd', required=True)

    ap_unpack = sub.add_parser('unpack', help='解包')
    ap_unpack.add_argument('-i', '--input', required=True)
    ap_unpack.add_argument('-o', '--out', required=True)

    ap_pack = sub.add_parser('pack', help='打包')
    ap_pack.add_argument('-i', '--input', required=True)
    ap_pack.add_argument('-o', '--out', required=True)

    args = ap.parse_args()

    if args.cmd == 'unpack':
        unpack(Path(args.input), Path(args.out))
    else:
        pack(Path(args.input), Path(args.out))


if __name__ == '__main__':
    main()
