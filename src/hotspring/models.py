"""Models for Hot Spring Connected Spa Kit 2."""
# mypy: disable-error-code="union-attr, arg-type, call-overload, attr-defined"
# Rationale: This module parses nested JSON dicts typed as dict[str, object].
# The .get() return type is `object`, which mypy cannot narrow without runtime
# isinstance checks on every access. This is a known typing limitation for
# hand-parsed JSON; schema libraries (mashumaro, pydantic) solve this at the
# cost of an extra dependency.

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, NamedTuple

from .const import (
    BrightnessLevel,
    DeviceType,
    EnergySavingMode,
    HeatingMode,
    JetSpeed,
    JetSpeedType,
    LightColor,
    LightWheelMode,
    SpaBrand,
    SpaFailureState,
    TemperatureUnit,
    resolve_spa_model,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class Spa:
    """Object holding all information from a Hot Spring Spa.

    This is the top-level container that aggregates all sub-models
    parsed from the various API endpoints.
    """

    info: SpaInfo
    heater: Heater
    jets: dict[int, Jet]
    blower: Blower
    light_zones: dict[int, LightZone]
    logo_light: LogoLight
    clean_cycle: CleanCycle
    spa_lock: SpaLock
    water_care: WaterCare
    freshwater_iq: FreshWaterIQ
    energy_savings: dict[int, EnergySaving]
    versions: Versions
    connection_status: ConnectionStatus
    diagnostics: Diagnostics
    test_metrics: SpaTestData
    power: PowerMetrics
    system_uptime_seconds: int | None
    _status_electrical: _StatusElectrical | None

    def __init__(self, data: dict[str, object]) -> None:
        """Initialize a Spa from the API response.

        Args:
        ----
            data: The API response dict from a GET /status call.

        """
        self.heater = Heater()
        self.jets = {}
        self.blower = Blower()
        self.light_zones = {}
        self.logo_light = LogoLight()
        self.clean_cycle = CleanCycle()
        self.spa_lock = SpaLock()
        self.water_care = WaterCare()
        self.freshwater_iq = FreshWaterIQ()
        self.test_metrics = SpaTestData()
        self.power = PowerMetrics()
        self.system_uptime_seconds = None
        self.energy_savings = {}
        self.versions = Versions()
        self.info = SpaInfo()
        self.connection_status = ConnectionStatus()
        self.diagnostics = Diagnostics()
        self._status_electrical = None
        if data:
            self.update_from_dict(data)

    def update_from_dict(self, data: dict[str, object]) -> set[str]:
        """Update the Spa object from a /status response or partial command response.

        Args:
        ----
            data: The JSON response dict from GET /status or POST /spaManager.

        Returns:
        -------
            The set of updated attribute names.

        """
        updated: set[str] = set()
        prior_active = self._active_circuit_flags
        prev_power = self.power
        prev_uptime = self.system_uptime_seconds

        for section in _SECTION_PARSERS:
            if section.json_key in data and isinstance(data[section.json_key], dict):
                current = getattr(self, section.attr_name, None)
                setattr(
                    self,
                    section.attr_name,
                    section.parser(data[section.json_key], existing=current),
                )
                updated.add(section.attr_name)

        if "JET" in data and isinstance(data["JET"], dict):
            new_jets = Jet.dict_from_dict(data["JET"], existing=self.jets)
            self.jets.update(new_jets)
            updated.add("jets")

        if "lights" in data and isinstance(data["lights"], dict):
            new_zones = LightZone.dict_from_dict(
                data["lights"], existing=self.light_zones
            )
            self.light_zones.update(new_zones)
            updated.add("light_zones")

        if "energySavings" in data and isinstance(data["energySavings"], dict):
            new_schedules = EnergySaving.dict_from_dict(
                data["energySavings"], existing=self.energy_savings
            )
            self.energy_savings.update(new_schedules)
            updated.add("energy_savings")

        # Handle cleanCycleTimer (POST /spaManager command echo for the 24h clean timer)
        # Note: 'cleanCycle' key provides runtime cycle status from /status,
        # whereas 'cleanCycleTimer' provides recurring timer schedule settings.
        if "cleanCycleTimer" in data and isinstance(data["cleanCycleTimer"], dict):
            self.clean_cycle = CleanCycle.from_dict(
                data["cleanCycleTimer"], existing=self.clean_cycle
            )
            updated.add("clean_cycle")

        if "productVersions" in data and isinstance(data["productVersions"], dict):
            status = data["productVersions"].get("status", {})
            self.versions = Versions.from_dict(
                status if isinstance(status, dict) else {},
                existing=self.versions,
            )
            if self._apply_fwiq_firmware_installed():
                updated.add("freshwater_iq")
            updated.add("versions")

        self._apply_shifted_runtimes(data, updated)
        if self.system_uptime_seconds != prev_uptime:
            updated.add("system_uptime_seconds")

        next_electrical = _extract_status_electrical(data)
        if next_electrical is not None:
            self._status_electrical = next_electrical

        self._recompute_power(
            prior_active=prior_active,
            status_fresh=next_electrical is not None,
        )
        if self.power != prev_power:
            updated.add("power")

        return updated

    def update_info(self, data: dict[str, object]) -> None:
        """Update spa identity from /startup and /spamodel responses.

        Args:
        ----
            data: Combined data from /startup and /spamodel endpoints.

        """
        if not hasattr(self, "info"):
            self.info = SpaInfo.from_dict(data)
            return

        # Update existing info fields if present in data
        if "HOSTNAME" in data:
            self.info.hostname = str(data["HOSTNAME"])
        if "rootTopic" in data:
            self.info.root_topic = str(data["rootTopic"])
        if "SNAready" in data:
            self.info.sna_ready = data["SNAready"] in ("Ready", "Yes")

        if "SPAModelData" in data:
            model_data = data["SPAModelData"]
            if isinstance(model_data, dict):
                status = model_data.get("status", {})
                if isinstance(status, dict):
                    if "brandName" in status:
                        self.info.brand_id = str(status["brandName"])
                    if "collectionType" in status:
                        self.info.collection_id = str(status["collectionType"])
                    if "modelType" in status:
                        self.info.model_id = str(status["modelType"])
                    if "volume" in status:
                        self.info.volume = int(status["volume"] or 0)
                    brand, collection, model_name = resolve_spa_model(
                        self.info.brand_id, self.info.collection_id, self.info.model_id
                    )
                    self.info.brand = brand
                    self.info.brand_name = brand.value
                    self.info.collection = collection
                    self.info.model_name = model_name

    def update_connection_status(self, data: dict[str, object]) -> None:
        """Update connection status from /spaConnectStatus response.

        Args:
        ----
            data: The JSON response from GET /spaConnectStatus.

        """
        self.connection_status = ConnectionStatus.from_dict(data)

    def update_diagnostics(self, data: dict[str, object]) -> None:
        """Update diagnostics and power metrics from /addDebugData response.

        Args:
        ----
            data: The JSON response from GET /addDebugData.

        """
        self.diagnostics, debug_electrical = _parse_diagnostics_and_electrical(data)
        self._recompute_power(
            prior_active=self._active_circuit_flags,
            debug_electrical=debug_electrical,
        )

    def update_freshwater_iq(self, data: dict[str, object]) -> None:
        """Update FreshWater IQ data from /getFWIQData response.

        Args:
        ----
            data: The JSON response from GET /getFWIQData.

        """
        self.freshwater_iq = FreshWaterIQ.from_dict(data, existing=self.freshwater_iq)
        self._apply_fwiq_firmware_installed()

    def _apply_fwiq_firmware_installed(self) -> bool:
        """Ensure installed=True when FWIQFirmwareVersion is reported.

        A non-empty FWIQFirmwareVersion takes priority over FWIQinstalled from
        /getFWIQData so pre-sync responses cannot clear hardware presence.
        """
        if self.versions.fwiq and not self.freshwater_iq.installed:
            self.freshwater_iq = replace(self.freshwater_iq, installed=True)
            return True
        return False

    def _apply_shifted_runtimes(
        self, data: dict[str, object], updated: set[str]
    ) -> None:
        """Route misaligned 24-bit runtime fields to their actual components.

        Live testing shows that runtime counters in /status are shifted across
        adjacent fields: ``heaterHours`` tracks Jet 1 runtime, ``jet_1_ON_sec``
        tracks overall system uptime, ``jet_2_ON_sec`` tracks Jet 3 runtime, and
        ``jet_3_ON_sec`` tracks blower runtime.
        """
        raw_j1_on, raw_upt, raw_j3_on, raw_blower_on = _extract_raw_runtimes(data)
        present_values = [
            v for v in (raw_j1_on, raw_upt, raw_j3_on, raw_blower_on) if v is not None
        ]
        if not present_values:
            return

        is_synced = (
            bool(self.versions.control_box)
            or self.system_uptime_seconds is not None
            or any(v != 0 for v in present_values)
        )
        if not is_synced:
            return

        if raw_upt is not None:
            self.system_uptime_seconds = raw_upt
        if (
            raw_j1_on is not None
            and 1 in self.jets
            and self.jets[1].on_seconds != raw_j1_on
        ):
            self.jets[1] = replace(self.jets[1], on_seconds=raw_j1_on)
            updated.add("jets")
        if (
            raw_j3_on is not None
            and 3 in self.jets
            and self.jets[3].on_seconds != raw_j3_on
        ):
            self.jets[3] = replace(self.jets[3], on_seconds=raw_j3_on)
            updated.add("jets")
        if raw_blower_on is not None and self.blower.on_seconds != raw_blower_on:
            self.blower = replace(self.blower, on_seconds=raw_blower_on)
            updated.add("blower")

    def _recompute_power(
        self,
        *,
        prior_active: tuple[bool, bool, tuple[JetSpeed, JetSpeed, bool]],
        status_fresh: bool = False,
        debug_electrical: _DebugElectrical | None = None,
    ) -> None:
        """Reconstruct PowerMetrics from /status and paired /addDebugData words."""
        if self._status_electrical is None:
            self.power = PowerMetrics()
            return

        se = self._status_electrical
        small_loads_power = _reconstruct_u16(se.h_cur, se.j3_cur)
        if small_loads_power <= 0:
            self.power = PowerMetrics()
            return

        was_heating, was_jet3_on, prior_j12b_state = prior_active
        jet3_is_on = self._is_jet3_on
        j12b_state = self._j12b_state
        j12b_is_on = j12b_state != (JetSpeed.OFF, JetSpeed.OFF, False)
        same_j12b = j12b_is_on and j12b_state == prior_j12b_state
        de = debug_electrical

        self.power = PowerMetrics(
            supported=True,
            small_loads_power=small_loads_power,
            jet1_jet2_blower_power=_resolve_gated_metric(
                is_active=j12b_is_on,
                was_active=same_j12b,
                fresh_value=(
                    _reconstruct_u16(se.sl_cur, se.h_cur) if status_fresh else None
                ),
                previous_value=self.power.jet1_jet2_blower_power,
            ),
            heater_power=_resolve_gated_metric(
                is_active=self.heater.is_on,
                was_active=was_heating,
                fresh_value=(
                    _reconstruct_u16(se.j3_cur, de.j12p_raw) if de is not None else None
                ),
                previous_value=self.power.heater_power,
            ),
            jet3_power=_resolve_gated_metric(
                is_active=jet3_is_on,
                was_active=was_jet3_on,
                fresh_value=(
                    _reconstruct_u16(de.j12p_raw, de.slp_raw)
                    if de is not None
                    else None
                ),
                previous_value=self.power.jet3_power,
            ),
            jet1_jet2_blower_current=_resolve_gated_metric(
                is_active=j12b_is_on,
                was_active=same_j12b,
                fresh_value=(
                    _reconstruct_u16(de.l2_raw, de.hv_raw) if de is not None else None
                ),
                previous_value=self.power.jet1_jet2_blower_current,
            ),
            small_loads_current=(
                _reconstruct_u16(de.hv_raw, de.j3v_raw)
                if de is not None
                else self.power.small_loads_current
            ),
            heater_current=_resolve_gated_metric(
                is_active=self.heater.is_on,
                was_active=was_heating,
                fresh_value=(
                    _reconstruct_u16(de.j3v_raw, se.j12b_cur)
                    if de is not None
                    else None
                ),
                previous_value=self.power.heater_current,
            ),
            jet3_current=_resolve_gated_metric(
                is_active=jet3_is_on,
                was_active=was_jet3_on,
                fresh_value=(
                    _reconstruct_u16(se.j12b_cur, se.sl_cur) if status_fresh else None
                ),
                previous_value=self.power.jet3_current,
            ),
        )

    @property
    def _active_circuit_flags(
        self,
    ) -> tuple[bool, bool, tuple[JetSpeed, JetSpeed, bool]]:
        """Return active-state snapshot for (heater, jet3, jet1+jet2+blower)."""
        return (self.heater.is_on, self._is_jet3_on, self._j12b_state)

    @property
    def _is_jet3_on(self) -> bool:
        """Return True if an enabled Jet 3 is currently running."""
        return bool((jet3 := self.jets.get(3)) and jet3.is_enabled and jet3.is_on)

    @property
    def _j12b_state(self) -> tuple[JetSpeed, JetSpeed, bool]:
        """Return normalized active state of (Jet 1, Jet 2, Blower)."""
        jet1 = self.jets.get(1)
        jet2 = self.jets.get(2)
        return (
            jet1.speed if jet1 is not None and jet1.is_on else JetSpeed.OFF,
            jet2.speed if jet2 is not None and jet2.is_on else JetSpeed.OFF,
            self.blower.is_on,
        )

    @property
    def system_uptime_hours(self) -> float | None:
        """Return system uptime in hours when available."""
        if self.system_uptime_seconds is None:
            return None
        return round(self.system_uptime_seconds / 3600.0, 2)

    @property
    def needs_diagnostics_for_power(self) -> bool:
        """Return True when /addDebugData is needed for active power readings."""
        return self.power.supported and (self.heater.is_on or self._is_jet3_on)

    @property
    def is_hna(self) -> bool:
        """Return True if this device is the Home Network Adapter (HNA)."""
        return self.info.sna_ready or bool(getattr(self.versions, "control_box", ""))

    @property
    def device_type(self) -> DeviceType:
        """Determine whether the device is an HNA or SNA."""
        if not self.info.hostname:
            return DeviceType.UNKNOWN
        return DeviceType.HNA if self.is_hna else DeviceType.SNA


@dataclass
class SpaInfo:
    """Spa identity and configuration information.

    Populated from the /startup and /spamodel endpoints.
    """

    hostname: str = ""
    root_topic: str = ""
    sna_ready: bool = False
    brand: SpaBrand = SpaBrand.UNKNOWN
    brand_name: str = SpaBrand.UNKNOWN.value
    collection: str = "Unknown"
    model_name: str = "Unknown"
    brand_id: str = ""
    collection_id: str = ""
    model_id: str = ""
    volume: int = 0

    @property
    def collection_type(self) -> str:
        """Alias for collection_id for backward compatibility."""
        return self.collection_id

    @property
    def model_type(self) -> str:
        """Alias for model_id for backward compatibility."""
        return self.model_id

    @staticmethod
    def from_dict(data: dict[str, object]) -> SpaInfo:
        """Create a SpaInfo from API response data.

        Args:
        ----
            data: Combined data from /startup and /spamodel.

        Returns:
        -------
            A SpaInfo instance.

        """
        model_status: dict[str, object] = {}
        model_data = data.get("SPAModelData")
        if isinstance(model_data, dict):
            status = model_data.get("status")
            if isinstance(status, dict):
                model_status = status

        brand_id = str(model_status.get("brandName", ""))
        collection_id = str(model_status.get("collectionType", ""))
        model_id = str(model_status.get("modelType", ""))
        brand, collection, model_name = resolve_spa_model(
            brand_id, collection_id, model_id
        )

        return SpaInfo(
            hostname=str(data.get("HOSTNAME", "")),
            root_topic=str(data.get("rootTopic", "")),
            sna_ready=data.get("SNAready", "") in ("Ready", "Yes"),
            brand=brand,
            brand_name=brand.value,
            collection=collection,
            model_name=model_name,
            brand_id=brand_id,
            collection_id=collection_id,
            model_id=model_id,
            volume=int(model_status.get("volume") or 0),
        )

    @property
    def mac_address(self) -> str:
        """Derive the MAC address from root_topic.

        The HNA firmware builds root_topic as ``mySpa%02X%02X%02X%02X%02X%02X``
        using the device's 6-byte WiFi MAC, so the 12 hex characters after the
        ``mySpa`` prefix are the full MAC address.

        Returns
        -------
            Colon-separated uppercase MAC (e.g. ``"AA:BB:CC:11:22:33"``),
            or ``""`` if root_topic does not match the expected format.

        """
        prefix = "mySpa"
        if not self.root_topic.startswith(prefix):
            return ""
        mac_hex = self.root_topic[len(prefix) :]
        try:
            mac_bytes = bytes.fromhex(mac_hex)
        except ValueError:
            return ""
        if len(mac_bytes) != 6:
            return ""
        return ":".join(f"{b:02X}" for b in mac_bytes)

    @property
    def device_type(self) -> DeviceType:
        """Determine whether the device is an HNA or SNA.

        Only the HNA can report 'SNAready' as 'Yes'; the SNA firmware always
        reports 'No'. The hostname/rootTopic MAC suffixes cannot be used,
        since rootTopic is built from the higher of the two adapter MACs.

        Returns
        -------
            DeviceType.UNKNOWN if /startup data is missing,
            DeviceType.HNA if sna_ready is True, otherwise DeviceType.SNA.

        """
        if not self.hostname:
            return DeviceType.UNKNOWN
        return DeviceType.HNA if self.sna_ready else DeviceType.SNA

    @property
    def is_hna(self) -> bool:
        """Return True if this device is the Home Network Adapter (HNA)."""
        return self.sna_ready


@dataclass
class Heater:
    """Heater status and configuration."""

    is_on: bool = False
    heater_lock: bool = False
    heatpump_installed: bool = False
    heating_mode: HeatingMode = HeatingMode.UNKNOWN
    set_temperature: float | None = None
    current_temperature: float | None = None
    temperature_unit: TemperatureUnit = TemperatureUnit.UNKNOWN

    @staticmethod
    def from_dict(data: dict[str, object], existing: Heater | None = None) -> Heater:
        """Create a Heater from API response data.

        Args:
        ----
            data: The ``heater`` dict from the /status response.
            existing: Optional existing Heater instance to preserve cached fields.

        Returns:
        -------
            A Heater instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            kwargs.update(_parse_heater_status(status))

        control = data.get("control")
        if isinstance(control, dict):
            kwargs.update(_parse_heater_control(control))

        base = existing or Heater()
        return replace(base, **kwargs)


@dataclass
class Jet:
    """Status and configuration for a single jet pump."""

    jet_id: int
    speed: JetSpeed = JetSpeed.OFF
    speed_type: JetSpeedType = JetSpeedType.UNKNOWN
    is_enabled: bool = True
    concurrent_mode: bool = False
    on_seconds: int | None = None

    @property
    def is_available(self) -> bool:
        """Return True if the jet is available on the spa."""
        return self.is_enabled

    @property
    def is_on(self) -> bool:
        """Return True if the jet pump is currently running."""
        return self.speed not in (JetSpeed.OFF, JetSpeed.UNKNOWN)

    @property
    def is_single_speed(self) -> bool:
        """Return True if the jet is configured as single-speed."""
        return self.speed_type == JetSpeedType.SINGLE_SPEED

    @property
    def is_dual_speed(self) -> bool:
        """Return True if the jet is configured as dual-speed."""
        return self.speed_type == JetSpeedType.DUAL_SPEED

    @property
    def supported_speeds(self) -> list[JetSpeed]:
        """Return the list of supported speeds for this jet."""
        if not self.is_enabled:
            return [JetSpeed.OFF]
        if self.is_dual_speed:
            return [JetSpeed.OFF, JetSpeed.LOW_SPEED, JetSpeed.HIGH_SPEED]
        return [JetSpeed.OFF, JetSpeed.HIGH_SPEED]

    @property
    def on_hours(self) -> float | None:
        """Return cumulative jet runtime in hours when available."""
        if self.on_seconds is None:
            return None
        return round(self.on_seconds / 3600.0, 2)

    @staticmethod
    def from_dict(
        jet_id: int,
        data: dict[str, object],
        existing: Jet | None = None,
    ) -> Jet:
        """Create a Jet from API response data.

        Args:
        ----
            jet_id: The jet number (1-based).
            data: The ``JETn`` dict from the /status response.
            existing: Optional existing Jet instance to preserve cached fields.

        Returns:
        -------
            A Jet instance.

        """
        kwargs: dict[str, object] = {}
        config = data.get("config")
        if isinstance(config, dict):
            kwargs["is_enabled"] = config.get(f"JET{jet_id}", "enable") != "disable"
            if "speed" in config:
                kwargs["speed_type"] = JetSpeedType.build(config.get("speed"))
            elif jet_id == 3 and kwargs["is_enabled"]:
                # Jet 3 hardware is fixed single-speed if enabled
                kwargs["speed_type"] = JetSpeedType.SINGLE_SPEED
            if "concurrent" in config:
                kwargs["concurrent_mode"] = (
                    config.get("concurrent", "disable") != "disable"
                )

        status = data.get("status")
        if isinstance(status, dict) and "speed" in status:
            kwargs["speed"] = JetSpeed.build(status["speed"])

        control = data.get("control")
        if isinstance(control, str):
            speed = JetSpeed.build(control)
            if speed != JetSpeed.UNKNOWN:
                kwargs["speed"] = speed
        elif isinstance(control, dict) and "speed" in control:
            speed = JetSpeed.build(control["speed"])
            if speed != JetSpeed.UNKNOWN:
                kwargs["speed"] = speed

        base = existing or Jet(jet_id=jet_id)
        return replace(base, **kwargs)

    @staticmethod
    def dict_from_dict(
        data: dict[str, object],
        existing: dict[int, Jet] | None = None,
    ) -> dict[int, Jet]:
        """Parse all jets from the JET section of the /status response.

        Args:
        ----
            data: The ``JET`` dict from the /status response.
            existing: Optional existing dict of Jet instances for field preservation.

        Returns:
        -------
            A dict of Jet instances keyed by jet ID.

        """
        if "control" in data and isinstance(data["control"], dict):
            data = data["control"]
        existing_map = existing or {}
        jets: dict[int, Jet] = {}
        for key, value in data.items():
            if key.upper().startswith("JET") and isinstance(value, dict):
                try:
                    jet_id = int(key[3:])
                except ValueError:
                    continue
                jets[jet_id] = Jet.from_dict(
                    jet_id, value, existing=existing_map.get(jet_id)
                )
        return jets


@dataclass
class Blower:
    """Blower status and configuration."""

    is_enabled: bool = False
    is_on: bool = False
    on_seconds: int | None = None

    @property
    def on_hours(self) -> float | None:
        """Return cumulative blower runtime in hours when available."""
        if self.on_seconds is None:
            return None
        return round(self.on_seconds / 3600.0, 2)

    @staticmethod
    def from_dict(data: dict[str, object], existing: Blower | None = None) -> Blower:
        """Create a Blower from API response data.

        Args:
        ----
            data: The ``blower`` dict from the /status response.
            existing: Optional existing Blower instance to preserve cached fields.

        Returns:
        -------
            A Blower instance.

        """
        kwargs: dict[str, object] = {}
        config = data.get("config")
        if isinstance(config, dict) and "blower" in config:
            kwargs["is_enabled"] = config["blower"] != "disable"

        status = data.get("status")
        if isinstance(status, dict) and "blower" in status:
            kwargs["is_on"] = status["blower"] not in ("off", "disable")

        control = data.get("control")
        if isinstance(control, str):
            kwargs["is_on"] = _is_truthy(control)
        elif isinstance(control, dict) and "blower" in control:
            raw_blower = control["blower"]
            if raw_blower is not None:
                kwargs["is_on"] = _is_truthy(raw_blower)

        base = existing or Blower()
        return replace(base, **kwargs)


@dataclass
class LightZone:
    """Status and configuration for a single light zone."""

    zone_id: int
    is_enabled: bool = False
    is_on: bool = False
    color: LightColor = LightColor.UNKNOWN
    light_wheel: LightWheelMode = LightWheelMode.OFF
    intensity: int = 0
    loop_speed: int = 0
    c_red: int = 0
    c_green: int = 0
    c_blue: int = 0
    rgb_state: str = "inactive"

    @staticmethod
    def from_dict(
        zone_id: int,
        data: dict[str, object],
        existing: LightZone | None = None,
    ) -> LightZone:
        """Create a LightZone from API response data.

        Args:
        ----
            zone_id: The zone number (1-based).
            data: The ``zoneN`` dict from the /status response.
            existing: Optional existing LightZone instance to preserve cached fields.

        Returns:
        -------
            A LightZone instance.

        """
        kwargs: dict[str, object] = {}
        config = data.get("config")
        if isinstance(config, dict):
            kwargs["is_enabled"] = config.get(f"zone_{zone_id}", "disable") != "disable"

        status = data.get("status")
        if isinstance(status, dict):
            kwargs.update(_parse_light_zone_status(status))

        control = data.get("control")
        if isinstance(control, dict):
            kwargs.update(_parse_light_zone_control(control))

        base = existing or LightZone(zone_id=zone_id)
        merged_rgb_state = kwargs.get("rgb_state", base.rgb_state)
        r = kwargs.get("c_red", base.c_red)
        g = kwargs.get("c_green", base.c_green)
        b = kwargs.get("c_blue", base.c_blue)
        if merged_rgb_state == "active" and (r, g, b) != (0, 0, 0):
            kwargs["color"] = LightColor.CUSTOM

        return replace(base, **kwargs)

    @staticmethod
    def dict_from_dict(
        data: dict[str, object],
        existing: dict[int, LightZone] | None = None,
    ) -> dict[int, LightZone]:
        """Parse all light zones from the lights section.

        Args:
        ----
            data: The ``lights`` dict from the /status response.
            existing: Optional existing dict of LightZone instances.

        Returns:
        -------
            A dict of LightZone instances keyed by zone ID.

        """
        if "control" in data and isinstance(data["control"], dict):
            data = data["control"]
        existing_map = existing or {}
        zones: dict[int, LightZone] = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower.startswith("zone") and isinstance(value, dict):
                try:
                    zone_id = int(key_lower[4:])
                except ValueError:
                    continue
                zones[zone_id] = LightZone.from_dict(
                    zone_id, value, existing=existing_map.get(zone_id)
                )
        return zones


@dataclass
class LogoLight:
    """Logo light status."""

    brightness: BrightnessLevel = BrightnessLevel.UNKNOWN

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: LogoLight | None = None
    ) -> LogoLight:
        """Create a LogoLight from API response data.

        Args:
        ----
            data: The ``logoLight`` dict from the /status response.
            existing: Optional existing LogoLight instance to preserve cached fields.

        Returns:
        -------
            A LogoLight instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict) and "brightness" in status:
            kwargs["brightness"] = BrightnessLevel.build(status.get("brightness"))

        control = data.get("control")
        if isinstance(control, dict) and "brightness" in control:
            brightness = BrightnessLevel.build(control.get("brightness"))
            if brightness != BrightnessLevel.UNKNOWN:
                kwargs["brightness"] = brightness
        elif isinstance(control, str):
            brightness = BrightnessLevel.build(control)
            if brightness != BrightnessLevel.UNKNOWN:
                kwargs["brightness"] = brightness

        base = existing or LogoLight()
        return replace(base, **kwargs)


