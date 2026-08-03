"""Models for Hot Spring Connected Spa Kit 2."""
# mypy: disable-error-code="union-attr, arg-type, call-overload, attr-defined"
# Rationale: This module parses nested JSON dicts typed as dict[str, object].
# The .get() return type is `object`, which mypy cannot narrow without runtime
# isinstance checks on every access. This is a known typing limitation for
# hand-parsed JSON; schema libraries (mashumaro, pydantic) solve this at the
# cost of an extra dependency.

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
    LightColor,
    LightWheelMode,
    SpaFailureState,
    TemperatureUnit,
)


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
        """Initialize a Spa from the full API response.

        Args:
        ----
            data: The full API response from a GET /status call.

        """
        self.update_from_dict(data)

    def update_from_dict(self, data: dict[str, object]) -> Spa:
        """Update the Spa object from a /status API response.

        Args:
        ----
            data: The full JSON response from GET /status.

        Returns:
        -------
            The updated Spa object.

        """
        self.heater = Heater.from_dict(data.get("heater", {}))
        self.jets = Jet.list_from_dict(data.get("JET", {}))
        self.blower = Blower.from_dict(data.get("blower", {}))
        self.light_zones = LightZone.list_from_dict(data.get("lights", {}))
        self.logo_light = LogoLight.from_dict(data.get("logoLight", {}))
        self.clean_cycle = CleanCycle.from_dict(data.get("cleanCycle", {}))
        self.spa_lock = SpaLock.from_dict(data.get("spaLock", {}))
        self.water_care = WaterCare.from_dict(data.get("waterCare", {}))
        self.freshwater_iq = FreshWaterIQ.from_dict(data.get("FWIQ_Parameters", {}))
        self.test_metrics = SpaTestData.from_dict(data.get("test_data", {}))
        self.energy_savings = EnergySaving.list_from_dict(data.get("energySavings", {}))
        self.versions = Versions.from_dict(
            data.get("productVersions", {}).get("status", {})
        )
        # These are populated by separate API calls
        if not hasattr(self, "info"):
            self.info = SpaInfo.from_dict({})
        if not hasattr(self, "connection_status"):
            self.connection_status = ConnectionStatus.from_dict({})
        if not hasattr(self, "diagnostics"):
            self.diagnostics = Diagnostics.from_dict({})
        if not hasattr(self, "test_metrics"):
            self.test_metrics = SpaTestData.from_dict({})

        return self

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
                        self.info.brand_name = str(status["brandName"])
                    if "collectionType" in status:
                        self.info.collection_type = str(status["collectionType"])
                    if "modelType" in status:
                        self.info.model_type = str(status["modelType"])
                    if "volume" in status:
                        self.info.volume = int(status["volume"] or 0)

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

    hostname: str
    root_topic: str
    sna_ready: bool
    brand_name: str
    collection_type: str
    model_type: str
    volume: int

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

        return SpaInfo(
            hostname=str(data.get("HOSTNAME", "")),
            root_topic=str(data.get("rootTopic", "")),
            sna_ready=data.get("SNAready", "") in ("Ready", "Yes"),
            brand_name=str(model_status.get("brandName", "")),
            collection_type=str(model_status.get("collectionType", "")),
            model_type=str(model_status.get("modelType", "")),
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

    is_on: bool
    heater_lock: bool
    heatpump_installed: bool
    heating_mode: HeatingMode
    heater_current: float
    heater_on_seconds: int
    set_temperature: float | None
    current_temperature: float | None
    temperature_unit: TemperatureUnit

    @staticmethod
    def from_dict(data: dict[str, object]) -> Heater:
        """Create a Heater from API response data.

        Args:
        ----
            data: The ``heater`` dict from the /status response.

        Returns:
        -------
            A Heater instance.

        """
        status = data.get("status", {})
        return Heater(
            is_on=status.get("heater", "off") != "off",
            heater_lock=status.get("heaterLock", "off") != "off",
            heatpump_installed=status.get("heatpumpInstalled", "notinstalled")
            != "notinstalled",
            heating_mode=HeatingMode.build(status.get("heatingMode")),
            heater_current=int(status.get("heaterCurrent", 0)) / 2560.0,
            heater_on_seconds=int(status.get("heaterHours", 0)) // 256,
            set_temperature=_parse_temperature(status.get("setWaterTemperature")),
            current_temperature=_parse_temperature(
                status.get("currentWaterTemperature")
            ),
            temperature_unit=TemperatureUnit.build(status.get("temperatureUnit")),
        )


@dataclass
class Jet:
    """Status and configuration for a single jet pump."""

    jet_id: int
    speed: JetSpeed
    is_enabled: bool
    on_seconds: int

    @staticmethod
    def from_dict(jet_id: int, data: dict[str, object]) -> Jet:
        """Create a Jet from API response data.

        Args:
        ----
            jet_id: The jet number (1-based).
            data: The ``JETn`` dict from the /status response.

        Returns:
        -------
            A Jet instance.

        """
        config = data.get("config", {})
        status = data.get("status", {})

        # A jet is disabled if its key in config is set to "disable"
        jet_key = f"JET{jet_id}"
        is_enabled = config.get(jet_key, "enable") != "disable"

        # Find the on_seconds key dynamically (e.g., jet_1_ON_sec)
        on_sec_key = f"jet_{jet_id}_ON_sec"
        on_seconds = int(status.get(on_sec_key, 0)) // 256

        return Jet(
            jet_id=jet_id,
            speed=JetSpeed.build(status.get("speed")),
            is_enabled=is_enabled,
            on_seconds=on_seconds,
        )

    @staticmethod
    def list_from_dict(data: dict[str, object]) -> list[Jet]:
        """Parse all jets from the JET section of the /status response.

        Args:
        ----
            data: The ``JET`` dict from the /status response.

        Returns:
        -------
            A list of Jet instances.

        """
        jets: list[Jet] = []
        for key, value in data.items():
            if key.startswith("JET") and isinstance(value, dict):
                try:
                    jet_id = int(key[3:])
                except ValueError:
                    continue
                jets.append(Jet.from_dict(jet_id, value))
        return sorted(jets, key=lambda j: j.jet_id)


@dataclass
class Blower:
    """Blower status and configuration."""

    is_enabled: bool
    is_on: bool

    @staticmethod
    def from_dict(data: dict[str, object]) -> Blower:
        """Create a Blower from API response data.

        Args:
        ----
            data: The ``blower`` dict from the /status response.

        Returns:
        -------
            A Blower instance.

        """
        config = data.get("config", {})
        status = data.get("status", {})
        return Blower(
            is_enabled=config.get("blower", "disable") != "disable",
            is_on=status.get("blower", "off") not in ("off", "disable"),
        )


@dataclass
class LightZone:
    """Status and configuration for a single light zone."""

    zone_id: int
    is_enabled: bool
    is_on: bool
    color: LightColor
    light_wheel: LightWheelMode
    intensity: int
    loop_speed: int

    @staticmethod
    def from_dict(zone_id: int, data: dict[str, object]) -> LightZone:
        """Create a LightZone from API response data.

        Args:
        ----
            zone_id: The zone number (1-based).
            data: The ``zoneN`` dict from the /status response.

        Returns:
        -------
            A LightZone instance.

        """
        config = data.get("config", {})
        status = data.get("status", {})

        zone_key = f"zone_{zone_id}"
        is_enabled = config.get(zone_key, "disable") != "disable"

        color = LightColor.build(status.get("color"))
        light_wheel = LightWheelMode.build(status.get("lightWheel"))
        is_on = color not in (
            LightColor.OFF,
            LightColor.UNKNOWN,
        ) or light_wheel not in (LightWheelMode.OFF, LightWheelMode.UNKNOWN)

        return LightZone(
            zone_id=zone_id,
            is_enabled=is_enabled,
            is_on=is_on,
            color=color,
            light_wheel=light_wheel,
            intensity=int(status.get("Intensity", 0)),
            loop_speed=int(status.get("loopSpeed", 0)),
        )

    @staticmethod
    def list_from_dict(data: dict[str, object]) -> list[LightZone]:
        """Parse all light zones from the lights section.

        Args:
        ----
            data: The ``lights`` dict from the /status response.

        Returns:
        -------
            A list of LightZone instances.

        """
        zones: list[LightZone] = []
        for key, value in data.items():
            if key.startswith("zone") and isinstance(value, dict):
                try:
                    zone_id = int(key[4:])
                except ValueError:
                    continue
                zones.append(LightZone.from_dict(zone_id, value))
        return sorted(zones, key=lambda z: z.zone_id)


@dataclass
class LogoLight:
    """Logo light status."""

    brightness: BrightnessLevel

    @staticmethod
    def from_dict(data: dict[str, object]) -> LogoLight:
        """Create a LogoLight from API response data.

        Args:
        ----
            data: The ``logoLight`` dict from the /status response.

        Returns:
        -------
            A LogoLight instance.

        """
        status = data.get("status", {})
        return LogoLight(
            brightness=BrightnessLevel.build(status.get("brightness")),
        )


@dataclass
class CleanCycle:
    """Clean cycle status and configuration."""

    is_enabled: bool
    vanishing_act: bool

    @staticmethod
    def from_dict(data: dict[str, object]) -> CleanCycle:
        """Create a CleanCycle from API response data.

        Args:
        ----
            data: The ``cleanCycle`` dict from the /status response.

        Returns:
        -------
            A CleanCycle instance.

        """
        status = data.get("status", {})
        return CleanCycle(
            is_enabled=status.get("cleanCycle", "disable") == "enable",
            vanishing_act=status.get("vanishingAct", "off") != "off",
        )


@dataclass
class SpaLock:
    """Spa lock status."""

    is_locked: bool

    @staticmethod
    def from_dict(data: dict[str, object]) -> SpaLock:
        """Create a SpaLock from API response data.

        Args:
        ----
            data: The ``spaLock`` dict from the /status response.

        Returns:
        -------
            A SpaLock instance.

        """
        status = data.get("status", {})
        return SpaLock(
            is_locked=status.get("spaLock", "off") != "off",
        )


@dataclass
class WaterCare:  # pylint: disable=too-many-instance-attributes
    """Water care / salt system status."""

    cartridge_installed: bool
    ten_day_timer: int
    one_twenty_day_timer: int
    level: int
    system_enabled: bool
    ace_mode: str
    boost_active: bool
    salt_value: int

    @staticmethod
    def from_dict(data: dict[str, object]) -> WaterCare:
        """Create a WaterCare from API response data.

        Args:
        ----
            data: The ``waterCare`` dict from the /status response.

        Returns:
        -------
            A WaterCare instance.

        """
        status = data.get("status", {})
        return WaterCare(
            cartridge_installed=status.get("cartridgeInstalled", "notinstalled")
            != "notinstalled",
            ten_day_timer=int(status.get("10DayTimer", 0)),
            one_twenty_day_timer=int(status.get("120DayTimer", 0)),
            level=int(status.get("level", 0)),
            system_enabled=status.get("SystemEnable", "disable") == "enable",
            ace_mode=str(status.get("AceMode", "inactive")),
            boost_active=status.get("boost", "inactive") != "inactive",
            salt_value=int(status.get("saltValue", 0)),
        )


@dataclass
class FreshWaterIQ:
    """FreshWater IQ water quality sensor data."""

    conductivity: int
    orp: int
    chlorine: float
    ph: float
    sensor_life_percentage: float

    installed: bool

    @staticmethod
    def from_dict(data: dict[str, object]) -> FreshWaterIQ:
        """Create a FreshWaterIQ from API response data.

        Handles two response formats:
        - ``FWIQ_Parameters`` from /status (flat keys)
        - ``waterCare.status.FWIQstatus`` from /getFWIQData (nested)

        Args:
        ----
            data: Data from either source.

        Returns:
        -------
            A FreshWaterIQ instance.

        """
        # Handle the nested /getFWIQData format
        fwiq = data.get("waterCare", {}).get("status", {}).get("FWIQstatus", {})
        if fwiq:
            return FreshWaterIQ(
                conductivity=int(fwiq.get("Conductivity", 0)),
                orp=int(fwiq.get("ORP", 0)),
                chlorine=float(fwiq.get("Chlorine", 0.0)),
                ph=float(fwiq.get("pH", 0.0)),
                sensor_life_percentage=float(fwiq.get("SensorLife", 0.0)),
                installed=fwiq.get("FWIQinstalled", "notinstalled") != "notinstalled",
            )

        # Handle the flat /status FWIQ_Parameters format
        return FreshWaterIQ(
            conductivity=int(data.get("current_Current_CompConductivity", 0)),
            orp=int(data.get("current_ORP", 0)),
            chlorine=float(data.get("current_chlorine", 0.0)),
            ph=float(data.get("current_pH", 0.0)),
            sensor_life_percentage=float(
                data.get("current_SensorLife_Percentage", 0.0)
            ),
            installed=True,  # Assume installed if using flat format
        )


@dataclass
class EnergySaving:
    """Energy saving schedule configuration."""

    schedule_id: int
    mode: int
    start_hour: int
    start_minute: int
    duration: int

    @staticmethod
    def from_dict(schedule_id: int, data: dict[str, object]) -> EnergySaving:
        """Create an EnergySaving from API response data.

        Args:
        ----
            schedule_id: The schedule number (1-based).
            data: The ``energySavingN`` dict from the /status response.

        Returns:
        -------
            An EnergySaving instance.

        """
        status = data.get("status", {})
        return EnergySaving(
            schedule_id=schedule_id,
            mode=int(status.get("mode", 0)),
            start_hour=int(status.get("startHour", 0)),
            start_minute=int(status.get("startMinute", 0)),
            duration=int(status.get("duration", 0)),
        )

    @staticmethod
    def list_from_dict(data: dict[str, object]) -> list[EnergySaving]:
        """Parse all energy saving schedules from the /status response.

        Args:
        ----
            data: The ``energySavings`` dict from the /status response.

        Returns:
        -------
            A list of EnergySaving instances.

        """
        schedules: list[EnergySaving] = []
        for key, value in data.items():
            if key.startswith("energySaving") and isinstance(value, dict):
                try:
                    schedule_id = int(key[12:])
                except ValueError:
                    continue
                schedules.append(EnergySaving.from_dict(schedule_id, value))
        return sorted(schedules, key=lambda s: s.schedule_id)


@dataclass
class Versions:  # pylint: disable=too-many-instance-attributes
    """Firmware versions for all spa sub-components."""

    control_box: str
    control_panel: str
    fwss: str
    fwiq: str
    btxr: str
    cool_zone: str
    wifi_dongle: str
    amp: str
    dosing: str
    logolight: str

    @staticmethod
    def from_dict(data: dict[str, object]) -> Versions:
        """Create a Versions from API response data.

        Args:
        ----
            data: The ``productVersions.status`` dict from /status
                or from GET /versions.

        Returns:
        -------
            A Versions instance.

        """
        return Versions(
            control_box=data.get("ControlBoxFirmwareVersion", ""),
            control_panel=data.get("ControlPanelFirmwareVersion", ""),
            fwss=data.get("FWSSFirmwareVersion", ""),
            fwiq=data.get("FWIQFirmwareVersion", ""),
            btxr=data.get("BTXRFirmwareVersion", ""),
            cool_zone=data.get("CoolZoneFirmwareVersion", ""),
            wifi_dongle=data.get("WiFiDongleVersion", ""),
            amp=data.get("AMPFirmwareVersion", ""),
            dosing=data.get("DosingFirmwareVersion", ""),
            logolight=data.get("LogolightFirmwareVersion", ""),
        )


@dataclass
class ConnectionStatus:
    """Connection status between the HNA, SNA, and cloud."""

    spa_connected: bool

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
        return ConnectionStatus(
            spa_connected=connected,
        )


@dataclass
class SpaTestData:
    """Test data metrics from the spa, including raw current readings."""

    heater_test_status: str
    temp_offset: float
    vsense_cal: float
    jet1_jet2_blower_current: float
    small_loads_current: float
    heater_current: float
    jet3_current: float

    @staticmethod
    def from_dict(data: dict[str, object]) -> SpaTestData:
        """Create a SpaTestData from API response data.

        Args:
        ----
            data: The ``test_data`` dict from the /status response.

        Returns:
        -------
            A SpaTestData instance.

        """
        status = data.get("status", {})
        return SpaTestData(
            heater_test_status=str(status.get("heaterTestStatus", "off")),
            temp_offset=float(status.get("tempOffset", 0.0)),
            vsense_cal=float(status.get("VsenseCal", 0.0)),
            jet1_jet2_blower_current=(
                int(status.get("jet1+jet2+blowerCurrent", 0)) / 2560.0
            ),
            small_loads_current=int(status.get("smallLoadsCurrent", 0)) / 2560.0,
            heater_current=int(status.get("heaterCurrent", 0)) / 2560.0,
            jet3_current=int(status.get("jet3Current", 0)) / 2560.0,
        )


@dataclass
class Diagnostics:  # pylint: disable=too-many-instance-attributes
    """Diagnostic and power metrics from the spa.

    Availability depends on the spa model and whether the main control
    board (IQ2020/Eagle) is equipped with current-sensing transformers.
    Values may be ``0`` if sensors are not installed.
    """

    spa_failure_state: SpaFailureState
    heater_error: str
    power_frequency: str
    pressure_switch_status: str
    l1_n_volts: float
    l2_n_volts: float
    heater_volts: float
    jet3_volts: float
    jet1_jet2_blower_power: str
    small_loads_power: str
    heater_power: str
    jet3_power: str

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
        return Diagnostics(
            spa_failure_state=SpaFailureState.build(debug.get("spaFailureState")),
            heater_error=debug.get("heaterError", "0"),
            power_frequency=debug.get("powerFrequency", "0"),
            pressure_switch_status=debug.get("pressureSwitchStatus", "0"),
            # NOTE: The /32 scaling for volts is likely incorrect for all models or
            # specific configurations, as real-world readings (e.g., 56V on L2)
            # do not match expectations. This needs further investigation.
            l1_n_volts=int(debug.get("L1_N_Volts") or 0) / 32.0,
            l2_n_volts=int(debug.get("L2_N_Volts") or 0) / 32.0,
            heater_volts=int(debug.get("Heater_Volts") or 0) / 32.0,
            jet3_volts=int(debug.get("jet3_Volts") or 0) / 32.0,
            jet1_jet2_blower_power=debug.get("jet1_jet2_blowerPower", "0"),
            small_loads_power=debug.get("smallLoadsPower", "0"),
            heater_power=debug.get("heaterPower", "0"),
            jet3_power=debug.get("jet3Power", "0"),
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
