import os
from pathlib import Path

import pytest

from chat_agent.config import MAX_READ_BYTES
from chat_agent.knowledge import (
    AccessDenied,
    Entry,
    KnowledgeBase,
    KnowledgeError,
    NotFound,
    NotText,
)


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A folder next to the knowledge root holding a secret the assistant must never see."""
    folder = tmp_path / "outside"
    folder.mkdir()
    (folder / "secret.txt").write_text("TOP SECRET")
    return folder


@pytest.fixture
def root(tmp_path: Path, outside: Path) -> Path:
    folder = tmp_path / "knowledge"
    (folder / "notes").mkdir(parents=True)
    (folder / "notes" / "todo.md").write_text("# Todo\n- buy milk\n")
    (folder / "readme.txt").write_text("hello")
    (folder / "link_to_secret.txt").symlink_to(outside / "secret.txt")
    (folder / "link_to_outside").symlink_to(outside, target_is_directory=True)
    (folder / "link_to_notes").symlink_to(folder / "notes", target_is_directory=True)
    return folder


@pytest.fixture
def kb(root: Path) -> KnowledgeBase:
    return KnowledgeBase(root)


@pytest.mark.parametrize(
    "path",
    [
        "../outside/secret.txt",
        "notes/../../outside/secret.txt",
        "..",
        "/etc/passwd",
        "~/secret.txt",
        "~",
        "link_to_secret.txt",
        "link_to_outside",
        "link_to_outside/secret.txt",
    ],
)
def test_ac20_paths_outside_root_are_denied(kb: KnowledgeBase, path: str) -> None:
    with pytest.raises(AccessDenied):
        kb._resolve(path)


def test_ac20_absolute_path_to_inside_file_is_still_denied(kb: KnowledgeBase, root: Path) -> None:
    with pytest.raises(AccessDenied):
        kb._resolve(str(root / "readme.txt"))


def test_ac20_error_message_reveals_no_outside_path(kb: KnowledgeBase, outside: Path) -> None:
    with pytest.raises(AccessDenied) as exc:
        kb._resolve("link_to_secret.txt")
    message = str(exc.value)
    assert str(outside) not in message
    assert "TOP SECRET" not in message


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", "."),
        (".", "."),
        ("readme.txt", "readme.txt"),
        ("notes/todo.md", "notes/todo.md"),
        ("link_to_notes/todo.md", "notes/todo.md"),
    ],
)
def test_paths_inside_root_resolve(kb: KnowledgeBase, root: Path, path: str, expected: str) -> None:
    assert kb._resolve(path) == (root / expected).resolve()


def test_ac15_lists_top_level_names_only(kb: KnowledgeBase) -> None:
    assert kb.list_dir() == [
        Entry("link_to_notes", is_dir=True),
        Entry("notes", is_dir=True),
        Entry("readme.txt", is_dir=False),
    ]


def test_ac15_lists_nested_names_only(kb: KnowledgeBase) -> None:
    assert kb.list_dir("notes") == [Entry("notes/todo.md", is_dir=False)]


def test_ac15_entry_carries_no_metadata() -> None:
    assert set(Entry.__dataclass_fields__) == {"path", "is_dir"}


def test_ac20_listing_hides_escaping_symlinks(kb: KnowledgeBase) -> None:
    names = [entry.path for entry in kb.list_dir()]
    assert "link_to_secret.txt" not in names
    assert "link_to_outside" not in names


def test_ac20_listing_outside_root_is_denied(kb: KnowledgeBase) -> None:
    with pytest.raises(AccessDenied):
        kb.list_dir("..")


def test_ac19_list_missing_dir_not_found(kb: KnowledgeBase) -> None:
    with pytest.raises(NotFound):
        kb.list_dir("no/such/folder")


def test_ac19_list_file_is_not_found_as_folder(kb: KnowledgeBase) -> None:
    with pytest.raises(NotFound):
        kb.list_dir("readme.txt")


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes/deep/plan.md", "# Plan\n\n* step one — ünïcödé ✓\n"),
        ("code/app.py", "print('hi')\n"),
        ("data/table.csv", "a,b\n1,2\n"),
        ("data/config.json", '{"key": [1, 2]}'),
    ],
)
def test_ac16_reads_text_files_in_subfolders(
    kb: KnowledgeBase, root: Path, name: str, content: str
) -> None:
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    result = kb.read_text(name)
    assert result.path == name
    assert result.text == content
    assert result.truncated is False


def test_ac17_large_file_truncated_at_100kb(kb: KnowledgeBase, root: Path) -> None:
    (root / "big.txt").write_text("x" * 150_000)
    result = kb.read_text("big.txt")
    assert result.truncated is True
    assert result.text == "x" * MAX_READ_BYTES


def test_ac17_file_of_exactly_limit_is_not_truncated(kb: KnowledgeBase, root: Path) -> None:
    (root / "exact.txt").write_text("y" * MAX_READ_BYTES)
    result = kb.read_text("exact.txt")
    assert result.truncated is False
    assert len(result.text) == MAX_READ_BYTES


def test_ac17_truncation_does_not_split_utf8_char(kb: KnowledgeBase, root: Path) -> None:
    # 'é' is 2 bytes; one leading ASCII byte puts a character boundary across the limit.
    (root / "accents.txt").write_text("a" + "é" * MAX_READ_BYTES, encoding="utf-8")
    result = kb.read_text("accents.txt")
    assert result.truncated is True
    assert result.text == "a" + "é" * ((MAX_READ_BYTES - 1) // 2)


@pytest.mark.parametrize(
    "data",
    [
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",  # image header
        b"%PDF-1.7\n\xe2\xe3\xcf\xd3\n",  # PDF with binary marker
        b"plain text\x00with a NUL byte",
        b"\xff\xfe\xfa invalid utf-8",
    ],
)
def test_ac18_binary_file_not_text(kb: KnowledgeBase, root: Path, data: bytes) -> None:
    (root / "blob.bin").write_bytes(data)
    with pytest.raises(NotText):
        kb.read_text("blob.bin")


def test_ac19_read_missing_not_found(kb: KnowledgeBase) -> None:
    with pytest.raises(NotFound):
        kb.read_text("notes/missing.md")


def test_ac19_read_folder_is_not_found_as_file(kb: KnowledgeBase) -> None:
    with pytest.raises(NotFound):
        kb.read_text("notes")


def test_ac20_read_through_escaping_symlink_denied(kb: KnowledgeBase) -> None:
    with pytest.raises(AccessDenied):
        kb.read_text("link_to_secret.txt")


def test_ac21_knowledge_base_has_no_write_methods() -> None:
    public = {name for name in dir(KnowledgeBase) if not name.startswith("_")}
    assert public == {"list_dir", "read_text"}


@pytest.mark.parametrize(
    "path",
    ["notes/../readme.txt", "./notes/../notes/todo.md", "notes/..", "link_to_outside/../knowledge"],
)
def test_ac20_dotdot_components_denied(kb: KnowledgeBase, path: str) -> None:
    # Even ".." that would stay inside is refused, so probes can't map symlinks outside the root.
    with pytest.raises(AccessDenied):
        kb._resolve(path)


@pytest.mark.parametrize("path", ["a\x00b", "notes/\x00"])
def test_nul_byte_path_is_knowledge_error(kb: KnowledgeBase, path: str) -> None:
    with pytest.raises(KnowledgeError):
        kb.read_text(path)
    with pytest.raises(KnowledgeError):
        kb.list_dir(path)


needs_permissions = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")


@needs_permissions
def test_unreadable_file_is_knowledge_error(kb: KnowledgeBase, root: Path) -> None:
    secret = root / "locked.txt"
    secret.write_text("x")
    secret.chmod(0)
    try:
        with pytest.raises(KnowledgeError):
            kb.read_text("locked.txt")
    finally:
        secret.chmod(0o600)


@needs_permissions
def test_unreadable_folder_is_knowledge_error(kb: KnowledgeBase, root: Path) -> None:
    folder = root / "locked"
    folder.mkdir()
    folder.chmod(0)
    try:
        with pytest.raises(KnowledgeError):
            kb.list_dir("locked")
    finally:
        folder.chmod(0o700)


def test_symlink_loop_is_not_found_and_hidden(kb: KnowledgeBase, root: Path) -> None:
    (root / "loop").symlink_to(root / "loop")
    with pytest.raises(KnowledgeError):
        kb.read_text("loop")
    assert "loop" not in [entry.path for entry in kb.list_dir()]
