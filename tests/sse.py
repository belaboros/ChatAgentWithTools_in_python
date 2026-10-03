"""Build Claude API streaming (SSE) responses for a mocked HTTP transport."""

import json
from typing import Any


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps({'type': name, **data})}\n\n"


def sse_body(*blocks: dict[str, Any], stop_reason: str = "end_turn") -> bytes:
    """Stream `blocks` the way the API does: start, deltas, stop for each content block."""
    out = [
        _event(
            "message_start",
            {
                "message": {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-5-5",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 1},
                }
            },
        )
    ]
    for index, block in enumerate(blocks):
        kind = block["type"]
        if kind == "text":
            out.append(
                _event(
                    "content_block_start",
                    {"index": index, "content_block": {"type": "text", "text": ""}},
                )
            )
            for piece in (
                block["text"][: len(block["text"]) // 2],
                block["text"][len(block["text"]) // 2 :],
            ):
                delta = {"type": "text_delta", "text": piece}
                out.append(_event("content_block_delta", {"index": index, "delta": delta}))
            for cite in block.get("citations") or []:
                delta = {"type": "citations_delta", "citation": cite}
                out.append(_event("content_block_delta", {"index": index, "delta": delta}))
        elif kind in ("tool_use", "server_tool_use"):
            start = {**block, "input": {}}
            out.append(_event("content_block_start", {"index": index, "content_block": start}))
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
            out.append(_event("content_block_delta", {"index": index, "delta": delta}))
        else:
            out.append(_event("content_block_start", {"index": index, "content_block": block}))
        out.append(_event("content_block_stop", {"index": index}))
    out.append(
        _event(
            "message_delta",
            {
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 5},
            },
        )
    )
    out.append(_event("message_stop", {}))
    return "".join(out).encode()
