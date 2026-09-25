# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Two code-grounded conceptual method figures, not solver runs. Use build.py."""
import math
from typing import Final

from helpers import first_fitting_gap
from model_layout import AMBER, BLUE, GRAY, PALE_AMBER, PALE_BLUE, PALE_TEAL, RED, TEAL, Scene

CHAINS: Final = ((0, 1), (2,), (3,), (4,), (5,), (6, 7), (8,), (9,))
EDGES: Final = ((0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5), (5, 6), (5, 7))
DEPTHS: Final = (0, 1, 1, 2, 2, 3, 4, 4)
BAND_GROUPS: Final = ((0, 1, 2), (3, 4, 5), (6,), (7,))
GAPS: Final = ((0, 2), (4, 7), (9, 11), (14, 22), (25, math.inf))


def f33() -> None:
    s = Scene("F33", 181)
    s.panel((2, 97), "(a) 安全链：源出度=1，目标入度=1")
    for x, chain, first, second in ((4, 0, 0, 1), (55, 5, 6, 7)):
        s.box((x, 77, 40, 14), fill="#FAFBFC", stroke=GRAY, dashed=True, layer=0)
        s.label((x + 5, 84), f"C{chain}", size=8.8)
        s.box((x + 12, 80, 9, 8), f"u{first}", fill=PALE_BLUE)
        s.box((x + 28, 80, 9, 8), f"u{second}", fill=PALE_BLUE)
        s.link([(x + 21, 84), (x + 28, 84)])
    s.panel((2, 70), "(b) 链块深度分带：band(C)=⌊depth(C)/2⌋")
    for rect, color, stroke in (((2, 27, 34, 34), PALE_BLUE, BLUE), ((39, 27, 37, 34), PALE_TEAL, TEAL), ((79, 27, 19, 34), PALE_AMBER, AMBER)):
        s.box(rect, fill=color, stroke=stroke, dashed=True, layer=0)
    positions = {0: (10, 44), 1: (26, 54), 2: (26, 34), 3: (48, 54), 4: (48, 34), 5: (67, 44), 6: (89, 54), 7: (89, 34)}
    for a, b in EDGES:
        start, end = positions[a], positions[b]
        s.link([(start[0] + 4.5, start[1]), (end[0] - 4.5, end[1])], color=GRAY)
    for i, (x, y) in positions.items():
        s.box((x - 4.5, y - 3.5, 9, 7), f"C{i}", fill="white", stroke=BLUE)
        s.rows.append({"record": "conceptual_chain", "chain": i, "members": ",".join(map(str, CHAINS[i])),
                       "depth": DEPTHS[i], "band": DEPTHS[i] // 2})
    for x, depth in ((10, 0), (26, 1), (48, 2), (67, 3), (89, 4)):
        s.label((x, 63), f"d={depth}", size=8)
    for x, name in ((19, "带0：一个弱连通分量"), (57, "带1：一个弱连通分量"), (89, "带2：两分量")):
        s.label((x, 23), name, size=7.9)
    s.panel((2, 16), "(c) 子图结果：带内按弱连通分量合并，不把整带强行并为一个Task")
    for rect, label, fill, stroke in (((2, 2, 28, 9), "S0：u0, u1, u2, u3", PALE_BLUE, BLUE),
                                     ((36, 2, 28, 9), "S1：u4, u5, u6, u7", PALE_TEAL, TEAL),
                                     ((77, 8, 20, 6), "S2：u8", PALE_AMBER, AMBER),
                                     ((77, 0, 20, 6), "S3：u9", PALE_AMBER, AMBER)):
        s.box(rect, label, fill=fill, stroke=stroke, size=8)
    s.link([(30, 6.5), (36, 6.5)])
    s.link([(64, 6.5), (77, 11)])
    s.link([(64, 6.5), (77, 3)])
    s.finish()


def f34() -> None:
    s = Scene("F34", 171)
    start = first_fitting_gap(GAPS, (5, 5, 1))
    assert start == 14
    s.panel((2, 97), "(a) 同一候选日历：ready=5，duration=5，gap=1")
    for i, (low, high) in enumerate(GAPS):
        right = min(high, 32)
        x, width = 6 + 2.7 * low, 2.7 * (right - low)
        s.box((x, 75, width, 8), fill=PALE_TEAL if i == 3 else PALE_BLUE, stroke=TEAL if i == 3 else BLUE)
        s.label((x + width / 2, 88), f"I{i}", size=8.8)
        s.label((x + width / 2, 69), f"[{low},{int(high) if math.isfinite(high) else '∞'})", size=8)
        s.rows.append({"record": "conceptual_gap", "interval": i, "low": low,
                       "high": high if math.isfinite(high) else "infinity", "fit": i == 3, "proxy_cycles_per_unit": 100})
    s.box((6 + 14 * 2.7, 75, 5 * 2.7, 8), "任务", fill=PALE_TEAL, stroke=TEAL, size=8)
    s.box((6 + 19 * 2.7, 75, 2.7, 8), fill=PALE_AMBER, stroke=AMBER, hatch="//")
    s.link([(6, 61), (96, 61)])
    for tick in range(0, 31, 5):
        s.label((6 + tick * 2.7, 56), str(tick), size=8)
    s.label((50, 51), "代理时间（1单位=100 cycles）；斜线段为间隔gap", size=8)
    s.link([(92.4, 79), (98, 79)], color=BLUE)
    s.panel((2, 47), "(b) 增强索引：用子树摘要排除不可能容纳任务的区间")
    s.box((36, 28, 29, 13), "I3：[14,22)\n原不等式确认 t=14", fill=PALE_TEAL, stroke=TEAL, size=9)
    s.box((2, 6, 33, 14), "左子树：I0 / I1 / I2\nmax span=3 < need=6", fill="#F2F3F5", stroke=GRAY, size=8.6)
    s.box((71, 6, 27, 14), "右子树：[25,∞)\n更晚，无需继续搜索", fill="white", stroke=GRAY, size=8.6)
    s.link([(40, 28), (19, 20)], color=RED, dashed=True)
    s.link([(61, 28), (85, 20)], color=GRAY, dashed=True)
    s.label((19, 25), "可整体跳过", color=RED, size=8.3)
    s.label((50, 1), "t=max(ready, low)；t+duration+gap≤high。t=14即1400代理cycles。", size=8)
    s.finish()


DRAW = {"F33": f33, "F34": f34}
