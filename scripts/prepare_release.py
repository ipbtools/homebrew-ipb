#!/usr/bin/env python3
"""Validate a published ipb candidate release and prepare its Homebrew formula."""

import argparse
import hashlib
import json
import os
import re
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

REPOSITORY = "ipbtools/ipb"
ARCHIVE_SUFFIX = "-macos27-arm64.tar.gz"
VERSION_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseError(ValueError):
    pass


def version_from_tag(tag):
    if not VERSION_RE.fullmatch(tag):
        raise ReleaseError("tag must have the form vX.Y.Z")
    return tag[1:]


def request_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ipb-homebrew-release"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"GitHub API request failed for {url}: {exc}") from exc


def download_release(tag, destination):
    version = version_from_tag(tag)
    release = request_json(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}")
    if release.get("tag_name") != tag:
        raise ReleaseError(f"GitHub returned tag {release.get('tag_name')!r}, expected {tag!r}")
    if release.get("draft") is not False:
        raise ReleaseError("release must be published and non-draft")
    if release.get("prerelease") is not False:
        raise ReleaseError("release must be published as a standard (non-prerelease) release")

    archive_name = f"ipb-{version}{ARCHIVE_SUFFIX}"
    names = {
        "archive": archive_name,
        "checksum": archive_name + ".sha256",
        "formula": "ipb.rb",
        "build_info": "BUILD_INFO.json",
    }
    assets = {asset.get("name"): asset for asset in release.get("assets", [])}
    absent = [name for name in names.values() if name not in assets]
    if absent:
        raise ReleaseError(f"release is missing required assets: {', '.join(absent)}")

    destination.mkdir(parents=True, exist_ok=True)
    downloaded = {}
    for role, name in names.items():
        asset = assets[name]
        if asset.get("state") != "uploaded" or not asset.get("browser_download_url"):
            raise ReleaseError(f"asset {name} is not fully uploaded")
        path = destination / name
        request = urllib.request.Request(
            asset["browser_download_url"], headers={"User-Agent": "ipb-homebrew-release"}
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output)
        except (urllib.error.URLError, OSError) as exc:
            raise ReleaseError(f"could not download asset {name}: {exc}") from exc
        downloaded[role] = path
    return release, downloaded


def formula_value(formula, name):
    matches = re.findall(rf'^\s*{name}\s+"([^"]+)"\s*$', formula, re.MULTILINE)
    if len(matches) != 1:
        raise ReleaseError(f"formula must contain exactly one {name} declaration")
    return matches[0]


def verify_payload_hashes(archive_path, top_level, files):
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers() if member.isfile()}
            for relative_path, expected in files.items():
                rel = PurePosixPath(relative_path)
                if rel.is_absolute() or ".." in rel.parts or not SHA_RE.fullmatch(str(expected)):
                    raise ReleaseError(f"unsafe or invalid BUILD_INFO.json file entry: {relative_path!r}")
                member = members.get(f"{top_level}/{rel.as_posix()}")
                if member is None:
                    raise ReleaseError(f"archive is missing file listed in BUILD_INFO.json: {relative_path}")
                stream = archive.extractfile(member)
                if stream is None or hashlib.sha256(stream.read()).hexdigest() != expected:
                    raise ReleaseError(f"archive payload hash mismatch for {relative_path}")
    except (tarfile.TarError, OSError) as exc:
        raise ReleaseError(f"archive is not a readable gzip tarball: {exc}") from exc


