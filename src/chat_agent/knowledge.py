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


class Unreadable(KnowledgeError):
    """Exists, but the OS refused access (e.g. permissions). Messages carry no absolute paths."""


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

        This is the single sandbox check (AC-20): `~`, absolute paths, and any `..` component are
        refused outright (so probes can't map symlinks outside the root); then the path is fully
        resolved, following symlinks, and must still lie inside the root.
        """
        if "\x00" in path:
            raise NotFound("Not found: the path contains an invalid character.")
        denied = AccessDenied(f"Access denied: '{path}' is outside the knowledge folder.")
        if path.startswith("~") or Path(path).is_absolute() or ".." in Path(path).parts:
            raise denied
        try:
            resolved = (self.root / path).resolve()
        except OSError, RuntimeError:  # e.g. a symlink loop
            raise NotFound(f"Not found: '{path}' cannot be resolved.") from None
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
        try:
            children = list(folder.iterdir())
        except OSError:
            raise Unreadable(f"'{path}' cannot be listed (permission denied).") from None
        for child in children:
            try:
                target = child.resolve(strict=True)
            except OSError, RuntimeError:  # broken link or symlink loop: nothing to read
                continue
            # Hide symlinks whose target escapes the root, so no outside names leak (AC-20).
            if not target.is_relative_to(self.root):
                continue
            entries.append(Entry(self._relative(folder / child.name), is_dir=target.is_dir()))
        return sorted(entries, key=lambda entry: entry.path)

    def read_text(self, path: str) -> FileContent:
        """Read a UTF-8 text file; files over the limit are truncated (AC-16..AC-18)."""
        file = self._resolve(path)
        if not file.is_file():
            raise NotFound(f"Not found: '{path}' is not a file in the knowledge folder.")
        try:
            with file.open("rb") as handle:
                data = handle.read(self.max_read_bytes + 1)
        except OSError:
            raise Unreadable(f"'{path}' cannot be read (permission denied or I/O error).") from None
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
