import unittest
import json
import tempfile
from pathlib import Path

from provider_bindings import _runtime_auth_contains_raw_authority


class Wf048AuthorityScanTests(unittest.TestCase):
    def test_rejects_nested_oauth_and_api_material(self):
        self.assertTrue(_runtime_auth_contains_raw_authority({"providers": {"github": {"tokens": {"access_token": "x"}}}}))
        self.assertTrue(_runtime_auth_contains_raw_authority({"credentials": [{"api_key": "x"}]}))

    def test_allows_opaque_capability_metadata(self):
        self.assertFalse(_runtime_auth_contains_raw_authority({
            "providers": {"github": {"account": "octocat", "capability_ref": "wf_cap_123"}},
            "credential_pool": {"github": [{"source": "workframe-capability", "auth_type": "lease"}]},
        }))

    def test_scans_runtime_files_without_returning_secret_values(self):
        from provider_bindings import _scan_runtime_auth_files

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profiles/a").mkdir(parents=True)
            (root / "profiles/a/auth.json").write_text(json.dumps({"providers": {"github": {"access_token": "do-not-return"}}}), encoding="utf-8")
            (root / "profiles/b").mkdir(parents=True)
            (root / "profiles/b/auth.json").write_text("{", encoding="utf-8")
            findings = _scan_runtime_auth_files(root)
            self.assertEqual({item["kind"] for item in findings}, {"raw_authority", "malformed"})
            self.assertNotIn("do-not-return", repr(findings))


if __name__ == "__main__":
    unittest.main()
