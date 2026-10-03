"""In-memory conversations, one per page load or "New chat" (AC-5, AC-6)."""

import uuid
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from anthropic.types.beta import BetaMessageParam


class UnknownConversation(KeyError):
    pass


class ConversationBusy(Exception):
    """A reply is still being generated for this conversation (AC-7)."""


@dataclass
class Conversation:
    id: str
    history: list[BetaMessageParam] = field(default_factory=list)
    busy: bool = False

    @contextmanager
    def turn(self) -> Iterator[None]:
        """Hold the conversation for one reply; a second concurrent reply is rejected."""
        if self.busy:
            raise ConversationBusy(self.id)
        self.busy = True
        try:
            yield
        finally:
            self.busy = False


class ConversationStore:
    """Single-user store; old conversations are dropped so memory stays bounded."""

    def __init__(self, max_conversations: int = 100) -> None:
        self.max_conversations = max_conversations
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()

    def new(self) -> Conversation:
        conversation = Conversation(uuid.uuid4().hex)
        self._conversations[conversation.id] = conversation
        while len(self._conversations) > self.max_conversations:
            self._conversations.popitem(last=False)
        return conversation

    def get(self, conversation_id: str) -> Conversation:
        try:
            return self._conversations[conversation_id]
        except KeyError:
            raise UnknownConversation(conversation_id) from None
