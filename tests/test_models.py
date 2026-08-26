"""Tests for Hot Spring model parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hotspring import (
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
    JetSpeedType,
    LightColor,
    LightWheelMode,
    SpaBrand,
    SpaFailureState,
    TemperatureUnit,
)
from hotspring.models import (
    Blower,
    CleanCycle,
    ConnectionStatus,
    Diagnostics,
    EnergySaving,
    FreshWaterIQ,
    Heater,
    Jet,
    LightZone,
    LogoLight,
    Spa,
    SpaInfo,
    SpaLock,
    SpaTestData,
    Versions,
    WaterCare,
    _merge_entities,
    _parse_temperature,
)

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


class TestEnums:
    """Tests for enum parsing with build() factory."""

    def test_heating_mode_known(self) -> None:
        """Test parsing a known heating mode value."""
        assert HeatingMode.build("heatWithBoost") == HeatingMode.HEAT_WITH_BOOST

    def test_heating_mode_invalid(self) -> None:
        """Test parsing 'invalid' heating mode from real API."""
        assert HeatingMode.build("invalid") == HeatingMode.INVALID

    def test_heating_mode_unknown(self) -> None:
        """Test parsing an unknown heating mode value."""
        assert HeatingMode.build("turbo") == HeatingMode.UNKNOWN

    def test_heating_mode_none(self) -> None:
        """Test parsing None heating mode."""
        assert HeatingMode.build(None) == HeatingMode.UNKNOWN

    def test_jet_speed_known(self) -> None:
        """Test parsing a known jet speed value."""
        assert JetSpeed.build("highSpeed") == JetSpeed.HIGH_SPEED

    def test_jet_speed_off(self) -> None:
        """Test parsing jet speed off."""
        assert JetSpeed.build("off") == JetSpeed.OFF

    def test_jet_speed_unknown(self) -> None:
        """Test parsing an unknown jet speed value."""
        assert JetSpeed.build("warp") == JetSpeed.UNKNOWN

    def test_jet_speed_type_known(self) -> None:
        """Test parsing known jet speed types."""
        assert JetSpeedType.build("singleSpeed") == JetSpeedType.SINGLE_SPEED
        assert JetSpeedType.build("dualSpeed") == JetSpeedType.DUAL_SPEED

    def test_jet_speed_type_unknown(self) -> None:
        """Test parsing unknown or None jet speed types."""
        assert JetSpeedType.build("tripleSpeed") == JetSpeedType.UNKNOWN
        assert JetSpeedType.build(None) == JetSpeedType.UNKNOWN

    def test_light_color_known(self) -> None:
        """Test parsing a known light color (case-insensitive)."""
        assert LightColor.build("Blue") == LightColor.BLUE

    def test_light_color_uppercase(self) -> None:
        """Test parsing uppercase color from real API."""
        assert LightColor.build("BLUE") == LightColor.BLUE
        assert LightColor.build("RED") == LightColor.RED
        assert LightColor.build("GREEN") == LightColor.GREEN
        assert LightColor.build("YELLOW") == LightColor.YELLOW
        assert LightColor.build("WHITE") == LightColor.WHITE
        assert LightColor.build("AQUA") == LightColor.AQUA
        assert LightColor.build("MAGENTA") == LightColor.MAGENTA

    def test_light_color_unknown(self) -> None:
        """Test parsing an unknown light color."""
        assert LightColor.build("Purple") == LightColor.UNKNOWN
        assert LightColor.build("WHEEL_OFF") == LightColor.UNKNOWN
        assert LightColor.build(None) == LightColor.UNKNOWN

    def test_light_wheel_known(self) -> None:
        """Test parsing a known light wheel mode."""
        assert LightWheelMode.build("loopUp") == LightWheelMode.LOOP_UP

    def test_light_wheel_unknown(self) -> None:
        """Test parsing an unknown light wheel mode."""
        assert LightWheelMode.build("turbo") == LightWheelMode.UNKNOWN

    def test_brightness_known(self) -> None:
        """Test parsing a known brightness level."""
        assert BrightnessLevel.build("brightness_level_2") == BrightnessLevel.LEVEL_2

    def test_brightness_unknown(self) -> None:
        """Test parsing an unknown brightness level."""
        assert BrightnessLevel.build("brightness_level_99") == BrightnessLevel.UNKNOWN

    def test_temperature_unit_fahrenheit(self) -> None:
        """Test parsing Fahrenheit temperature unit."""
        assert TemperatureUnit.build("DegF") == TemperatureUnit.FAHRENHEIT

    def test_temperature_unit_celsius(self) -> None:
        """Test parsing Celsius temperature unit."""
        assert TemperatureUnit.build("DegC") == TemperatureUnit.CELSIUS

    def test_spa_failure_state_ok(self) -> None:
        """Test parsing Spa_Ok failure state."""
        assert SpaFailureState.build("Spa_Ok") == SpaFailureState.OK

    def test_spa_failure_state_unknown(self) -> None:
        """Test parsing unknown failure state."""
        assert SpaFailureState.build("Spa_Error_42") == SpaFailureState.UNKNOWN


class TestHeater:
    """Tests for Heater model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing heater from a full status response."""
        heater = Heater.from_dict(status_response["heater"])  # type: ignore[arg-type]
        assert heater == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing heater from empty dict uses defaults."""
        heater = Heater.from_dict({})
        assert heater.is_on is False
        assert heater.set_temperature is None
        assert heater.current_temperature is None
        assert heater.heating_mode == HeatingMode.UNKNOWN

    def test_empty_temperature_string(self) -> None:
        """Test that empty temperature strings parse as None."""
        heater = Heater.from_dict(
            {"status": {"setWaterTemperature": "", "currentWaterTemperature": ""}}
        )
        assert heater.set_temperature is None
        assert heater.current_temperature is None

    def test_temperature_with_unit_suffix(self) -> None:
        """Test that temperature with F/C suffix parses correctly."""
        heater = Heater.from_dict(
            {
                "status": {
                    "setWaterTemperature": " 97F",
                    "currentWaterTemperature": " 38C",
                }
            }
        )
        assert heater.set_temperature == 97.0
        assert heater.current_temperature == 38.0


