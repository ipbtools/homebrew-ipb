import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_release import ReleaseError, validate_and_prepare


TAG = "v1.2.3"
VERSION = "1.2.3"
ARCHIVE = f"ipb-{VERSION}-macos27-arm64.tar.gz"


def fixture(directory):
    payload = b"#!/bin/sh\necho ipb 1.2.3\n"
    payload_sha = hashlib.sha256(payload).hexdigest()
    archive_path = directory / ARCHIVE
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo(f"ipb-{VERSION}-macos27-arm64/bin/ipb")
        info.mode = 0o755
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = directory / f"{ARCHIVE}.sha256"
    checksum_path.write_text(f"{archive_sha}  {ARCHIVE}\n", encoding="utf-8")
    formula_path = directory / "ipb.rb"
    formula_path.write_text(
        f'class Ipb < Formula\n  url "https://github.com/ipbtools/ipb/releases/download/{TAG}/{ARCHIVE}"\n'
        f'  version "{VERSION}"\n  sha256 "{archive_sha}"\nend\n',
        encoding="utf-8",
    )
    info_path = directory / "BUILD_INFO.json"
    info_path.write_text(json.dumps({
        "schemaVersion": 1, "kind": "release-candidate", "version": VERSION, "releaseTag": TAG,
        "commit": "a" * 40, "pullRequestHead": None,
        "os": {
            "ProductName": "macOS", "ProductVersion": "27.0.1", "BuildVersion": "26A434"
        },
        "architecture": "arm64", "xcode": "Xcode 27.0",
        "coreDevice": "651.19", "files": {"bin/ipb": payload_sha},
        "verification": "native build, host regressions and extracted package startup; no physical device gate",
    }), encoding="utf-8")
    return {
        "archive": archive_path,
        "checksum": checksum_path,
        "formula": formula_path,
        "build_info": info_path,
        }, {"tag_name": TAG, "draft": False, "prerelease": False}


class PrepareReleaseTests(unittest.TestCase):
    def validate(self, mutation=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        assets, release = fixture(root)
        if mutation:
            mutation(assets, release)
        with patch("scripts.prepare_release.request_json", side_effect=[
            {"sha": "a" * 40}, {"status": "identical"}
        ]):
            return validate_and_prepare(TAG, release, assets, root / "prepared")

    def test_published_candidate_prepares_formula(self):
        digest = self.validate()
        self.assertEqual(len(digest), 64)

    def test_rejects_draft_release(self):
        with self.assertRaisesRegex(ReleaseError, "published as a standard"):
            self.validate(lambda assets, release: release.update(draft=True))

    def test_rejects_prerelease_release(self):
        with self.assertRaisesRegex(ReleaseError, "published as a standard"):
            self.validate(lambda assets, release: release.update(prerelease=True))

    def test_rejects_wrong_requested_tag(self):
        with self.assertRaisesRegex(ReleaseError, "does not exactly match"):
            self.validate(lambda assets, release: release.update(tag_name="v9.9.9"))

    def test_rejects_tampered_archive_hash(self):
        def tamper(assets, release):
            archive = assets["archive"]
            archive.write_bytes(archive.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ReleaseError, "archive .sha256"):
            self.validate(tamper)

    def test_rejects_formula_with_wrong_version(self):
        def alter(assets, release):
            formula = assets["formula"]
            formula.write_text(formula.read_text().replace('version "1.2.3"', 'version "9.9.9"'))
        with self.assertRaisesRegex(ReleaseError, "formula version"):
            self.validate(alter)


if __name__ == "__main__":
    unittest.main()
