# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Existing Python: build.py [F01 F02 ...]; no argument renders all 32 figures."""
import json
import sys
from dataclasses import asdict
from collections import Counter
from pathlib import Path

import diagrams
import plots_a
import plots_b
import plots_c
import refined_plots
import method_figures
import v3_plots
from specs import SPECS


def main() -> None:
    root=Path(__file__).resolve().parents[1]
    draw={**diagrams.DRAW,**plots_a.DRAW,**plots_b.DRAW,**plots_c.DRAW}
    draw.update({"F08": refined_plots.f08, "F18": refined_plots.f18,
                 "F19": refined_plots.f19, "F28": refined_plots.f28})
    draw.update(method_figures.DRAW)
    draw.update(v3_plots.DRAW)
    assert set(draw)=={s.id for s in SPECS} and len(draw)==34
    contract={"scope":"R12 frozen results; no new solver or scoring calls", "width_mm":166,
              "minimum_regular_font_pt":7.8,"png_dpi":600,"formats":["PDF","PNG","SVG"],
              "palette":"semantic low-saturation with marker/line redundancy",
              "baseline_scope":"C3 is not an equal-search-budget ablation",
              "counts":dict(Counter(s.kind for s in SPECS)),"figures":[asdict(s) for s in SPECS]}
    with (root/"visual_contract.json").open("w",encoding="utf-8") as stream:
        json.dump(contract,stream,ensure_ascii=False,indent=2)
    with (root/"figure_requirements.json").open("w",encoding="utf-8") as stream:
        json.dump([asdict(s) for s in SPECS],stream,ensure_ascii=False,indent=2)
    for key in sys.argv[1:] or sorted(draw):
        draw[key]()


if __name__=="__main__":
    main()
