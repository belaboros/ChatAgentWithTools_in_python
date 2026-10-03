import importlib


def test_package_imports() -> None:
    for module in ("chat_agent", "chat_agent.config"):
        importlib.import_module(module)
