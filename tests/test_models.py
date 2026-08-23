"""Tests for Hot Spring model parsing."""

from __future__ import annotations

import pytest

from hotspring import (
    BrightnessLevel,
    HeatingMode,
    JetSpeed,
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
    _parse_temperature,
)


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

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing heater from a full status response."""
        heater = Heater.from_dict(status_response["heater"])  # type: ignore[arg-type]
        assert heater.is_on is True
        assert heater.heater_lock is False
        assert heater.heatpump_installed is False
        assert heater.heating_mode == HeatingMode.HEAT_WITH_BOOST
        assert heater.heater_current == 7.5
        assert heater.heater_on_seconds == 52046
        assert heater.set_temperature == 100.0
        assert heater.current_temperature == 100.0
        assert heater.temperature_unit == TemperatureUnit.FAHRENHEIT

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

    def test_list_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing all jets from status response."""
        jets = Jet.list_from_dict(status_response["JET"])  # type: ignore[arg-type]
        assert len(jets) == 3

        # JET1 should be enabled and running
        assert jets[0].jet_id == 1
        assert jets[0].speed == JetSpeed.HIGH_SPEED
        assert jets[0].on_seconds == 1061668

        # JET2 should be enabled (no JET2 key = default enable) and off
        assert jets[1].jet_id == 2
        assert jets[1].is_enabled is True
        assert jets[1].speed == JetSpeed.OFF

        # JET3 should be disabled
        assert jets[2].jet_id == 3
        assert jets[2].is_enabled is False

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


class TestBlower:
    """Tests for Blower model parsing."""

    def test_from_dict_disabled(self, status_response: dict[str, object]) -> None:
        """Test parsing disabled blower."""
        blower = Blower.from_dict(status_response["blower"])  # type: ignore[arg-type]
        assert blower.is_enabled is False
        assert blower.is_on is False

    def test_from_dict_enabled_on(self) -> None:
        """Test parsing enabled and running blower."""
        blower = Blower.from_dict(
            {"config": {"blower": "enable"}, "status": {"blower": "on"}}
        )
        assert blower.is_enabled is True
        assert blower.is_on is True


class TestLightZone:
    """Tests for LightZone model parsing."""

    def test_list_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing all light zones from status response."""
        zones = LightZone.list_from_dict(status_response["lights"])  # type: ignore[arg-type]
        assert len(zones) == 4

        # Zone 1 should be on with Blue color (API sends "BLUE")
        assert zones[0].zone_id == 1
        assert zones[0].is_enabled is True
        assert zones[0].is_on is True
        assert zones[0].color == LightColor.BLUE
        assert zones[0].light_wheel == LightWheelMode.OFF
        assert zones[0].intensity == 5
        assert zones[0].loop_speed == 0

        # Zone 2 should be disabled
        assert zones[1].zone_id == 2
        assert zones[1].is_enabled is False

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

    def test_custom_rgb_from_payload(self) -> None:
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
        assert zone.color == LightColor.CUSTOM
        assert zone.rgb_state == "active"
        assert zone.c_red == 0
        assert zone.c_green == 255
        assert zone.c_blue == 255


class TestLogoLight:
    """Tests for LogoLight model parsing."""

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing logo light."""
        logo = LogoLight.from_dict(status_response["logoLight"])  # type: ignore[arg-type]
        assert logo.brightness == BrightnessLevel.LEVEL_2

    def test_from_empty_dict(self) -> None:
        """Test parsing logo light from empty dict."""
        logo = LogoLight.from_dict({})
        assert logo.brightness == BrightnessLevel.UNKNOWN