class TestJet:
    """Tests for Jet model parsing."""

    def test_list_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing all jets from status response."""
        jets = Jet.list_from_dict(status_response["JET"])  # type: ignore[arg-type]
        assert jets == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing jets from empty dict."""
        jets = Jet.list_from_dict({})
        assert jets == []

    def test_jets_sorted_by_id(self) -> None:
        """Test that jets are sorted by ID."""
        data = {
            "JET3": {"config": {}, "status": {"speed": "off"}},
            "JET1": {"config": {}, "status": {"speed": "off"}},
        }
        jets = Jet.list_from_dict(data)  # type: ignore[arg-type]
        assert jets[0].jet_id == 1
        assert jets[1].jet_id == 3

    def test_jet3_concurrent_and_current(self, snapshot: SnapshotAssertion) -> None:
        """Test parsing Jet 3 concurrent mode and electrical current."""
        jet = Jet.from_dict(
            3,
            {
                "config": {"JET3": "enable", "concurrent": "enable"},
                "status": {"speed": "highSpeed", "current": 9216, "jet_3_ON_sec": 512},
            },
        )
        assert jet == snapshot

    def test_jet_negative_runtime_overflow(self) -> None:
        """Test graceful handling of negative signed integer overflow in runtime."""
        jet = Jet.from_dict(
            1,
            {
                "config": {"speed": "dualSpeed"},
                "status": {"speed": "off", "jet_1_ON_sec": -1568323328},
            },
        )
        assert jet.on_seconds == 0
        assert jet.is_on is False
        assert jet.speed_type == JetSpeedType.DUAL_SPEED

    def test_jet_properties(self) -> None:
        """Test computed properties on Jet."""
        dual_jet = Jet(
            jet_id=1,
            speed=JetSpeed.HIGH_SPEED,
            speed_type=JetSpeedType.DUAL_SPEED,
            is_enabled=True,
        )
        assert dual_jet.is_available is True
        assert dual_jet.is_on is True
        assert dual_jet.is_dual_speed is True
        assert dual_jet.is_single_speed is False
        assert dual_jet.supported_speeds == [
            JetSpeed.OFF,
            JetSpeed.LOW_SPEED,
            JetSpeed.HIGH_SPEED,
        ]

        single_jet = Jet(
            jet_id=2,
            speed=JetSpeed.OFF,
            speed_type=JetSpeedType.SINGLE_SPEED,
            is_enabled=True,
        )
        assert single_jet.is_available is True
        assert single_jet.is_on is False
        assert single_jet.is_dual_speed is False
        assert single_jet.is_single_speed is True
        assert single_jet.supported_speeds == [JetSpeed.OFF, JetSpeed.HIGH_SPEED]

        disabled_jet = Jet(
            jet_id=3,
            speed=JetSpeed.OFF,
            speed_type=JetSpeedType.SINGLE_SPEED,
            is_enabled=False,
        )
        assert disabled_jet.is_available is False
        assert disabled_jet.supported_speeds == [JetSpeed.OFF]


