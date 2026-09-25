# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Structural and mechanistic figures; no algorithm decision flowcharts."""
from model_graphs import f01, f02, f05, f06
from model_memory import f13, f14, f22, f23

DRAW = {"F01": f01, "F02": f02, "F05": f05, "F06": f06,
        "F13": f13, "F14": f14, "F22": f22, "F23": f23}
