"""Models for Hot Spring Connected Spa Kit 2."""
# mypy: disable-error-code="union-attr, arg-type, call-overload, attr-defined"
# Rationale: This module parses nested JSON dicts typed as dict[str, object].
# The .get() return type is `object`, which mypy cannot narrow without runtime
# isinstance checks on every access. This is a known typing limitation for
# hand-parsed JSON; schema libraries (mashumaro, pydantic) solve this at the
# cost of an extra dependency.

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, NamedTuple

from .const import (
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
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
    jets: list[Jet]
    blower: Blower
    light_zones: list[LightZone]
    logo_light: LogoLight
    clean_cycle: CleanCycle
    spa_lock: SpaLock
    water_care: WaterCare
    freshwater_iq: FreshWaterIQ
    energy_savings: list[EnergySaving]
    versions: Versions
    connection_status: ConnectionStatus
    diagnostics: Diagnostics
    test_metrics: SpaTestData

    def __init__(self, data: dict[str, object]) -> None:
        """Initialize a Spa from the API response.

        Args:
        ----
            data: The API response dict from a GET /status call.

        """
        self.heater = Heater()
        self.jets = []
        self.blower = Blower()
        self.light_zones = []
        self.logo_light = LogoLight()
        self.clean_cycle = CleanCycle()
        self.spa_lock = SpaLock()
        self.water_care = WaterCare()
        self.freshwater_iq = FreshWaterIQ()
        self.test_metrics = SpaTestData()
        self.energy_savings = []
        self.versions = Versions()
        self.info = SpaInfo()
        self.connection_status = ConnectionStatus()
        self.diagnostics = Diagnostics()

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
            new_jets = Jet.list_from_dict(data["JET"], existing=self.jets)
            self.jets = _merge_entities(self.jets, new_jets, lambda j: j.jet_id)
            updated.add("jets")

        if "lights" in data and isinstance(data["lights"], dict):
            new_zones = LightZone.list_from_dict(
                data["lights"], existing=self.light_zones
            )
            self.light_zones = _merge_entities(
                self.light_zones, new_zones, lambda z: z.zone_id
            )
            updated.add("light_zones")

        if "energySavings" in data and isinstance(data["energySavings"], dict):
            new_schedules = EnergySaving.list_from_dict(
                data["energySavings"], existing=self.energy_savings
            )
            self.energy_savings = _merge_entities(
                self.energy_savings, new_schedules, lambda s: s.schedule_id
            )
            updated.add("energy_savings")

        if "productVersions" in data and isinstance(data["productVersions"], dict):
            status = data["productVersions"].get("status", {})
            self.versions = Versions.from_dict(
                status if isinstance(status, dict) else {}
            )
            updated.add("versions")

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
        """Update diagnostics from /addDebugData response.

        Args:
        ----
            data: The JSON response from GET /addDebugData.

        """
        self.diagnostics = Diagnostics.from_dict(data)

    def update_freshwater_iq(self, data: dict[str, object]) -> None:
        """Update FreshWater IQ data from /getFWIQData response.

        Args:
        ----
            data: The JSON response from GET /getFWIQData.

        """
        self.freshwater_iq = FreshWaterIQ.from_dict(data)


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


@dataclass
class Heater:  # pylint: disable=too-many-instance-attributes
    """Heater status and configuration."""

    is_on: bool = False
    heater_lock: bool = False
    heatpump_installed: bool = False
    heating_mode: HeatingMode = HeatingMode.UNKNOWN
    heater_current: float = 0.0
    heater_on_seconds: int = 0
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
            if "heater" in status:
                kwargs["is_on"] = status.get("heater", "off") != "off"
            if "heaterLock" in status:
                kwargs["heater_lock"] = status.get("heaterLock", "off") != "off"
            if "heatpumpInstalled" in status:
                kwargs["heatpump_installed"] = (
                    status.get("heatpumpInstalled", "notinstalled") != "notinstalled"
                )
            if "heatingMode" in status:
                kwargs["heating_mode"] = HeatingMode.build(status.get("heatingMode"))
            if "heaterCurrent" in status:
                kwargs["heater_current"] = int(status.get("heaterCurrent", 0)) / 2560.0
            if "heaterHours" in status:
                kwargs["heater_on_seconds"] = int(status.get("heaterHours", 0)) // 256
            if "setWaterTemperature" in status:
                kwargs["set_temperature"] = _parse_temperature(
                    status.get("setWaterTemperature")
                )
            if "currentWaterTemperature" in status:
                kwargs["current_temperature"] = _parse_temperature(
                    status.get("currentWaterTemperature")
                )
            if "temperatureUnit" in status:
                kwargs["temperature_unit"] = TemperatureUnit.build(
                    status.get("temperatureUnit")
                )

        base = existing or Heater()
        return replace(base, **kwargs)


@dataclass
class Jet:
    """Status and configuration for a single jet pump."""

    jet_id: int
    speed: JetSpeed = JetSpeed.OFF
    is_enabled: bool = True
    on_seconds: int = 0

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

        status = data.get("status")
        if isinstance(status, dict):
            if "speed" in status:
                kwargs["speed"] = JetSpeed.build(status.get("speed"))
            on_sec_key = f"jet_{jet_id}_ON_sec"
            if on_sec_key in status:
                kwargs["on_seconds"] = int(status.get(on_sec_key, 0)) // 256

        base = existing or Jet(jet_id=jet_id)
        return replace(base, **kwargs)

    @staticmethod
    def list_from_dict(
        data: dict[str, object],
        existing: list[Jet] | None = None,
    ) -> list[Jet]:
        """Parse all jets from the JET section of the /status response.

        Args:
        ----
            data: The ``JET`` dict from the /status response.
            existing: Optional existing list of Jet instances for field preservation.

        Returns:
        -------
            A list of Jet instances.

        """
        existing_map = {j.jet_id: j for j in existing} if existing else {}
        jets: list[Jet] = []
        for key, value in data.items():
            if key.upper().startswith("JET") and isinstance(value, dict):
                try:
                    jet_id = int(key[3:])
                except ValueError:
                    continue
                jets.append(
                    Jet.from_dict(jet_id, value, existing=existing_map.get(jet_id))
                )
        return sorted(jets, key=lambda j: j.jet_id)


@dataclass
class Blower:
    """Blower status and configuration."""

    is_enabled: bool = False
    is_on: bool = False

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
            kwargs["is_enabled"] = config.get("blower", "disable") != "disable"

        status = data.get("status")
        if isinstance(status, dict) and "blower" in status:
            kwargs["is_on"] = status.get("blower", "off") not in ("off", "disable")

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

        base = existing or LightZone(zone_id=zone_id)
        zone = replace(base, **kwargs)
        if zone.rgb_state == "active" and (
            (zone.c_red, zone.c_green, zone.c_blue) != (0, 0, 0)
        ):
            zone.color = LightColor.CUSTOM
        return zone

    @staticmethod
    def list_from_dict(
        data: dict[str, object],
        existing: list[LightZone] | None = None,
    ) -> list[LightZone]:
        """Parse all light zones from the lights section.

        Args:
        ----
            data: The ``lights`` dict from the /status response.
            existing: Optional existing list of LightZone instances.

        Returns:
        -------
            A list of LightZone instances.

        """
        existing_map = {z.zone_id: z for z in existing} if existing else {}
        zones: list[LightZone] = []
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower.startswith("zone") and isinstance(value, dict):
                try:
                    zone_id = int(key_lower[4:])
                except ValueError:
                    continue
                zones.append(
                    LightZone.from_dict(
                        zone_id, value, existing=existing_map.get(zone_id)
                    )
                )
        return sorted(zones, key=lambda z: z.zone_id)


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

        base = existing or LogoLight()
        return replace(base, **kwargs)


@dataclass
class CleanCycle:
    """Clean cycle status and configuration."""

    is_enabled: bool = False
    vanishing_act: bool = False

    @staticmethod
    def from_dict(
        data: dict[str, object], existing: CleanCycle | None = None
    ) -> CleanCycle:
        """Create a CleanCycle from API response data.

        Args:
        ----
            data: The ``cleanCycle`` dict from the /status response.
            existing: Optional existing CleanCycle instance to preserve cached fields.

        Returns:
        -------
            A CleanCycle instance.

        """
        kwargs: dict[str, object] = {}
        status = data.get("status")
        if isinstance(status, dict):
            if "cleanCycle" in status:
                kwargs["is_enabled"] = status.get("cleanCycle", "disable") == "enable"
            if "vanishingAct" in status:
                kwargs["vanishing_act"] = status.get("vanishingAct", "off") != "off"

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
            kwargs["is_locked"] = status.get("spaLock", "off") != "off"

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
                kwargs["system_enabled"] = (
                    status.get("SystemEnable", "disable") == "enable"
                )
            if "AceMode" in status:
                kwargs["ace_mode"] = str(status.get("AceMode", "inactive"))
            if "boost" in status:
                kwargs["boost_active"] = status.get("boost", "inactive") != "inactive"
            if "saltValue" in status:
                kwargs["salt_value"] = int(status.get("saltValue", 0))

        base = existing or WaterCare()
        return replace(base, **kwargs)


@dataclass
class FreshWaterIQ:
    """FreshWater IQ water quality sensor data."""

    conductivity: int = 0
    orp: int = 0
    chlorine: float = 0.0
    ph: float = 0.0
    sensor_life_percentage: float = 0.0
    installed: bool = False

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
            return FreshWaterIQ(
                conductivity=int(fwiq.get("Conductivity", 0)),
                orp=int(fwiq.get("ORP", 0)),
                chlorine=float(fwiq.get("Chlorine", 0.0)),
                ph=float(fwiq.get("pH", 0.0)),
                sensor_life_percentage=float(fwiq.get("SensorLife", 0.0)),
                installed=fwiq.get("FWIQinstalled", "notinstalled") != "notinstalled",
            )

        # Handle the flat /status FWIQ_Parameters format
        kwargs: dict[str, object] = {}
        if "current_Current_CompConductivity" in data:
            kwargs["conductivity"] = int(
                data.get("current_Current_CompConductivity", 0)
            )
        if "current_ORP" in data:
            kwargs["orp"] = int(data.get("current_ORP", 0))
        if "current_chlorine" in data:
            kwargs["chlorine"] = float(data.get("current_chlorine", 0.0))
        if "current_pH" in data:
            kwargs["ph"] = float(data.get("current_pH", 0.0))
        if "current_SensorLife_Percentage" in data:
            kwargs["sensor_life_percentage"] = float(
                data.get("current_SensorLife_Percentage", 0.0)
            )

        base = existing or FreshWaterIQ(installed=True)
        return replace(base, **kwargs)


@dataclass
class EnergySaving:
    """Energy saving schedule configuration."""

    schedule_id: int
    mode: int = 0
    start_hour: int = 0
    start_minute: int = 0
    duration: int = 0

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
            if "mode" in status:
                kwargs["mode"] = int(status.get("mode", 0))
            if "startHour" in status:
                kwargs["start_hour"] = int(status.get("startHour", 0))
            if "startMinute" in status:
                kwargs["start_minute"] = int(status.get("startMinute", 0))
            if "duration" in status:
                kwargs["duration"] = int(status.get("duration", 0))

        base = existing or EnergySaving(schedule_id=schedule_id)
        return replace(base, **kwargs)

    @staticmethod
    def list_from_dict(
        data: dict[str, object],
        existing: list[EnergySaving] | None = None,
    ) -> list[EnergySaving]:
        """Parse all energy saving schedules from the /status response.

        Args:
        ----
            data: The ``energySavings`` dict from the /status response.
            existing: Optional existing list of EnergySaving instances
                for field preservation.

        Returns:
        -------
            A list of EnergySaving instances.

        """
        existing_map = {s.schedule_id: s for s in existing} if existing else {}
        schedules: list[EnergySaving] = []
        for key, value in data.items():
            if key.startswith("energySaving") and isinstance(value, dict):
                try:
                    schedule_id = int(key[12:])
                except ValueError:
                    continue
                schedules.append(
                    EnergySaving.from_dict(
                        schedule_id, value, existing=existing_map.get(schedule_id)
                    )
                )
        return sorted(schedules, key=lambda s: s.schedule_id)


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
class SpaTestData:
    """Test data metrics from the spa, including raw current readings."""

    heater_test_status: str = "off"
    temp_offset: float = 0.0
    vsense_cal: float = 0.0
    jet1_jet2_blower_current: float = 0.0
    small_loads_current: float = 0.0
    heater_current: float = 0.0
    jet3_current: float = 0.0

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
                kwargs["heater_test_status"] = str(
                    status.get("heaterTestStatus", "off")
                )
            if "tempOffset" in status:
                kwargs["temp_offset"] = float(status.get("tempOffset", 0.0))
            if "VsenseCal" in status:
                kwargs["vsense_cal"] = float(status.get("VsenseCal", 0.0))
            if "jet1+jet2+blowerCurrent" in status:
                kwargs["jet1_jet2_blower_current"] = (
                    int(status.get("jet1+jet2+blowerCurrent", 0)) / 2560.0
                )
            if "smallLoadsCurrent" in status:
                kwargs["small_loads_current"] = (
                    int(status.get("smallLoadsCurrent", 0)) / 2560.0
                )
            if "heaterCurrent" in status:
                kwargs["heater_current"] = int(status.get("heaterCurrent", 0)) / 2560.0
            if "jet3Current" in status:
                kwargs["jet3_current"] = int(status.get("jet3Current", 0)) / 2560.0

        base = existing or SpaTestData()
        return replace(base, **kwargs)


@dataclass
class Diagnostics:  # pylint: disable=too-many-instance-attributes
    """Diagnostic and power metrics from the spa.

    Availability depends on the spa model and whether the main control
    board (IQ2020/Eagle) is equipped with current-sensing transformers.
    Values may be ``0`` if sensors are not installed.
    """

    spa_failure_state: SpaFailureState = SpaFailureState.UNKNOWN
    heater_error: str = "0"
    power_frequency: str = "0"
    pressure_switch_status: str = "0"
    l1_n_volts: float = 0.0
    l2_n_volts: float = 0.0
    heater_volts: float = 0.0
    jet3_volts: float = 0.0
    jet1_jet2_blower_power: str = "0"
    small_loads_power: str = "0"
    heater_power: str = "0"
    jet3_power: str = "0"

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
        debug = data.get("debugData", {}).get("status", {})
        if not isinstance(debug, dict) or not debug:
            return Diagnostics()

        volt_keys = {
            "L1_N_Volts": "l1_n_volts",
            "L2_N_Volts": "l2_n_volts",
            "Heater_Volts": "heater_volts",
            "jet3_Volts": "jet3_volts",
        }
        str_keys = {
            "heaterError": "heater_error",
            "powerFrequency": "power_frequency",
            "pressureSwitchStatus": "pressure_switch_status",
            "jet1_jet2_blowerPower": "jet1_jet2_blower_power",
            "smallLoadsPower": "small_loads_power",
            "heaterPower": "heater_power",
            "jet3Power": "jet3_power",
        }
        kwargs: dict[str, object] = {}
        if "spaFailureState" in debug:
            kwargs["spa_failure_state"] = SpaFailureState.build(
                debug.get("spaFailureState")
            )
        for json_key, attr in str_keys.items():
            if json_key in debug:
                kwargs[attr] = str(debug[json_key])
        for json_key, attr in volt_keys.items():
            if json_key in debug:
                kwargs[attr] = int(debug.get(json_key) or 0) / 32.0

        return replace(Diagnostics(), **kwargs)


def _merge_entities[T, K](
    existing: list[T], incoming: list[T], key_func: Callable[[T], K]
) -> list[T]:
    """Merge incoming partial updates into an existing list by entity ID."""
    incoming_map = {key_func(item): item for item in incoming}
    if not existing:
        return list(incoming_map.values())
    result = [incoming_map.get(key_func(item), item) for item in existing]
    existing_keys = {key_func(item) for item in existing}
    result.extend(incoming_map[k] for k in incoming_map if k not in existing_keys)
    return result


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
