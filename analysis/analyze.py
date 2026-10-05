#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五笔 86 码表分析：简码层级、重码结构、键位负荷与击键成本。

用法:
    python analyze.py                                  # 使用仓库内默认数据路径
    python analyze.py --data path/to/wubi86.json       # 指定码表
    python analyze.py --out charts                     # 指定图表输出目录

数据来源: wubi86-genracer/data/wubi86.json
每条记录形如 {"字": {"c": 主用码, "l": 简码级别(0=仅全码), "f": 全码}}
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---------------------------------------------------------------- 中文字体
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def setup_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return name
    print("警告: 未找到中文字体，图表中的中文可能显示为方块", file=sys.stderr)
    return None


# ---------------------------------------------------------------- 指标计算
LEVEL_NAMES = {1: "一级简码\n(1 键)", 2: "二级简码\n(2 键)", 3: "三级简码\n(3 键)", 0: "仅全码\n(3-4 键)"}
ZONES = {
    "横区 GFDSA": list("GFDSA"),
    "竖区 HJKLM": list("HJKLM"),
    "撇区 TREWQ": list("TREWQ"),
    "捺区 YUIOP": list("YUIOP"),
    "折区 NBVCX": list("NBVCX"),
}


def compute_metrics(table):
    total = len(table)
    codes = collections.Counter(v["c"] for v in table.values())
    level_counts = collections.Counter(v["l"] for v in table.values())

    group_sizes = collections.Counter()
    for code, n in codes.items():
        group_sizes[n] += 1

    collision_chars = sum(n for code, n in codes.items() if n > 1)
    collision_codes = sum(1 for n in codes.values() if n > 1)

    key_load = collections.Counter(v["c"][0] for v in table.values() if v["c"])

    with_short = [v for v in table.values() if v["l"] > 0]
    full_only = [v for v in table.values() if v["l"] == 0]

    def collision_rate(items):
        return sum(1 for v in items if codes[v["c"]] > 1) / len(items) if items else 0.0

    metrics = {
        "总字数": total,
        "不同编码数": len(codes),
        "简码层级分布": {int(k): level_counts[k] for k in (1, 2, 3, 0)},
        "有简码字数": len(with_short),
        "仅全码字数": len(full_only),
        "重码编码数": collision_codes,
        "重码字数": collision_chars,
        "重码率": round(collision_chars / total, 4),
        "最大重码组": max(codes.values()),
        "重码最多的编码": [(c, n) for c, n in codes.most_common(5)],
        "首键负荷": dict(key_load.most_common()),
        "有简码字重码率": round(collision_rate(with_short), 4),
        "仅全码字重码率": round(collision_rate(full_only), 4),
        "平均击键_简码优先": round(sum(len(v["c"]) for v in table.values()) / total, 3),
        "平均击键_全码": round(sum(len(v["f"]) for v in table.values()) / total, 3),
        "组大小分布": dict(sorted(group_sizes.items())),
    }
    metrics["平均击键节省_百分比"] = round(
        (1 - metrics["平均击键_简码优先"] / metrics["平均击键_全码"]) * 100, 2)
    return metrics


# ---------------------------------------------------------------- 图表
def fig_level_distribution(m, out):
    levels = [1, 2, 3, 0]
    counts = [m["简码层级分布"][l] for l in levels]
    labels = [LEVEL_NAMES[l] for l in levels]
    colors = ["#2f6db3", "#4e9ad4", "#8fc4e8", "#c9d6e2"]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.bar(labels, counts, color=colors, width=0.62)
    for bar, c in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, c, "%d\n%.1f%%" % (c, c / m["总字数"] * 100),
                ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("字数")
    ax.set_ylim(0, max(counts) * 1.22)
    ax.set_title("图 1  简码层级分布：%.1f%% 的汉字只有全码可用"
                 % (m["简码层级分布"][0] / m["总字数"] * 100))
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "01_code_level_distribution.png"), dpi=160)
    plt.close(fig)


def fig_collision_sizes(m, out):
    dist = {int(k): v for k, v in m["组大小分布"].items()}
    sizes = sorted(dist)
    counts = [dist[s] for s in sizes]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.bar([str(s) for s in sizes], counts, color="#d97757")
    ax.set_yscale("log")
    ax.set_xlabel("同一编码对应的字数")
    ax.set_ylabel("编码数量（对数轴）")
    ax.set_title("图 2  重码组大小分布：%d 个编码被多字共用，最多 %d 字撞码"
                 % (m["重码编码数"], m["最大重码组"]))
    for i, (s, c) in enumerate(zip(sizes, counts)):
        ax.text(i, c, str(c), ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "02_collision_group_sizes.png"), dpi=160)
    plt.close(fig)


