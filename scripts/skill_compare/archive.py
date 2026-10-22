"""Validate archive members before extracting into a new directory."""

import os
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .github import FetchError


def extract_archive(archive: Path, destination: Path, max_bytes: int, max_files: int = 20000) -> int:
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if not members or len(members) > max_files:
            raise FetchError("Archive is empty or contains too many members.")
        if sum(item.file_size for item in members) > max_bytes:
            raise FetchError("Archive exceeds the configured extracted size limit.")
        root = None
        planned = []
        seen = set()
        for item in members:
            raw = item.filename
            parts = raw.rstrip("/").split("/")
            if not raw or raw.startswith("/") or "\\" in raw or any(p in ("", ".", "..") for p in parts):
                raise FetchError("Archive contains an unsafe path.")
            if any(":" in p or "\x00" in p for p in parts):
                raise FetchError("Archive contains an invalid path segment.")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise FetchError("Archive contains symbolic links; automatic extraction stopped.")
            root = root or parts[0]
            if parts[0] != root:
                raise FetchError("Expected a single GitHub archive root directory.")
            if len(parts) == 1:
                if not item.is_dir():
                    raise FetchError("Unexpected file at archive root.")
                continue
            relative = PurePosixPath(*parts[1:])
            if os.name == "nt":
                for part in relative.parts:
                    if re.search(r'[<>"|?*\x00-\x1f]', part) or part.endswith((" ", ".")):
                        raise FetchError("Archive contains a Windows-incompatible path.")
                    if re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0], re.I):
                        raise FetchError("Archive contains a Windows-reserved path.")
            target = (destination / Path(*relative.parts)).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise FetchError("Archive path would escape the extraction directory.")
            key = os.path.normcase(str(target))
            if key in seen:
                raise FetchError("Archive contains duplicate destination paths.")
            seen.add(key)
            planned.append((item, target))
        destination.mkdir(parents=True, exist_ok=False)
        for item, target in planned:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
        return sum(not item.is_dir() for item, _ in planned)
