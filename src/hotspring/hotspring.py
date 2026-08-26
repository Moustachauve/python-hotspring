"""Asynchronous Python client for Hot Spring Connected Spa Kit 2."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from typing import Self

import aiohttp
import backoff
from yarl import URL

from .const import (
    _BRIGHTNESS_TO_WIRE,
    VALID_ENERGY_SAVING_SCHEDULE_IDS,
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
    LightColor,
    LightWheelMode,
)
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
    SpaInfo,
)


@dataclass
class HotSpring:  # pylint: disable=too-many-public-methods
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
    _identity_loaded: bool = False
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
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
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
            except json.JSONDecodeError as exc:
                msg = f"Invalid JSON response from {uri}: {body[:200]}"
                raise HotSpringError(msg) from exc

        except asyncio.TimeoutError as exception:
            msg = f"Timeout occurred while connecting to Hot Spring HNA at {self.host}"
            raise HotSpringConnectionTimeoutError(msg) from exception
        except aiohttp.ClientError as exception:
            msg = (
                f"Error occurred while communicating with Hot Spring HNA at {self.host}"
            )
            raise HotSpringConnectionError(msg) from exception

        if not isinstance(response_data, dict):
            msg = f"Unexpected response type from {uri}"
            raise HotSpringError(msg)

        return response_data

    async def _safe_request(self, uri: str) -> dict[str, object] | None:
        """Fetch an endpoint, returning None on error."""
        with contextlib.suppress(HotSpringError):
            return await self.request(uri)
        return None

    async def update(self, *, refresh_identity: bool = False) -> Spa:
        """Get all spa information.

        On the initial call (or when `refresh_identity=True`), this method fetches
        the main /status endpoint concurrently with /startup, /spaConnectStatus,
        and /spamodel.

        On subsequent routine polling cycles, it queries /status and /spaConnectStatus
        concurrently, avoiding redundant radio (LoRA) queries for static identity data
        while keeping telemetry and connection status fresh.

        Args:
        ----
            refresh_identity: Force re-fetching static identity from /startup
                and /spamodel.

        Returns:
        -------
            The updated Spa data object.

        Raises:
        ------
            HotSpringError: If no data is returned from the spa.

        """
        if not self._identity_loaded or refresh_identity:
            status_res, startup_res, connect_res, model_res = await asyncio.gather(
                self.request("/status"),
                self._safe_request("/startup"),
                self._safe_request("/spaConnectStatus"),
                self._safe_request("/spamodel"),
            )

            if self.spa is None:
                self.spa = Spa(status_res)
            else:
                self.spa.update_from_dict(status_res)

            if startup_res:
                self.spa.update_info(startup_res)

            if model_res:
                self.spa.update_info(model_res)

            if connect_res:
                self.spa.update_connection_status(connect_res)

            self._identity_loaded = True
            return self.spa

        status_res, connect_res = await asyncio.gather(
            self.request("/status"),
            self._safe_request("/spaConnectStatus"),
        )

        if self.spa is None:  # Safety guard; spa is always set after cold sync
            self.spa = Spa(status_res)
        else:
            self.spa.update_from_dict(status_res)

        if connect_res:
            self.spa.update_connection_status(connect_res)

        return self.spa

    async def update_identity(self) -> SpaInfo:
        """Fetch and update static spa identity info (/startup and /spamodel).

        Returns
        -------
            The updated SpaInfo data.

        Raises
        ------
            HotSpringError: If the spa has not been initialized with update().

        """
        if self.spa is None:
            msg = "Call update() before update_identity()"
            raise HotSpringError(msg)

        startup_res, model_res = await asyncio.gather(
            self._safe_request("/startup"),
            self._safe_request("/spamodel"),
        )

        identity_data: dict[str, object] = {}
        if startup_res:
            identity_data.update(startup_res)
        if model_res:
            identity_data.update(model_res)

        if identity_data:
            self.spa.update_info(identity_data)

        self._identity_loaded = True
        return self.spa.info

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

        if self.spa is None:
            msg = "Call update() before update_connection_status()"
            raise HotSpringError(msg)

        self.spa.update_connection_status(data)
        return self.spa.connection_status

    async def _send_command(self, payload: dict[str, object]) -> None:
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
            response_data = await self.request(
                "/spaManager", method="POST", data=payload
            )
            if self.spa is not None:
                self.spa.update_from_dict(response_data)
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

    async def set_heating_mode(self, mode: str | HeatingMode) -> None:
        """Set the heating mode.

        Args:
        ----
            mode: The heating mode value. Use HeatingMode enum values or string,
                e.g. ``HeatingMode.HEAT_WITH_BOOST.value`` or ``"heatWithBoost"``.

        """
        mode_val = mode.value if isinstance(mode, HeatingMode) else str(mode)
        await self._send_command({"heater": {"control": {"heatingMode": mode_val}}})

    async def set_jet(self, jet: int, speed: str | JetSpeed) -> None:
        """Set the speed of a jet pump.

        Args:
        ----
            jet: The jet number (1-based).
            speed: The speed value. Use JetSpeed enum values or string,
                e.g. ``JetSpeed.HIGH_SPEED.value`` or ``"highSpeed"``.

        """
        speed_val = speed.value if isinstance(speed, JetSpeed) else str(speed)
        await self._send_command({"JET": {f"JET{jet}": {"control": speed_val}}})

    async def set_light_color(
        self,
        zone: int,
        color: str | LightColor,
    ) -> None:
        """Set the color of a light zone.

        Args:
        ----
            zone: The light zone number (1-based).
            color: The color value. Use LightColor enum values or string,
                e.g. ``LightColor.BLUE.value`` or ``"BLUE"``.

        """
        color_val = color.value if isinstance(color, LightColor) else str(color)
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "color": color_val.upper(),
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

    async def set_light_brightness(self, zone: int, brightness: int) -> None:
        """Set the brightness intensity of a light zone (0-5).

        Args:
        ----
            zone: The light zone number (1-based).
            brightness: The brightness level (0 = off, 1 = lowest, 5 = maximum).

        Raises:
        ------
            ValueError: If brightness is not an integer between 0 and 5.

        """
        if not 0 <= brightness <= 5:
            msg = f"Brightness must be between 0 and 5, got {brightness}"
            raise ValueError(msg)

        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "IntensityAbs": brightness,
                            }
                        }
                    }
                }
            }
        )

    async def set_light_wheel(
        self,
        zone: int,
        mode: str | LightWheelMode = LightWheelMode.ON,
    ) -> None:
        """Set the light wheel (color cycle / rainbow loop) mode for a light zone.

        Args:
        ----
            zone: The light zone number (1-based).
            mode: The light wheel mode. Use LightWheelMode enum values or string,
                e.g. ``LightWheelMode.ON.value``, ``"loopUp"``,
                ``"loopDown"``, or ``"off"``. Defaults to LightWheelMode.ON.

        """
        mode_val = mode.value if isinstance(mode, LightWheelMode) else str(mode)
        await self._send_command(
            {
                "lights": {
                    "control": {
                        f"Zone{zone}": {
                            "control": {
                                "lightWheel": mode_val,
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

        Raises:
        ------
            ValueError: If any RGB component is not between 0 and 255.

        """
        for component in (red, green, blue):
            if not 0 <= component <= 255:
                msg = (
                    f"RGB values must be between 0 and 255, "
                    f"got ({red}, {green}, {blue})"
                )
                raise ValueError(msg)

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

    async def set_spa_lock(self, *, locked: bool) -> None:
        """Lock or unlock all spa controls (Spa Lock).

        Args:
        ----
            locked: True to lock, False to unlock.

        """
        value = "on" if locked else "off"
        await self._send_command({"spaLock": {"control": value}})

    async def set_temperature_lock(self, *, locked: bool) -> None:
        """Lock or unlock the spa heater temperature setting (Temperature Lock).

        Args:
        ----
            locked: True to lock, False to unlock.

        """
        value = "on" if locked else "off"
        await self._send_command({"heater": {"control": {"temperatureLock": value}}})

    async def set_heater_lock(self, *, locked: bool) -> None:
        """Alias for set_temperature_lock."""
        await self.set_temperature_lock(locked=locked)

    async def set_vanishing_act(self, *, enabled: bool) -> None:
        """Enable or disable Vanishing Act (calcium remover cycle).

        Args:
        ----
            enabled: True to enable, False to disable.

        """
        value = "on" if enabled else "off"
        await self._send_command({"cleanCycle": {"control": {"vanishingAct": value}}})

    async def toggle_water_care_boost(self) -> None:
        """Trigger or toggle the water care chlorine boost.

        Note:
        ----
            The underlying ESP32 firmware endpoint only supports toggling
            the boost state via ``{"waterCare": {"control": {"boost": "toggle"}}}``.

        """
        await self._send_command({"waterCare": {"control": {"boost": "toggle"}}})

    async def set_water_care_boost(self) -> None:
        """Alias for toggle_water_care_boost."""
        await self.toggle_water_care_boost()

    async def set_water_care_level(self, level: int) -> None:
        """Set the salt water care cartridge output level (0-10).

        Args:
        ----
            level: The output level (0 = off/disabled, 1-10 = active output).

        Raises:
        ------
            ValueError: If level is not an integer between 0 and 10.

        """
        if not 0 <= level <= 10:
            msg = f"Water care level must be between 0 and 10, got {level}"
            raise ValueError(msg)
        await self._send_command({"waterCare": {"control": {"level": str(level)}}})

    async def set_salt_system_power(
        self,
        *,
        power_a: bool | None = None,
        power_b: bool | None = None,
    ) -> None:
        """Set the salt system power configuration states.

        Args:
        ----
            power_a: Enable or disable saltSystemPowerA, or None to leave unchanged.
            power_b: Enable or disable saltSystemPowerB, or None to leave unchanged.

        Raises:
        ------
            ValueError: If neither power_a nor power_b is specified.

        """
        cfg: dict[str, object] = {}
        if power_a is not None:
            cfg["saltSystemPowerA"] = "enable" if power_a else "disable"
        if power_b is not None:
            cfg["saltSystemPowerB"] = "enable" if power_b else "disable"
        if not cfg:
            msg = "At least one of power_a or power_b must be provided"
            raise ValueError(msg)
        await self._send_command({"waterCare": {"config": cfg}})

    async def set_logo_light(self, level: BrightnessLevel | str | int) -> None:
        """Set the brightness level of the spa logo light.

        Args:
        ----
            level: BrightnessLevel enum, integer (1-3), or string
                ("1", "2", "3", "auto").

        Raises:
        ------
            ValueError: If the brightness level is unrecognized.

        """
        brightness = (
            level
            if isinstance(level, BrightnessLevel)
            else BrightnessLevel.build(level)
        )
        if (
            brightness == BrightnessLevel.UNKNOWN
            or brightness not in _BRIGHTNESS_TO_WIRE
        ):
            msg = f"Invalid logo light brightness level: {level}"
            raise ValueError(msg)

        wire_val = _BRIGHTNESS_TO_WIRE[brightness]
        await self._send_command({"logoLight": {"control": wire_val}})

    async def set_energy_saving_schedule(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        schedule_id: int,
        *,
        enabled: bool,
        start_hour: int,
        start_minute: int,
        duration: int,
    ) -> None:
        """Configure an Energy Saving schedule (schedule 1 or 2).

        Args:
        ----
            schedule_id: Schedule number (1 or 2).
            enabled: Whether the schedule should be active.
            start_hour: Start hour in 24-hour format (0-23).
            start_minute: Start minute (0-59).
            duration: Duration in hours (1-24).

        Raises:
        ------
            ValueError: If schedule_id or time/duration parameters are invalid.

        """
        if schedule_id not in VALID_ENERGY_SAVING_SCHEDULE_IDS:
            msg = (
                f"Schedule ID must be one of {VALID_ENERGY_SAVING_SCHEDULE_IDS}, "
                f"got {schedule_id}"
            )
            raise ValueError(msg)
        if not 0 <= start_hour <= 23:
            msg = f"start_hour must be between 0 and 23, got {start_hour}"
            raise ValueError(msg)
        if not 0 <= start_minute <= 59:
            msg = f"start_minute must be between 0 and 59, got {start_minute}"
            raise ValueError(msg)
        if not 1 <= duration <= 24:
            msg = f"duration must be between 1 and 24, got {duration}"
            raise ValueError(msg)

        # Note: The ESP32 HNA firmware energySavings handler expects startHour,
        # startMinute, and duration formatted as strings in the control object.
        mode_val = "on" if enabled else "off"
        await self._send_command(
            {
                "energySavings": {
                    f"energySaving{schedule_id}": {
                        "control": {
                            "mode": mode_val,
                            "startHour": str(start_hour),
                            "startMinute": str(start_minute),
                            "duration": str(duration),
                        }
                    }
                }
            }
        )

    async def set_clean_cycle_schedule(
        self,
        *,
        enabled: bool,
        start_hour: int,
        start_minute: int,
    ) -> None:
        """Configure the recurring clean cycle timer schedule.

        Args:
        ----
            enabled: True to enable 24-hour clean cycle schedule, False to disable.
            start_hour: Start hour in 24-hour format (0-23).
            start_minute: Start minute (0-59).

        Raises:
        ------
            ValueError: If time parameters are out of range.

        """
        if not 0 <= start_hour <= 23:
            msg = f"start_hour must be between 0 and 23, got {start_hour}"
            raise ValueError(msg)
        if not 0 <= start_minute <= 59:
            msg = f"start_minute must be between 0 and 59, got {start_minute}"
            raise ValueError(msg)

        # Note: Unlike energySavings, the ESP32 HNA cleanCycleTimer endpoint
        # parses startHour and startMinute as raw integers.
        clean_timer = "enable" if enabled else "disable"
        await self._send_command(
            {
                "cleanCycleTimer": {
                    "cleanTimer": clean_timer,
                    "startHour": start_hour,
                    "startMinute": start_minute,
                }
            }
        )

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