@dataclass
class CleanCycle:
    """Clean cycle status and configuration."""

    is_enabled: bool = False
    vanishing_act: bool = False
    clean_timer_enabled: bool = False
    start_hour: int = 0
    start_minute: int = 0

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: CleanCycle | None = None
    ) -> CleanCycle:
        """Create a CleanCycle from API response data.

        Args:
        ----
            data: The ``cleanCycle`` or ``cleanCycleTimer`` dict from the API.
            existing: Optional existing CleanCycle instance to preserve cached fields.

        Returns:
        -------
            A CleanCycle instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            kwargs.update(_parse_clean_cycle_status(status))

        config = data.get("config")
        if isinstance(config, dict) and "twentyFourHourTimer" in config:
            kwargs["clean_timer_enabled"] = (
                config.get("twentyFourHourTimer", "disable") != "disable"
            )

        control = data.get("control")
        if isinstance(control, (dict, str)):
            kwargs.update(_parse_clean_cycle_control(control))

        kwargs.update(_parse_clean_cycle_timer(data))

        base = existing or CleanCycle()
        return replace(base, **kwargs)


@dataclass
class SpaLock:
    """Spa lock status."""

    is_locked: bool = False

    @staticmethod
    def from_dict(data: dict[str, object], existing: SpaLock | None = None) -> SpaLock:
        """Create a SpaLock from API response data.

        Args:
        ----
            data: The ``spaLock`` dict from the /status response.
            existing: Optional existing SpaLock instance to preserve cached fields.

        Returns:
        -------
            A SpaLock instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict) and "spaLock" in status:
            kwargs["is_locked"] = status.get("spaLock", "off") not in (
                "off",
                "disable",
            )

        control = data.get("control")
        if isinstance(control, dict) and "spaLock" in control:
            raw_lock = control.get("spaLock")
            if raw_lock is not None:
                kwargs["is_locked"] = _is_truthy(raw_lock)
        elif isinstance(control, str):
            kwargs["is_locked"] = _is_truthy(control)

        base = existing or SpaLock()
        return replace(base, **kwargs)


