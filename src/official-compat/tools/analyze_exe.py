#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位官方 Quake4.exe 中与 GUI 字体路径有关的字符串和代码引用。"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM


DEFAULT_NEEDLES = (
    b"gui_smallFontLimit",
    b"gui_mediumFontLimit",
    b"fonts/%s",
    b"Could not register font",
    b"english",
    b"french",
    b"german",
    b"spanish",
    b"italian",
)


@dataclass(frozen=True)
class LocatedString:
    value: bytes
    file_offset: int
    rva: int
    va: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="分析官方 Quake4.exe 的 GUI 字体相关代码引用"
    )
    parser.add_argument("exe", type=Path, help="官方 Quake4.exe 路径")
    parser.add_argument(
        "--context",
        type=int,
        default=6,
        help="每个引用前后输出的反汇编指令数",
    )
    parser.add_argument(
        "--dump",
        action="append",
        default=[],
        type=lambda value: int(value, 0),
        help="从指定虚拟地址开始输出反汇编，可重复指定",
    )
    parser.add_argument(
        "--dump-size",
        type=lambda value: int(value, 0),
        default=0x100,
        help="--dump 的最大字节数",
    )
    parser.add_argument(
        "--xref",
        action="append",
        default=[],
        type=lambda value: int(value, 0),
        help="输出对指定绝对地址的代码引用，可重复指定",
    )
    return parser.parse_args()


def locate_strings(pe: pefile.PE, data: bytes) -> list[LocatedString]:
    image_base = pe.OPTIONAL_HEADER.ImageBase
    found: list[LocatedString] = []
    for needle in DEFAULT_NEEDLES:
        start = 0
        while True:
            offset = data.find(needle + b"\0", start)
            if offset < 0:
                break
            rva = pe.get_rva_from_offset(offset)
            found.append(LocatedString(needle, offset, rva, image_base + rva))
            start = offset + 1
    return found


def operand_references(insn, target: int) -> bool:
    for operand in insn.operands:
        if operand.type == X86_OP_IMM and operand.imm == target:
            return True
        if operand.type == X86_OP_MEM and operand.mem.disp == target:
            return True
    return False


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    data = exe.read_bytes()
    digest = hashlib.sha256(data).hexdigest().upper()
    pe = pefile.PE(data=data, fast_load=False)

    if pe.FILE_HEADER.Machine != pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_I386"]:
        raise SystemExit(f"目标不是 x86 PE：0x{pe.FILE_HEADER.Machine:04X}")

    text_section = next(
        section for section in pe.sections if section.Name.rstrip(b"\0") == b".text"
    )
    text = text_section.get_data()
    text_va = pe.OPTIONAL_HEADER.ImageBase + text_section.VirtualAddress

    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    disassembler.detail = True
    instructions = list(disassembler.disasm(text, text_va))

    print(f"文件: {exe}")
    print(f"SHA-256: {digest}")
    print(f"映像基址: 0x{pe.OPTIONAL_HEADER.ImageBase:08X}")
    print(f"入口点: 0x{pe.OPTIONAL_HEADER.AddressOfEntryPoint:08X}")
    print(f"时间戳: 0x{pe.FILE_HEADER.TimeDateStamp:08X}")
    print()

    for address in args.dump:
        rva = address - pe.OPTIONAL_HEADER.ImageBase
        offset = pe.get_offset_from_rva(rva)
        block = data[offset : offset + args.dump_size]
        print(f"反汇编 0x{address:08X}，最多 0x{args.dump_size:X} 字节:")
        for insn in disassembler.disasm(block, address):
            print(f"  0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}")
        print()

    for target in args.xref:
        print(f"地址 0x{target:08X} 的代码引用:")
        hit_indexes = [
            index
            for index, insn in enumerate(instructions)
            if operand_references(insn, target)
        ]
        if not hit_indexes:
            print("  代码引用: 0")
            continue
        print(f"  代码引用: {len(hit_indexes)}")
        for hit_index in hit_indexes:
            first = max(0, hit_index - args.context)
            last = min(len(instructions), hit_index + args.context + 1)
            print(f"  --- xref 0x{instructions[hit_index].address:08X} ---")
            for index in range(first, last):
                insn = instructions[index]
                marker = ">" if index == hit_index else " "
                print(
                    f"  {marker} 0x{insn.address:08X}: "
                    f"{insn.mnemonic:<8} {insn.op_str}"
                )
        print()

    for item in locate_strings(pe, data):
        label = item.value.decode("ascii")
        print(
            f"字符串 {label!r}: file=0x{item.file_offset:X} "
            f"rva=0x{item.rva:X} va=0x{item.va:08X}"
        )
        hit_indexes = [
            index
            for index, insn in enumerate(instructions)
            if operand_references(insn, item.va)
        ]
        if not hit_indexes:
            print("  代码引用: 0")
            continue

        print(f"  代码引用: {len(hit_indexes)}")
        for hit_index in hit_indexes:
            first = max(0, hit_index - args.context)
            last = min(len(instructions), hit_index + args.context + 1)
            print(f"  --- xref 0x{instructions[hit_index].address:08X} ---")
            for index in range(first, last):
                insn = instructions[index]
                marker = ">" if index == hit_index else " "
                print(
                    f"  {marker} 0x{insn.address:08X}: "
                    f"{insn.mnemonic:<8} {insn.op_str}"
                )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
