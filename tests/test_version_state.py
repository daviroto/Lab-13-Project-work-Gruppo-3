"""Test dello stato attivo e del registro delle transizioni (S5)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lab13.version_state import (  # noqa: E402
    VersionStateError,
    apply_transition,
    build_state,
    read_state,
    read_transitions,
    validate_mode,
    validate_version_name,
    write_state_atomic,
)


class VersionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.state_path = self.tmp / "config" / "active_version.json"
        self.transitions_path = self.tmp / "reports" / "transitions.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_state_uses_default_version(self) -> None:
        state = read_state(self.state_path, default_version="v1")
        self.assertEqual(state["version"], "v1")
        self.assertEqual(state["source"], "default")

    def test_atomic_write_replaces_state_without_temp_files(self) -> None:
        write_state_atomic(
            self.state_path,
            build_state(
                version="v1",
                previous_version=None,
                action="prepare",
                mode="normal",
                run_id="run-v1",
                artifact_sha256="a" * 64,
                dataset_sha256_canonical="c" * 64,
                source="test",
            ),
        )
        write_state_atomic(
            self.state_path,
            build_state(
                version="v2",
                previous_version="v1",
                action="activate",
                mode="drill",
                run_id="run-v2",
                artifact_sha256="b" * 64,
                dataset_sha256_canonical="c" * 64,
                source="test",
            ),
        )
        state = read_state(self.state_path)
        self.assertEqual(state["version"], "v2")
        self.assertEqual(state["previous_version"], "v1")
        self.assertEqual(state["mode"], "drill")
        leftovers = [path.name for path in self.state_path.parent.iterdir()]
        self.assertEqual(leftovers, ["active_version.json"])

    def test_apply_transition_records_before_and_after(self) -> None:
        before = {
            "version": "v1",
            "run_id": "run-v1",
            "artifact_sha256": "a" * 64,
        }
        after = {
            "version": "v2",
            "run_id": "run-v2",
            "artifact_sha256": "b" * 64,
        }
        state = apply_transition(
            state_path=self.state_path,
            transitions_path=self.transitions_path,
            before=before,
            after=after,
            action="activate",
            mode="drill",
            source="test",
            dataset_sha256_canonical="c" * 64,
        )
        self.assertEqual(state["version"], "v2")
        self.assertEqual(state["previous_version"], "v1")
        self.assertEqual(state["run_id"], "run-v2")
        self.assertEqual(state["artifact_sha256"], "b" * 64)

        records = read_transitions(self.transitions_path)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["action"], "activate")
        self.assertEqual(record["mode"], "drill")
        self.assertEqual(record["before"], before)
        self.assertEqual(record["after"], after)
        self.assertEqual(record["dataset_sha256_canonical"], "c" * 64)
        self.assertIn("timestamp", record)

    def test_rollback_updates_state_after_previous_activation(self) -> None:
        v1 = {"version": "v1", "run_id": "run-v1", "artifact_sha256": "a" * 64}
        v2 = {"version": "v2", "run_id": "run-v2", "artifact_sha256": "b" * 64}
        apply_transition(
            state_path=self.state_path,
            transitions_path=self.transitions_path,
            before=v1,
            after=v2,
            action="activate",
            mode="drill",
            source="test",
            dataset_sha256_canonical="c" * 64,
        )
        state = apply_transition(
            state_path=self.state_path,
            transitions_path=self.transitions_path,
            before=v2,
            after=v1,
            action="rollback",
            mode="drill",
            source="test",
            dataset_sha256_canonical="c" * 64,
        )
        self.assertEqual(state["version"], "v1")
        self.assertEqual(state["previous_version"], "v2")
        records = read_transitions(self.transitions_path)
        self.assertEqual([item["action"] for item in records], ["activate", "rollback"])
        self.assertEqual(records[-1]["after"], v1)

    def test_invalid_version_and_mode_are_rejected(self) -> None:
        with self.assertRaises(VersionStateError):
            validate_version_name("latest")
        with self.assertRaises(VersionStateError):
            validate_mode("production")
        with self.assertRaises(VersionStateError):
            write_state_atomic(self.state_path, {"version": "latest"})

    def test_transitions_file_is_jsonl(self) -> None:
        apply_transition(
            state_path=self.state_path,
            transitions_path=self.transitions_path,
            before=None,
            after={"version": "v1", "run_id": "r", "artifact_sha256": "a"},
            action="prepare",
            mode="normal",
            source="test",
            dataset_sha256_canonical="c",
        )
        lines = self.transitions_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["action"], "prepare")


if __name__ == "__main__":
    unittest.main()