@dataclass
class WaterCare:  # pylint: disable=too-many-instance-attributes
    """Water care / salt system status."""

    cartridge_installed: bool = False
    ten_day_timer: int = 0
    one_twenty_day_timer: int = 0
    level: int = 0
    system_enabled: bool = False
    power_a: bool = False
    power_b: bool = False
    ace_mode: str = "inactive"
    boost_active: bool = False
    salt_value: int = 0

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: WaterCare | None = None
    ) -> WaterCare:
        """Create a WaterCare from API response data.

        Args:
        ----
            data: The ``waterCare`` dict from the /status response.
            existing: Optional existing WaterCare instance to preserve cached fields.

        Returns:
        -------
            A WaterCare instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            kwargs.update(_parse_water_care_status(status))

        config = data.get("config")
        if isinstance(config, dict):
            kwargs.update(_parse_water_care_config(config))

        control = data.get("control")
        if isinstance(control, dict):
            kwargs.update(_parse_water_care_control(control))

        base = existing or WaterCare()
        return replace(base, **kwargs)


@dataclass
class FreshWaterIQ:
    """FreshWater IQ water quality sensor data.

    Sensor reading fields are ``None`` when no valid measurement is available
    (sensor not installed, ``-1`` firmware sentinel, or pre-sync all-zero state).
    """

    conductivity: int | None = None
    orp: int | None = None
    chlorine: float | None = None
    ph: float | None = None
    sensor_life_percentage: float | None = None
    installed: bool = False
    system_enabled: bool = False
    cl_calibration_factor: float | None = None
    ph_calibration_factor: float | None = None
    regional_cl_selection: str = ""

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: FreshWaterIQ | None = None
    ) -> FreshWaterIQ:
        """Create a FreshWaterIQ from API response data.

        Handles two response formats:
        - ``FWIQ_Parameters`` from /status (flat keys)
        - ``waterCare.status.FWIQstatus`` from /getFWIQData (nested)

        Args:
        ----
            data: Data from either source.
            existing: Optional existing FreshWaterIQ instance to preserve cached fields.

        Returns:
        -------
            A FreshWaterIQ instance.

        """
        base = existing or FreshWaterIQ()

        # Handle the nested /getFWIQData format
        water_care = data.get("waterCare")
        fwiq = None
        if isinstance(water_care, dict):
            status = water_care.get("status")
            if isinstance(status, dict):
                fwiq_status = status.get("FWIQstatus")
                if isinstance(fwiq_status, dict):
                    fwiq = fwiq_status

        if fwiq is not None:
            return replace(base, **_parse_fwiq_status(fwiq))

        # Handle the flat /status FWIQ_Parameters format
        kwargs = _parse_fwiq_parameters(data)
        return replace(base, **kwargs)


@dataclass
class EnergySaving:
    """Energy saving schedule configuration."""

    schedule_id: int
    mode: int = 0
    start_hour: int = 0
    start_minute: int = 0
    duration: int = 0

    @property
    def is_enabled(self) -> bool:
        """Return True if the energy saving schedule is active."""
        return self.mode == 1

    @property
    def saving_mode(self) -> EnergySavingMode:
        """Return the EnergySavingMode enum representation."""
        return EnergySavingMode.build(self.mode)

    @staticmethod
    def from_dict(
        schedule_id: int,
        data: dict[str, object],
        existing: EnergySaving | None = None,
    ) -> EnergySaving:
        """Create an EnergySaving from API response data.

        Args:
        ----
            schedule_id: The schedule number (1-based).
            data: The ``energySavingN`` dict from the /status response.
            existing: Optional existing EnergySaving instance to preserve cached fields.

        Returns:
        -------
            An EnergySaving instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            kwargs.update(_parse_energy_saving_status(status))

        control = data.get("control")
        if isinstance(control, dict):
            kwargs.update(_parse_energy_saving_control(control))

        base = existing or EnergySaving(schedule_id=schedule_id)
        return replace(base, **kwargs)

    @staticmethod
    def dict_from_dict(
        data: dict[str, object],
        existing: dict[int, EnergySaving] | None = None,
    ) -> dict[int, EnergySaving]:
        """Parse all energy saving schedules from the /status response.

        Args:
        ----
            data: The ``energySavings`` dict from the /status response.
            existing: Optional existing dict of EnergySaving instances
                for field preservation.

        Returns:
        -------
            A dict of EnergySaving instances keyed by schedule ID.

        """
        items = (
            data["control"]
            if "control" in data and isinstance(data["control"], dict)
            else data
        )
        existing_map = existing or {}
        schedules: dict[int, EnergySaving] = {}
        for key, value in items.items():
            if key.startswith("energySaving") and isinstance(value, dict):
                try:
                    schedule_id = int(key[12:])
                except ValueError:
                    continue
                schedules[schedule_id] = EnergySaving.from_dict(
                    schedule_id, value, existing=existing_map.get(schedule_id)
                )
        return schedules


