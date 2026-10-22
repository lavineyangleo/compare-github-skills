"""Resolve public GitHub URLs to immutable commits and download archives."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class FetchError(Exception):
    """An actionable download or source-selection failure."""


class GitHub:
    def __init__(self, no_proxy: bool = False, timeout: int = 30):
        handlers = [urllib.request.ProxyHandler({})] if no_proxy else []
        self.opener = urllib.request.build_opener(*handlers)
        self.timeout = timeout

    def api(self, route: str, missing_ok: bool = False):
        headers = {"User-Agent": "compare-github-skills-v2", "Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request("https://api.github.com/" + route, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise FetchError("GitHub API response exceeds the 4 MiB limit.")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            if missing_ok and exc.code == 422:
                try:
                    detail = json.loads(exc.read(8192))
                except (ValueError, OSError):
                    detail = {}
                if str(detail.get("message", "")).startswith("No commit found for SHA:"):
                    return None
            hint = " Check API rate limits or repository access." if exc.code in (403, 429) else ""
            raise FetchError(f"GitHub API HTTP {exc.code}.{hint}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise FetchError("GitHub API connection failed; check network and proxy settings.") from None

    def resolve(self, url: str, ref_override: str | None = None) -> dict:
        parsed = urllib.parse.urlsplit(url.strip())
        if parsed.scheme != "https" or parsed.netloc.lower() not in ("github.com", "www.github.com"):
            raise FetchError("Use an HTTPS github.com repository, tree, or blob URL.")
        parts = [urllib.parse.unquote(p) for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise FetchError("The GitHub URL must include owner and repository.")
        owner, repo = parts[:2]
        repo = repo.removesuffix(".git")
        if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", p) or p in (".", "..") for p in (owner, repo)):
            raise FetchError("Invalid GitHub owner or repository name.")
        if any(p in (".", "..") or "\\" in p or "/" in p for p in parts[2:]):
            raise FetchError("Invalid URL path segments; use normal GitHub links.")
        mode = "repository"
        tail = []
        if len(parts) > 2:
            mode = parts[2]
            if mode not in ("tree", "blob") or len(parts) < 4:
                raise FetchError("Only repository, tree, and blob URLs are supported.")
            tail = parts[3:]
        prefix = f"repos/{owner}/{repo}"
        metadata = self.api(prefix)
        selection = ""
        if not tail:
            ref = ref_override or metadata["default_branch"]
            commit = self.api(prefix + "/commits/" + urllib.parse.quote(ref, safe=""))
        elif ref_override:
            tail_text = "/".join(tail)
            if tail_text != ref_override and not tail_text.startswith(ref_override + "/"):
                raise FetchError("For tree/blob links, --ref must match the link's ref prefix; use a root URL to override versions.")
            ref = ref_override
            selection = tail_text[len(ref):].lstrip("/")
            commit = self.api(prefix + "/commits/" + urllib.parse.quote(ref, safe=""))
        else:
            if len(tail) > 12:
                raise FetchError("Deep URL: specify --ref INDEX=REF to identify its branch explicitly.")
            commit = None
            for count in range(len(tail), 0, -1):
                candidate = "/".join(tail[:count])
                found = self.api(prefix + "/commits/" + urllib.parse.quote(candidate, safe=""), missing_ok=True)
                if found:
                    ref, commit = candidate, found
                    selection = "/".join(tail[count:])
                    break
            if not commit:
                raise FetchError("No branch, tag, or commit in this tree/blob URL could be resolved.")
        sha = commit.get("sha", "")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
            raise FetchError("GitHub did not return a valid full commit SHA.")
        if mode == "blob" and not selection:
            raise FetchError("A blob URL must select a file beneath a valid ref.")
        return {
            "input_url": url,
            "repository": metadata["full_name"],
            "repository_url": metadata["html_url"],
            "requested_ref": ref,
            "commit_sha": sha,
            "selection": selection,
            "selection_kind": mode,
            "archive_url": f"https://codeload.github.com/{metadata['full_name']}/zip/{sha}",
        }

    def download(self, url: str, destination: Path, max_bytes: int) -> int:
        request = urllib.request.Request(url, headers={"User-Agent": "compare-github-skills-v2"})
        total = 0
        try:
            with self.opener.open(request, timeout=self.timeout) as response, destination.open("xb") as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise FetchError("Archive exceeds the configured download size limit.")
                    output.write(chunk)
        except urllib.error.HTTPError as exc:
            raise FetchError(f"Archive download HTTP {exc.code}; this downloader supports public repositories.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise FetchError("Archive connection or write failed; inspect network and output directory.") from None
        return total