class TestCleanCycle:
    """Tests for CleanCycle model parsing."""

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing clean cycle."""
        clean = CleanCycle.from_dict(status_response["cleanCycle"])  # type: ignore[arg-type]
        assert clean.is_enabled is True
        assert clean.vanishing_act is False


class TestSpaLock:
    """Tests for SpaLock model parsing."""

    def test_from_dict_unlocked(self, status_response: dict[str, object]) -> None:
        """Test parsing unlocked spa."""
        lock = SpaLock.from_dict(status_response["spaLock"])  # type: ignore[arg-type]
        assert lock.is_locked is False

    def test_from_dict_locked(self) -> None:
        """Test parsing locked spa."""
        lock = SpaLock.from_dict({"status": {"spaLock": "on"}})
        assert lock.is_locked is True


class TestWaterCare:
    """Tests for WaterCare model parsing."""

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing water care data."""
        water = WaterCare.from_dict(status_response["waterCare"])  # type: ignore[arg-type]
        assert water.cartridge_installed is True
        assert water.ten_day_timer == 0
        assert water.one_twenty_day_timer == 0
        assert water.level == 3
        assert water.system_enabled is True
        assert water.ace_mode == "normal"
        assert water.boost_active is False
        assert water.salt_value == 0


class TestFreshWaterIQ:
    """Tests for FreshWaterIQ model parsing."""

    def test_from_status_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing FWIQ data from /status FWIQ_Parameters section."""
        fwiq = FreshWaterIQ.from_dict(status_response["FWIQ_Parameters"])  # type: ignore[arg-type]
        assert fwiq.conductivity == 1500
        assert fwiq.orp == 650
        assert fwiq.chlorine == 3.2
        assert fwiq.ph == 7.5
        assert fwiq.sensor_life_percentage == 85.0
        assert fwiq.installed is True  # Flat format assumes installed

    def test_from_fwiq_endpoint(self, fwiq_response: dict[str, object]) -> None:
        """Test parsing FWIQ data from /getFWIQData endpoint (nested)."""
        fwiq = FreshWaterIQ.from_dict(fwiq_response)
        assert fwiq.installed is False
        assert fwiq.ph == -1.0
        assert fwiq.chlorine == -1.0
        assert fwiq.orp == -1
        assert fwiq.conductivity == -1
        assert fwiq.sensor_life_percentage == -1.0

    def test_from_empty_dict(self) -> None:
        """Test parsing FWIQ from empty dict uses defaults."""
        fwiq = FreshWaterIQ.from_dict({})
        assert fwiq.conductivity == 0
        assert fwiq.ph == 0.0
        assert fwiq.installed is True  # Flat format default


class TestEnergySaving:
    """Tests for EnergySaving model parsing."""

    def test_list_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing energy saving schedules."""
        schedules = EnergySaving.list_from_dict(status_response["energySavings"])  # type: ignore[arg-type]
        assert len(schedules) == 2
        assert schedules[0].schedule_id == 1
        assert schedules[0].mode == 0
        assert schedules[1].schedule_id == 2