def fig_key_load(m, out):
    load = m["首键负荷"]
    keys = sorted(load, key=lambda k: -load[k])
    zone_color = {}
    palette = ["#2f6db3", "#4e9ad4", "#e0a458", "#6aa84f", "#9b6bab"]
    for (zone, ks), color in zip(ZONES.items(), palette):
        for k in ks:
            zone_color[k] = (color, zone)
    fig, ax = plt.subplots(figsize=(7.6, 5.6))
    y = range(len(keys))
    ax.barh(list(y), [load[k] for k in keys],
            color=[zone_color.get(k, ("#888", ""))[0] for k in keys])
    ax.set_yticks(list(y))
    ax.set_yticklabels(keys)
    ax.invert_yaxis()
    ax.set_xlabel("以该键起笔的汉字数")
    ax.set_title("图 3  首键负荷：Q 键承担 %d 字，是最轻键位的 %.1f 倍"
                 % (load[keys[0]], load[keys[0]] / max(1, load[keys[-1]])))
    for i, k in enumerate(keys):
        ax.text(load[k], i, " %d" % load[k], va="center", fontsize=8.5)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in palette]
    ax.legend(handles, list(ZONES.keys()), fontsize=8, ncol=2, loc="lower right")
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "03_key_load.png"), dpi=160)
    plt.close(fig)


def fig_shortcode_value(m, out):
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2))
    ax = axes[0]
    vals = [m["有简码字重码率"] * 100, m["仅全码字重码率"] * 100]
    bars = ax.bar(["有简码的字\n(%d 字)" % m["有简码字数"], "仅全码的字\n(%d 字)" % m["仅全码字数"]],
                  vals, color=["#2f6db3", "#c9d6e2"], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, "%.1f%%" % v, ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("重码率")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_title("重码率对比", fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    ax = axes[1]
    vals = [m["平均击键_简码优先"], m["平均击键_全码"]]
    bars = ax.bar(["简码优先", "全部打全码"], vals, color=["#2f6db3", "#c9d6e2"], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, "%.3f 键" % v, ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("平均击键数")
    ax.set_ylim(0, max(vals) * 1.18)
    ax.set_title("平均击键成本对比（节省 %.1f%%）" % m["平均击键节省_百分比"], fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    fig.suptitle("图 4  简码机制的实际价值：高频字既少撞码，也少按键", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(os.path.join(out, "04_shortcode_value.png"), dpi=160)
    plt.close(fig)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    default_candidates = [
        os.path.join("data", "wubi86.json"),                                    # 仓库根目录下运行
        os.path.join(here, "..", "data", "wubi86.json"),                        # analysis/ 子目录
        os.path.join(here, "..", "..", "work", "github", "wubi86-genracer",
                     "data", "wubi86.json"),                                    # 本地分析工作区
    ]
    default_data = next((c for c in default_candidates if os.path.exists(c)), default_candidates[0])
    ap.add_argument("--data", default=default_data)
    ap.add_argument("--out", default=os.path.join(here, "charts"))
    args = ap.parse_args()

    if not os.path.exists(args.data):
        sys.exit("找不到码表文件: %s" % args.data)
    os.makedirs(args.out, exist_ok=True)
    setup_font()

    table = json.load(open(args.data, encoding="utf-8"))
    m = compute_metrics(table)

    fig_level_distribution(m, args.out)
    fig_collision_sizes(m, args.out)
    fig_key_load(m, args.out)
    fig_shortcode_value(m, args.out)

    with open(os.path.join(here, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

    print("样本量: %d 字" % m["总字数"])
    print("简码层级: 一级 %d / 二级 %d / 三级 %d / 仅全码 %d"
          % (m["简码层级分布"][1], m["简码层级分布"][2],
             m["简码层级分布"][3], m["简码层级分布"][0]))
    print("编码总数: %d，重码编码 %d 个，重码字 %d 个（%.1f%%），最大重码组 %d 字"
          % (m["不同编码数"], m["重码编码数"], m["重码字数"], m["重码率"] * 100, m["最大重码组"]))
    print("重码率: 有简码 %.1f%% vs 仅全码 %.1f%%"
          % (m["有简码字重码率"] * 100, m["仅全码字重码率"] * 100))
    print("平均击键: %.3f（简码优先） vs %.3f（全码），节省 %.1f%%"
          % (m["平均击键_简码优先"], m["平均击键_全码"], m["平均击键节省_百分比"]))
    print("图表输出: %s" % os.path.abspath(args.out))


if __name__ == "__main__":
    main()
