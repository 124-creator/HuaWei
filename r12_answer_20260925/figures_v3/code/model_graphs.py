# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Resource topology, model mapping and feasibility; run via build.py."""
from model_examples import CYCLIC_QUEUES, GROUPS, LEGAL_QUEUES, TASK_EDGES
from model_layout import AMBER, BLUE, GRAY, INK, PALE_AMBER, PALE_BLUE, PALE_TEAL, RED, TEAL, Scene


def f01() -> None:
    s = Scene("F01", 145)
    s.box((3, 83, 53, 14), "共享DDR（读 / 写）\n总带宽 60 bytes/cycle", fill=PALE_AMBER, stroke=AMBER)
    s.box((63, 83, 34, 14), "只读L2  /  独立于DDR\n1 MiB；250 bytes/cycle", fill=PALE_TEAL, stroke=TEAL)
    s.link([(28, 83), (28, 77), (14, 77), (80, 77)], color=AMBER, arrow=False)
    s.link([(94, 83), (94, 72), (25, 72)], color=TEAL, arrow=False)
    for x, name in ((3, "核心0"), (36, "核心1"), (69, "核心k−1")):
        s.box((x, 12, 28, 54), fill="#FAFBFC", stroke=GRAY)
        s.label((x + 14, 62), name, bold=True)
        s.link([(x + 11, 77), (x + 11, 66)], color=AMBER, both=True)
        s.link([(x + 22, 72), (x + 22, 66)], color=TEAL)
        s.box((x + 3, 45, 10, 10), "M", fill=PALE_BLUE)
        s.box((x + 15, 45, 10, 10), "V", fill=PALE_TEAL, stroke=TEAL)
        s.box((x + 3, 31, 10, 9), "IN", fill=PALE_AMBER, stroke=AMBER)
        s.box((x + 15, 31, 10, 9), "OUT", fill="#F5E8E5", stroke=RED)
        s.box((x + 3, 16, 10, 11), "L1\n512 KiB", fill="white", size=8.0)
        s.box((x + 15, 16, 10, 11), "UB\n128 KiB", fill="white", size=8.0)
    s.label((50, 5), "私有容量按核心独立；带宽由全部核心共享；只读L2仅在Q3启用", size=8.5)
    s.finish()


def f02() -> None:
    s = Scene("F02", 174)
    s.panel((2, 96), "(a) 输入：操作—张量二部DAG")
    positions = {0: (6, 83), 1: (27, 83), 2: (50, 89), 3: (50, 76), 4: (76, 83), 5: (96, 83)}
    tensors = {0: (16, 83), 1: (38, 83), 2: (63, 89), 3: (63, 76), 4: (86, 83)}
    links = [(0, 0, 1), (1, 1, 2), (1, 1, 3), (2, 2, 4), (3, 3, 4), (4, 4, 5)]
    for op, (x, y) in positions.items():
        s.box((x - 3.5, y - 3, 7, 6), f"$u_{op}$", fill=PALE_BLUE)
    for tensor, pos in tensors.items():
        s.tensor(pos, f"$t_{tensor}$")
    for producer, tensor in sorted({(a, t) for a, t, _ in links}):
        a, t = positions[producer], tensors[tensor]
        s.link([(a[0] + 3.5, a[1]), (t[0] - 2.5, t[1])])
    for _, tensor, consumer in links:
        t, b = tensors[tensor], positions[consumer]
        s.link([(t[0] + 2.5, t[1]), (b[0] - 3.5, b[1])])
    s.panel((2, 65), "(b) 划分 g：原操作恰好归入一个子图")
    locations = ((3, 44, 30, 15), (43, 53, 17, 9), (43, 39, 17, 9), (72, 44, 26, 15))
    centers = {}
    for i, (rect, members) in enumerate(zip(locations, GROUPS)):
        x, y, w, h = rect
        s.box(rect, f"$S_{i}$  :  " + ", ".join(f"u{j}" for j in members),
              fill=PALE_TEAL if i == 2 else PALE_BLUE, stroke=TEAL if i == 2 else BLUE)
        centers[i] = (x, y, w, h)
    for a, b in TASK_EDGES:
        x, y, w, h = centers[a]
        xx, yy, ww, hh = centers[b]
        s.link([(x + w, y + h / 2), (xx, yy + hh / 2)])
    s.panel((2, 32), "(c) 分核 a 与核序 π：相同子图、不同核心队列")
    for y, core, groups in ((23, 0, (0, 1, 3)), (10, 1, (2,))):
        s.label((9, y), f"核心{core}", size=8.5)
        s.box((20, y - 4.5, 77, 9), fill="#FAFBFC", stroke=GRAY, dashed=True)
        for j, group in enumerate(groups):
            s.box((24 + 25 * j, y - 3, 19, 6), f"$S_{group}$",
                  fill=PALE_BLUE if core == 0 else PALE_TEAL, stroke=BLUE if core == 0 else TEAL)
        s.label((97, y - 6), "队列序号，不是执行时刻", align="right", size=7.8)
    s.finish()