class TestBlower:
    """Tests for Blower model parsing."""

    def test_from_dict_disabled(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing disabled blower."""
        blower = Blower.from_dict(status_response["blower"])  # type: ignore[arg-type]
        assert blower == snapshot

    def test_from_dict_enabled_on(self, snapshot: SnapshotAssertion) -> None:
        """Test parsing enabled and running blower."""
        blower = Blower.from_dict(
            {"config": {"blower": "enable"}, "status": {"blower": "on"}}
        )
        assert blower == snapshot


class TestLightZone:
    """Tests for LightZone model parsing."""

    def test_list_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing all light zones from status response."""
        zones = LightZone.list_from_dict(status_response["lights"])  # type: ignore[arg-type]
        assert zones == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing light zones from empty dict."""
        zones = LightZone.list_from_dict({})
        assert zones == []

    def test_is_on_based_on_intensity(self) -> None:
        """Test that is_on evaluates based on intensity > 0."""
        # When Intensity is 0, is_on is False even if a color is present
        off_zone = LightZone.from_dict(
            1,
            {
                "config": {"zone_1": "enable"},
                "status": {
                    "lightWheel": "off",
                    "loopSpeed": 0,
                    "Intensity": 0,
                    "color": "BLUE",
                },
            },
        )
        assert off_zone.is_on is False
        assert off_zone.intensity == 0
        assert off_zone.color == LightColor.BLUE

        # When Intensity is 1..5, is_on is True
        on_zone = LightZone.from_dict(
            1,
            {
                "config": {"zone_1": "enable"},
                "status": {
                    "lightWheel": "off",
                    "loopSpeed": 0,
                    "Intensity": 3,
                    "color": "RED",
                },
            },
        )
        assert on_zone.is_on is True
        assert on_zone.intensity == 3
        assert on_zone.color == LightColor.RED

    def test_custom_rgb_from_payload(self, snapshot: SnapshotAssertion) -> None:
        """Test parsing custom RGB from explicit payload fields."""
        zone = LightZone.from_dict(
            1,
            {
                "config": {"zone_1": "enable"},
                "status": {
                    "color": "custom",
                    "RGBstate": "active",
                    "cRed": 0,
                    "cGreen": 255,
                    "cBlue": 255,
                    "Intensity": 5,
                },
            },
        )
        assert zone == snapshot


class TestLogoLight:
    """Tests for LogoLight model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing logo light."""
        logo = LogoLight.from_dict(status_response["logoLight"])  # type: ignore[arg-type]
        assert logo == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing logo light from empty dict."""
        logo = LogoLight.from_dict({})
        assert logo.brightness == BrightnessLevel.UNKNOWN


class TestCleanCycle:
    """Tests for CleanCycle model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing clean cycle."""
        clean = CleanCycle.from_dict(status_response["cleanCycle"])  # type: ignore[arg-type]
        assert clean == snapshot


class TestSpaLock:
    """Tests for SpaLock model parsing."""

    def test_from_dict_unlocked(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing unlocked spa."""
        lock = SpaLock.from_dict(status_response["spaLock"])  # type: ignore[arg-type]
        assert lock == snapshot

    def test_from_dict_locked(self) -> None:
        """Test parsing locked spa."""
        lock = SpaLock.from_dict({"status": {"spaLock": "on"}})
        assert lock.is_locked is True


class TestWaterCare:
    """Tests for WaterCare model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing water care data."""
        water = WaterCare.from_dict(status_response["waterCare"])  # type: ignore[arg-type]
        assert water == snapshot


class TestFreshWaterIQ:
    """Tests for FreshWaterIQ model parsing."""

    def test_from_status_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing FWIQ data from /status FWIQ_Parameters section."""
        fwiq = FreshWaterIQ.from_dict(status_response["FWIQ_Parameters"])  # type: ignore[arg-type]
        assert fwiq == snapshot

    def test_from_fwiq_endpoint(
        self, fwiq_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing FWIQ data from /getFWIQData endpoint (nested)."""
        fwiq = FreshWaterIQ.from_dict(fwiq_response)
        assert fwiq == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing FWIQ from empty dict uses defaults."""
        fwiq = FreshWaterIQ.from_dict({})
        assert fwiq.conductivity == 0
        assert fwiq.ph == 0.0
        assert fwiq.installed is False

    def test_from_flat_dict_with_existing_not_installed(self) -> None:
        """Test flat parameters set installed=True on existing instance."""
        existing = FreshWaterIQ(installed=False)
        data: dict[str, object] = {"current_pH": 7.4, "current_chlorine": 2.5}
        fwiq = FreshWaterIQ.from_dict(data, existing=existing)
        assert fwiq.installed is True
        assert fwiq.ph == 7.4
        assert fwiq.chlorine == 2.5


class TestEnergySaving:
    """Tests for EnergySaving model parsing."""

    def test_list_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing energy saving schedules."""
        schedules = EnergySaving.list_from_dict(status_response["energySavings"])  # type: ignore[arg-type]
        assert schedules == snapshot

    def test_from_dict_and_is_enabled(self) -> None:
        """Test EnergySaving is_enabled property and parsing."""
        s_off = EnergySaving.from_dict(1, {"status": {"mode": 0, "startHour": 0}})
        assert s_off.is_enabled is False

        s_on = EnergySaving.from_dict(
            2,
            {"status": {"mode": 1, "startHour": 14, "startMinute": 30, "duration": 4}},
        )
        assert s_on.is_enabled is True
        assert s_on.start_hour == 14
        assert s_on.start_minute == 30
        assert s_on.duration == 4

    def test_from_control_dict(self) -> None:
        """Test EnergySaving parsing from control dict."""
        s = EnergySaving.from_dict(
            1,
            {
                "control": {
                    "mode": "on",
                    "startHour": "10",
                    "startMinute": "15",
                    "duration": "2",
                }
            },
        )
        assert s.is_enabled is True
        assert s.start_hour == 10
        assert s.start_minute == 15
        assert s.duration == 2

        s_off = EnergySaving.from_dict(1, {"control": {"mode": "off"}}, existing=s)
        assert s_off.is_enabled is False
        assert s_off.start_hour == 10

    def test_list_from_control_dict(self) -> None:
        """Test EnergySaving list_from_dict with control wrapper."""
        schedules = EnergySaving.list_from_dict(
            {
                "control": {
                    "energySaving1": {"control": {"mode": "on", "startHour": "8"}}
                }
            }
        )
        assert len(schedules) == 1
        assert schedules[0].schedule_id == 1
        assert schedules[0].is_enabled is True
        assert schedules[0].start_hour == 8


class TestVersions:
    """Tests for Versions model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing firmware versions."""
        versions = Versions.from_dict(status_response["productVersions"]["status"])  # type: ignore[index]
        assert versions == snapshot


class TestConnectionStatus:
    """Tests for ConnectionStatus model parsing."""

    def test_from_dict_connected(
        self, connect_status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing connection status when connected."""
        status = ConnectionStatus.from_dict(connect_status_response)
        assert status == snapshot

    def test_from_dict_disconnected(self) -> None:
        """Test parsing connection status when disconnected."""
        status = ConnectionStatus.from_dict({"spaConnectStatus": "false"})
        assert status.spa_connected is False

    def test_from_empty_dict(self) -> None:
        """Test parsing connection status from empty dict."""
        status = ConnectionStatus.from_dict({})
        assert status.spa_connected is False


class TestDiagnostics:
    """Tests for Diagnostics model parsing."""

    def test_from_dict(
        self, debug_data_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing diagnostics data."""
        diag = Diagnostics.from_dict(debug_data_response)
        assert diag == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing diagnostics from empty dict uses defaults."""
        diag = Diagnostics.from_dict({})
        assert diag.spa_failure_state == SpaFailureState.UNKNOWN
        assert diag.heater_power == "0"

    def test_from_invalid_dict(self) -> None:
        """Test parsing diagnostics with invalid/null nested objects."""
        invalid_cases: list[dict[str, object]] = [
            {"debugData": None},
            {"debugData": "invalid"},
            {"debugData": {"status": None}},
            {"debugData": {"status": "invalid"}},
            {"debugData": {"status": {}}},
        ]
        for invalid_data in invalid_cases:
            diag = Diagnostics.from_dict(invalid_data)
            assert diag.spa_failure_state == SpaFailureState.UNKNOWN
            assert diag.heater_power == "0"


class TestSpaTestData:
    """Tests for SpaTestData model parsing."""

    def test_from_dict(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing test data metrics."""
        test_metrics = SpaTestData.from_dict(status_response["test_data"])  # type: ignore[arg-type]
        assert test_metrics == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing test data from empty dict uses defaults."""
        test_metrics = SpaTestData.from_dict({})
        assert test_metrics.small_loads_current == 0.0


class TestSpaInfo:
    """Tests for SpaInfo model parsing."""

    def test_from_dict(
        self, startup_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing spa identity info."""
        # Mix in spamodel data for test
        startup_response["SPAModelData"] = {
            "status": {
                "brandName": "0",
                "collectionType": "1",
                "modelType": "4",
                "volume": "335",
            }
        }
        info = SpaInfo.from_dict(startup_response)
        assert info == snapshot

    def test_from_empty_dict(self) -> None:
        """Test parsing info from empty dict uses defaults."""
        info = SpaInfo.from_dict({})
        assert info.hostname == ""
        assert info.root_topic == ""
        assert info.mac_address == ""
        assert info.sna_ready is False
        assert info.brand == SpaBrand.UNKNOWN
        assert info.brand_name == "Unknown"
        assert info.collection == "Unknown"
        assert info.model_name == "Unknown"
        assert info.brand_id == ""
        assert info.collection_id == ""
        assert info.model_id == ""
        assert info.collection_type == ""
        assert info.model_type == ""
        assert info.volume == 0

    @pytest.mark.parametrize(
        ("inputs", "expected"),
        [
            (
                ("0", "0", "7"),
                (SpaBrand.HOTSPRING, "HotSpring", "HighLife", "HighLife Envoy"),
            ),
            (
                ("0", "1", "4"),
                (SpaBrand.HOTSPRING, "HotSpring", "Limelight", "Limelight Beam Canada"),
            ),
            (
                ("0", "2", "4"),
                (SpaBrand.HOTSPRING, "HotSpring", "Hot Spot", "Hot Spot Relay"),
            ),
            (
                ("1", "1", "5"),
                (SpaBrand.CALDERA, "Caldera", "Utopia", "Utopia Geneva International"),
            ),
            (
                ("1", "3", "1"),
                (SpaBrand.CALDERA, "Caldera", "Paradise", "Paradise Kauai"),
            ),
            (
                ("1", "4", "0"),
                (SpaBrand.CALDERA, "Caldera", "Vacanza", "Vacanza Aventine"),
            ),
            (
                ("99", "99", "99"),
                (SpaBrand.UNKNOWN, "Unknown", "Unknown", "Unknown"),
            ),
            (
                ("invalid", "invalid", "invalid"),
                (SpaBrand.UNKNOWN, "Unknown", "Unknown", "Unknown"),
            ),
            (
                ("00", "01", "04"),
                (SpaBrand.HOTSPRING, "HotSpring", "Limelight", "Limelight Beam Canada"),
            ),
            (
                ("+1", "1", "5"),
                (SpaBrand.CALDERA, "Caldera", "Utopia", "Utopia Geneva International"),
            ),
            (
                (None, None, None),
                (SpaBrand.UNKNOWN, "Unknown", "Unknown", "Unknown"),
            ),
        ],
    )
    def test_spa_model_resolution(
        self,
        inputs: tuple[str | None, str | None, str | None],
        expected: tuple[SpaBrand, str, str, str],
    ) -> None:
        """Test resolution of various brand, collection, and model ID combinations."""
        brand_id, collection_id, model_id = inputs
        (
            expected_brand,
            expected_brand_name,
            expected_collection,
            expected_model,
        ) = expected
        status: dict[str, object] = {}
        if brand_id is not None:
            status["brandName"] = brand_id
        if collection_id is not None:
            status["collectionType"] = collection_id
        if model_id is not None:
            status["modelType"] = model_id
        data: dict[str, object] = {"SPAModelData": {"status": status}}
        info = SpaInfo.from_dict(data)
        assert info.brand == expected_brand
        assert info.brand_name == expected_brand_name
        assert info.collection == expected_collection
        assert info.model_name == expected_model
        assert info.brand_id == (brand_id or "")
        assert info.collection_id == (collection_id or "")
        assert info.model_id == (model_id or "")
        assert info.collection_type == (collection_id or "")
        assert info.model_type == (model_id or "")
        assert SpaBrand.build(None) == SpaBrand.UNKNOWN

    def test_mac_address_formatting(self) -> None:
        """Test MAC address extraction from invalid or valid root topics."""
        info = SpaInfo.from_dict({"rootTopic": "mySpa112233445566"})
        assert info.mac_address == "11:22:33:44:55:66"

        invalid_info = SpaInfo.from_dict({"rootTopic": "invalid_topic"})
        assert invalid_info.mac_address == ""

    @pytest.mark.parametrize(
        ("root_topic", "expected_mac"),
        [
            # Real device format example (firmware %02X produces uppercase)
            ("mySpaAABBCC112233", "AA:BB:CC:11:22:33"),
            # All zeros
            ("mySpa000000000000", "00:00:00:00:00:00"),
            # All F's
            ("mySpaFFFFFFFFFFFF", "FF:FF:FF:FF:FF:FF"),
            # Lowercase hex (defensive: not produced by firmware but valid hex)
            ("mySpaabcdef123456", "AB:CD:EF:12:34:56"),
            # Mixed case
            ("mySpaAaBbCcDdEeFf", "AA:BB:CC:DD:EE:FF"),
            # Wrong prefix
            ("otherAABBCC112233", ""),
            # Right prefix, too short (only 10 hex chars)
            ("mySpaAABBCC1122", ""),
            # Right prefix, too long (14 hex chars)
            ("mySpaAABBCC11223344", ""),
            # Right prefix + length but contains non-hex char 'G'
            ("mySpaAABBCC1122GG", ""),
            # Empty root_topic
            ("", ""),
            # Just the prefix, no hex
            ("mySpa", ""),
            # Prefix with spaces instead of hex
            ("mySpa  BBCC112233", ""),
        ],
        ids=[
            "real_device",
            "all_zeros",
            "all_ff",
            "lowercase",
            "mixed_case",
            "wrong_prefix",
            "too_short",
            "too_long",
            "non_hex",
            "empty",
            "prefix_only",
            "spaces",
        ],
    )
    def test_mac_address_edge_cases(self, root_topic: str, expected_mac: str) -> None:
        """Test MAC address extraction across all edge cases."""
        info = SpaInfo.from_dict({"rootTopic": root_topic})
        assert info.mac_address == expected_mac

    def test_sna_unknown_state(self) -> None:
        """Test SNA unknown state (real HNA reports this)."""
        info = SpaInfo.from_dict({"SNAready": "Unknown"})
        assert info.sna_ready is False


class TestSpa:  # pylint: disable=too-many-public-methods
    """Tests for the top-level Spa model."""

    def test_full_status_parsing(
        self, status_response: dict[str, object], snapshot: SnapshotAssertion
    ) -> None:
        """Test parsing a complete /status response into a Spa object."""
        spa = Spa(status_response)
        assert spa == snapshot

    def test_update_info(self, status_response: dict[str, object]) -> None:
        """Test updating spa info with startup and spamodel data."""
        spa = Spa(status_response)
        spa.update_info(
            {"HOSTNAME": "new_host", "rootTopic": "new_topic", "SNAready": "Yes"}
        )
        assert spa.info.hostname == "new_host"
        assert spa.info.root_topic == "new_topic"
        assert spa.info.sna_ready is True

        spa.update_info(
            {
                "SPAModelData": {
                    "status": {
                        "brandName": "0",
                        "collectionType": "1",
                        "modelType": "4",
                        "volume": "100",
                    }
                }
            }
        )
        assert spa.info.hostname == "new_host"
        assert spa.info.brand == SpaBrand.HOTSPRING
        assert spa.info.brand_name == "HotSpring"
        assert spa.info.collection == "Limelight"
        assert spa.info.model_name == "Limelight Beam Canada"
        assert spa.info.brand_id == "0"
        assert spa.info.collection_id == "1"
        assert spa.info.model_id == "4"
        assert spa.info.volume == 100

    def test_update_info_empty(self, status_response: dict[str, object]) -> None:
        """Test update_info with empty dicts."""
        spa = Spa(status_response)
        spa.update_info({})
        assert spa.info.hostname == ""
        assert spa.info.volume == 0

        spa.update_info({"SPAModelData": {}})
        assert spa.info.hostname == ""

        spa.update_info({"SPAModelData": {"status": "string"}})
        assert spa.info.hostname == ""

    def test_update_from_dict(self, status_response: dict[str, object]) -> None:
        """Test updating an existing Spa from new data."""
        spa = Spa(status_response)
        assert spa.heater.is_on is True

        # Modify the fixture to turn heater off
        modified = status_response.copy()
        modified["heater"] = {"status": {"heater": "off", "setWaterTemperature": "98"}}
        updated = spa.update_from_dict(modified)
        assert "heater" in updated
        assert spa.heater.is_on is False
        assert spa.heater.set_temperature == 98.0

    def test_update_from_dict_empty(self, status_response: dict[str, object]) -> None:
        """Test updating with empty dict returns empty set and preserves state."""
        spa = Spa(status_response)
        updated = spa.update_from_dict({})
        assert updated == set()
        assert spa.heater.is_on is True

    def test_update_from_dict_full_reparse(
        self, status_response: dict[str, object]
    ) -> None:
        """Test full re-parsing from status response returns all updated names."""
        spa = Spa({})
        updated = spa.update_from_dict(status_response)
        assert "heater" in updated
        assert "jets" in updated
        assert "blower" in updated
        assert "light_zones" in updated
        assert "logo_light" in updated
        assert "clean_cycle" in updated
        assert "spa_lock" in updated
        assert "water_care" in updated
        assert "freshwater_iq" in updated
        assert "test_metrics" in updated
        assert "energy_savings" in updated
        assert "versions" in updated

    def test_update_from_dict_non_dict_section(
        self, status_response: dict[str, object]
    ) -> None:
        """Test that non-dict section values in response are gracefully ignored."""
        spa = Spa(status_response)
        updated = spa.update_from_dict(
            {
                "heater": "invalid",
                "JET": [1, 2, 3],
                "lights": None,
                "energySavings": 123,
                "productVersions": "bad",
            }
        )
        assert updated == set()
        assert spa.heater.is_on is True

    def test_update_from_dict_multiple_sections(
        self, status_response: dict[str, object]
    ) -> None:
        """Test updating multiple sections at once."""
        spa = Spa(status_response)
        payload: dict[str, object] = {
            "heater": {"status": {"heater": "off", "setWaterTemperature": "100"}},
            "blower": {"config": {"blower": "enable"}, "status": {"blower": "on"}},
        }
        updated = spa.update_from_dict(payload)
        assert updated == {"heater", "blower"}
        assert spa.heater.is_on is False
        assert spa.blower.is_on is True

    def test_update_from_dict_product_versions_partial(
        self, status_response: dict[str, object]
    ) -> None:
        """Test partial update containing productVersions."""
        spa = Spa(status_response)
        payload: dict[str, object] = {
            "productVersions": {
                "status": {
                    "ControlBoxFirmwareVersion": "9.9.9",
                }
            }
        }
        updated = spa.update_from_dict(payload)
        assert updated == {"versions"}
        assert spa.versions.control_box == "9.9.9"
        assert spa.versions.control_panel == "HT25.1102F0"

    def test_update_from_dict_energy_savings_partial(
        self, status_response: dict[str, object]
    ) -> None:
        """Test partial update of energy savings preserves other schedules."""
        spa = Spa(status_response)
        initial_len = len(spa.energy_savings)
        assert initial_len > 0

        payload: dict[str, object] = {
            "energySavings": {
                "energySaving1": {
                    "status": {
                        "mode": "1",
                        "startHour": "10",
                        "startMinute": "30",
                        "duration": "120",
                    }
                }
            }
        }
        updated = spa.update_from_dict(payload)
        assert updated == {"energy_savings"}
        assert len(spa.energy_savings) == initial_len
        assert spa.energy_savings[0].start_hour == 10
        assert spa.energy_savings[0].duration == 120

    def test_partial_update_single_light_zone(
        self, status_response: dict[str, object]
    ) -> None:
        """Test that updating a single light zone preserves other zones."""
        spa = Spa(status_response)
        assert len(spa.light_zones) == 4
        assert spa.light_zones[0].color == LightColor.BLUE
        assert spa.light_zones[1].zone_id == 2

        # Simulate a command response containing only Zone 1
        partial_payload: dict[str, object] = {
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
        updated = spa.update_from_dict(partial_payload)
        assert updated == {"light_zones"}

        # Zone 1 should be updated to custom Cyan with intensity 4
        # while preserving is_enabled
        assert len(spa.light_zones) == 4
        assert spa.light_zones[0].intensity == 4
        assert spa.light_zones[0].color == LightColor.CUSTOM
        assert spa.light_zones[0].c_red == 0
        assert spa.light_zones[0].c_green == 255
        assert spa.light_zones[0].c_blue == 255
        assert spa.light_zones[0].rgb_state == "active"
        assert spa.light_zones[0].is_enabled is True

        # Other zones should be preserved intact
        assert spa.light_zones[1].zone_id == 2
        assert spa.light_zones[2].zone_id == 3
        assert spa.light_zones[3].zone_id == 4

    def test_partial_update_light_zone_switch_from_custom_to_preset(
        self, status_response: dict[str, object]
    ) -> None:
        """Test switching from custom RGB to a preset color resets rgb_state."""
        spa = Spa(status_response)
        # First set Zone 1 to custom RGB
        spa.update_from_dict(
            {
                "lights": {
                    "zone1": {
                        "status": {
                            "color": "custom",
                            "RGBstate": "active",
                            "cRed": 255,
                            "cGreen": 0,
                            "cBlue": 0,
                        }
                    }
                }
            }
        )
        assert spa.light_zones[0].color == LightColor.CUSTOM
        assert spa.light_zones[0].rgb_state == "active"

        # Now send a partial update setting color to GREEN without RGBstate
        spa.update_from_dict(
            {
                "lights": {
                    "zone1": {
                        "status": {
                            "color": "green",
                        }
                    }
                }
            }
        )
        assert spa.light_zones[0].color == LightColor.GREEN
        assert spa.light_zones[0].rgb_state == "inactive"

    def test_partial_update_single_jet(
        self, status_response: dict[str, object]
    ) -> None:
        """Test updating a single jet preserves other jets and omitted fields."""
        spa = Spa(status_response)
        assert len(spa.jets) == 3
        assert spa.jets[0].speed == JetSpeed.HIGH_SPEED
        initial_on_seconds = spa.jets[0].on_seconds
        assert initial_on_seconds > 0

        # Simulate a command response updating JET1 to off
        # (omitting config and on_seconds)
        partial_payload: dict[str, object] = {
            "JET": {
                "JET1": {
                    "status": {
                        "speed": "off",
                    }
                }
            }
        }
        updated = spa.update_from_dict(partial_payload)
        assert updated == {"jets"}

        assert len(spa.jets) == 3
        assert spa.jets[0].speed == JetSpeed.OFF
        assert spa.jets[0].is_enabled is True
        assert spa.jets[0].on_seconds == initial_on_seconds
        assert spa.jets[1].jet_id == 2
        assert spa.jets[2].jet_id == 3

    def test_partial_update_versions(self, status_response: dict[str, object]) -> None:
        """Test updating product versions partially retains cached fields."""
        spa = Spa(status_response)
        assert spa.versions.control_box == "EG25.2100K0"
        assert spa.versions.control_panel == "HT25.1102F0"

        # Update only WiFiDongleVersion
        partial_payload: dict[str, object] = {
            "productVersions": {
                "status": {
                    "WiFiDongleVersion": "NEW.123",
                }
            }
        }
        updated = spa.update_from_dict(partial_payload)
        assert updated == {"versions"}
        assert spa.versions.wifi_dongle == "NEW.123"
        # Omitted fields should retain their cached values
        assert spa.versions.control_box == "EG25.2100K0"
        assert spa.versions.control_panel == "HT25.1102F0"

    def test_merge_entities_union_and_append(self) -> None:
        """Test _merge_entities union (replace matching, retain, append new)."""
        existing = [
            Jet(jet_id=1, speed=JetSpeed.OFF, is_enabled=True, on_seconds=100),
            Jet(jet_id=2, speed=JetSpeed.OFF, is_enabled=True, on_seconds=200),
        ]
        incoming = [
            Jet(jet_id=2, speed=JetSpeed.HIGH_SPEED, is_enabled=True, on_seconds=250),
            Jet(jet_id=3, speed=JetSpeed.LOW_SPEED, is_enabled=True, on_seconds=50),
        ]

        result = _merge_entities(existing, incoming, lambda j: j.jet_id)
        assert len(result) == 3
        assert result[0].jet_id == 1
        assert result[0].speed == JetSpeed.OFF
        assert result[1].jet_id == 2
        assert result[1].speed == JetSpeed.HIGH_SPEED
        assert result[2].jet_id == 3
        assert result[2].speed == JetSpeed.LOW_SPEED

    def test_merge_entities_with_duplicate_incoming_keys(self) -> None:
        """Test _merge_entities deduplicates incoming keys cleanly."""
        existing = [
            Jet(jet_id=1, speed=JetSpeed.OFF, is_enabled=True, on_seconds=100),
        ]
        incoming = [
            Jet(jet_id=2, speed=JetSpeed.LOW_SPEED, is_enabled=True, on_seconds=50),
            Jet(jet_id=2, speed=JetSpeed.HIGH_SPEED, is_enabled=True, on_seconds=100),
        ]
        result = _merge_entities(existing, incoming, lambda j: j.jet_id)
        assert len(result) == 2
        assert result[0].jet_id == 1
        assert result[1].jet_id == 2
        assert result[1].speed == JetSpeed.HIGH_SPEED

    def test_merge_entities_empty_incoming(self) -> None:
        """Test _merge_entities with empty incoming list returns existing."""
        existing = [
            Jet(jet_id=1, speed=JetSpeed.OFF, is_enabled=True, on_seconds=100),
        ]
        result = _merge_entities(existing, [], lambda j: j.jet_id)
        assert result == existing

    def test_merge_entities_empty_existing(self) -> None:
        """Test _merge_entities with empty existing list deduplicates incoming."""
        incoming = [
            Jet(jet_id=1, speed=JetSpeed.LOW_SPEED, is_enabled=True, on_seconds=50),
            Jet(jet_id=1, speed=JetSpeed.HIGH_SPEED, is_enabled=True, on_seconds=100),
        ]
        result = _merge_entities([], incoming, lambda j: j.jet_id)
        assert len(result) == 1
        assert result[0].jet_id == 1
        assert result[0].speed == JetSpeed.HIGH_SPEED

    def test_jet_list_from_dict_case_insensitive(self) -> None:
        """Test Jet.list_from_dict parses case-insensitive keys."""
        data: dict[str, object] = {
            "jet1": {"status": {"speed": "highSpeed"}},
            "Jet2": {"status": {"speed": "lowSpeed"}},
            "JET3": {"status": {"speed": "off"}},
        }
        jets = Jet.list_from_dict(data)
        assert len(jets) == 3
        assert jets[0].jet_id == 1
        assert jets[0].speed == JetSpeed.HIGH_SPEED
        assert jets[1].jet_id == 2
        assert jets[1].speed == JetSpeed.LOW_SPEED
        assert jets[2].jet_id == 3
        assert jets[2].speed == JetSpeed.OFF

    def test_light_zone_list_from_dict_case_insensitive(self) -> None:
        """Test LightZone.list_from_dict parses case-insensitive keys."""
        data: dict[str, object] = {
            "Zone1": {"status": {"color": "BLUE", "Intensity": 3}},
            "ZONE2": {"status": {"color": "RED", "Intensity": 4}},
            "zone3": {"status": {"color": "GREEN", "Intensity": 5}},
        }
        zones = LightZone.list_from_dict(data)
        assert len(zones) == 3
        assert zones[0].zone_id == 1
        assert zones[0].color == LightColor.BLUE
        assert zones[1].zone_id == 2
        assert zones[1].color == LightColor.RED
        assert zones[2].zone_id == 3
        assert zones[2].color == LightColor.GREEN

    def test_update_info_startup(self, startup_response: dict[str, object]) -> None:
        """Test updating spa info from startup response."""
        spa = Spa({})
        spa.update_info(startup_response)
        assert spa.info.hostname == "ConnectedSpa_112233"
        assert spa.info.sna_ready is True

    def test_update_connection_status(
        self, connect_status_response: dict[str, object]
    ) -> None:
        """Test updating connection status."""
        spa = Spa({})
        spa.update_connection_status(connect_status_response)
        assert spa.connection_status.spa_connected is True

    def test_update_diagnostics(self, debug_data_response: dict[str, object]) -> None:
        """Test updating diagnostics."""
        spa = Spa({})
        spa.update_diagnostics(debug_data_response)
        assert spa.diagnostics.spa_failure_state == SpaFailureState.OK

    def test_update_freshwater_iq(self) -> None:
        """Test updating FreshWater IQ data."""
        spa = Spa({})
        spa.update_freshwater_iq(
            {
                "waterCare": {
                    "status": {
                        "FWIQstatus": {
                            "Conductivity": 1500,
                            "ORP": 750,
                            "Chlorine": 3.5,
                            "pH": 7.4,
                            "SensorLife": 95.0,
                            "FWIQinstalled": "installed",
                        }
                    }
                }
            }
        )
        assert spa.freshwater_iq.installed is True
        assert spa.freshwater_iq.chlorine == 3.5
        assert spa.freshwater_iq.ph == 7.4

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("100", 100.0),
            ("98.5", 98.5),
            ("", None),
            (None, None),
            (102, 102.0),
            (" 97F", 97.0),
            (" 38C", 38.0),
            ("100F", 100.0),
            (" F ", None),
        ],
    )
    def test_parse_temperature(
        self, value: str | int | None, expected: float | None
    ) -> None:
        """Test temperature parsing from various input formats."""
        assert _parse_temperature(value) == expected


class TestControlResponseParsing:
    """Tests for parsing control response payloads from commands."""

    def test_heater_control_payload(self) -> None:
        """Test parsing heater control command response."""
        existing = Heater(
            set_temperature=100.0,
            heating_mode=HeatingMode.AUTO_WITH_BOOST,
            temperature_unit=TemperatureUnit.FAHRENHEIT,
        )
        # Control dict sets temp and lock
        updated = Heater.from_dict(
            {
                "control": {
                    "temperatureABS": "104",
                    "heatingMode": "heatWithBoost",
                    "temperatureLock": "on",
                }
            },
            existing=existing,
        )
        assert updated.set_temperature == 104.0
        assert updated.heating_mode == HeatingMode.HEAT_WITH_BOOST
        assert updated.heater_lock is True
        assert updated.temperature_unit == TemperatureUnit.FAHRENHEIT

    def test_heater_invalid_mode_accepted(self) -> None:
        """Test that 'invalid' mode in response is accepted as a valid state."""
        existing = Heater(heating_mode=HeatingMode.AUTO_WITH_BOOST)
        updated = Heater.from_dict(
            {"status": {"heatingMode": "invalid"}}, existing=existing
        )
        assert updated.heating_mode == HeatingMode.INVALID

    def test_heater_unknown_mode_preserves_existing(self) -> None:
        """Test that 'unknown' or unparsable mode does not overwrite known mode."""
        existing = Heater(heating_mode=HeatingMode.AUTO_WITH_BOOST)
        updated = Heater.from_dict(
            {"status": {"heatingMode": "unknown"}}, existing=existing
        )
        assert updated.heating_mode == HeatingMode.AUTO_WITH_BOOST

        updated2 = Heater.from_dict(
            {"control": {"heatingMode": "nonexistent"}}, existing=existing
        )
        assert updated2.heating_mode == HeatingMode.AUTO_WITH_BOOST

    def test_heater_temperature_lock_formats(self) -> None:
        """Test parsing various truthy and falsy temperature lock formats."""
        existing = Heater(heater_lock=False)
        for val in ("on", "ON", "enable", "true", "1"):
            h = Heater.from_dict(
                {"control": {"temperatureLock": val}}, existing=existing
            )
            assert h.heater_lock is True

        for val in ("off", "OFF", "disable", "false", "0"):
            h = Heater.from_dict(
                {"control": {"temperatureLock": val}}, existing=existing
            )
            assert h.heater_lock is False

    def test_jet_control_payload(self) -> None:
        """Test parsing jet control responses."""
        jet = Jet.from_dict(1, {"control": "highSpeed"})
        assert jet.speed == JetSpeed.HIGH_SPEED

        jet2 = Jet.from_dict(2, {"control": {"speed": "lowSpeed"}})
        assert jet2.speed == JetSpeed.LOW_SPEED

        # Unknown speed preserves existing
        existing_jet = Jet(jet_id=1, speed=JetSpeed.HIGH_SPEED)
        jet_unknown = Jet.from_dict(
            1, {"control": "invalid_speed"}, existing=existing_jet
        )
        assert jet_unknown.speed == JetSpeed.HIGH_SPEED

        # Nested in control dict
        jets = Jet.list_from_dict(
            {"control": {"JET1": {"control": "highSpeed"}, "JET2": {"control": "off"}}}
        )
        assert len(jets) == 2
        assert jets[0].speed == JetSpeed.HIGH_SPEED
        assert jets[1].speed == JetSpeed.OFF

    def test_blower_control_payload(self) -> None:
        """Test parsing blower control responses."""
        blower_on = Blower.from_dict({"control": "on"})
        assert blower_on.is_on is True

        blower_off = Blower.from_dict({"control": "off"})
        assert blower_off.is_on is False

        blower_dict = Blower.from_dict({"control": {"blower": "on"}})
        assert blower_dict.is_on is True

        # Null safety
        blower_none = Blower.from_dict({"control": {"blower": None}})
        assert blower_none.is_on is False

    def test_light_zone_control_payload(self) -> None:
        """Test parsing light zone control responses."""
        # Color, wheel, and intensity
        zone = LightZone.from_dict(
            1,
            {
                "control": {
                    "color": "BLUE",
                    "lightWheel": "loopUp",
                    "IntensityAbs": 4,
                }
            },
        )
        assert zone.color == LightColor.BLUE
        assert zone.light_wheel == LightWheelMode.LOOP_UP
        assert zone.intensity == 4
        assert zone.is_on is True

        # Intensity off
        zone_off = LightZone.from_dict(1, {"control": {"Intensity": "off"}})
        assert zone_off.intensity == 0
        assert zone_off.is_on is False

        # Intensity digit
        zone_dim = LightZone.from_dict(1, {"control": {"Intensity": "3"}})
        assert zone_dim.intensity == 3
        assert zone_dim.is_on is True

        # RGB factor
        zone_rgb = LightZone.from_dict(
            1,
            {
                "control": {
                    "rgbFactor": {"red": 128, "green": 64, "blue": 255},
                }
            },
        )
        assert zone_rgb.color == LightColor.CUSTOM
        assert zone_rgb.c_red == 128
        assert zone_rgb.c_green == 64
        assert zone_rgb.c_blue == 255
        assert zone_rgb.rgb_state == "active"

        # Nested in control dict
        zones = LightZone.list_from_dict(
            {"control": {"Zone1": {"control": {"IntensityAbs": 2}}}}
        )
        assert len(zones) == 1
        assert zones[0].intensity == 2

    def test_logo_light_control_payload(self) -> None:
        """Test parsing logo light control responses."""
        logo = LogoLight.from_dict({"control": "brightness_level_1"})
        assert logo.brightness == BrightnessLevel.LEVEL_1

        logo_dict = LogoLight.from_dict(
            {"control": {"brightness": "brightness_level_2"}}
        )
        assert logo_dict.brightness == BrightnessLevel.LEVEL_2

    def test_clean_cycle_control_payload(self) -> None:
        """Test parsing clean cycle control responses."""
        cc = CleanCycle.from_dict({"control": "on"})
        assert cc.is_enabled is True

        cc_dict = CleanCycle.from_dict(
            {"control": {"cleanCycle": "off", "vanishingAct": "on"}}
        )
        assert cc_dict.is_enabled is False
        assert cc_dict.vanishing_act is True

        # Null safety
        cc_none = CleanCycle.from_dict(
            {"control": {"cleanCycle": None, "vanishingAct": None}}
        )
        assert cc_none.is_enabled is False
        assert cc_none.vanishing_act is False

    def test_spa_lock_control_payload(self) -> None:
        """Test parsing spa lock control responses."""
        lock = SpaLock.from_dict({"control": "on"})
        assert lock.is_locked is True

        lock_dict = SpaLock.from_dict({"control": {"spaLock": "off"}})
        assert lock_dict.is_locked is False

        # Null safety
        lock_none = SpaLock.from_dict({"control": {"spaLock": None}})
        assert lock_none.is_locked is False

    def test_spa_update_from_dict_control_payload(self) -> None:
        """Test full Spa model update from POST /spaManager response payloads."""
        spa = Spa(
            {
                "heater": {
                    "status": {
                        "setWaterTemperature": "100F",
                        "heatingMode": "invalid",
                    }
                },
                "JET": {"JET1": {"status": {"speed": "off"}}},
                "lights": {"zone1": {"status": {"color": "RED", "Intensity": 0}}},
            }
        )
        assert spa.heater.set_temperature == 100.0
        assert spa.heater.heating_mode == HeatingMode.INVALID

        # Partial heater control echo
        updated = spa.update_from_dict(
            {"heater": {"control": {"temperatureABS": "104"}}}
        )
        assert "heater" in updated
        assert spa.heater.set_temperature == 104.0
        assert spa.heater.heating_mode == HeatingMode.INVALID

        # Partial jet control echo
        updated_jet = spa.update_from_dict(
            {"JET": {"control": {"JET1": {"control": "highSpeed"}}}}
        )
        assert "jets" in updated_jet
        assert spa.jets[0].speed == JetSpeed.HIGH_SPEED

        # Partial light control echo
        updated_light = spa.update_from_dict(
            {"lights": {"control": {"Zone1": {"control": {"color": "BLUE"}}}}}
        )
        assert "light_zones" in updated_light
        assert spa.light_zones[0].color == LightColor.BLUE

        # Partial waterCare control echo
        updated_wc = spa.update_from_dict(
            {"waterCare": {"control": {"level": "5", "boost": "on"}}}
        )
        assert "water_care" in updated_wc
        assert spa.water_care.level == 5
        assert spa.water_care.boost_active is True

        # Partial waterCare config echo
        updated_wc_cfg = spa.update_from_dict(
            {"waterCare": {"config": {"saltSystemPowerA": "enable"}}}
        )
        assert "water_care" in updated_wc_cfg
        assert spa.water_care.system_enabled is True

        # Partial cleanCycleTimer echo
        updated_timer = spa.update_from_dict(
            {
                "cleanCycleTimer": {
                    "cleanTimer": "enable",
                    "startHour": 18,
                    "startMinute": 30,
                }
            }
        )
        assert "clean_cycle" in updated_timer
        assert spa.clean_cycle.clean_timer_enabled is True
        assert spa.clean_cycle.start_hour == 18
        assert spa.clean_cycle.start_minute == 30

        # Partial energySavings echo
        updated_es = spa.update_from_dict(
            {
                "energySavings": {
                    "energySaving1": {
                        "control": {
                            "mode": "on",
                            "startHour": "14",
                            "startMinute": "0",
                            "duration": "4",
                        }
                    }
                }
            }
        )
        assert "energy_savings" in updated_es
        assert spa.energy_savings[0].is_enabled is True
        assert spa.energy_savings[0].start_hour == 14
        assert spa.energy_savings[0].duration == 4
