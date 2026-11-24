"""Helpers for recovering buffer-truncated JSON payloads from the HNA.

The HNA firmware serializes GET /status into a fixed 3,072-byte (0xc00)
buffer and null-terminates at index 3,071, returning HTTP 200 with truncated
JSON when a spa's payload exceeds that capacity.
"""

from __future__ import annotations

import json
import re

# Match one JSON token at a time: a complete double-quoted string, a structural
# character, or a bare scalar run. An unterminated string at EOF fails to match
# and exits the loop cleanly.
_JSON_TOKEN_RE = re.compile(r'\s*(?P<tok>"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^"\s{}\[\]:,]+)')
_CONTAINER_CLOSERS: dict[str, str] = {"{": "}", "[": "]"}
_SCALAR_DELIMITERS = frozenset(" \t\r\n,}]")


def _find_truncated_json_cut(body: str) -> tuple[int, str] | None:
    """Return the cut index and closing delimiters after the last complete value."""
    stack: list[str] = []
    expect_value = False
    safe_state: tuple[int, str] | None = None
    pos = 0
    end = len(body)

    while (match := _JSON_TOKEN_RE.match(body, pos)) is not None:
        tok = match.group("tok")
        pos = match.end()
        if (closer := _CONTAINER_CLOSERS.get(tok)) is not None:
            stack.append(closer)
            expect_value = tok == "["
        elif tok in "}]":
            if not stack or stack[-1] != tok:
                return None
            stack.pop()
            safe_state = (pos, "".join(reversed(stack)))
            expect_value = bool(stack) and stack[-1] == "]"
        elif tok in ":,":
            expect_value = tok == ":" or (bool(stack) and stack[-1] == "]")
        elif tok.startswith('"'):
            if expect_value and len(stack) == 1:
                safe_state = (pos, "".join(reversed(stack)))
            expect_value = False
        elif expect_value and pos == end:
            break
        elif expect_value and body[pos] in _SCALAR_DELIMITERS:
            if len(stack) == 1:
                safe_state = (pos, "".join(reversed(stack)))
            expect_value = False
        else:
            return None

    return safe_state


def recover_truncated_json(body: str) -> dict[str, object] | None:
    """Recover a valid JSON object prefix from a buffer-truncated response."""
    if (cut := _find_truncated_json_cut(body)) is None:
        return None
    cut_pos, closers = cut
    try:
        parsed = json.loads(body[:cut_pos] + closers)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and parsed:
        return parsed
    return None