def f05() -> None:
    s = Scene("F05", 139)
    for x, title, combined in ((2, "(a) 场景A：两个Task", False), (53, "(b) 场景B：同一Task", True)):
        s.panel((x, 96), title)
        s.box((x + 1, 80, 43, 9), "DDR", fill=PALE_AMBER, stroke=AMBER)
        if combined:
            s.box((x + 1, 40, 43, 31), fill="#FAFBFC", dashed=True, layer=0)
            s.label((x + 23, 67), "核心0 / 一个Task", size=8.3)
        else:
            for offset, name in ((1, "Task S0"), (25, "Task S1")):
                s.box((x + offset, 40, 19, 31), fill="#FAFBFC", dashed=True, layer=0)
                s.label((x + offset + 9.5, 45), name, size=8.3)
        s.box((x + 5, 53, 11, 8), "$u_0$", fill=PALE_BLUE)
        s.box((x + 29, 53, 11, 8), "$u_1$", fill=PALE_BLUE)
        if combined:
            s.tensor((x + 23, 57), "$t$")
            s.link([(x + 16, 57), (x + 20.5, 57)], color=TEAL)
            s.link([(x + 25.5, 57), (x + 29, 57)], color=TEAL)
            s.label((x + 23, 45), "私有缓存允许保留 t", size=8.3)
        else:
            s.link([(x + 10.5, 61), (x + 10.5, 80)], color=AMBER)
            s.link([(x + 34.5, 80), (x + 34.5, 61)], color=AMBER)
            s.label((x + 4, 75), "OUT", size=8.0)
            s.label((x + 41, 75), "IN", size=8.0)
            s.label((x + 23, 34), "同核边界仍需一次写出、一次读入", size=8.0)
        s.label((x + 23, 25), "边界COPY：2b" if not combined else "驻留且无Spill时：边界COPY为0", size=8.7, bold=True)
    s.label((50, 12), "相同片段：u₀产生 b 字节中间张量，u₁消费；无其他消费者、非最终输出", size=8.0)
    s.label((50, 5), "场景B消除该同核边界，不代表容量足够或不会Spill", size=8.5, color=TEAL)
    s.finish()


def f06() -> None:
    s = Scene("F06", 140)
    for offset, title, queues, color in ((1, "(a) 合法核序", LEGAL_QUEUES, TEAL), (53, "(b) 核序造成等待环", CYCLIC_QUEUES, RED)):
        s.panel((offset, 96), title)
        p = {0: (offset + 5, 69), 1: (offset + 23, 84), 2: (offset + 23, 54), 3: (offset + 41, 69)}
        for a, b in TASK_EDGES:
            aa, bb = p[a], p[b]
            s.link([(aa[0] + 4, aa[1]), (bb[0] - 4, bb[1])], color=INK)
        for i, (x, y) in p.items():
            s.box((x - 4, y - 4, 8, 8), f"$S_{i}$", fill=PALE_BLUE if i in (0, 3) else PALE_TEAL)
        a, b = queues[0]
        s.link([(p[a][0], p[a][1] - 4), (p[a][0], 39), (p[b][0], 39), (p[b][0], p[b][1] - 4)], color=color, dashed=True)
        s.link([(p[1][0], 80), (p[2][0], 58)], color=color, dashed=True)
        s.label((offset + 23, 27), f"核心0：S{a}，S{b}\n核心1：S1，S2", size=9)
    s.label((25, 11), "依赖边与核序边的并图仍无环", color=TEAL, size=8.3)
    s.label((76, 11), "S0 → S1 → S3 → S0", color=RED, size=8.8)
    s.link([(22, 3), (30, 3)], color=INK)
    s.label((39, 3), "数据依赖", size=8)
    s.link([(57, 3), (65, 3)], color=TEAL, dashed=True)
    s.label((75, 3), "核心队列约束", size=8)
    s.finish()
