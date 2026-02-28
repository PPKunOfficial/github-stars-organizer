#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(".codex-output")
RAW_FILE = ROOT / "starred_raw.ndjson"
CACHE_FILE = ROOT / "readme_cache.json"
META_FILE = ROOT / "fetch_meta.json"
ERROR_LOG_FILE = ROOT / "fetch_errors.log"
API = "https://api.github.com"


def token() -> str:
    t = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if not t:
        raise RuntimeError("缺少 GITHUB_TOKEN/GH_TOKEN")
    return t


def get_json(path: str, tk: str, retries: int = 4):
    url = f"{API}{path}"
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {tk}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-stars-organizer",
        },
    )
    for i in range(1, retries + 1):
        try:
            with urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (403, 429, 500, 502, 503) and i < retries:
                time.sleep(i * 2)
                continue
            raise RuntimeError(f"GET {path} failed {e.code}: {body}") from e
        except URLError as e:
            if i < retries:
                time.sleep(i * 2)
                continue
            raise RuntimeError(f"GET {path} failed: {e}") from e
    raise RuntimeError(f"GET {path} failed after retries")


def fetch_all_starred(tk: str) -> List[dict]:
    page = 1
    out: List[dict] = []
    while True:
        data = get_json(f"/user/starred?per_page=100&page={page}", tk)
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return out


def decode_readme(content_b64: str) -> str:
    if not content_b64:
        return ""
    try:
        raw = base64.b64decode(content_b64, validate=False).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    raw = " ".join(raw.split())
    return raw[:12000]


def fetch_readme(full_name: str, tk: str) -> tuple[str, str | None]:
    owner, repo = full_name.split("/", 1)
    try:
        data = get_json(f"/repos/{owner}/{repo}/readme", tk)
    except RuntimeError as e:
        msg = str(e)
        if "failed 404" in msg:
            return "", None
        return "", msg
    return decode_readme(data.get("content", "")), None


def write_error_log(errors: List[Dict[str, str]]) -> None:
    if not errors:
        ERROR_LOG_FILE.write_text("", encoding="utf-8")
        return
    lines = [json.dumps(item, ensure_ascii=False) for item in errors]
    ERROR_LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    tk = token()

    stars = fetch_all_starred(tk)
    RAW_FILE.write_text(json.dumps(stars, ensure_ascii=False), encoding="utf-8")

    cache: Dict[str, str] = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    missing = [r.get("full_name", "") for r in stars if r.get("full_name") and r.get("full_name") not in cache]
    total = len(missing)
    readme_errors: List[Dict[str, str]] = []
    for i, name in enumerate(missing, start=1):
        readme_text, err = fetch_readme(name, tk)
        cache[name] = readme_text.lower()
        if err:
            readme_errors.append({"repo": name, "error": err})
            print(f"[readme][error] {name}: {err}")
        if i % 50 == 0 or i == total:
            print(f"[readme] {i}/{total}")

    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    write_error_log(readme_errors)

    meta = {
        "star_count": len(stars),
        "readme_cache_count": len(cache),
        "new_readmes_fetched": total,
        "readme_fetch_error_count": len(readme_errors),
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