@dataclass
class Versions:  # pylint: disable=too-many-instance-attributes
    """Firmware versions for all spa sub-components."""

    control_box: str = ""
    control_panel: str = ""
    fwss: str = ""
    fwiq: str = ""
    btxr: str = ""
    cool_zone: str = ""
    wifi_dongle: str = ""
    amp: str = ""
    dosing: str = ""
    logolight: str = ""

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: Versions | None = None
    ) -> Versions:
        """Create a Versions from API response data.

        Args:
        ----
            data: The ``productVersions.status`` dict from /status
                or from GET /versions.
            existing: Optional existing Versions instance to preserve cached fields.

        Returns:
        -------
            A Versions instance.

        """
        key_map = {
            "ControlBoxFirmwareVersion": "control_box",
            "ControlPanelFirmwareVersion": "control_panel",
            "FWSSFirmwareVersion": "fwss",
            "FWIQFirmwareVersion": "fwiq",
            "BTXRFirmwareVersion": "btxr",
            "CoolZoneFirmwareVersion": "cool_zone",
            "WiFiDongleVersion": "wifi_dongle",
            "AMPFirmwareVersion": "amp",
            "DosingFirmwareVersion": "dosing",
            "LogolightFirmwareVersion": "logolight",
        }
        kwargs: dict[str, object] = {}
        for json_key, attr in key_map.items():
            if json_key in data:
                kwargs[attr] = str(data[json_key])

        base = existing or Versions()
        return replace(base, **kwargs)


