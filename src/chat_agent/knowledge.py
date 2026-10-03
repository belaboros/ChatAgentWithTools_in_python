"""Read-only, sandboxed access to the knowledge folder (spec 001, AC-15..AC-21)."""

import codecs
from dataclasses import dataclass
from pathlib import Path

from chat_agent.config import MAX_READ_BYTES


class KnowledgeError(Exception):
    """Base class for errors reported back to the model as tool errors."""


class AccessDenied(KnowledgeError):
    pass


class NotFound(KnowledgeError):
    pass


class NotText(KnowledgeError):
    pass


@dataclass(frozen=True)
class Entry:
    """A listing entry: name only, no sizes or other metadata (AC-15)."""

    path: str  # POSIX path relative to the knowledge root
    is_dir: bool


@dataclass(frozen=True)
class FileContent:
    path: str
    text: str
    truncated: bool


class KnowledgeBase:
    def __init__(self, root: Path, max_read_bytes: int = MAX_READ_BYTES) -> None:
        self.root = root.resolve()
        self.max_read_bytes = max_read_bytes

    def _resolve(self, path: str) -> Path:
        """Map a model-supplied relative path to an absolute path inside the root.

        This is the single sandbox check (AC-20): the path is fully resolved, following
        symlinks and `..`, and must still lie inside the root.
        """
        denied = AccessDenied(f"Access denied: '{path}' is outside the knowledge folder.")
        if path.startswith("~") or Path(path).is_absolute():
            raise denied
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise denied
        return resolved

    def _relative(self, resolved: Path) -> str:
        return resolved.relative_to(self.root).as_posix()

    def list_dir(self, path: str = "") -> list[Entry]:
        folder = self._resolve(path)
        if not folder.is_dir():
            raise NotFound(f"Not found: '{path}' is not a folder in the knowledge folder.")
        entries: list[Entry] = []
        for child in folder.iterdir():
            # Hide symlinks whose target escapes the root, so no outside names leak (AC-20).
            if not child.resolve().is_relative_to(self.root):
                continue
            entries.append(Entry(self._relative(folder / child.name), is_dir=child.is_dir()))
        return sorted(entries, key=lambda entry: entry.path)

    def read_text(self, path: str) -> FileContent:
        """Read a UTF-8 text file; files over the limit are truncated (AC-16..AC-18)."""
        file = self._resolve(path)
        if not file.is_file():
            raise NotFound(f"Not found: '{path}' is not a file in the knowledge folder.")
        with file.open("rb") as handle:
            data = handle.read(self.max_read_bytes + 1)
        truncated = len(data) > self.max_read_bytes
        data = data[: self.max_read_bytes]
        not_text = NotText(f"'{path}' is not a readable text file.")
        if b"\x00" in data:
            raise not_text
        # An incremental decoder with final=False drops a multi-byte character cut by the limit.
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        try:
            text = decoder.decode(data, final=not truncated)
        except UnicodeDecodeError:
            raise not_text from None
        return FileContent(self._relative(file), text, truncated)