class TestVersions:
    """Tests for Versions model parsing."""

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing firmware versions."""
        versions = Versions.from_dict(status_response["productVersions"]["status"])  # type: ignore[index]
        assert versions.control_box == "EG25.2100K0"
        assert versions.control_panel == "HT25.1102F0"
        assert versions.fwss == "105"
        assert versions.cool_zone == ""
        assert versions.amp == ""


class TestConnectionStatus:
    """Tests for ConnectionStatus model parsing."""

    def test_from_dict_connected(
        self, connect_status_response: dict[str, object]
    ) -> None:
        """Test parsing connection status when connected."""
        status = ConnectionStatus.from_dict(connect_status_response)
        assert status.spa_connected is True

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

    def test_from_dict(self, debug_data_response: dict[str, object]) -> None:
        """Test parsing diagnostics data."""
        diag = Diagnostics.from_dict(debug_data_response)
        assert diag.spa_failure_state == SpaFailureState.OK
        assert diag.heater_error == "0"
        assert diag.power_frequency == "0"
        assert diag.heater_power == "60"
        assert diag.l1_n_volts == 0.0

    def test_from_empty_dict(self) -> None:
        """Test parsing diagnostics from empty dict uses defaults."""
        diag = Diagnostics.from_dict({})
        assert diag.spa_failure_state == SpaFailureState.UNKNOWN
        assert diag.heater_power == "0"


class TestSpaTestData:
    """Tests for SpaTestData model parsing."""

    def test_from_dict(self, status_response: dict[str, object]) -> None:
        """Test parsing test data metrics."""
        test_metrics = SpaTestData.from_dict(status_response["test_data"])  # type: ignore[arg-type]
        assert test_metrics.heater_test_status == "off"
        assert test_metrics.temp_offset == 0.0
        assert test_metrics.vsense_cal == 0.0
        assert test_metrics.small_loads_current == 0.0
        assert test_metrics.heater_current == 7.5
        assert test_metrics.jet3_current == 0.0

    def test_from_empty_dict(self) -> None:
        """Test parsing test data from empty dict uses defaults."""
        test_metrics = SpaTestData.from_dict({})
        assert test_metrics.small_loads_current == 0.0


class TestSpaInfo:
    """Tests for SpaInfo model parsing."""

    def test_from_dict(self, startup_response: dict[str, object]) -> None:
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
        assert info.hostname == "ConnectedSpa_112233"
        assert info.root_topic == "mySpaAABBCC112233"
        assert info.mac_address == "AA:BB:CC:11:22:33"
        assert info.sna_ready is True
        assert info.brand == SpaBrand.HOTSPRING
        assert info.brand_name == "HotSpring"
        assert info.collection == "Limelight"
        assert info.model_name == "Limelight Beam Canada"
        assert info.brand_id == "0"
        assert info.collection_id == "1"
        assert info.model_id == "4"
        assert info.collection_type == "1"
        assert info.model_type == "4"
        assert info.volume == 335

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


class TestSpa:
    """Tests for the top-level Spa model."""

    def test_full_status_parsing(self, status_response: dict[str, object]) -> None:
        """Test parsing a complete /status response into a Spa object."""
        spa = Spa(status_response)

        # Verify heater
        assert spa.heater.is_on is True
        assert spa.heater.current_temperature == 100.0

        # Verify jets
        assert len(spa.jets) == 3
        assert spa.jets[0].speed == JetSpeed.HIGH_SPEED

        # Verify lights
        assert len(spa.light_zones) == 4
        assert spa.light_zones[0].color == LightColor.BLUE

        # Verify other components
        assert spa.clean_cycle.is_enabled is True
        assert spa.spa_lock.is_locked is False
        assert spa.blower.is_enabled is False
        assert spa.logo_light.brightness == BrightnessLevel.LEVEL_2

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
        spa.update_from_dict(modified)
        assert spa.heater.is_on is False
        assert spa.heater.set_temperature == 98.0

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
        assert len(spa.light_zones) == 4
        assert spa.light_zones[0].intensity == 4
        assert spa.light_zones[0].color == LightColor.CUSTOM
        assert spa.light_zones[0].c_red == 0
        assert spa.light_zones[0].c_green == 255
        assert spa.light_zones[0].c_blue == 255
        assert spa.light_zones[0].rgb_state == "active"

        # Other zones should be preserved intact
        assert spa.light_zones[1].zone_id == 2
        assert spa.light_zones[2].zone_id == 3
        assert spa.light_zones[3].zone_id == 4

    def test_partial_update_single_jet(
        self, status_response: dict[str, object]
    ) -> None:
        """Test that updating a single jet preserves other jets."""
        spa = Spa(status_response)
        assert len(spa.jets) == 3
        assert spa.jets[0].speed == JetSpeed.HIGH_SPEED

        # Simulate a command response updating JET1 to off
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
        assert spa.jets[1].jet_id == 2
        assert spa.jets[2].jet_id == 3

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
        ],
    )
    def test_parse_temperature(
        self, value: str | int | None, expected: float | None
    ) -> None:
        """Test temperature parsing from various input formats."""
        assert _parse_temperature(value) == expected
