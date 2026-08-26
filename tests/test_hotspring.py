"""Tests for Hot Spring client."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

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
from hotspring.const import (
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
    LightColor,
    LightWheelMode,
)

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

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
    spamodel_status: int = 200,
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
    aresponses.add(
        host,
        "/spamodel",
        "GET",
        _json_response("spamodel.json", status=spamodel_status),
    )


class TestUpdate:
    """Tests for the update() method."""

    async def test_update_success(
        self, aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
    ) -> None:
        """Test successful full update."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()

        assert spa == snapshot
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
        # Second update fetches /status and /spaConnectStatus (cached static identity)
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            _json_response("status.json"),
        )
        aresponses.add(
            "192.168.1.100",
            "/spaConnectStatus",
            "GET",
            _json_response("spa_connect_status.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa1 = await client.update()
            spa2 = await client.update()

        assert spa1 is spa2

    async def test_update_cached_identity(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that subsequent updates preserve cached identity."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            _json_response("status.json"),
        )
        aresponses.add(
            "192.168.1.100",
            "/spaConnectStatus",
            "GET",
            _json_response("spa_connect_status.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()
            # pylint: disable=protected-access
            assert client._identity_loaded is True
            assert spa.info.hostname == "ConnectedSpa_112233"

            # Routine update
            spa_updated = await client.update()
            assert spa_updated.info.hostname == "ConnectedSpa_112233"

    async def test_update_refreshes_connection_status(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that routine updates refresh connection_status dynamically."""
        _add_update_mocks(
            aresponses, connect_payload=json.dumps({"spaConnectStatus": "false"})
        )
        aresponses.add(
            "192.168.1.100",
            "/status",
            "GET",
            _json_response("status.json"),
        )
        aresponses.add(
            "192.168.1.100",
            "/spaConnectStatus",
            "GET",
            _json_response("spa_connect_status.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()
            assert spa.connection_status.spa_connected is False

            # Routine update receives reconnect
            spa_updated = await client.update()
            assert spa_updated.connection_status.spa_connected is True

    async def test_update_force_refresh_identity(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that refresh_identity=True forces re-fetching identity."""
        _add_update_mocks(aresponses)
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            spa = await client.update(refresh_identity=True)

        assert spa.info.hostname == "ConnectedSpa_112233"

    async def test_update_with_spamodel_response(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test update including spamodel endpoint."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()

        assert spa.info.brand_id == "0"
        assert spa.info.volume == 335

    async def test_update_identity_explicit(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test explicit update_identity() method."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/startup",
            "GET",
            _json_response("startup.json"),
        )
        aresponses.add(
            "192.168.1.100",
            "/spamodel",
            "GET",
            _json_response("spamodel.json"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            info = await client.update_identity()

        assert info.hostname == "ConnectedSpa_112233"
        assert info.brand_id == "0"
        assert info.volume == 335

    async def test_update_identity_both_fail_gracefully(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test update_identity() when both /startup and /spamodel fail."""
        _add_update_mocks(aresponses)
        aresponses.add(
            "192.168.1.100",
            "/startup",
            "GET",
            Response(status=500, text="error"),
        )
        aresponses.add(
            "192.168.1.100",
            "/spamodel",
            "GET",
            Response(status=500, text="error"),
        )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            info = await client.update_identity()

        # Identity from initial cold sync should be preserved
        assert info.hostname == "ConnectedSpa_112233"

    async def test_update_identity_without_update_raises(self) -> None:
        """Test that update_identity() before update() raises HotSpringError."""
        async with HotSpring(host="192.168.1.100") as client:
            with pytest.raises(HotSpringError, match="Call update"):
                await client.update_identity()

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

    async def test_update_spamodel_failure_non_critical(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that /spamodel failure doesn't break update."""
        _add_update_mocks(aresponses, spamodel_status=500)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            spa = await client.update()

        assert spa is not None
        assert spa.heater.is_on is True

    async def test_cold_sync_status_failure_propagates(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test that /status failure in cold sync propagates as HotSpringError."""
        for _ in range(3):
            aresponses.add(
                "192.168.1.100",
                "/status",
                "GET",
                Response(status=500, text="error"),
            )
            aresponses.add(
                "192.168.1.100",
                "/startup",
                "GET",
                _json_response("startup.json"),
            )
            aresponses.add(
                "192.168.1.100",
                "/spaConnectStatus",
                "GET",
                _json_response("spa_connect_status.json"),
            )
            aresponses.add(
                "192.168.1.100",
                "/spamodel",
                "GET",
                _json_response("spamodel.json"),
            )
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            with pytest.raises(HotSpringError):
                await client.update()


class TestUpdateWaterCare:
    """Tests for the update_water_care() method."""

    async def test_update_water_care(
        self, aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
    ) -> None:
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

        assert fwiq == snapshot

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

    async def test_update_diagnostics(
        self, aresponses: ResponsesMockServer, snapshot: SnapshotAssertion
    ) -> None:
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

        assert diag == snapshot


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

    async def test_set_jet_enum(self, aresponses: ResponsesMockServer) -> None:
        """Test setting jet speed using JetSpeed enum."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"JET": {"JET2": {"control": "lowSpeed"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_jet(2, JetSpeed.LOW_SPEED)

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

    async def test_set_light_color_enum(self, aresponses: ResponsesMockServer) -> None:
        """Test setting light color using LightColor enum."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {
                    "control": {
                        "Zone2": {
                            "control": {
                                "color": "RED",
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
            await client.set_light_color(2, LightColor.RED)

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
        """Test setting light brightness level (0-5)."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {
                    "control": {
                        "Zone1": {
                            "control": {
                                "IntensityAbs": 3,
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
            await client.set_light_brightness(1, 3)

    async def test_set_light_brightness_invalid(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test setting invalid light brightness levels raises ValueError."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            match_msg = "Brightness must be between 0 and 5"
            with pytest.raises(ValueError, match=match_msg):
                await client.set_light_brightness(1, -1)
            with pytest.raises(ValueError, match=match_msg):
                await client.set_light_brightness(1, 6)

    async def test_set_light_wheel(self, aresponses: ResponsesMockServer) -> None:
        """Test setting light wheel mode."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "lights": {
                    "control": {
                        "Zone1": {
                            "control": {
                                "lightWheel": "on",
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
            await client.set_light_wheel(1, LightWheelMode.ON)

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

    async def test_set_light_rgb_invalid(self, aresponses: ResponsesMockServer) -> None:
        """Test setting invalid RGB components raises ValueError."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            err_msg = "RGB values must be between 0 and 255"
            with pytest.raises(ValueError, match=err_msg):
                await client.set_light_rgb(1, 256, 0, 0)
            with pytest.raises(ValueError, match=err_msg):
                await client.set_light_rgb(1, 0, -1, 0)
            with pytest.raises(ValueError, match=err_msg):
                await client.set_light_rgb(1, 0, 0, 300)

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

    async def test_set_heating_mode_enum(self, aresponses: ResponsesMockServer) -> None:
        """Test setting heating mode using HeatingMode enum."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"heater": {"control": {"heatingMode": "heatWithBoost"}}}
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_heating_mode(HeatingMode.HEAT_WITH_BOOST)

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

    async def test_set_spa_lock(self, aresponses: ResponsesMockServer) -> None:
        """Test locking and unlocking spa controls."""
        _add_update_mocks(aresponses)

        async def handler_on(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"spaLock": {"control": "on"}}
            return Response(
                status=200,
                text=json.dumps({"spaLock": {"status": {"spaLock": "on"}}}),
            )

        async def handler_off(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"spaLock": {"control": "off"}}
            return Response(
                status=200,
                text=json.dumps({"spaLock": {"status": {"spaLock": "off"}}}),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler_on)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler_off)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_spa_lock(locked=True)
            assert client.spa.spa_lock.is_locked is True
            await client.set_spa_lock(locked=False)
            assert client.spa.spa_lock.is_locked is False

    async def test_set_temperature_lock(self, aresponses: ResponsesMockServer) -> None:
        """Test setting temperature lock and its alias set_heater_lock."""
        _add_update_mocks(aresponses)

        async def handler_on(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"heater": {"control": {"temperatureLock": "on"}}}
            return Response(
                status=200,
                text=json.dumps({"heater": {"status": {"heaterLock": "on"}}}),
            )

        async def handler_off(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"heater": {"control": {"temperatureLock": "off"}}}
            return Response(
                status=200,
                text=json.dumps({"heater": {"status": {"heaterLock": "off"}}}),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler_on)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler_off)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_temperature_lock(locked=True)
            assert client.spa.heater.heater_lock is True
            await client.set_heater_lock(locked=False)
            assert client.spa.heater.heater_lock is False

    async def test_set_vanishing_act(self, aresponses: ResponsesMockServer) -> None:
        """Test setting vanishing act."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"cleanCycle": {"control": {"vanishingAct": "on"}}}
            return Response(
                status=200,
                text=json.dumps({"cleanCycle": {"status": {"vanishingAct": "on"}}}),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_vanishing_act(enabled=True)
            assert client.spa.clean_cycle.vanishing_act is True

    async def test_set_water_care_boost(self, aresponses: ResponsesMockServer) -> None:
        """Test triggering water care boost."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"waterCare": {"control": {"boost": "toggle"}}}
            return Response(
                status=200,
                text=json.dumps({"waterCare": {"status": {"boost": "active"}}}),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_water_care_boost()
            assert client.spa.water_care.boost_active is True

    async def test_set_water_care_level(self, aresponses: ResponsesMockServer) -> None:
        """Test setting water care cartridge output level."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {"waterCare": {"control": {"level": "7"}}}
            return Response(
                status=200,
                text=json.dumps({"waterCare": {"status": {"level": 7}}}),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_water_care_level(7)
            assert client.spa.water_care.level == 7

            with pytest.raises(ValueError, match="between 0 and 10"):
                await client.set_water_care_level(-1)
            with pytest.raises(ValueError, match="between 0 and 10"):
                await client.set_water_care_level(11)

    async def test_set_salt_system_power(self, aresponses: ResponsesMockServer) -> None:
        """Test setting salt system power configuration."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "waterCare": {
                    "config": {
                        "saltSystemPowerA": "enable",
                        "saltSystemPowerB": "disable",
                    }
                }
            }
            return Response(
                status=200,
                text=json.dumps(
                    {
                        "waterCare": {
                            "config": {
                                "saltSystemPowerA": "enable",
                                "saltSystemPowerB": "disable",
                            }
                        }
                    }
                ),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_salt_system_power(power_a=True, power_b=False)
            assert client.spa.water_care.system_enabled is True

            with pytest.raises(ValueError, match="At least one of power_a or power_b"):
                await client.set_salt_system_power()

    async def test_set_logo_light(self, aresponses: ResponsesMockServer) -> None:
        """Test setting logo light brightness with enums and strings."""
        _add_update_mocks(aresponses)

        calls = []

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            calls.append(data)
            return Response(status=200, text='{"status": "ok"}')

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)

        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            await client.set_logo_light(BrightnessLevel.LEVEL_1)
            await client.set_logo_light(BrightnessLevel.LEVEL_2)
            await client.set_logo_light(BrightnessLevel.LEVEL_3)
            await client.set_logo_light("auto")
            await client.set_logo_light(2)

        assert calls == [
            {"logoLight": {"control": "1"}},
            {"logoLight": {"control": "2"}},
            {"logoLight": {"control": "3"}},
            {"logoLight": {"control": "auto"}},
            {"logoLight": {"control": "2"}},
        ]

    async def test_set_logo_light_invalid(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test setting invalid logo light brightness raises ValueError."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            with pytest.raises(ValueError, match="Invalid logo light"):
                await client.set_logo_light("invalid_level")

    async def test_set_energy_saving_schedule(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test configuring energy saving schedule."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "energySavings": {
                    "energySaving1": {
                        "control": {
                            "mode": "on",
                            "startHour": "14",
                            "startMinute": "30",
                            "duration": "4",
                        }
                    }
                }
            }
            return Response(
                status=200,
                text=json.dumps(
                    {
                        "energySavings": {
                            "energySaving1": {
                                "status": {
                                    "mode": 1,
                                    "startHour": 14,
                                    "startMinute": 30,
                                    "duration": 4,
                                }
                            }
                        }
                    }
                ),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_energy_saving_schedule(
                1, enabled=True, start_hour=14, start_minute=30, duration=4
            )
            s1 = client.spa.energy_savings[0]
            assert s1.is_enabled is True
            assert s1.start_hour == 14
            assert s1.start_minute == 30
            assert s1.duration == 4

    async def test_set_energy_saving_schedule_validation(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test energy saving schedule input validation."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            with pytest.raises(ValueError, match="Schedule ID must be 1 or 2"):
                await client.set_energy_saving_schedule(
                    3, enabled=True, start_hour=0, start_minute=0, duration=1
                )
            with pytest.raises(ValueError, match="start_hour must be between 0 and 23"):
                await client.set_energy_saving_schedule(
                    1, enabled=True, start_hour=24, start_minute=0, duration=1
                )
            msg_minute = "start_minute must be between 0 and 59"
            with pytest.raises(ValueError, match=msg_minute):
                await client.set_energy_saving_schedule(
                    1, enabled=True, start_hour=10, start_minute=60, duration=1
                )
            with pytest.raises(ValueError, match="duration must be between 1 and 24"):
                await client.set_energy_saving_schedule(
                    1, enabled=True, start_hour=10, start_minute=0, duration=0
                )

    async def test_set_clean_cycle_schedule(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test configuring clean cycle recurring schedule."""
        _add_update_mocks(aresponses)

        async def handler(request: aiohttp.web.Request) -> Response:
            data = await request.json()
            assert data == {
                "cleanCycleTimer": {
                    "cleanTimer": "enable",
                    "startHour": 18,
                    "startMinute": 45,
                }
            }
            return Response(
                status=200,
                text=json.dumps(
                    {
                        "cleanCycleTimer": {
                            "cleanTimer": "enable",
                            "startHour": 18,
                            "startMinute": 45,
                        }
                    }
                ),
            )

        aresponses.add("192.168.1.100", "/spaManager", "POST", handler)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None
            await client.set_clean_cycle_schedule(
                enabled=True, start_hour=18, start_minute=45
            )
            assert client.spa.clean_cycle.clean_timer_enabled is True
            assert client.spa.clean_cycle.start_hour == 18
            assert client.spa.clean_cycle.start_minute == 45

    async def test_set_clean_cycle_schedule_validation(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test clean cycle schedule input validation."""
        _add_update_mocks(aresponses)
        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            with pytest.raises(ValueError, match="start_hour must be between 0 and 23"):
                await client.set_clean_cycle_schedule(
                    enabled=True, start_hour=24, start_minute=0
                )
            msg_minute = "start_minute must be between 0 and 59"
            with pytest.raises(ValueError, match=msg_minute):
                await client.set_clean_cycle_schedule(
                    enabled=True, start_hour=10, start_minute=60
                )

    async def test_command_response_reactively_updates_state(
        self, aresponses: ResponsesMockServer
    ) -> None:
        """Test POST /spaManager response immediately updates spa state in memory."""
        _add_update_mocks(aresponses)

        # Light command response with real hardware state
        async def light_handler(_request: aiohttp.web.Request) -> Response:
            resp = {
                "lights": {
                    "zone1": {
                        "status": {
                            "lightWheel": "off",
                            "loopSpeed": 0,
                            "Intensity": 4,
                            "color": "custom",
                            "RGBstate": "active",
                            "cRed": 0,
                            "cGreen": 255,
                            "cBlue": 255,
                        }
                    }
                }
            }
            return Response(status=200, text=json.dumps(resp))

        # Jet command response with real hardware state
        async def jet_handler(_request: aiohttp.web.Request) -> Response:
            resp = {
                "JET": {
                    "JET1": {
                        "status": {
                            "speed": "off",
                        }
                    }
                }
            }
            return Response(status=200, text=json.dumps(resp))

        aresponses.add("192.168.1.100", "/spaManager", "POST", light_handler)
        aresponses.add("192.168.1.100", "/spaManager", "POST", jet_handler)

        async with aiohttp.ClientSession() as session:
            client = HotSpring(host="192.168.1.100", session=session)
            await client.update()
            assert client.spa is not None

            # Initial state
            assert client.spa.light_zones[0].intensity == 5
            assert client.spa.light_zones[0].color == LightColor.BLUE
            assert client.spa.jets[0].speed == JetSpeed.HIGH_SPEED

            # Execute light command -> immediately updates zone 1 in memory
            await client.set_light_rgb(1, 0, 255, 255)
            assert client.spa.light_zones[0].intensity == 4
            assert client.spa.light_zones[0].color == LightColor.CUSTOM
            assert client.spa.light_zones[0].c_red == 0
            assert client.spa.light_zones[0].c_green == 255
            assert client.spa.light_zones[0].c_blue == 255
            assert client.spa.light_zones[0].rgb_state == "active"
            # Other zones untouched
            assert client.spa.light_zones[1].zone_id == 2

            # Execute jet command -> immediately updates jet 1 in memory to off
            await client.set_jet(1, "off")
            assert client.spa.jets[0].speed == JetSpeed.OFF
            assert client.spa.jets[1].jet_id == 2

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
        """Test command failure wraps in HotSpringCommandError and preserves state."""
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
            assert client.spa is not None
            initial_temp = client.spa.heater.set_temperature
            with pytest.raises(HotSpringCommandError, match="Command failed"):
                await client.set_temperature(102)
            assert client.spa.heater.set_temperature == initial_temp


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

    async def test_close_is_safe_without_session(self) -> None:
        """Test that close() works cleanly when no session was created."""
        client = HotSpring(host="192.168.1.100")
        await client.close()
