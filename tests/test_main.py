import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from chat_agent import __main__ as main_module
from chat_agent import config


def test_ac23_missing_api_key_exits_with_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        config.require_api_key()
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err
    assert ".env" in err


def test_ac23_blank_api_key_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    with pytest.raises(SystemExit):
        config.require_api_key()


def test_ac23_present_api_key_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    config.require_api_key()


def test_ac22_missing_knowledge_dir_is_created(tmp_path: Path) -> None:
    folder = tmp_path / "knowledge"
    config.ensure_knowledge_dir(folder)
    assert folder.is_dir()
    assert list(folder.iterdir()) == []


def test_ac22_existing_knowledge_dir_is_left_alone(tmp_path: Path) -> None:
    folder = tmp_path / "knowledge"
    folder.mkdir()
    (folder / "note.md").write_text("keep me")
    config.ensure_knowledge_dir(folder)
    assert (folder / "note.md").read_text() == "keep me"


def test_ac2_server_binds_localhost_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(main_module, "KNOWLEDGE_DIR", tmp_path / "knowledge")
    monkeypatch.setattr(main_module.uvicorn, "run", lambda app, **kw: captured.update(kw))
    main_module.main()
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == config.PORT
    assert (tmp_path / "knowledge").is_dir()  # AC-22 wired into startup


def test_ac23_main_exits_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setattr(main_module.uvicorn, "run", lambda *a, **kw: pytest.fail("server started"))
    with pytest.raises(SystemExit):
        main_module.main()


def _lan_ip() -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # TEST-NET address: no packet is sent for UDP connect
            ip = probe.getsockname()[0]
        except OSError:
            return None
    return None if ip.startswith("127.") else ip


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_ac2_not_reachable_on_lan_ip() -> None:
    lan_ip = _lan_ip()
    if lan_ip is None:
        pytest.skip("machine has no non-loopback IPv4 address")

    async def app(scope: dict, receive: object, send: object) -> None:  # minimal ASGI app
        raise RuntimeError("not used")

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host=config.HOST, port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        socket.create_connection(("127.0.0.1", port), timeout=1).close()  # reachable locally
        with pytest.raises(OSError):
            socket.create_connection((lan_ip, port), timeout=1).close()  # but not on the LAN IP
    finally:
        server.should_exit = True
        thread.join(timeout=5)
