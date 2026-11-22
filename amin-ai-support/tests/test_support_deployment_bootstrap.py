"""JAVAB deployment preflight: real default project registration and scoping.

Does not claim any external network or phone test; GitHub checkout paths only.
"""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from amin_support import SupportEngine, load_projects


ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/"amin-ai-support"/"projects.json"


class SupportDeploymentBootstrapTests(unittest.TestCase):
    def test_support_registered_and_documentation_exists_in_checkout(self):
        projects=load_projects(CONFIG)
        self.assertIn("support", projects, "Live server cannot issue support access without this entry")
        support=projects["support"]
        paths=support["source_prefixes"]
        self.assertEqual(set(paths), set(support["public_paths"]))
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            self.assertTrue((ROOT/path).is_file(), f"Missing support source: {path}")
            self.assertTrue(path.startswith("amin-ai-support/"))
            self.assertNotIn("..", Path(path).parts)

    def test_support_scoped_key_is_a_real_registered_project(self):
        with tempfile.TemporaryDirectory() as root:
            engine=SupportEngine(CONFIG, Path(root)/"bootstrap.sqlite3")
            secret=engine.access.issue("support", allow_ticket=True)
            verified=engine.access.verify(secret["token"])
            self.assertEqual(verified["project_id"], "support")
            self.assertTrue(verified["allow_ticket"])
            self.assertEqual(engine.projects["support"]["id"], "support")
            self.assertFalse(engine.answer("support", "مسئله ناشناخته")["model_used"])


if __name__ == "__main__":
    unittest.main()
