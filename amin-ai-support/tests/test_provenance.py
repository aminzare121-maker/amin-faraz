import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from amin_support import SupportEngine, main, scrub
from github_evidence import repository_slug, relevant, update_provenance


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        config = root / "projects.json"
        config.write_text(json.dumps({"projects": [
            {"id": "faraz", "name": "فراز", "git_url": "https://github.com/owner/shared.git",
             "provenance_terms": ["faraz", "فراز"], "source_prefixes": [], "public_paths": []},
            {"id": "artin", "name": "آرتین", "git_url": "https://github.com/owner/shared.git",
             "provenance_terms": ["artin", "آرتین"], "source_prefixes": [], "public_paths": []}
        ]}, ensure_ascii=False), encoding="utf-8")
        self.engine = SupportEngine(config, root / "data.sqlite3")
        self.data = [
            {"number": 12, "title": "Faraz data crash", "state": "open", 
             "body": "password: abc123\nUNVERIFIED symptom: candles missing",
             "html_url": "https://github.com/owner/shared/issues/12",
             "updated_at": "2026-11-21T20:00:00Z"},
            {"number": 13, "title": "Artin video extraction", "state": "closed",
             "body": "This is artin evidence only",
             "html_url": "https://github.com/owner/shared/pull/13",
             "updated_at": "2026-11-20T20:00:00Z", "pull_request": {}},
            {"number": 14, "title": "Unrelated UI update", "body": "Faraz in issue body only",
             "state": "open"}
        ]

    def test_slug_is_strict(self):
        self.assertEqual(repository_slug("https://github.com/owner/repo.git"), "owner/repo")
        for url in ["http://github.com/a/b.git", "https://elsewhere.com/a/b.git",
                    "https://github.com/a/b.git?token=secret",
                    "https://github.com/a/b.git/extra"]:
            with self.assertRaises(ValueError):
                repository_slug(url)

    def test_title_only_scope_not_body(self):
        self.assertFalse(relevant(self.data[2], ["faraz"]))
        self.assertTrue(relevant(self.data[0], ["faraz"]))
        self.assertFalse(relevant(self.data[1], ["faraz"]))
        self.assertTrue(relevant(self.data[1], ["artin"]))

    def test_filtered_developer_only_and_redaction(self):
        fetch = lambda url: self.data
        a = update_provenance(self.engine.projects["faraz"], self.engine.knowledge, scrub, fetch)
        b = update_provenance(self.engine.projects["artin"], self.engine.knowledge, scrub, fetch)
        self.assertEqual(a["issues_and_prs"], 1)
        self.assertEqual(b["issues_and_prs"], 1)
        self.assertEqual(self.engine.knowledge.search("faraz", "candles missing"), [])
        self.assertEqual(self.engine.knowledge.search("artin", "candles missing", "developer"), [])
        d = self.engine.knowledge.search("faraz", "candles missing", "developer")
        self.assertTrue(d)
        self.assertEqual(d[0]["path"], "__github__/issues/12")
        self.assertNotIn("abc123", json.dumps(d))
        self.assertIn("UNVERIFIED", d[0]["excerpt"])
        a = self.engine.knowledge.search("artin", "extraction", "developer")
        self.assertTrue(a)
        self.assertEqual(a[0]["path"], "__github__/pulls/13")

    def test_refresh_removes_old_issues_without_touching_other_projects(self):
        fetch = lambda url: self.data
        update_provenance(self.engine.projects["faraz"], self.engine.knowledge, scrub, fetch)
        update_provenance(self.engine.projects["artin"], self.engine.knowledge, scrub, fetch)
        update_provenance(self.engine.projects["faraz"], self.engine.knowledge,
                          scrub, lambda url: [])
        self.assertEqual(self.engine.knowledge.search("faraz", "candles missing", "developer"), [])
        self.assertTrue(self.engine.knowledge.search("artin", "extraction", "developer"))


    def test_developer_cli_can_read_internal_issues_not_public_api(self):
        update_provenance(self.engine.projects["faraz"], self.engine.knowledge,
                          scrub, lambda url: self.data)
        args = ["--config", str(self.engine.projects_config_path) if hasattr(
            self.engine, "projects_config_path") else str(Path(self.temp.name) / "projects.json"),
                "--db", str(self.engine.knowledge.db_path), "ask",
                "--project", "faraz", "--message", "candles",
                "--role", "developer"]
        output = io.StringIO()
        with redirect_stdout(output):
            main(args)
        result = json.loads(output.getvalue())
        self.assertTrue(result["sources"])
        self.assertEqual(result["role"], "developer")
        args[-1] = "customer"
        output = io.StringIO()
        with redirect_stdout(output):
            main(args)
        result = json.loads(output.getvalue())
        self.assertTrue(result["needs_human"])
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
