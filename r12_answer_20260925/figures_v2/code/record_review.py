# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Persist already-performed human-visible author inspection; this does not inspect images."""
import json
from pathlib import Path

from specs import SPECS
from version_guard import check, sha

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = {
    "F01": "检查嵌套资源、DDR双向读写和独立L2读池；修正两条总线的重合竖线。容量与共享带宽含义可区分。",
    "F02": "三层视图对象对应；六操作、五张量、四子图及两核心队列清晰。重复绘制的共享生产边已去重。数学下标单独检查。",
    "F05": "检查A/B相同片段、Task容器和2b/0的限定。修正背景遮住内部连线、搬运线穿过Task标签的问题；仅为单消费中间张量示意。",
    "F06": "黑实线为数据依赖、彩色虚线为核心约束；合法例与成环反例清楚，循环关系另经拓扑测试。",
    "F08": "完整400格色标不截断；九个退化配置逐一显示。小幅负例有框线冗余编码，下图标签、单位与数值可读。",
    "F13": "活期与容量需求分图表达；512 KiB容量线和576 KiB概念需求可区分。不是实测驻留峰值或Spill计量。",
    "F14": "原依赖、操作顺序和共享输入分层；前后八操作覆盖与A_i先于B_i经测试。顺序宽度未冒充执行时长。",
    "F18": "非零22图及零值78图明确；左log10右完整100图累计比例，前十图93.84%注释可读，未删零值分母。",
    "F19": "检查六位小数均值与增量标注，修正首点数值与增量邻近冲突；12/100和2/100分母明确。增量按未舍入数值计算。",
    "F22": "FIFO三个状态与在途请求分开；最早键在左，命中不刷新、途中逐出、完成重插的概念关系可读。",
    "F23": "三评分格及未纳入比较格明确；去掉影响文字的密集阴影，R_hw与R_select符号对应主解。",
    "F28": "两全局图共用绝对时间，两个细节图共用0.90—1.20窗口；20泳道与核心0局部明确，未对两配置各自归一化。",
}


def main() -> None:
    check()
    previous = ROOT.parent / "figures32"
    old = json.loads((previous / "qa/visual_notes.json").read_bytes())
    figures = {}
    hashes = {}
    for spec in SPECS:
        key = spec.id
        hashes[key] = sha(ROOT / "figures" / f"{key}.pdf")
        if key in REVIEWS:
            figures[key] = REVIEWS[key]
        else:
            for suffix in ("pdf", "png", "svg"):
                assert sha(ROOT / "figures" / f"{key}.{suffix}") == sha(previous / "figures" / f"{key}.{suffix}")
            figures[key] = "本轮逐字节沿用旧图，继承既有作者检查：" + old["figures"][key]
    notes = {"review_type": "AUTHOR_REVIEW_NOT_INDEPENDENT_SCIENCE_APPROVAL",
             "scope": "12 revised PDF renders directly viewed; 20 unchanged figures inherit hash-matched prior author review",
             "freshly_reviewed": sorted(REVIEWS), "inherited_review": sorted(set(figures) - set(REVIEWS)),
             "pdf_hashes": hashes, "figures": figures}
    with (ROOT / "qa/visual_notes.json").open("w", encoding="utf-8") as stream:
        json.dump(notes, stream, ensure_ascii=False, indent=2)
    print("RECORDED 12 direct author inspections and 20 hash-matched inherited inspections")


if __name__ == "__main__":
    main()
