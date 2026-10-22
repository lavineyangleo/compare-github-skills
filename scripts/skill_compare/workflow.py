"""Collect multiple repository downloads and a factual, durable evidence record."""

import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .archive import extract_archive
from .github import FetchError, GitHub


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(source: Path, selection: str, kind: str) -> list[dict]:
    scope = (source / selection).resolve()
    if not scope.is_relative_to(source.resolve()) or not scope.exists():
        raise FetchError("Selected path is absent at the resolved commit.")
    if kind == "blob" and not scope.is_file():
        raise FetchError("Blob URL did not select a file.")
    if kind == "tree" and not scope.is_dir():
        raise FetchError("Tree URL did not select a directory.")
    candidates = [scope] if scope.is_file() else sorted(scope.rglob("*"))
    entries = []
    for path in candidates:
        if not path.is_file() or path.name.lower() != "skill.md":
            continue
        relative = path.relative_to(source).as_posix()
        entries.append({"path": relative, "sha256": file_hash(path), "bytes": path.stat().st_size})
    return entries


def run_comparison_download(urls: list[str], output: Path, refs=None,
                            no_proxy=False, max_download_mb=100, max_extract_mb=400) -> tuple[Path, bool]:
    if len(urls) < 2:
        raise ValueError("Provide at least two GitHub URLs.")
    refs = refs or {}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output.resolve() / ("comparison-" + run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.json"
    manifest = {"schema_version": "2.0", "started_at_utc": utc_now(),
                "run_directory": str(run_dir), "status": "running", "projects": []}
    def save():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    client = GitHub(no_proxy=no_proxy)
    for index, url in enumerate(urls, start=1):
        label = f"{index:02d}"
        ref = refs.get(index)
        directory = run_dir / label
        directory.mkdir()
        record = {"index": index, "label": label, "input_url": url, "status": "running", "started_at_utc": utc_now()}
        manifest["projects"].append(record)
        save()
        try:
            record.update(client.resolve(url, ref))
            archive = directory / "archive.zip"
            source = directory / "source"
            record["downloaded_bytes"] = client.download(record["archive_url"], archive, max_download_mb * 1024 * 1024)
            record["archive_sha256"] = file_hash(archive)
            record["extracted_files"] = extract_archive(archive, source, max_extract_mb * 1024 * 1024)
            record["source_directory"] = str(source)
            record["skills"] = inventory(source, record["selection"], record["selection_kind"])
            record["status"] = "ready" if record["skills"] else "no_skill_found"
            if not record["skills"]:
                record["note"] = "Download completed, but no SKILL.md was found in the selected scope."
            groups = {}
            for skill in record["skills"]:
                groups.setdefault(skill["sha256"], []).append(skill["path"])
            record["identical_entrypoint_groups"] = [paths for paths in groups.values() if len(paths) > 1]
        except (FetchError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
        record["finished_at_utc"] = utc_now()
        save()
    complete = all(project["status"] == "ready" for project in manifest["projects"])
    manifest["status"] = "ready_for_analysis" if complete else "incomplete"
    manifest["ready_project_count"] = sum(project["status"] == "ready" for project in manifest["projects"])
    manifest["finished_at_utc"] = utc_now()
    save()
    return manifest_path, complete
