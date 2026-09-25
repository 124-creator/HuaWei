# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record completed author inspection; this script itself does not inspect images."""
import json
from pathlib import Path

from specs import SPECS
from version_guard import check, sha

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = {
    "F33": "实际查看PDF渲染。安全链、链块深度、width=2分带和四个子图对应明确；同带独立分量未强并，示例覆盖10操作且安全边和深度关系经测试。",
    "F34": "实际查看PDF渲染。区间、左子树摘要和原插入不等式分开；标明1单位=100代理cycles及gap斜线，不冒充实际Treap快照或官方时刻。",
    "F21": "实际查看PDF渲染。两案例共用相对尺度并标注原始cycles；展示全部进一步改善案例，98个其余请求状态与非独立消融限定保留。",
    "F24": "实际查看PDF渲染。PB/B、PB/L2和PL/L2三条曲线由颜色和标记区分；右侧逐图配置比独立计算，均值不能相除。",
    "F25": "实际查看PDF渲染。长尾完整保留，局部ECDF保持100分母；修正原生压缩重复值导致的计数问题，比例1处为39/100，图例背景避免竖线穿字。",
    "F27": "实际查看PDF渲染。全4252事件保留，共同窗口及e2428可定位；219 KiB只称占用净降，不称驱逐总量或流水线瓶颈原因。",
    "F28": "实际查看PDF渲染。高度从255降至235 mm，字号保持；两配置共用时间，红线只标在L2视图，局部仍明确是核心0而缓存事件是全局事件。",
}


def main() -> None:
    check()
    old = ROOT.parent / "figures_v2"
    previous = json.loads((old / "qa/visual_notes.json").read_bytes())
    figures = {}
    hashes = {}
    for spec in SPECS:
        key = spec.id
        hashes[key] = sha(ROOT / "figures" / f"{key}.pdf")
        if key in REVIEWS:
            figures[key] = REVIEWS[key]
        else:
            for suffix in ("pdf", "png", "svg"):
                assert sha(ROOT / "figures" / f"{key}.{suffix}") == sha(old / "figures" / f"{key}.{suffix}")
            figures[key] = "逐字节沿用v2，继承其作者检查：" + previous["figures"][key]
    notes = {"review_type": "AUTHOR_REVIEW_NOT_INDEPENDENT_SCIENCE_APPROVAL",
             "scope": "7 new/revised PDF renders directly viewed; 27 unchanged figures inherit hash-matched v2 inspection",
             "freshly_reviewed": list(REVIEWS), "inherited_review": sorted(set(figures) - set(REVIEWS)),
             "pdf_hashes": hashes, "figures": figures}
    with (ROOT / "qa/visual_notes.json").open("w", encoding="utf-8") as stream:
        json.dump(notes, stream, ensure_ascii=False, indent=2)
    print("RECORDED 7 direct inspections and 27 hash-matched inherited inspections")


if __name__ == "__main__":
    main()
