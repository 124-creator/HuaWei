# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称、版本/型号、开发机构/公司、版本发布日期：【由参赛队按实际使用情况填写，见论文附录D】
"""技术路线图与三问求解流程图（结构示意，不含实验数据以外的推断）。

由队伍“流程图初级稿件”（参考材料/流程图_初级稿件_20260925）优化与适配而来：
  0_总流程图  → F35 技术路线（与原F35合并，按四个阶段组织）
  1_问题一    → F38 问题一求解流程（补“减少活动核心”与3%近优性证书，去掉图内结果数字）
  2_问题二    → F39 问题二求解流程（补关键链局部移动与3%近优性证书）
  3_问题三    → F40 问题三求解与受控对照（与原F23合并，术语与正文一致）
流程与参数逐项取自 reproduction/NPU_R12 源码（solve_round12/10/7/6、solve_case_v2、residency_bands）。
坐标以毫米为单位、自上而下计；字体与figures_v3一致（西文Times系、中文黑体）。
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

MM = 1 / 25.4
GREY, RED = "#555555", "#B55252"
C = {"A": "#3C5488", "B": "#007C83", "L2": "#B16D24", "ok": "#267F74"}
FC = {"A": "#EDF0F7", "B": "#E6F2F2", "L2": "#F7EFE6", "red": "#FBEFEF", "light": "#F3F4F7", "ok": "#E8F3F0", "white": "white"}
plt.rcParams.update({"font.family": ["Liberation Serif", "WenQuanYi Zen Hei", "DejaVu Serif"], "mathtext.fontset": "stix",
                     "svg.hashsalt": "R12-paper", "pdf.fonttype": 42})

# 正文现行流程图 V1.1：只增强可读性，不改变流程拓扑、节点关系或配色。
# 166 mm 版心下，原 7.6–8.2 pt 的小字提升到约 8.9–9.2 pt；
# 9 pt 以上公式/重点文字按比例放大。为避免节点增高，行距略收紧。
FONT_SCALE = 1.12
FONT_MIN = 8.9

def readable_fs(fs: float) -> float:
    return max(FONT_MIN, fs * FONT_SCALE)


class Canvas:
    def __init__(self, h, w=166.0):
        self.w, self.h = w, h
        self.fig = plt.figure(figsize=(w * MM, h * MM))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w); self.ax.set_ylim(0, h); self.ax.axis("off")

    def y(self, top):
        return self.h - top

    def lines(self, cx, cy, text, fs=8.2, color="black", weight="normal", ha="center"):
        """多行文字：以“$”开头的行按数学式排（不含汉字），其余按普通文字排。"""
        fs = readable_fs(fs)
        rows = text.split("\n")
        step = fs * 0.3528 * 1.34
        top = cy - step * (len(rows) - 1) / 2
        for i, r in enumerate(rows):
            self.ax.text(cx, self.y(top + i * step), r, ha=ha, va="center", fontsize=fs, color=color, weight=weight)

    def node(self, cx, top, w, h, text, ec=GREY, fc="white", fs=8.2, lw=1.0, r=1.6, weight="normal", color="black", ls="-"):
        self.ax.add_patch(FancyBboxPatch((cx - w / 2, self.y(top + h)), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                         fc=fc, ec=ec, lw=lw, ls=ls))
        self.lines(cx, top + h / 2, text, fs=fs, color=color, weight=weight)
        return dict(l=cx - w / 2, r=cx + w / 2, t=top, b=top + h, cx=cx, cy=top + h / 2)

    def diamond(self, cx, top, w, h, text, ec=GREY, fc=FC["light"], fs=8.0):
        cy = top + h / 2
        self.ax.add_patch(Polygon([(cx, self.y(top)), (cx + w / 2, self.y(cy)), (cx, self.y(top + h)), (cx - w / 2, self.y(cy))],
                                  closed=True, fc=fc, ec=ec, lw=1.0))
        self.lines(cx, cy, text, fs=fs)
        return dict(l=cx - w / 2, r=cx + w / 2, t=top, b=top + h, cx=cx, cy=cy)

    def path(self, pts, label=None, at=0, dx=1.2, dy=-2.0, color=GREY, ls="-", ha="left", fs=7.8):
        xy = [(x, self.y(t)) for x, t in pts]
        for (x0, y0), (x1, y1) in zip(xy[:-2], xy[1:-1]):
            self.ax.plot([x0, x1], [y0, y1], color=color, lw=0.9, ls=ls, solid_capstyle="butt")
        self.ax.add_patch(FancyArrowPatch(xy[-2], xy[-1], arrowstyle="-|>", mutation_scale=8, lw=0.9, color=color,
                                          linestyle=ls, shrinkA=0, shrinkB=0))
        if label:
            x, y = xy[at]
            self.ax.text(x + dx, y + dy, label, fontsize=readable_fs(fs), color=color, ha=ha, va="center")

    def save(self, out, name):
        out.mkdir(parents=True, exist_ok=True)
        for ext in ("png", "pdf", "svg"):
            kw = {"dpi": 600} if ext == "png" else {}
            self.fig.savefig(out / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.04,
                             metadata=None if ext != "pdf" else {"CreationDate": None}, **kw)
        plt.close(self.fig)


def roadmap(out):
    """F35 技术路线：四个阶段，中间一条贯穿全文的求解逻辑。"""
    cv = Canvas(178)
    stages = [(3, 34, "阶段一\n数据与口径"), (40, 44, "阶段二\n统一建模"), (89, 58, "阶段三\n分问求解"), (152, 24, "阶段四\n检验与交付")]
    for top, h, lab in stages:
        cv.ax.add_patch(FancyBboxPatch((1, cv.y(top + h)), 16, h, boxstyle="round,pad=0,rounding_size=1.2",
                                       fc=FC["light"], ec="#9AA0A8", lw=0.8))
        cv.lines(9, top + h / 2, lab, fs=8.0, weight="bold", color="#333333")
    x0, x1 = 21, 164
    xm = (x0 + x1) / 2
    w3 = (x1 - x0 - 6) / 3
    ins = [cv.node(x0 + w3 / 2 + i * (w3 + 3), 3, w3, 15, t, fc=FC["light"], fs=7.9) for i, t in enumerate([
        "100张正式计算图\n规模、依赖结构与复用特征普查",
        "固定配置 θ：L1/UB容量、共享DDR\n60 B/cycle、同步等待；问题三另加\n1 MiB只读L2（250 B/cycle）",
        "官方评估程序：唯一评分口径\n整图单核REF：统一加速比分母"])]
    base = cv.node(xm, 23, x1 - x0, 12, "识别主导代价：切图、分核与核序相互耦合；Makespan由官方事件模拟确定，难以写成闭式目标函数", fs=7.9)
    for n in ins:
        cv.path([(n["cx"], n["b"]), (n["cx"], base["t"])])
    model = cv.node(xm, 40, x1 - x0, 20,
                    "决策 P=(g, a, π)；覆盖、唯一排布与联合无环；字典序目标（Makespan，新增搬运量）\n"
                    "评价语义约束：依赖与Pipe串行、Task释放、活跃集合容量、带宽公平共享、边界计账\n"
                    "复杂性与下界：忽略搬运时已NP难；与方案无关的计算下界与窗口下界", fs=7.9)
    cv.path([(xm, base["b"]), (xm, model["t"])])
    steps = [("识代价", "识别各场景的\n主导代价"), ("构候选", "构造面向瓶颈的\n结构化候选族"), ("下界筛选", "下界剪枝与\n3%近优性证书"), ("官方评测", "官方评价器\n字典序择优")]
    w4 = (x1 - x0 - 9) / 4
    for i, (h, b) in enumerate(steps):
        cx = x0 + w4 / 2 + i * (w4 + 3)
        cv.node(cx, 64, w4, 6.5, h, ec=RED, fc=FC["red"], fs=8.2, weight="bold")
        cv.node(cx, 70.5, w4, 10.5, b, ec=RED, fc="white", fs=7.8)
        if i:
            cv.path([(cx - w4 / 2 - 3, 67.25), (cx - w4 / 2, 67.25)], color=RED)
    cv.path([(xm, model["b"]), (xm, 64)])
    cols = [("A", "问题一 · 场景A", "主导代价：Task边界搬运与启动等待",
             "安全链收缩、依赖带弱连通分组\n尾长优先的追加式分核\n划分不变的反馈重排\nTreap区间索引的插入候选", "五核平均加速比 3.743"),
            ("B", "问题二 · 场景B", "主导代价：核内驻留与容量溢出",
             "活动核数与驻留组织候选\n沿官方关键链的局部移动\nSpill触发的局部微批\n核归属不变 ⇒ 边界搬运不变", "五核平均加速比 4.131"),
            ("L2", "问题三 · 共享只读L2", "新增代价：命中、逐出与双带宽池",
             "沿用场景B候选机制\nB类候选在L2配置下重评\n同方案配置比与分别选优比\n逐例分解恒等式", "五核平均加速比 4.219")]
    for i, (k, head, cost, body, res) in enumerate(cols):
        cx = x0 + w3 / 2 + i * (w3 + 3)
        h1 = cv.node(cx, 89, w3, 11, head + "\n" + cost, ec=C[k], fc=C[k], fs=7.8, color="white", weight="bold")
        cv.path([(cx, 81), (cx, h1["t"])])
        b1 = cv.node(cx, 102.5, w3, 30, body, ec=C[k], fc="white", fs=7.8, lw=1.1)
        r1 = cv.node(cx, 135.5, w3, 8.5, res, ec=C["ok"], fc=FC["ok"], fs=8.0, weight="bold")
        cv.path([(cx, b1["b"]), (cx, r1["t"])])
        cv.path([(cx, r1["b"]), (cx, 152)])
    cv.node(xm, 152, x1 - x0, 12, "模型检验：加速比分布与并行效率 ｜ 相对静态构造基线（SCB）的配对检验 ｜ 核数、规模与并行度的稳健性\n最终方案来源的白盒统计 ｜ 求解预算的灵敏度", fs=7.8)
    cv.node(xm, 167, x1 - x0, 9, "交付：1至5核平均加速比曲线、无L2与只读Cache对比曲线、逐例结果表、可复现程序", fc=FC["light"], fs=7.8)
    cv.path([(xm, 164), (xm, 167)])
    cv.save(out, "F35")


def q1_flow(out):
    """F38 问题一（场景A）求解流程。"""
    cv = Canvas(168)
    xm, W = 76, 134
    s = cv.node(xm, 3, 110, 9, "输入：原始图 G、固定A配置 θ、核数 k = 2～5、软预算 600 s", fc=FC["light"], r=4.5)
    b1 = cv.node(xm, 17, W, 12, "① 基础构造并逐个评价：分量打包、链块波次、分量批次 → 首个可行解 P*\n计算与方案无关的下界 LB（计算下界与窗口下界）")
    cv.path([(xm, s["b"]), (xm, b1["t"])])
    hdr = cv.node(xm, 35, W, 8, "生成下一候选：以下五类按固定顺序、在剩余预算内依次尝试", fc=FC["A"], ec=C["A"])
    cv.path([(xm, b1["b"]), (xm, hdr["t"])])
    names = ["② 减少活动核心\n（至多6个）", "③ 依赖带\nw = 4/8/2/16", "④ 反馈重排\n划分 g 不变", "⑤ 分量家族\nm ≤ k（至多6个）", "⑥ Treap插入\n同一插入规则"]
    bw, gap = 24.6, 2.25
    left = xm - W / 2
    boxes = []
    for i, n in enumerate(names):
        cx = left + bw / 2 + i * (bw + gap)
        boxes.append(cv.node(cx, 50, bw, 12, n, ec=C["A"] if i in (1, 2) else GREY, fc=FC["A"] if i in (1, 2) else "white", fs=7.8))
        cv.path([(cx, hdr["b"]), (cx, 50)])
    # 3%近优性证书作用于②—⑤：红色虚线框仅标示适用范围
    gl, gr = boxes[0]["l"] - 1.2, boxes[3]["r"] + 1.2
    cv.ax.add_patch(FancyBboxPatch((gl, cv.y(63.3)), gr - gl, 14.6, boxstyle="round,pad=0,rounding_size=1.2",
                                   fc="none", ec=RED, lw=0.9, ls=(0, (3, 2))))
    for b in boxes:
        cv.ax.plot([b["cx"], b["cx"]], [cv.y(b["b"]), cv.y(65.5)], color=GREY, lw=0.9)
    cv.ax.plot([boxes[0]["cx"], boxes[-1]["cx"]], [cv.y(65.5), cv.y(65.5)], color=GREY, lw=0.9)
    cv.ax.text(boxes[0]["l"], cv.y(69.8), "红框内②—⑤适用3%近优性证书：每阶段开始前\n若 T(P*) ≤ 1.03·LB，则跳过其余早期改进阶段", color=RED,
               fontsize=readable_fs(7.8), ha="left", va="center", linespacing=1.25)
    d1 = cv.diamond(xm, 74, 72, 16, "方案合法且未重复，\n且候选下界 ≤ 当前 Makespan？")
    cv.path([(xm, 65.5), (xm, d1["t"])])
    ev = cv.node(xm, 95, W, 13, "场景A官方完整评价：核内 Step 1～3 ＋ 多核全局事件模拟\n评价成功且 (Makespan, 新增COPY) 字典序更优，则更新当前方案 P*")
    cv.path([(xm, d1["b"]), (xm, ev["t"])], label="是", dy=-2.2)
    d2 = cv.diamond(xm, 113, 60, 13, "仍有候选与预算？")
    cv.path([(xm, ev["b"]), (xm, d2["t"])])
    cv.path([(d1["r"], d1["cy"]), (150, d1["cy"]), (150, d2["cy"]), (d2["r"], d2["cy"])], label="否（剪枝，不送评）", at=0, dx=1.5, dy=2.0)
    cv.path([(d2["l"], d2["cy"]), (4, d2["cy"]), (4, hdr["cy"]), (hdr["l"], hdr["cy"])], label="是", at=0, dx=-5, dy=2.0)
    d3 = cv.diamond(xm, 131, 60, 13, "已获得可行方案？")
    cv.path([(xm, d2["b"]), (xm, d3["t"])], label="否", dy=-2.2)
    ok = cv.node(38, 153, 64, 12, "输出切图映射与各核子图序列\n并保存官方评价结果", ec=C["ok"], fc=FC["ok"])
    bad = cv.node(116, 153, 64, 12, "返回失败状态\n并保留原始失败原因", ec=RED, fc=FC["red"])
    cv.path([(d3["l"], d3["cy"]), (ok["cx"], d3["cy"]), (ok["cx"], ok["t"])], label="是", at=0, dx=-5, dy=2.0)
    cv.path([(d3["r"], d3["cy"]), (bad["cx"], d3["cy"]), (bad["cx"], bad["t"])], label="否", at=0, dx=2.5, dy=2.0)
    cv.save(out, "F38")


def q2_flow(out):
    """F39 问题二（场景B）求解流程。"""
    cv = Canvas(214)
    xm, W = 72, 128
    s = cv.node(xm, 3, 108, 9, "输入：原始图 G、固定B配置 θ、核数 k = 1～5、软预算 600 s", fc=FC["light"], r=4.5)
    b1 = cv.node(xm, 17, W, 12, "① 基础构造并逐个评价（同核全部子图合成一个Task）：分量打包、链块波次、\n分量批次、链块迁移 → 首个可行解 P*；计算与方案无关的下界 LB")
    cv.path([(xm, s["b"]), (xm, b1["t"])])
    g = cv.diamond(xm, 34, 70, 14, "3%近优性证书成立：T(P*) ≤ 1.03·LB？", ec=RED, fc=FC["red"])
    cv.path([(xm, b1["b"]), (xm, g["t"])])
    c2 = cv.node(xm, 53, W, 8, "② 减少活动核心的候选（至多6个）")
    c3 = cv.node(xm, 66, W, 8, "③ 沿官方时间线关键链的局部移动（至多4个；仅用于不超过10000个操作的图）", ec=C["B"], fc=FC["B"])
    c4 = cv.node(xm, 79, W, 12, "④ 分量家族与驻留组织：活动核数 m ≤ k，target ∈ {0, 512, 2048}；其余核心保留空队列\n去重与下界剪枝后至多评价6个新候选", ec=C["B"], fc=FC["B"])
    c5 = cv.node(xm, 96, W, 8, "⑤ 插入式候选：HEFT式优先级 ＋ Treap区间索引（生成至多30 s，评价至多120 s）")
    cv.path([(xm, g["b"]), (xm, c2["t"])], label="否", dy=-2.2)
    cv.path([(xm, c2["b"]), (xm, c3["t"])]); cv.path([(xm, c3["b"]), (xm, c4["t"])]); cv.path([(xm, c4["b"]), (xm, c5["t"])])
    cv.path([(g["r"], g["cy"]), (142, g["cy"]), (142, c5["cy"]), (c5["r"], c5["cy"])], label="是：跳过②—④", at=0, dx=1.5, dy=2.0, color=RED)
    cv.ax.text(143.5, cv.y(74), "②—④每个阶段\n开始前均检查", color=RED, fontsize=readable_fs(7.8), ha="left", va="center", linespacing=1.25)
    d = cv.diamond(xm, 109, 74, 15, "当前最优可行方案出现实测 Spill，\n且诊断预算尚有剩余？")
    cv.path([(xm, c5["b"]), (xm, d["t"])])
    m1 = cv.node(xm, 129, W, 12, "⑥ 依据官方 Step 2 的 Spill 记录进行诊断（至多40 s）\n筛选大张量事件：不小于容量的1/4，前后两次使用的子图距离不超过8", ec=C["B"], fc=FC["B"])
    cv.path([(xm, d["b"]), (xm, m1["t"])], label="是", dy=-2.2)
    m2 = cv.node(xm, 146, W, 12, "生成至多两个固定窗口候选：窗口宽4或8个子图，至多16个互不重叠的窗口，\n每个窗口不超过128个原计算操作；窗口内让共享输入的使用者连续执行", ec=C["B"], fc=FC["B"])
    cv.path([(xm, m1["b"]), (xm, m2["t"])])
    inv = cv.node(xm, 163, W, 9, "不变量：窗口外次序与每个操作的核归属都不变 ⇒ Spill前的边界COPY严格不变", ec=GREY, fc=FC["light"], ls=(0, (3, 2)))
    cv.path([(xm, m2["b"]), (xm, inv["t"])])
    m3 = cv.node(xm, 177, W, 8, "每个候选仍经结构检查与场景B官方完整评价（至多45 s）；字典序更优才更新 P*")
    cv.path([(xm, inv["b"]), (xm, m3["t"])])
    out_ok = cv.node(xm, 196, 110, 12, "已有可行方案则输出切图映射、各核子图序列及官方评价结果；\n若无可行方案则返回失败状态", ec=C["ok"], fc=FC["ok"])
    cv.path([(xm, m3["b"]), (xm, out_ok["t"])])
    cv.path([(d["l"], d["cy"]), (4, d["cy"]), (4, 190), (xm - 20, 190), (xm - 20, out_ok["t"])], label="否", at=0, dx=-5, dy=2.0)
    cv.save(out, "F39")


def q3_flow(out):
    """F40 问题三：求解与“方案×配置”受控对照。"""
    cv = Canvas(175)
    xm = 83
    top = cv.node(xm, 3, 160, 10, "输入：100张图 × 1～5核；无L2配置（场景B）与只读Cache配置（1 MiB只读FIFO，读带宽250 B/cycle，\n与60 B/cycle的DDR池互不占用）；整图单核REF", fc=FC["light"], fs=7.8)
    lb = cv.node(42, 20, 76, 20, "场景B求解（第6章流程）\n在无L2配置下选出方案\n\n", ec=C["B"], fc=FC["B"])
    cv.lines(42, 34.5, "$P_B$", fs=9.5)
    rb = cv.node(124, 20, 76, 20, "只读Cache配置下独立求解\n沿用场景B候选机制，并额外生成B类候选\n统一按L2配置重评后继续插入与微批\n\n", ec=C["L2"], fc=FC["L2"], fs=7.6)
    cv.lines(124, 36, "$P_L$", fs=9.5)
    cv.path([(42, top["b"]), (42, lb["t"])]); cv.path([(124, top["b"]), (124, rb["t"])])
    e = [cv.node(x, 49, 50, 14, t, ec=GREY) for x, t in ((29, "有L2，同一方案\n\n"), (83, "无L2（共同分子）\n\n"), (137, "有L2，独立选优\n\n"))]
    for n, m in zip(e, (r"$T_L(P_B)$", r"$T_B(P_B)$", r"$T_L(P_L)$")):
        cv.lines(n["cx"], n["cy"] + 2.2, m, fs=9)
    cv.path([(42, lb["b"]), (42, 44.5), (29, 44.5), (29, e[0]["t"])])
    cv.path([(42, 44.5), (83, 44.5), (83, e[1]["t"])])
    cv.path([(124, rb["b"]), (124, 44.5), (137, 44.5), (137, e[2]["t"])])
    hw = cv.node(48, 72, 64, 18, "同方案配置比：固定方案下的硬件配置效应\n\n", ec=C["ok"], fc=FC["ok"])
    cv.lines(48, 83, r"$R_{\mathrm{hw}}=T_B(P_B)\,/\,T_L(P_B)$", fs=9)
    sel = cv.node(118, 72, 64, 18, "分别选优比：同时包含配置与选解效应\n\n", ec=C["L2"], fc=FC["L2"])
    cv.lines(118, 83, r"$R_{\mathrm{select}}=T_B(P_B)\,/\,T_L(P_L)$", fs=9)
    cv.path([(29, e[0]["b"]), (29, hw["t"])])
    cv.ax.plot([83, 83], [cv.y(e[1]["b"]), cv.y(67.5)], color=GREY, lw=0.9)
    cv.ax.plot([70, 96], [cv.y(67.5), cv.y(67.5)], color=GREY, lw=0.9)
    cv.path([(70, 67.5), (70, hw["t"])]); cv.path([(96, 67.5), (96, sel["t"])])
    cv.path([(137, e[2]["b"]), (137, sel["t"])])
    idn = cv.node(xm, 96, 160, 16, "逐例分解恒等式：分别选优比 ＝ 同方案配置比 × 选解比\n\n", ec=GREY, fc="white")
    cv.lines(xm, 107, r"$R_{\mathrm{select},i}=R_{\mathrm{hw},i}\times T_L(P_{B,i})\,/\,T_L(P_{L,i})$", fs=9)
    cv.path([(48, hw["b"]), (48, idn["t"])]); cv.path([(118, sel["b"]), (118, idn["t"])])
    agg = cv.node(xm, 117, 160, 12, "汇总：先逐图计算比值，再对100张图取算术平均\n500组配对评估中，430组两配置最终方案相同，70组不同", fc=FC["light"])
    cv.path([(xm, idn["b"]), (xm, agg["t"])])
    fifo = cv.node(xm, 134, 160, 21, "只读Cache语义（与官方实现一致）\n"
                   "COPY_IN 在发射时按逻辑张量编号查询：命中则走L2读带宽池，未命中则访问DDR；\n"
                   "读取完成后才插入Cache，命中不刷新次序；容量不足时按先进先出淘汰；\n"
                   "新增COPY在事件模拟之前计账，Cache命中不改变已计入的新增COPY字节", ec=C["L2"], fc="white", fs=7.8, ls=(0, (3, 2)))
    res = cv.node(xm, 160, 160, 12, "报告：1至5核两种配置的对比曲线；同核数的配置比与选优比；\n逐例两配置的Makespan、新增COPY与命中率；全部同方案退化实例", ec=C["ok"], fc=FC["ok"])
    cv.path([(xm, agg["b"]), (xm, fifo["t"])])
    cv.path([(xm, fifo["b"]), (xm, res["t"])])
    cv.save(out, "F40")


if __name__ == "__main__":
    from pathlib import Path
    o = Path(__file__).resolve().parent.parent / "figures"
    roadmap(o); q1_flow(o); q2_flow(o); q3_flow(o)
