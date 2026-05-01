"""Fixtures for Hot Spring tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    """Load a JSON fixture file.

    Args:
    ----
        name: The fixture filename (e.g. "status.json").

    Returns:
    -------
        The parsed JSON as a dict.

    """
    return json.loads((FIXTURES_DIR / name).read_text())  # type: ignore[no-any-return]


@pytest.fixture
def status_response() -> dict[str, object]:
    """Return the full /status fixture data."""
    return load_fixture("status.json")


@pytest.fixture
def startup_response() -> dict[str, object]:
    """Return the /startup fixture data."""
    return load_fixture("startup.json")


@pytest.fixture
def connect_status_response() -> dict[str, object]:
    """Return the /spaConnectStatus fixture data."""
    return load_fixture("spa_connect_status.json")


@pytest.fixture
def fwiq_response() -> dict[str, object]:
    """Return the /getFWIQData fixture data."""
    return load_fixture("fwiq_data.json")


@pytest.fixture
def debug_data_response() -> dict[str, object]:
    """Return the /addDebugData fixture data."""
    return load_fixture("debug_data.json")
