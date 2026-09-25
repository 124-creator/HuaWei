# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Residency examples, FIFO snapshots and experiment structure; use build.py."""
from model_examples import AFTER, BEFORE, FIFO_STATES
from model_layout import AMBER, BLUE, GRAY, PALE_AMBER, PALE_BLUE, PALE_TEAL, RED, TEAL, Scene


def f13() -> None:
    s = Scene("F13", 143)
    s.panel((2, 95), "(a) 逻辑活跃区间：仍有后续使用")
    for name, start, end, y, size, color in (("A", 0, 6, 72, 320, BLUE), ("B", 2, 8, 54, 256, TEAL)):
        s.box((8 + start * 4.8, y - 4, (end - start) * 4.8, 8), fill=PALE_BLUE if name == "A" else PALE_TEAL, stroke=color)
        s.label((28, y + 9), f"张量{name}：{size} KiB", size=8.8, color=color)
        s.rows.append({"record": "conceptual_lifetime", "tensor": name, "start": start, "end": end, "bytes": size * 1024})
    for i in (0, 2, 4, 6, 8):
        s.label((8 + i * 4.8, 37), str(i), size=8)
    s.link([(8, 42), (48, 42)], arrow=True)
    s.label((28, 28), "示意顺序索引（非实测cycles）", size=8)
    s.panel((56, 95), "(b) 两者不能同时留在L1")
    s.box((65, 34, 15, 25), "A\n320", fill=PALE_BLUE, stroke=BLUE)
    s.box((65, 59, 15, 20), "B\n256", fill=PALE_TEAL, stroke=TEAL)
    s.box((65, 74, 15, 5), fill="none", stroke=RED, hatch="///")
    s.link([(58, 74), (95, 74)], color=RED, dashed=True, arrow=False)
    s.label((86, 86), "合计576 KiB", size=8.5)
    s.label((87, 68), "L1容量\n512 KiB", size=8.3, color=RED)
    s.label((77, 24), "每张量单独可容纳\n不等于二者同时可驻留", size=9, color=RED)
    s.label((50, 11), "逻辑活跃 ≠ 物理常驻：需换出再读入，或选择不同的合法顺序", size=8.7)
    s.label((50, 4), "此图仅解释容量冲突；不指定替换策略，不推断实测Spill字节数", size=8.0)
    s.finish()


def f14() -> None:
    s = Scene("F14", 159)
    s.panel((2, 97), "(a) 原依赖：每条链 Aᵢ 在 Bᵢ 之前，无跨链依赖")
    for i, x in enumerate((17, 39, 61, 83), 1):
        s.box((x - 6, 82, 12, 8), f"A{i}", fill=PALE_BLUE, stroke=BLUE)
        s.box((x - 6, 65, 12, 8), f"B{i}", fill=PALE_AMBER, stroke=AMBER)
        s.link([(x, 82), (x, 73)], color=GRAY)
    s.label((50, 58), "所有 Aᵢ 读取同一大输入 tA；所有 Bᵢ 读取同一大输入 tB", size=8.4)
    for order, y, heading in ((BEFORE, 39, "(b) 交替顺序"), (AFTER, 15, "(c) 同核局部重排")):
        s.panel((2, y + 11), heading)
        for i, op in enumerate(order):
            x = 4 + 11.5 * i
            is_a = op.startswith("A")
            fill, stroke = (PALE_BLUE, BLUE) if is_a else (PALE_AMBER, AMBER)
            s.box((x, y, 10, 7), op, fill=fill, stroke=stroke)
            s.box((x, y - 6, 10, 4), "tA" if is_a else "tB", fill=fill, stroke=stroke, size=8)
            s.rows.append({"record": "conceptual_schedule", "panel": heading[:3], "position": i,
                           "operation": op, "core": 0, "input": "tA" if is_a else "tB"})
        s.label((97, y + 11), "核心0；横向为顺序，不是持续时间", align="right", size=8)
    s.label((50, 1), "下排同输入连续使用；原始依赖与核心归属不变，但实际收益仍须完整评价", size=8)
    s.finish()


def f22() -> None:
    s = Scene("F22", 152)
    s.label((51, 96), "概念例：每个键256 KiB；FIFO容量1 MiB；左端最早插入", size=8.5)
    events = ("t₀：发射读取A", "t₁：其他读取E完成", "t₂：读取A完成")
    comments = ("命中，但不刷新FIFO次序", "插入E，最早的A被逐出", "A已不在缓存：逐出B后重插A")
    for i, (y, state) in enumerate(zip((80, 52, 24), FIFO_STATES)):
        s.label((2, y), events[i], align="left", size=8.4)
        for j, name in enumerate(state):
            s.box((27 + j * 10, y - 5, 9, 10), name,
                  fill=PALE_TEAL if name == "A" else PALE_BLUE,
                  stroke=TEAL if name == "A" else BLUE)
            s.rows.append({"record": "conceptual_fifo", "snapshot": i, "position": j, "key": name, "bytes": 262144})
        s.label((46, y - 12), comments[i], size=8.0)
    s.link([(78, 80), (78, 24)], color=TEAL, arrow=False)
    s.box((75, 77, 6, 6), fill=PALE_TEAL, stroke=TEAL)
    s.box((75, 21, 6, 6), fill=PALE_TEAL, stroke=TEAL)
    s.label((90, 61), "读取A在途\n使用L2读池\n250 bytes/cycle", size=8.4, color=TEAL)
    s.label((90, 35), "发射定命中\n完成试插入", size=8.5, bold=True)
    s.label((50, 3), "t₀ < t₁ < t₂ 仅表示先后；缓存键被逐出，不撤销已发射读取的带宽池选择", size=8.0)
    s.finish()


def f23() -> None:
    s = Scene("F23", 139)
    s.label((43, 91), "B配置：无L2", bold=True)
    s.label((79, 91), "L2配置：有L2", bold=True)
    s.label((12, 72), "冻结方案\n$P_B$", bold=True)
    s.label((12, 47), "另选方案\n$P_L$", bold=True)
    s.box((27, 61, 32, 21), "$T_B(P_B)$\n共同分子", fill=PALE_BLUE, stroke=BLUE, size=10)
    s.box((63, 61, 32, 21), "$T_L(P_B)$\n同一方案", fill=PALE_TEAL, stroke=TEAL, size=10)
    s.box((27, 36, 32, 21), "未纳入本比较", fill="#F3F4F5", stroke=GRAY, size=8.8)
    s.box((63, 36, 32, 21), "$T_L(P_L)$\n方案可变化", fill=PALE_AMBER, stroke=AMBER, size=10)
    s.label((26, 23), "配置效应：固定方案", color=TEAL, bold=True)
    s.label((76, 23), "综合效应：允许另选", color=AMBER, bold=True)
    s.label((26, 14), "$R_{hw}=T_B(P_B)/T_L(P_B)$", size=10)
    s.label((76, 14), "$R_{select}=T_B(P_B)/T_L(P_L)$", size=10)
    s.label((50, 3), "先逐图求比值，再对100图取算术均值；不能用两条均值曲线相除", size=8.0)
    s.finish()
