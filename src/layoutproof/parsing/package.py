"""Safe loading and validation of OOXML (.pptx) zip packages.

The loader never extracts entries to disk and rejects unsafe member names
(zip-slip), duplicate entries, oversized/bomb-like payloads and parses XML
with entity resolution and network access disabled.
"""

from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path

from lxml import etree

from ..config import QualityConfig

MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024  # 2 GB hard ceiling
MAX_ENTRIES = 5000


class PackageError(Exception):
    """Raised when a package cannot be opened safely."""


def _is_unsafe_name(name: str) -> bool:
    if not name:
        return True
    # Reject absolute paths, drive letters and backslashes.
    if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        return True
    if "\\" in name:
        return True
    normalized = posixpath.normpath(name)
    parts = normalized.split("/")
    if any(part in ("..", "") for part in parts if part != ""):
        return True
    if ".." in parts:
        return True
    return False


class SafePackage:
    def __init__(self, path: str | Path, config: QualityConfig | None = None):
        self.path = Path(path)
        self.config = config or QualityConfig()
        self._anomalies: list[str] = []
        self._zip: zipfile.ZipFile | None = None
        self._name_set: set[str] = set()
        self._open()

    # ------------------------------------------------------------------
    def _open(self) -> None:
        if not self.path.exists():
            raise PackageError(f"File not found: {self.path}")
        if not self.path.is_file():
            raise PackageError(f"Not a file: {self.path}")
        if self.path.suffix.lower() != ".pptx":
            raise PackageError(f"Unsupported file type (expected .pptx): {self.path.name}")
        size_mb = self.path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise PackageError(
                f"File exceeds max size of {self.config.max_file_size_mb} MB "
                f"(actual {size_mb:.1f} MB)"
            )
        try:
            zf = zipfile.ZipFile(self.path, "r")
        except zipfile.BadZipFile as exc:
            raise PackageError(f"Not a valid zip/pptx package: {exc}") from exc

        self._zip = zf
        seen: set[str] = set()
        total = 0
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            self._anomalies.append(
                f"Package has {len(infos)} entries (limit {MAX_ENTRIES})"
            )
        for info in infos:
            name = info.filename
            if _is_unsafe_name(name):
                self._anomalies.append(f"Unsafe zip entry name: {name!r}")
                continue
            if name in seen:
                self._anomalies.append(f"Duplicate zip entry: {name}")
            seen.add(name)
            total += info.file_size
            if info.file_size > MAX_TOTAL_UNCOMPRESSED or total > MAX_TOTAL_UNCOMPRESSED:
                self._anomalies.append("Package exceeds uncompressed size limits")
                break
        self._name_set = seen
        if "[Content_Types].xml" not in seen:
            self._anomalies.append("Missing required [Content_Types].xml")
        if not any(n.startswith("ppt/presentation") for n in seen):
            self._anomalies.append("Missing ppt/presentation.xml main part")

    # ------------------------------------------------------------------
    @property
    def anomalies(self) -> list[str]:
        return list(self._anomalies)

    @property
    def names(self) -> set[str]:
        return set(self._name_set)

    def has_part(self, name: str) -> bool:
        return name in self._name_set

    def read(self, name: str) -> bytes:
        assert self._zip is not None
        try:
            return self._zip.read(name)
        except KeyError as exc:
            raise PackageError(f"Missing package part: {name}") from exc
        except (zipfile.BadZipFile, OSError) as exc:
            raise PackageError(f"Failed reading part {name}: {exc}") from exc

    def safe_parser(self) -> etree.XMLParser:
        return etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
            dtd_validation=False,
            load_dtd=False,
            remove_blank_text=False,
        )

    def parse_xml(self, name: str) -> etree._Element:
        parser = self.safe_parser()
        data = self.read(name)
        try:
            return etree.fromstring(data, parser=parser)
        except etree.XMLSyntaxError as exc:
            raise PackageError(f"Malformed XML in {name}: {exc}") from exc

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    def __enter__(self) -> "SafePackage":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