def validate_and_prepare(tag, release, assets, output_dir):
    version = version_from_tag(tag)
    archive_name = f"ipb-{version}{ARCHIVE_SUFFIX}"
    if release.get("tag_name") != tag:
        raise ReleaseError("release tag does not exactly match the requested tag")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ReleaseError("release must be published as a standard (non-prerelease) release")

    expected_names = {
        "archive": archive_name,
        "checksum": archive_name + ".sha256",
        "formula": "ipb.rb",
        "build_info": "BUILD_INFO.json",
    }
    for role, expected in expected_names.items():
        if role not in assets or assets[role].name != expected or not assets[role].is_file():
            raise ReleaseError(f"missing or misnamed {role} asset; expected {expected}")

    archive_sha = hashlib.sha256(assets["archive"].read_bytes()).hexdigest()
    checksum = assets["checksum"].read_text(encoding="utf-8")
    if checksum != f"{archive_sha}  {archive_name}\n":
        raise ReleaseError("archive .sha256 must be the exact SHA256 and filename line")

    try:
        build_info = json.loads(assets["build_info"].read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"BUILD_INFO.json is invalid: {exc}") from exc
    if not isinstance(build_info, dict):
        raise ReleaseError("BUILD_INFO.json must be a JSON object")
    if build_info.get("schemaVersion") != 1:
        raise ReleaseError("BUILD_INFO.json schemaVersion must be 1")
    if build_info.get("kind") != "release-candidate":
        raise ReleaseError("BUILD_INFO.json kind must be release-candidate")
    if build_info.get("version") != version or build_info.get("releaseTag") != tag:
        raise ReleaseError("BUILD_INFO.json version/releaseTag does not match requested tag")
    os_info = build_info.get("os")
    if (
        build_info.get("architecture") != "arm64"
        or not isinstance(os_info, dict)
        or os_info.get("ProductName") != "macOS"
        or not re.fullmatch(r"27\.\d+(?:\.\d+)?", str(os_info.get("ProductVersion", "")))
    ):
        raise ReleaseError("BUILD_INFO.json must describe a macOS 27 arm64 build")
    if not re.fullmatch(r"[0-9a-f]{40}", str(build_info.get("commit", ""))):
        raise ReleaseError("BUILD_INFO.json commit must be a full 40-character git SHA")
    if build_info.get("pullRequestHead") is not None:
        raise ReleaseError("BUILD_INFO.json must identify a mainline build (pullRequestHead: null)")
    if not isinstance(build_info.get("files"), dict) or not build_info["files"]:
        raise ReleaseError("BUILD_INFO.json files must be a non-empty path-to-SHA256 object")
    if not re.search(r"Xcode 27", str(build_info.get("xcode", ""))):
        raise ReleaseError("BUILD_INFO.json must identify Xcode 27")
    tagged_commit = request_json(
        f"https://api.github.com/repos/{REPOSITORY}/commits/{tag}"
    ).get("sha")
    if tagged_commit != build_info["commit"]:
        raise ReleaseError("BUILD_INFO.json commit does not match the exact release tag")
    comparison = request_json(
        f"https://api.github.com/repos/{REPOSITORY}/compare/{build_info['commit']}...main"
    )
    if comparison.get("status") not in {"ahead", "identical"}:
        raise ReleaseError("release commit is not an ancestor of source main")
    verify_payload_hashes(assets["archive"], f"ipb-{version}-macos27-arm64", build_info["files"])

    formula = assets["formula"].read_text(encoding="utf-8")
    expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{archive_name}"
    if formula_value(formula, "url") != expected_url:
        raise ReleaseError("formula URL does not point to this exact release archive")
    if formula_value(formula, "version") != version:
        raise ReleaseError("formula version does not match the requested tag")
    if formula_value(formula, "sha256") != archive_sha:
        raise ReleaseError("formula SHA256 does not match the verified archive")
    if not re.search(r"^class Ipb < Formula\s*$", formula, re.MULTILINE):
        raise ReleaseError("release formula must define class Ipb < Formula")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ipb.rb").write_text(formula, encoding="utf-8")
    return archive_sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="published release tag, for example v1.2.3")
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        release, assets = download_release(args.tag, args.download_dir)
        digest = validate_and_prepare(args.tag, release, assets, args.output_dir)
    except ReleaseError as exc:
        parser.error(str(exc))
    print(f"Validated {args.tag}; archive SHA256 {digest}")
    print(f"Prepared {args.output_dir / 'ipb.rb'}")


if __name__ == "__main__":
    main()
