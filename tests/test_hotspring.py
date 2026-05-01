"""Tests for Hot Spring client."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiohttp
import pytest
from aresponses import Response, ResponsesMockServer

from hotspring import (
    HotSpring,
    HotSpringCommandError,
    HotSpringConnectionError,
    HotSpringError,
    HotSpringNotReadyError,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    """Load a fixture as a JSON string."""
    return (FIXTURES_DIR / name).read_text()


def _json_response(fixture_name: str, status: int = 200) -> Response:
    """Create a JSON response from a fixture file."""
    return Response(
        status=status,
        headers={"Content-Type": "application/json"},
        text=_load(fixture_name),
    )


def _add_update_mocks(
    aresponses: ResponsesMockServer,
    *,
    startup_status: int = 200,
    connect_payload: str | None = None,
) -> None:
    """Add mock responses for a full update() call."""
    host = "192.168.1.100"
    aresponses.add(host, "/status", "GET", _json_response("status.json"))
    aresponses.add(
        host,
        "/startup",
        "GET",
        _json_response("startup.json", status=startup_status),
    )
    connect = connect_payload or _load("spa_connect_status.json")
    aresponses.add(
        host,
        "/spaConnectStatus",
        "GET",
        Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=connect,
        ),
    )


class TestUpdate:
    """Tests for the update() method."""

    async def test_update_success(self, aresponses: ResponsesMockServer) -> None:
        """Test successful full update."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()

        assert spa is not None
        assert spa.heater.is_on is True
        assert spa.heater.current_temperature == 100.0
        assert spa.info.hostname == "ConnectedSpa_C59C9C"
        assert spa.connection_status.spa_connected is True
        assert client.spa is spa

    async def test_update_empty_response(self, aresponses: ResponsesMockServer) -> None:
        """Test update with non-JSON response raises error."""
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            Response(
                status=200,
                headers={"Content-Type": "text/html"},
                text="not json",
            ),
        )
        # Backoff retries 3 times
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            Response(
                status=200,
                headers={"Content-Type": "text/html"},
                text="not json",
            ),
        )
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            Response(
                status=200,
                headers={"Content-Type": "text/html"},
                text="not json",
            ),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            with pytest.raises(HotSpringError, match="Invalid JSON"):
                await client.update()

    async def test_update_reuses_spa_object(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that update reuses the same Spa object."""
        _add_update_mocks(aresponses)
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa1 = await client.update()
            spa2 = await client.update()

        assert spa1 is spa2

    async def test_update_startup_failure_non_critical(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that /startup failure doesn't break update."""
        _add_update_mocks(aresponses, startup_status=500)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()

        assert spa is not None
        assert spa.heater.is_on is True


class TestUpdateWaterCare:
    """Tests for the update_water_care() method."""

    async def test_update_water_care(self, aresponses: ResponsesMockServer) -> None:
        """Test successful water care update."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/getFWIQData",
            "GET",
            _json_response("fwiq_data.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            fwiq = await client.update_water_care()

        assert fwiq.ph == -1.0
        assert fwiq.chlorine == -1.0

    async def test_update_water_care_without_update(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test water care update without initial update raises error."""
        aresponses.add(
            "192.168.1.100",
            "/getFWIQData",
            "GET",
            _json_response("fwiq_data.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            with pytest.raises(HotSpringError, match="Call update"):
                await client.update_water_care()


class TestUpdateDiagnostics:
    """Tests for the update_diagnostics() method."""

    async def test_update_diagnostics(self, aresponses: ResponsesMockServer) -> None:
        """Test successful diagnostics update."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/addDebugData",
            "GET",
            _json_response("debug_data.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            diag = await client.update_diagnostics()

        assert diag.heater_power == "4000"


class TestCommands:
    """Tests for control command methods."""

    async def test_set_temperature(self, aresponses: ResponsesMockServer) -> None:
        """Test setting temperature."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"heater": {"control": {"temperatureABS": "102"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_temperature(102)

    async def test_set_jet(self, aresponses: ResponsesMockServer) -> None:
        """Test setting jet speed."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"JET": {"JET1": {"control": "highSpeed"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_jet(1, "highSpeed")

    async def test_set_light_color(self, aresponses: ResponsesMockServer) -> None:
        """Test setting light color."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {
                    "control": {
                        "Zone1": {
                            "control": {
                                "color": "BLUE",
                                "IntensityAbs": 5,
                                "lightWheel": "off",
                            }
                        }
                    }
                }
            }
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_light_color(1, "Blue")

    async def test_turn_off_light(self, aresponses: ResponsesMockServer) -> None:
        """Test turning off a light zone."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {"control": {"Zone1": {"control": {"Intensity": "off"}}}}
            }
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.turn_off_light(1)

    async def test_set_light_brightness(self, aresponses: ResponsesMockServer) -> None:
        """Test setting light brightness."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {"control": {"Zone1": {"control": {"Intensity": "fullon"}}}}
            }
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_light_brightness(1)

    async def test_set_light_rgb(self, aresponses: ResponsesMockServer) -> None:
        """Test setting exact RGB light color."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {
                    "control": {
                        "Zone1": {
                            "control": {
                                "rgbFactor": {
                                    "red": "255",
                                    "green": "0",
                                    "blue": "128",
                                }
                            }
                        }
                    }
                }
            }
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_light_rgb(1, 255, 0, 128)

    async def test_set_heating_mode(self, aresponses: ResponsesMockServer) -> None:
        """Test setting heating mode."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"heater": {"control": {"heatingMode": "heatWithBoost"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_heating_mode("heatWithBoost")

    async def test_set_clean_cycle(self, aresponses: ResponsesMockServer) -> None:
        """Test setting clean cycle."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"cleanCycle": {"control": {"cleanCycle": "on"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_clean_cycle(enabled=True)

    async def test_set_blower(self, aresponses: ResponsesMockServer) -> None:
        """Test setting blower."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"blower": {"control": "on"}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_blower(on=True)

    async def test_command_sna_not_connected(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test command fails when SNA is not connected."""
        disconnected = json.dumps({"spaConnectStatus": "false"})
        _add_update_mocks(aresponses, connect_payload=disconnected)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            with pytest.raises(HotSpringNotReadyError, match="SNA bridge"):
                await client.set_temperature(102)

    async def test_command_server_error(self, aresponses: ResponsesMockServer) -> None:
        """Test command wraps server errors in HotSpringCommandError."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/spaManager",
            "POST",
            Response(status=500, text="error"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            with pytest.raises(HotSpringCommandError, match="Command failed"):
                await client.set_temperature(102)


class TestConnection:
    """Tests for connection handling."""

    async def test_connection_error(self, aresponses: ResponsesMockServer) -> None:
        """Test connection error is raised properly."""

        async def handler(_: aiohttp.ClientResponse) -> Response:
            await asyncio.sleep(0.2)
            return Response(text="timeout")

        # Backoff retries 3 times
        aresponses.add("192.168.1.100", "/status", "GET", handler)
        aresponses.add("192.168.1.100", "/status", "GET", handler)
        aresponses.add("192.168.1.100", "/status", "GET", handler)

        async with aiohttp.ClientSession() as session:
            client = HotSpring(
                host="192.168.1.100", session=session, request_timeout=0.1
            )
            with pytest.raises(HotSpringConnectionError):
                await client.update()

    async def test_context_manager(self) -> None:
        """Test async context manager."""
        async with HotSpring(host="192.168.1.100") as client:
            assert client.session is None  # Session is created lazily

    async def test_creates_session_if_none(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that client creates its own session if none provided."""
        _add_update_mocks(aresponses)
        async with HotSpring(host="192.168.1.100") as client:
            await client.update()
            assert client.session is not None
            # pylint: disable=protected-access
            assert client._close_session is True
