#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 pywubi 的 86 版码表生成 data/wubi86.json 与 data/jianma.json。

用法：
    python tools/make_data.py [path/to/wubi_86.json]

不传参数时，会尝试从本机已安装的 pywubi 包中读取码表：
    pip install pywubi

简码优先规则（与主流 86 输入法默认的单字输入设置一致）：
    一级简码(1 键) > 二级简码(2 键) > 三级简码(3 键) > 全码
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# 一级简码对应的键位顺序（键盘五区）
KEYS = ["G", "F", "D", "S", "A", "H", "J", "K", "L", "M",
        "T", "R", "E", "W", "Q", "Y", "U", "I", "O", "P",
        "N", "B", "V", "C", "X"]


def load_raw(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        import pywubi  # noqa: F401
        from importlib import resources

        ref = resources.files("pywubi").joinpath("data/wubi_86.json")
        with resources.as_file(ref) as p:
            return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        sys.exit("未找到码表源文件，请用参数指定 pywubi 的 wubi_86.json：%s" % exc)


def pick(codes):
    """返回 (应打码, 简码级别 0/1/2/3, 全码)。"""
    full = max(codes, key=len).upper()
    for length, level in ((1, 1), (2, 2), (3, 3)):
        code = next((c.upper() for c in codes if len(c) == length), None)
        if code:
            return code, level, full
    return full, 0, full


def main():
    ap = argparse.ArgumentParser(description="生成 86 五笔码表数据")
    ap.add_argument("source", nargs="?", help="pywubi 的 wubi_86.json 路径")
    args = ap.parse_args()

    raw = load_raw(args.source)
    table = {}
    level1, level2 = {}, {}
    stats = {1: 0, 2: 0, 3: 0, 0: 0}
    for ch, codes in raw.items():
        code, level, full = pick(codes)
        table[ch] = {"c": code, "l": level, "f": full}
        stats[level] += 1
        if level == 1:
            level1[code] = ch
        elif level == 2:
            level2[code] = ch

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "wubi86.json").write_text(
        json.dumps(table, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    (DATA_DIR / "jianma.json").write_text(
        json.dumps({"keys": KEYS, "level1": level1, "level2": level2},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    print("字符总数: %d" % len(table))
    print("一级简码: %d  二级简码: %d  三级简码: %d  仅全码: %d"
          % (stats[1], stats[2], stats[3], stats[0]))
    print("已写入: %s" % DATA_DIR)


if __name__ == "__main__":
    main()
