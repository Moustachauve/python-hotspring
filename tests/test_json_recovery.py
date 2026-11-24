"""Tests for truncated JSON recovery helpers."""

from __future__ import annotations

import pytest

from hotspring.json_recovery import recover_truncated_json


@pytest.mark.parametrize(
    ("truncated", "expected"),
    [
        pytest.param(
            '{"a": 1, "es": {"s": {"duration": 6 ',
            {"a": 1, "es": {"s": {"duration": 6}}},
            id="delimited_number_at_eof",
        ),
        pytest.param(
            '{"a": 1, "es": {"s": {"duration": 6 \n}\n}',
            {"a": 1, "es": {"s": {"duration": 6}}},
            id="mid_closing_braces",
        ),
        pytest.param(
            '{"a": 1, "es": {"s": {"mode": 2, "duration": 1',
            {"a": 1, "es": {"s": {"mode": 2}}},
            id="mid_number",
        ),
        pytest.param(
            '{"a": 1, "current_pH": 6.',
            {"a": 1},
            id="mid_float_dot",
        ),
        pytest.param(
            '{"a": 1, "current_pH": 6.7',
            {"a": 1},
            id="mid_float_digits",
        ),
        pytest.param(
            '{"a": 1, "color": "MAG',
            {"a": 1},
            id="mid_string_value",
        ),
        pytest.param(
            '{"a": 1, "color": "MAGENTA"',
            {"a": 1, "color": "MAGENTA"},
            id="complete_string_value_at_eof",
        ),
        pytest.param(
            '{"a": 1, "startHo',
            {"a": 1},
            id="mid_key",
        ),
        pytest.param(
            '{"a": 1, "startHour"',
            {"a": 1},
            id="complete_key_without_colon",
        ),
        pytest.param(
            '{"a": 1, "duration": ',
            {"a": 1},
            id="after_colon",
        ),
        pytest.param(
            '{"a": 1, "startMinute": 0,',
            {"a": 1, "startMinute": 0},
            id="after_comma",
        ),
        pytest.param(
            '{"a": 1, "energySaving2": {\n"status": {',
            {"a": 1},
            id="after_open_brace",
        ),
        pytest.param(
            '{"a": "hi \\"there\\"", "b": 1',
            {"a": 'hi "there"'},
            id="escaped_quote_in_string",
        ),
        pytest.param(
            '{"a": 1, "b": "foo\\',
            {"a": 1},
            id="trailing_backslash_at_eof",
        ),
        pytest.param(
            '{"a": [1, 2, 3',
            {"a": [1, 2]},
            id="array_truncation",
        ),
        pytest.param(
            "<html><body>500 error</body></html>",
            None,
            id="non_json_html",
        ),
        pytest.param(
            '{"a": 1]}',
            None,
            id="mismatched_brackets",
        ),
        pytest.param(
            '{"a": 1, "b": ???, "c": 2',
            None,
            id="corrupt_syntax_mid_payload",
        ),
        pytest.param(
            '{"a": 1, "b": 2"c": 3',
            None,
            id="scalar_without_delimiter_mid_payload",
        ),
        pytest.param(
            '{"a": ',
            None,
            id="no_complete_value",
        ),
        pytest.param(
            '{"a": 01, "b": 2',
            None,
            id="invalid_repaired_json",
        ),
        pytest.param(
            "{}{",
            None,
            id="empty_object_prefix",
        ),
    ],
)
def test_recover_truncated_json(
    truncated: str, expected: dict[str, object] | None
) -> None:
    """Test truncated JSON recovery across boundary conditions."""
    assert recover_truncated_json(truncated) == expected
