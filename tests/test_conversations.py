import pytest

from chat_agent.conversations import ConversationBusy, ConversationStore, UnknownConversation


def test_ac5_new_conversation_is_empty() -> None:
    store = ConversationStore()
    first = store.new()
    first.history.append({"role": "user", "content": "remember me"})
    second = store.new()
    assert second.id != first.id
    assert second.history == []
    assert store.get(first.id) is first


def test_unknown_conversation_raises() -> None:
    with pytest.raises(UnknownConversation):
        ConversationStore().get("nope")


def test_ac7_concurrent_turn_rejected() -> None:
    conversation = ConversationStore().new()
    with conversation.turn(), pytest.raises(ConversationBusy), conversation.turn():
        pass
    with conversation.turn():  # free again afterwards
        pass


def test_turn_released_after_error() -> None:
    conversation = ConversationStore().new()
    with pytest.raises(RuntimeError), conversation.turn():
        raise RuntimeError("boom")
    with conversation.turn():
        pass


def test_oldest_conversations_are_dropped() -> None:
    store = ConversationStore(max_conversations=2)
    first, second, third = store.new(), store.new(), store.new()
    with pytest.raises(UnknownConversation):
        store.get(first.id)
    assert store.get(second.id) is second
    assert store.get(third.id) is third
