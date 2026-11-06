"""Download Moodle course files without exposing authentication tokens."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from typing_extensions import TypedDict

from .moodle import APIFunction, MOODLE_TOKEN, MOODLE_URL, get_moodle_api_data


class CourseFile(TypedDict):
    moduleid: int
    module: str
    section: str
    filename: str
    filepath: str
    filesize: int
    mimetype: str
    timemodified: int


class DownloadResult(TypedDict):
    path: str
    filename: str
    bytes_written: int
    sha256: str
    mimetype: str


def _files(courseid: int):
    if courseid <= 0:
        raise ValueError("courseid must be positive")
    sections = get_moodle_api_data(APIFunction.core_course_get_contents,
                                  params={"courseid": courseid})
    for section in sections:
        for module in section.get("modules", []):
            for item in module.get("contents") or []:
                if item.get("type") == "file" and item.get("fileurl"):
                    yield ({"moduleid": module["id"], "module": module["name"],
                            "section": section["name"], "filename": item["filename"],
                            "filepath": item.get("filepath", "/"),
                            "filesize": item.get("filesize", 0),
                            "timemodified": item.get("timemodified", 0),
                            "mimetype": item.get("mimetype", "")}, item["fileurl"])


def list_course_files(courseid: int) -> list[CourseFile]:
    return [metadata for metadata, _ in _files(courseid)]


def _authenticated_url(fileurl: str) -> str:
    base, target = urlsplit(MOODLE_URL), urlsplit(fileurl)
    prefix = base.path.split("/webservice/", 1)[0]
    endpoint = prefix + "/webservice/pluginfile.php"
    if (target.scheme, target.netloc) != (base.scheme, base.netloc) or not (
        target.path == endpoint or target.path.startswith(endpoint + "/")
    ):
        raise ValueError("Only this Moodle site's webservice/pluginfile.php files are supported")
    query = [(k, v) for k, v in parse_qsl(target.query, keep_blank_values=True)
             if k.lower() not in {"token", "wstoken"}]
    query.append(("token", MOODLE_TOKEN))
    return urlunsplit((target.scheme, target.netloc, target.path, urlencode(query), ""))


def _safe_filename(filename: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename).rstrip(" .")
    if not name or name in {".", ".."}:
        raise ValueError("Invalid file name")
    if name.split(".", 1)[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        name = "_" + name
    return name


def download_course_file(courseid: int, moduleid: int, filename: str | None = None,
                         output_dir: str | None = None,
                         filepath: str | None = None) -> DownloadResult:
    """Resolve a file from the course API, authenticate, and save it atomically."""
    matches = [(meta, url) for meta, url in _files(courseid)
               if meta["moduleid"] == moduleid
               and (filename is None or meta["filename"] == filename)
               and (filepath is None or meta["filepath"] == filepath)]
    if len(matches) != 1:
        raise ValueError("File not found or ambiguous; use list_course_files and specify filename/filepath")
    metadata, fileurl = matches[0]
    directory = Path(output_dir or f"output/downloads/{courseid}").expanduser().resolve()
    return _download_file(metadata, fileurl, directory / _safe_filename(metadata["filename"]))


def _download_file(metadata: CourseFile, fileurl: str, destination: Path) -> DownloadResult:
    url = _authenticated_url(fileurl)
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"File already exists: {destination}")
    # Never forward a Moodle token through redirects to login pages or other sites.
    temporary = None
    try:
        with requests.get(url, stream=True, timeout=(15, 120), allow_redirects=False) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Moodle download returned HTTP {response.status_code}")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type == "text/html" and destination.suffix.lower() not in {".html", ".htm"}:
                raise RuntimeError("Moodle returned an HTML page instead of the requested file")
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".moodle-", delete=False) as handle:
                temporary = Path(handle.name)
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > 250 * 1024 * 1024:
                        raise RuntimeError("File exceeds the 250 MiB download limit")
                    handle.write(chunk)
                    digest.update(chunk)
            if content_type in {"application/json", "text/json"}:
                try:
                    payload = json.loads(temporary.read_bytes())
                except (ValueError, UnicodeError):
                    payload = None
                if isinstance(payload, dict) and ("errorcode" in payload or "exception" in payload):
                    raise RuntimeError("Moodle rejected the file download; check file access and service download permission")
            if not size:
                raise RuntimeError("Moodle returned an empty file")
            if metadata["filesize"] and size != metadata["filesize"]:
                raise RuntimeError("Downloaded size does not match Moodle file metadata")
            # Atomic creation without replacing an existing file, even in a race.
            os.link(temporary, destination)
            return {"path": str(destination), "filename": metadata["filename"],
                    "bytes_written": size, "sha256": digest.hexdigest(),
                    "mimetype": content_type}
    except requests.RequestException:
        # Request exceptions may contain token-bearing URLs.
        raise RuntimeError("Moodle file download failed due to a network error") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class BulkFileResult(TypedDict):
    moduleid: int
    filename: str
    path: str
    status: str
    error: str


class CourseDownloadResult(TypedDict):
    courseid: int
    output_dir: str
    total: int
    downloaded: int
    skipped: int
    failed: int
    bytes_written: int
    files: list[BulkFileResult]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_manifest(path: Path, data: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".manifest-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def download_course_files(courseid: int, output_dir: str | None = None) -> CourseDownloadResult:
    """Download all API-listed course files, with a resumable local manifest."""
    files = list(_files(courseid))  # Fetch course contents once for the entire batch.
    root = Path(output_dir or f"output/downloads/{courseid}/course").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "moodle-downloads.json"
    manifest = {"courseid": courseid, "files": {}}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("courseid") != courseid or not isinstance(manifest.get("files"), dict):
            raise ValueError("Destination manifest belongs to another course or is invalid")
    result = {"courseid": courseid, "output_dir": str(root), "total": len(files),
              "downloaded": 0, "skipped": 0, "failed": 0, "bytes_written": 0, "files": []}
    for metadata, url in files:
        entry = {"moduleid": metadata["moduleid"], "filename": metadata["filename"],
                 "path": "", "status": "failed", "error": ""}
        try:
            # The key and source fingerprint contain no authentication material.
            key = hashlib.sha256(json.dumps([metadata["moduleid"], metadata["filepath"],
                                            metadata["filename"]]).encode()).hexdigest()
            parsed = urlsplit(url)
            source = [parsed.scheme, parsed.netloc, parsed.path,
                      [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in {"token", "wstoken"}],
                      metadata["filesize"], metadata.get("timemodified", 0)]
            fingerprint = hashlib.sha256(json.dumps(source).encode()).hexdigest()
            previous = manifest["files"].get(key, {})
            old_path = (root / previous.get("path", "")).resolve()
            if (previous.get("source") == fingerprint and old_path.is_relative_to(root)
                    and old_path.is_file() and _hash_file(old_path) == previous.get("sha256")):
                entry.update(path=str(old_path), status="skipped")
                result["skipped"] += 1
            else:
                # Key suffix separates duplicate names and sanitized folder paths.
                directory = root / str(metadata["moduleid"]) / key[:12]
                destination = directory / _safe_filename(metadata["filename"])
                if destination.exists():
                    # Preserve previous versions and locally edited files.
                    destination = destination.with_name(
                        destination.stem + "__" + uuid.uuid4().hex[:8] + destination.suffix)
                downloaded = _download_file(metadata, url, destination)
                manifest["files"][key] = {"path": str(destination.relative_to(root)),
                                          "source": fingerprint, "sha256": downloaded["sha256"]}
                _save_manifest(manifest_path, manifest)
                entry.update(path=str(destination), status="downloaded")
                result["downloaded"] += 1
                result["bytes_written"] += downloaded["bytes_written"]
        except (OSError, ValueError, RuntimeError) as exc:
            entry["error"] = str(exc)
            result["failed"] += 1
        result["files"].append(entry)
    return result