@dataclass
class ConnectionStatus:
    """Connection status between the HNA, SNA, and cloud."""

    spa_connected: bool = False

    @staticmethod
    def from_dict(data: dict[str, object]) -> ConnectionStatus:
        """Create a ConnectionStatus from API response data.

        The real API returns ``{"spaConnectStatus": "true"}`` as a single
        field, not separate cloud/sna booleans.

        Args:
        ----
            data: The JSON response from GET /spaConnectStatus.

        Returns:
        -------
            A ConnectionStatus instance.

        """
        raw = data.get("spaConnectStatus", "false")
        connected = str(raw).lower() in ("true", "1")
        return ConnectionStatus(spa_connected=connected)


@dataclass
class PowerMetrics:  # pylint: disable=too-many-instance-attributes
    """Reconstructed electrical power and current telemetry.

    On IQ2020/Eagle control boards equipped with current-sensing hardware,
    power readings reflect apparent power (``V_rms * I_rms`` in VA, equal to
    real Watts for the resistive heater and within ~1-25% of real Watts on
    pump motors depending on power factor). On entry-level control boards
    without current sensors or before initial controller sync, ``supported``
    is ``False`` and all reading fields remain ``None``.
    """

    supported: bool = False
    small_loads_power: int | None = None
    jet1_jet2_blower_power: int | None = None
    heater_power: int | None = None
    jet3_power: int | None = None
    jet1_jet2_blower_current: int | None = None
    small_loads_current: int | None = None
    heater_current: int | None = None
    jet3_current: int | None = None

    @property
    def total_power(self) -> int | None:
        """Return combined power across all four spa circuits when known."""
        if (
            not self.supported
            or self.small_loads_power is None
            or self.jet1_jet2_blower_power is None
            or self.heater_power is None
            or self.jet3_power is None
        ):
            return None
        return (
            self.small_loads_power
            + self.jet1_jet2_blower_power
            + self.heater_power
            + self.jet3_power
        )


