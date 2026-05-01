"""Asynchronous Python client for Hot Spring Connected Spa Kit 2."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Self

import aiohttp
import backoff
from yarl import URL

from .exceptions import (
    HotSpringCommandError,
    HotSpringConnectionError,
    HotSpringConnectionTimeoutError,
    HotSpringError,
    HotSpringNotReadyError,
)
from .models import (
    ConnectionStatus,
    Diagnostics,
    FreshWaterIQ,
    Spa,
)


@dataclass
class HotSpring:
    """Main class for handling connections with a Hot Spring Spa.

    The Hot Spring Connected Spa Kit 2 uses a Home Network Adapter (HNA)
    that runs a local HTTP API. This client communicates with the HNA
    to poll spa state and send control commands.

    Usage::

        async with HotSpring("192.168.1.100") as spa_client:
            spa = await spa_client.update()
            print(spa.heater.current_temperature)
            await spa_client.set_temperature(102)

    """

    host: str
    session: aiohttp.ClientSession | None = None
    request_timeout: float = 10.0
    _close_session: bool = False
    spa: Spa | None = None

    @backoff.on_exception(
        backoff.expo,
        HotSpringConnectionError,
        max_tries=3,
        logger=None,
    )
    async def request(
        self,
        uri: str = "",
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Handle a request to the Hot Spring HNA.

        A generic method for sending/handling HTTP requests done against
        the Hot Spring Home Network Adapter.

        Args:
        ----
            uri: Request URI, for example ``/status``.
            method: HTTP method to use for the request.
            data: Dictionary of data to send to the HNA.

        Returns:
        -------
            A Python dictionary (JSON decoded) with the response from the
            Hot Spring HNA.

        Raises:
        ------
            HotSpringConnectionError: An error occurred while communicating
                with the Hot Spring HNA.
            HotSpringConnectionTimeoutError: A timeout occurred while
                communicating with the Hot Spring HNA.
            HotSpringError: Received an unexpected response from the HNA.

        """
        url = URL.build(scheme="http", host=self.host, port=80, path=uri)

        headers = {
            "Accept": "application/json, text/plain, */*",
        }

        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.request(
                    method,
                    url,
                    json=data,
                    headers=headers,
                )

            if response.status // 100 in [4, 5]:
                contents = await response.read()
                response.close()

                try:
                    raise HotSpringError(
                        response.status,
                        json.loads(contents.decode("utf8")),
                    )
                except json.JSONDecodeError:
                    raise HotSpringError(
                        response.status,
                        {"message": contents.decode("utf8")},
                    ) from None

            # The spa returns JSON with text/html Content-Type,
            # so always try JSON parsing first.
            body = await response.text()
            try:
                response_data = json.loads(body)
            except json.JSONDecodeError:
                response_data = body

        except asyncio.TimeoutError as exception:
            msg = f"Timeout occurred while connecting to Hot Spring HNA at {self.host}"
            raise HotSpringConnectionTimeoutError(msg) from exception
        except aiohttp.ClientError as exception:
            msg = (
                f"Error occurred while communicating with Hot Spring HNA at {self.host}"
            )
            raise HotSpringConnectionError(msg) from exception

        return response_data

    async def update(self) -> Spa:
        """Get all spa information in a single polling cycle.

        This method fetches the main /status endpoint and combines it with
        identity information from /startup and /spamodel. Use this for
        the primary 15-second polling cycle.

        Returns
        -------
            The updated Spa data object.

        Raises
        ------
            HotSpringError: If no data is returned from the spa.

        """
        # Fetch main status
        status_data = await self.request("/status")
        if not status_data:
            msg = "No data was returned by the spa"
            raise HotSpringError(msg)

        if self.spa is None:
            self.spa = Spa(status_data)
        else:
            self.spa.update_from_dict(status_data)

        # Fetch identity/startup info
        try:
            startup_data = await self.request("/startup")
            if isinstance(startup_data, dict):
                self.spa.update_info(startup_data)
        except HotSpringError:
            pass  # Non-critical; identity may already be populated

        # Fetch connection status
        try:
            connect_data = await self.request("/spaConnectStatus")
            if isinstance(connect_data, dict):
                self.spa.update_connection_status(connect_data)
        except HotSpringError:
            pass  # Non-critical

        return self.spa

    async def update_water_care(self) -> FreshWaterIQ:
        """Update FreshWater IQ water quality data.

        This polls the /getFWIQData endpoint. Recommended polling interval
        is 60 seconds (slower than the main status poll).

        Returns
        -------
            The updated FreshWaterIQ data.

        Raises
        ------
            HotSpringError: If no data is returned.

        """
        data = await self.request("/getFWIQData")
        if not data:
            msg = "No water care data was returned by the spa"
            raise HotSpringError(msg)

        if self.spa is None:
            msg = "Call update() before update_water_care()"
            raise HotSpringError(msg)

        self.spa.update_freshwater_iq(data)
        return self.spa.freshwater_iq

    async def update_diagnostics(self) -> Diagnostics:
        """Update diagnostic and power metrics.

        Fetches the /addDebugData endpoint. Availability depends on the
        spa model and sensor configuration.

        Returns
        -------
            The updated Diagnostics data.

        Raises
        ------
            HotSpringError: If no data is returned.

        """
        data = await self.request("/addDebugData")
        if not data:
            msg = "No diagnostic data was returned by the spa"
            raise HotSpringError(msg)

        if self.spa is None:
            msg = "Call update() before update_diagnostics()"
            raise HotSpringError(msg)

        self.spa.update_diagnostics(data)
        return self.spa.diagnostics

    async def update_connection_status(self) -> ConnectionStatus:
        """Update HNA/SNA/cloud connection status.

        Returns
        -------
            The updated ConnectionStatus data.

        Raises
        ------
            HotSpringError: If no data is returned.

        """
        data = await self.request("/spaConnectStatus")
        if not data:
            msg = "No connection status data was returned by the spa"
            raise HotSpringError(msg)

        if self.spa is None:
            msg = "Call update() before update_connection_status()"
            raise HotSpringError(msg)

        self.spa.update_connection_status(data)
        return self.spa.connection_status

    async def _send_command(self, payload: dict[str, Any]) -> None:
        """Send a control command to the spa via POST /spaManager.

        All control commands are sent as JSON payloads to
        the ``/spaManager`` endpoint on the HNA.

        .. note::

            The firmware requires deeply nested payload structures (e.g.,
            multiple `control` keys) for most commands.

        Args:
        ----
            payload: Flat key-value command payload.

        Raises:
        ------
            HotSpringNotReadyError: If the SNA bridge is not connected.
            HotSpringCommandError: If the command fails.

        """
        if self.spa is not None and not self.spa.connection_status.spa_connected:
            msg = (
                "Cannot send commands: SNA bridge is not connected. "
                "The LoRA link between the HNA and the spa is down."
            )
            raise HotSpringNotReadyError(msg)

        try:
            await self.request("/spaManager", method="POST", data=payload)
        except HotSpringError as exception:
            msg = f"Command failed: {payload}"
            raise HotSpringCommandError(msg) from exception

    async def set_temperature(self, temperature: int) -> None:
        """Set the target water temperature.

        Args:
        ----
            temperature: Target temperature in the spa's configured unit
                (Fahrenheit or Celsius).

        """
        await self._send_command(
            {"heater": {"control": {"temperatureABS": str(temperature)}}}
        )

    async def set_heating_mode(self, mode: str) -> None:
        """Set the heating mode.

        Args:
        ----
            mode: The heating mode value. Use HeatingMode enum values,
                e.g. ``HeatingMode.HEAT_WITH_BOOST.value``.

        """
        await self._send_command({"heater": {"control": {"heatingMode": mode}}})

    async def set_jet(self, jet: int, speed: str) -> None:
        """Set the speed of a jet pump.

        Args:
        ----
            jet: The jet number (1-based).
            speed: The speed value. Use JetSpeed enum values,
                e.g. ``JetSpeed.HIGH_SPEED.value``.

        """
        await self._send_command({"JET": {f"JET{jet}": {"control": speed}}})

    async def set_light_color(
        self,
        zone: int,
        color: str,
        intensity: int = 5,
        light_wheel: str = "off",
    ) -> None:
        """Set the color of a light zone.

        Args:
        ----
            zone: The light zone number (1-based).
            color: The color value. Use LightColor enum values,
                e.g. ``LightColor.BLUE.value``.
            intensity: The brightness intensity (0-5). Defaults to 5.
            light_wheel: The light wheel mode. Use LightWheelMode enum values,
                e.g. ``LightWheelMode.OFF.value``. Defaults to "off".

        """
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "color": color.upper(),
                                "IntensityAbs": intensity,
                                "lightWheel": light_wheel,
                            }
                        }
                    }
                }
            }
        )

    async def turn_off_light(self, zone: int) -> None:
        """Turn off a light zone.

        Args:
        ----
            zone: The light zone number (1-based).

        """
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "Intensity": "off",
                            }
                        }
                    }
                }
            }
        )

    async def set_light_brightness(self, zone: int, *, full: bool = True) -> None:
        """Set the brightness of a light zone.

        Args:
        ----
            zone: The light zone number (1-based).
            full: True to set to full brightness ("fullon"), False to turn off ("off").

        """
        intensity = "fullon" if full else "off"
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "Intensity": intensity,
                            }
                        }
                    }
                }
            }
        )

    async def set_light_rgb(
        self,
        zone: int,
        red: int,
        green: int,
        blue: int,
    ) -> None:
        """Set the exact RGB color of a light zone.

        Args:
        ----
            zone: The light zone number (1-based).
            red: Red value (0-255).
            green: Green value (0-255).
            blue: Blue value (0-255).

        """
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "rgbFactor": {
                                    "red": str(red),
                                    "green": str(green),
                                    "blue": str(blue),
                                }
                            }
                        }
                    }
                }
            }
        )

    async def set_clean_cycle(self, *, enabled: bool) -> None:
        """Enable or disable the clean cycle.

        Args:
        ----
            enabled: True to enable, False to disable.

        """
        value = "on" if enabled else "off"
        await self._send_command({"cleanCycle": {"control": {"cleanCycle": value}}})

    async def set_blower(self, *, on: bool) -> None:
        """Turn the blower on or off.

        Args:
        ----
            on: True to turn on, False to turn off.

        """
        value = "on" if on else "off"
        await self._send_command({"blower": {"control": value}})

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()

    async def __aenter__(self) -> Self:
        """Async enter.

        Returns
        -------
            The HotSpring object.

        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit.

        Args:
        ----
            _exc_info: Exec type.

        """
        await self.close()
