"""Regression checks for evidence reuse and aggregation; standard-library only."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidence import AuditError, Identity, cached_l2, digest, ratio_mean, read_score


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "result.json"
        self.data = {
            "scene": "B", "problem": 3, "cache_mode": "read_only",
            "num_cores": 1, "makespan": 10, "bandwidth_bytes_per_cycle": 60,
            "cache_capacity_bytes": 1048576, "cache_bandwidth_bytes_per_cycle": 250,
            "data_movement_bytes": {
                "original_graph_copy_bytes": 50, "scheduled_copy_bytes": 60,
                "added_copy_bytes": 10, "partition_added_copy_bytes": 6,
                "spill_added_copy_bytes": 4,
            },
            "cache_stats": {"hit_bytes": 20, "miss_bytes": 40, "hit_rate": 1 / 3},
        }
        self.raw.write_text(json.dumps(self.data), encoding="utf-8")
        self.identity = Identity("case_001", 1, "g", "c", "o", "p")
        self.meta = self.root / "meta.json"
        self.metadata = {
            "status": "ok", "case": "case_001", "requested_cores": 1,
            "mode": "L2", "graph_sha256": "g", "config_sha256": "c",
            "official_code_sha256": "o", "plan_sha256": "p",
            "official_result_file": "result.json", "official_result_sha256": digest(self.raw),
        }
        self.meta.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_mean_uses_per_case_ratios(self) -> None:
        # Given unequal denominators; when aggregated; then not a ratio of sums.
        self.assertEqual(ratio_mean([(2, 1), (9, 9)], 2), 1.5)

    def test_incomplete_group_is_rejected(self) -> None:
        with self.assertRaises(AuditError):
            ratio_mean([(2, 1)], 100)

    def test_zero_denominator_is_rejected(self) -> None:
        with self.assertRaises(AuditError):
            ratio_mean([(1, 0)], 1)

    def test_exact_candidate_is_reused(self) -> None:
        result = cached_l2(self.meta, self.identity)
        self.assertIsNotNone(result)
        self.assertEqual(result.makespan if result else None, 10)

    def test_other_plan_is_not_reused(self) -> None:
        other = Identity("case_001", 1, "g", "c", "o", "another-plan")
        self.assertIsNone(cached_l2(self.meta, other))

    def test_changed_graph_is_not_reused(self) -> None:
        other = Identity("case_001", 1, "different-graph", "c", "o", "p")
        self.assertIsNone(cached_l2(self.meta, other))

    def test_changed_evaluator_is_not_reused(self) -> None:
        other = Identity("case_001", 1, "g", "c", "different-evaluator", "p")
        self.assertIsNone(cached_l2(self.meta, other))

    def test_tampered_raw_is_rejected(self) -> None:
        self.raw.write_text(self.raw.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaises(AuditError):
            cached_l2(self.meta, self.identity)

    def test_byte_weighted_hit_rate_is_checked(self) -> None:
        self.data["cache_stats"]["hit_rate"] = 0.5
        self.raw.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(AuditError):
            read_score(self.raw, "L2", 1)

    def test_non_l2_result_cannot_supply_cache_control(self) -> None:
        self.data.pop("problem")
        self.raw.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(AuditError):
            read_score(self.raw, "L2", 1)


if __name__ == "__main__":
    unittest.main()