@dataclass
class SpaTestData:
    """Factory calibration and test-status values from the spa."""

    heater_test_status: str = "off"
    temp_offset: float = 0.0
    vsense_cal: float = 0.0

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: SpaTestData | None = None
    ) -> SpaTestData:
        """Create a SpaTestData from API response data.

        Args:
        ----
            data: The ``test_data`` dict from the /status response.
            existing: Optional existing SpaTestData instance to preserve cached fields.

        Returns:
        -------
            A SpaTestData instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            if "heaterTestStatus" in status:
                kwargs["heater_test_status"] = str(status["heaterTestStatus"])
            if "tempOffset" in status:
                kwargs["temp_offset"] = float(status["tempOffset"])
            if "VsenseCal" in status:
                kwargs["vsense_cal"] = float(status["VsenseCal"])

        base = existing or SpaTestData()
        return replace(base, **kwargs)


@dataclass
class Diagnostics:  # pylint: disable=too-many-instance-attributes
    """Hardware diagnostic status flags and filter settings from /addDebugData."""

    spa_failure_state: SpaFailureState = SpaFailureState.UNKNOWN
    heater_error: str = "0"
    power_frequency: str = "0"
    pressure_switch_status: str = "0"
    circulation_pump_flow_status: str = "0"
    regulation_thermistor_temp_status: str = "0"
    limit_thermistor_status: str = "0"
    l2_voltage_above_256v: bool | None = None
    jet3_volts: int | None = None
    daily_clean_cycle: int | None = None
    filter_1_minutes: int | None = None
    filter_2_minutes: int | None = None

    @staticmethod
    def from_dict(data: dict[str, object]) -> Diagnostics:
        """Create a Diagnostics from API response data.

        Args:
        ----
            data: The JSON response from GET /addDebugData, or an empty
                dict for default values.

        Returns:
        -------
            A Diagnostics instance.

        """
        diagnostics, _ = _parse_diagnostics_and_electrical(data)
        return diagnostics


@dataclass(frozen=True)
class _StatusElectrical:
    """Raw 16-bit electrical words carried in /status."""

    j12b_cur: int = 0
    sl_cur: int = 0
    h_cur: int = 0
    j3_cur: int = 0


@dataclass(frozen=True)
class _DebugElectrical:
    """Raw 16-bit electrical words carried in /addDebugData."""

    l2_raw: int = 0
    hv_raw: int = 0
    j3v_raw: int = 0
    j12p_raw: int = 0
    slp_raw: int = 0


def _reconstruct_u16(low_word: int, high_word: int) -> int:
    """Reconstruct a 16-bit register split across two adjacent misaligned words.

    Live load testing shows an alignment bug in the HNA's JSON output where
    adjacent 16-bit values are shifted by one byte: ``low_word`` holds the
    register's low byte in bits 8..15, and ``high_word`` holds its high byte
    in bits 0..7.
    """
    return ((high_word & 0xFF) << 8) | ((low_word >> 8) & 0xFF)


def _decode_runtime_seconds(raw: object) -> int:
    """Decode a 24-bit runtime counter shifted by 8 bits into signed 32-bit JSON.

    Runtime counters are left-shifted by 8 bits and formatted as signed 32-bit
    integers, wrapping negative past ~97.1 days. Masking with ``0xFFFFFFFF``
    and shifting right by 8 recovers elapsed whole seconds.
    """
    raw_int: int = int(raw)
    return (raw_int & 0xFFFFFFFF) >> 8


def _find_jet_status(jets_data: dict[str, object], jet_id: int) -> dict[str, object]:
    """Return the status dict for ``JET<jet_id>`` (case-insensitive), or empty dict."""
    target = f"JET{jet_id}"
    source = (
        jets_data["control"]
        if "control" in jets_data and isinstance(jets_data["control"], dict)
        else jets_data
    )
    for key, value in source.items():
        if key.upper() == target and isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, dict):
                return status
    return {}


def _extract_raw_runtimes(
    data: dict[str, object],
) -> tuple[int | None, int | None, int | None, int | None]:
    """Extract decoded runtime counters from /status sections when present."""
    raw_j1_on: int | None = None
    raw_upt: int | None = None
    raw_j3_on: int | None = None
    raw_blower_on: int | None = None

    heater = data.get("heater")
    if isinstance(heater, dict):
        h_status = heater.get("status")
        if isinstance(h_status, dict) and "heaterHours" in h_status:
            raw_j1_on = _decode_runtime_seconds(h_status["heaterHours"])

    jets = data.get("JET")
    if isinstance(jets, dict):
        j1_status = _find_jet_status(jets, 1)
        if "jet_1_ON_sec" in j1_status:
            raw_upt = _decode_runtime_seconds(j1_status["jet_1_ON_sec"])

        j2_status = _find_jet_status(jets, 2)
        if "jet_2_ON_sec" in j2_status:
            raw_j3_on = _decode_runtime_seconds(j2_status["jet_2_ON_sec"])

        j3_status = _find_jet_status(jets, 3)
        if "jet_3_ON_sec" in j3_status:
            raw_blower_on = _decode_runtime_seconds(j3_status["jet_3_ON_sec"])

    return raw_j1_on, raw_upt, raw_j3_on, raw_blower_on


_TD_ELECTRICAL_KEYS: tuple[str, ...] = (
    "jet1+jet2+blowerCurrent",
    "smallLoadsCurrent",
    "heaterCurrent",
    "jet3Current",
)


def _extract_status_electrical(data: dict[str, object]) -> _StatusElectrical | None:
    """Extract a complete 4-word electrical block from /status when present.

    Standalone ``heaterCurrent`` or ``JET3.status.current`` fields in partial
    command echoes are validated as integers, while ``_StatusElectrical`` is
    only updated when ``test_data.status`` carries all four contiguous words so
    adjacent bytes are never paired across different polls.
    """
    heater = data.get("heater")
    if isinstance(heater, dict):
        h_status = heater.get("status")
        if isinstance(h_status, dict) and "heaterCurrent" in h_status:
            int(h_status["heaterCurrent"])

    jets = data.get("JET")
    if isinstance(jets, dict):
        j3_status = _find_jet_status(jets, 3)
        if "current" in j3_status:
            int(j3_status["current"])

    test_data = data.get("test_data")
    if not isinstance(test_data, dict):
        return None
    td_status = test_data.get("status")
    if not isinstance(td_status, dict) or not all(
        key in td_status for key in _TD_ELECTRICAL_KEYS
    ):
        return None

    return _StatusElectrical(
        j12b_cur=int(td_status["jet1+jet2+blowerCurrent"]),
        sl_cur=int(td_status["smallLoadsCurrent"]),
        h_cur=int(td_status["heaterCurrent"]),
        j3_cur=int(td_status["jet3Current"]),
    )


_DEBUG_STR_KEYS: dict[str, str] = {
    "heaterError": "heater_error",
    "powerFrequency": "power_frequency",
    "pressureSwitchStatus": "pressure_switch_status",
    "circulationPumpFlowStatus": "circulation_pump_flow_status",
    "regulationThermistorTempStatus": "regulation_thermistor_temp_status",
    "limitThermistorStatus": "limit_thermistor_status",
}

_DEBUG_INT_KEYS: tuple[str, ...] = (
    "L1_N_Volts",
    "L2_N_Volts",
    "Heater_Volts",
    "jet3_Volts",
    "jet1_jet2_blowerPower",
    "smallLoadsPower",
    "heaterPower",
    "jet3Power",
)


def _resolve_gated_metric(
    *,
    is_active: bool,
    was_active: bool,
    fresh_value: int | None,
    previous_value: int | None,
) -> int | None:
    """Resolve an active-gated metric without tearing across asynchronous polls."""
    if not is_active:
        return 0
    if fresh_value is not None:
        return fresh_value
    if was_active:
        return previous_value
    return None


def _decode_synced_diagnostics_fields(parsed_ints: dict[str, int]) -> dict[str, object]:
    """Extract decoded voltage, clean-cycle, and filter fields from /addDebugData."""
    decoded: dict[str, object] = {}
    if "L1_N_Volts" in parsed_ints:
        l1_raw = parsed_ints["L1_N_Volts"]
        decoded["l2_voltage_above_256v"] = bool(l1_raw & 0xFF)
        if "L2_N_Volts" in parsed_ints:
            decoded["jet3_volts"] = _reconstruct_u16(l1_raw, parsed_ints["L2_N_Volts"])
    if "smallLoadsPower" in parsed_ints:
        decoded["daily_clean_cycle"] = (parsed_ints["smallLoadsPower"] >> 8) & 0xFF
    if "heaterPower" in parsed_ints:
        decoded["filter_1_minutes"] = parsed_ints["heaterPower"]
    if "jet3Power" in parsed_ints:
        decoded["filter_2_minutes"] = parsed_ints["jet3Power"]
    return decoded


def _parse_diagnostics_and_electrical(
    data: dict[str, object],
) -> tuple[Diagnostics, _DebugElectrical | None]:
    """Parse /addDebugData into Diagnostics and raw electrical words."""
    debug_data = data.get("debugData")
    if not isinstance(debug_data, dict):
        return Diagnostics(), None

    debug = debug_data.get("status")
    if not isinstance(debug, dict) or not debug:
        return Diagnostics(), None

    str_fields = {
        attr: str(debug[json_key])
        for json_key, attr in _DEBUG_STR_KEYS.items()
        if json_key in debug
    }
    parsed_ints = {
        json_key: int(debug[json_key])
        for json_key in _DEBUG_INT_KEYS
        if json_key in debug
    }

    raw_failure = debug.get("spaFailureState")
    has_fault = raw_failure is not None and str(raw_failure) not in ("", "Spa_Ok")
    is_synced = (
        has_fault
        or any(v != "0" for v in str_fields.values())
        or any(v != 0 for v in parsed_ints.values())
    )
    if not is_synced:
        return Diagnostics(), None

    kwargs: dict[str, object] = dict(str_fields)
    if "spaFailureState" in debug:
        kwargs["spa_failure_state"] = SpaFailureState.build(raw_failure)
    kwargs.update(_decode_synced_diagnostics_fields(parsed_ints))

    debug_elec = _DebugElectrical(
        l2_raw=parsed_ints.get("L2_N_Volts", 0),
        hv_raw=parsed_ints.get("Heater_Volts", 0),
        j3v_raw=parsed_ints.get("jet3_Volts", 0),
        j12p_raw=parsed_ints.get("jet1_jet2_blowerPower", 0),
        slp_raw=parsed_ints.get("smallLoadsPower", 0),
    )
    return replace(Diagnostics(), **kwargs), debug_elec


class _SectionParser(NamedTuple):
    """Mapping between JSON response key, Spa attribute name, and parser callable."""

    json_key: str
    attr_name: str
    parser: Callable[..., object]


_SECTION_PARSERS: tuple[_SectionParser, ...] = (
    _SectionParser("heater", "heater", Heater.from_dict),
    _SectionParser("blower", "blower", Blower.from_dict),
    _SectionParser("logoLight", "logo_light", LogoLight.from_dict),
    _SectionParser("cleanCycle", "clean_cycle", CleanCycle.from_dict),
    _SectionParser("spaLock", "spa_lock", SpaLock.from_dict),
    _SectionParser("waterCare", "water_care", WaterCare.from_dict),
    _SectionParser("FWIQ_Parameters", "freshwater_iq", FreshWaterIQ.from_dict),
    _SectionParser("test_data", "test_metrics", SpaTestData.from_dict),
)


def _is_truthy(value: object) -> bool:
    """Return True if a string or raw value represents an enabled/truthy state."""
    if value is None or value is False:
        return False
    return str(value).strip().lower() not in (
        "off",
        "disable",
        "false",
        "0",
        "inactive",
        "",
        "none",
        "null",
    )


def _parse_heater_temperatures(status: dict[str, object]) -> dict[str, object]:
    """Parse temperature and unit fields for the heater."""
    kwargs: dict[str, object] = {}
    if "setWaterTemperature" in status:
        parsed_temp = _parse_temperature(status.get("setWaterTemperature"))
        if parsed_temp is not None:
            kwargs["set_temperature"] = parsed_temp
    if "currentWaterTemperature" in status:
        parsed_current = _parse_temperature(status.get("currentWaterTemperature"))
        if parsed_current is not None:
            kwargs["current_temperature"] = parsed_current
    if "temperatureUnit" in status:
        unit = TemperatureUnit.build(status.get("temperatureUnit"))
        if unit != TemperatureUnit.UNKNOWN:
            kwargs["temperature_unit"] = unit
    return kwargs


def _parse_heater_status(status: dict[str, object]) -> dict[str, object]:
    """Parse status fields for the heater."""
    kwargs: dict[str, object] = {}
    if "heater" in status:
        kwargs["is_on"] = status.get("heater", "off") != "off"
    if "heaterLock" in status:
        kwargs["heater_lock"] = status.get("heaterLock", "off") != "off"
    if (raw_hp := status.get("heatpumpInstalled")) is not None:
        kwargs["heatpump_installed"] = raw_hp != "notinstalled"
    if kwargs.get("heatpump_installed") is False:
        # At boot before UART sync, the HNA zero-initializes heater_mode to 0
        # ("heatWithBoost") even when no CoolZone heat pump is installed.
        kwargs["heating_mode"] = HeatingMode.UNKNOWN
    elif (raw_mode := status.get("heatingMode")) is not None:
        mode = HeatingMode.build(raw_mode)
        if mode != HeatingMode.UNKNOWN or str(raw_mode).strip().lower() == "invalid":
            kwargs["heating_mode"] = mode
    kwargs.update(_parse_heater_temperatures(status))
    return kwargs


def _parse_heater_control(control: dict[str, object]) -> dict[str, object]:
    """Parse control fields for the heater."""
    kwargs: dict[str, object] = {}
    if "temperatureABS" in control:
        parsed_temp = _parse_temperature(control.get("temperatureABS"))
        if parsed_temp is not None:
            kwargs["set_temperature"] = parsed_temp
    if "heatingMode" in control:
        mode = HeatingMode.build(control.get("heatingMode"))
        if mode != HeatingMode.UNKNOWN:
            kwargs["heating_mode"] = mode
    if "temperatureLock" in control:
        raw_lock = control.get("temperatureLock")
        if raw_lock is not None:
            kwargs["heater_lock"] = _is_truthy(raw_lock)
    return kwargs


def _parse_light_zone_status(status: dict[str, object]) -> dict[str, object]:
    """Parse status parameters for a light zone."""
    kwargs: dict[str, object] = {}
    if "color" in status:
        color_val = LightColor.build(status.get("color"))
        kwargs["color"] = color_val
        if "RGBstate" not in status and color_val != LightColor.CUSTOM:
            kwargs["rgb_state"] = "inactive"
    if "lightWheel" in status:
        kwargs["light_wheel"] = LightWheelMode.build(status.get("lightWheel"))
    if "Intensity" in status:
        intensity = int(status.get("Intensity", 0))
        kwargs["intensity"] = intensity
        kwargs["is_on"] = intensity > 0
    if "loopSpeed" in status:
        kwargs["loop_speed"] = int(status.get("loopSpeed", 0))
    if "cRed" in status:
        kwargs["c_red"] = int(status.get("cRed", 0))
    if "cGreen" in status:
        kwargs["c_green"] = int(status.get("cGreen", 0))
    if "cBlue" in status:
        kwargs["c_blue"] = int(status.get("cBlue", 0))
    if "RGBstate" in status:
        kwargs["rgb_state"] = str(status.get("RGBstate", "inactive")).lower()
    return kwargs


def _parse_light_zone_control(control: dict[str, object]) -> dict[str, object]:
    """Parse control parameters for a light zone."""
    kwargs: dict[str, object] = {}
    if "color" in control:
        color_val = LightColor.build(control.get("color"))
        if color_val != LightColor.UNKNOWN:
            kwargs["color"] = color_val
            if color_val != LightColor.CUSTOM:
                kwargs["rgb_state"] = "inactive"
    if "lightWheel" in control:
        wheel_mode = LightWheelMode.build(control.get("lightWheel"))
        if wheel_mode != LightWheelMode.UNKNOWN:
            kwargs["light_wheel"] = wheel_mode
    if "IntensityAbs" in control:
        intensity = int(control.get("IntensityAbs", 0))
        kwargs["intensity"] = intensity
        kwargs["is_on"] = intensity > 0
    if "Intensity" in control:
        val = str(control.get("Intensity")).lower()
        if val == "off":
            kwargs["intensity"] = 0
            kwargs["is_on"] = False
        elif val.isdigit():
            intensity = int(val)
            kwargs["intensity"] = intensity
            kwargs["is_on"] = intensity > 0
    if "rgbFactor" in control and isinstance(control["rgbFactor"], dict):
        rgb = control["rgbFactor"]
        kwargs["c_red"] = int(rgb.get("red", 0))
        kwargs["c_green"] = int(rgb.get("green", 0))
        kwargs["c_blue"] = int(rgb.get("blue", 0))
        kwargs["rgb_state"] = "active"
        kwargs["color"] = LightColor.CUSTOM
    return kwargs


def _parse_temperature(value: str | float | None) -> float | None:
    """Parse a temperature value from the API.

    The API returns temperatures in formats like " 97F", " 38C",
    "100", or empty strings. This function strips whitespace and
    unit suffixes before parsing.

    Args:
    ----
        value: The raw temperature value from the API.

    Returns:
    -------
        The temperature as a float, or None if not available.

    """
    if value is None:
        return None
    # Convert to string and strip whitespace
    text = str(value).strip()
    if not text:
        return None
    # Strip trailing unit suffix (F or C)
    if text[-1] in ("F", "C"):
        text = text[:-1].strip()
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_clean_cycle_status(status: dict[str, object]) -> dict[str, object]:
    """Parse status fields for clean cycle."""
    kwargs: dict[str, object] = {}
    if "cleanCycle" in status:
        kwargs["is_enabled"] = status.get("cleanCycle", "disable") == "enable"
    if "vanishingAct" in status:
        kwargs["vanishing_act"] = status.get("vanishingAct", "off") != "off"
    return kwargs


def _parse_clean_cycle_control(control: dict[str, object] | str) -> dict[str, object]:
    """Parse control fields for clean cycle."""
    kwargs: dict[str, object] = {}
    if isinstance(control, dict):
        if "cleanCycle" in control:
            raw_cc = control.get("cleanCycle")
            if raw_cc is not None:
                kwargs["is_enabled"] = _is_truthy(raw_cc)
        if "vanishingAct" in control:
            raw_va = control.get("vanishingAct")
            if raw_va is not None:
                kwargs["vanishing_act"] = _is_truthy(raw_va)
    elif isinstance(control, str):
        kwargs["is_enabled"] = _is_truthy(control)
    return kwargs


def _parse_clean_cycle_timer(data: dict[str, object]) -> dict[str, object]:
    """Parse clean cycle timer parameters from command echo payload."""
    kwargs: dict[str, object] = {}
    if "cleanTimer" in data:
        kwargs["clean_timer_enabled"] = _is_truthy(data.get("cleanTimer"))
    if "startHour" in data:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["start_hour"] = int(str(data["startHour"]))
    if "startMinute" in data:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["start_minute"] = int(str(data["startMinute"]))
    return kwargs


def _parse_water_care_status(status: dict[str, object]) -> dict[str, object]:
    """Parse status fields for water care."""
    kwargs: dict[str, object] = {}
    if "cartridgeInstalled" in status:
        kwargs["cartridge_installed"] = (
            status.get("cartridgeInstalled", "notinstalled") != "notinstalled"
        )
    if "10DayTimer" in status:
        kwargs["ten_day_timer"] = int(status.get("10DayTimer", 0))
    if "120DayTimer" in status:
        kwargs["one_twenty_day_timer"] = int(status.get("120DayTimer", 0))
    if "level" in status:
        kwargs["level"] = int(status.get("level", 0))
    if "SystemEnable" in status:
        kwargs["system_enabled"] = _is_truthy(status.get("SystemEnable"))
    if "AceMode" in status:
        kwargs["ace_mode"] = str(status.get("AceMode", "inactive"))
    if "boost" in status:
        kwargs["boost_active"] = _is_truthy(status.get("boost"))
    if "saltValue" in status:
        kwargs["salt_value"] = int(status.get("saltValue", 0))
    return kwargs


def _parse_water_care_config(config: dict[str, object]) -> dict[str, object]:
    """Parse config fields for water care (such as salt system power channels)."""
    kwargs: dict[str, object] = {}
    if "saltSystemPowerA" in config:
        kwargs["power_a"] = _is_truthy(config.get("saltSystemPowerA"))
    if "saltSystemPowerB" in config:
        kwargs["power_b"] = _is_truthy(config.get("saltSystemPowerB"))
    if "power_a" in kwargs or "power_b" in kwargs:
        kwargs["system_enabled"] = bool(kwargs.get("power_a") or kwargs.get("power_b"))
    return kwargs


def _parse_water_care_control(control: dict[str, object]) -> dict[str, object]:
    """Parse control fields for water care."""
    kwargs: dict[str, object] = {}
    if "level" in control:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["level"] = int(str(control["level"]))
    if "boost" in control:
        kwargs["boost_active"] = _is_truthy(control.get("boost"))
    return kwargs


def _parse_energy_saving_status(status: dict[str, object]) -> dict[str, object]:
    """Parse status fields for energy saving schedule."""
    kwargs: dict[str, object] = {}
    if "mode" in status:
        kwargs["mode"] = int(status.get("mode", 0))
    if "startHour" in status:
        kwargs["start_hour"] = int(status.get("startHour", 0))
    if "startMinute" in status:
        kwargs["start_minute"] = int(status.get("startMinute", 0))
    if "duration" in status:
        kwargs["duration"] = int(status.get("duration", 0))
    return kwargs


def _parse_energy_saving_control(control: dict[str, object]) -> dict[str, object]:
    """Parse control fields for energy saving schedule."""
    kwargs: dict[str, object] = {}
    if "mode" in control:
        raw_mode = control.get("mode")
        if raw_mode in ("on", "enable", 1, "1", True):
            kwargs["mode"] = 1
        elif raw_mode in ("off", "disable", 0, "0", False):
            kwargs["mode"] = 0
    if "startHour" in control:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["start_hour"] = int(str(control["startHour"]))
    if "startMinute" in control:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["start_minute"] = int(str(control["startMinute"]))
    if "duration" in control:
        with contextlib.suppress(ValueError, TypeError):
            kwargs["duration"] = int(str(control["duration"]))
    return kwargs


_FWIQ_STATUS_READING_KEYS: tuple[tuple[str, str, type[int | float]], ...] = (
    ("Conductivity", "conductivity", int),
    ("ORP", "orp", int),
    ("Chlorine", "chlorine", float),
    ("pH", "ph", float),
    ("SensorLife", "sensor_life_percentage", float),
)

_FWIQ_PARAMS_READING_KEYS: tuple[tuple[str, str, type[int | float]], ...] = (
    ("current_Current_CompConductivity", "conductivity", int),
    ("current_ORP", "orp", int),
    ("current_chlorine", "chlorine", float),
    ("current_pH", "ph", float),
    ("current_SensorLife_Percentage", "sensor_life_percentage", float),
)


_FWIQ_STATUS_META_KEYS: tuple[tuple[str, str, type[float | str]], ...] = (
    ("Cl_CalibrationFactor", "cl_calibration_factor", float),
    ("pH_CalibrationFactor", "ph_calibration_factor", float),
    ("Regional_Cl_Selection", "regional_cl_selection", str),
)


def _normalize_fwiq_readings(
    source: dict[str, object],
    key_specs: tuple[tuple[str, str, type[int | float]], ...],
) -> dict[str, int | float | None]:
    """Parse and normalize FWIQ sensor readings.

    The HNA firmware initializes FWIQ registers to ``0`` at boot before the
    first UART packet arrives from the control box, and overwrites all five
    registers with ``-1`` / ``-1.0`` when FWIQ is not installed or no sensor
    readings are available. Negative values and payloads where no reading is
    positive are normalized to ``None``.
    """
    readings: dict[str, int | float | None] = {}
    for json_key, attr_name, converter in key_specs:
        if (raw := source.get(json_key)) is not None:
            val = converter(raw)
            readings[attr_name] = val if val >= 0 else None

    if readings and not any(v is not None and v > 0 for v in readings.values()):
        return dict.fromkeys(readings, None)
    return readings


def _parse_fwiq_status(fwiq: dict[str, object]) -> dict[str, object]:
    """Parse nested ``waterCare.status.FWIQstatus`` from GET /getFWIQData."""
    installed = fwiq.get("FWIQinstalled", "notinstalled") != "notinstalled"
    readings = _normalize_fwiq_readings(fwiq, _FWIQ_STATUS_READING_KEYS)
    if not installed:
        readings = dict.fromkeys(readings, None)

    kwargs: dict[str, object] = {**readings, "installed": installed}
    if (raw_state := fwiq.get("SystemState")) is not None:
        kwargs["system_enabled"] = str(raw_state).strip().lower() == "enabled"
    for json_key, attr_name, converter in _FWIQ_STATUS_META_KEYS:
        if (raw_meta := fwiq.get(json_key)) is not None:
            kwargs[attr_name] = converter(raw_meta)
    return kwargs


def _parse_fwiq_parameters(data: dict[str, object]) -> dict[str, object]:
    """Parse flat ``FWIQ_Parameters`` from GET /status."""
    readings = _normalize_fwiq_readings(data, _FWIQ_PARAMS_READING_KEYS)
    kwargs: dict[str, object] = dict(readings)
    if any(v is not None for v in readings.values()):
        kwargs["installed"] = True
    return kwargs
