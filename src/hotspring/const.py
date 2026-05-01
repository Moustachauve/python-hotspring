"""Constants and enumerations for Hot Spring Connected Spa Kit 2."""

from __future__ import annotations

from enum import Enum


class HeatingMode(Enum):
    """Heating mode for the spa heater.

    Controls how the spa manages water temperature regulation.
    """

    UNKNOWN = "unknown"
    INVALID = "invalid"
    HEAT_SAVER = "heatSaver"
    HEAT_WITH_BOOST = "heatWithBoost"
    CHILL = "chill"
    AUTO_WITH_BOOST = "autoWithBoost"
    AUTO_SAVER = "autoSaver"

    @classmethod
    def build(cls, value: str | None) -> HeatingMode:
        """Parse a raw API string into a HeatingMode.

        Args:
        ----
            value: The raw heating mode string from the API, or None.

        Returns:
        -------
            The matching HeatingMode, or HeatingMode.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _HEATING_MODE_MAP.get(value, cls.UNKNOWN)


_HEATING_MODE_MAP: dict[str, HeatingMode] = {m.value: m for m in HeatingMode}


class JetSpeed(Enum):
    """Speed setting for a spa jet pump.

    Jets can be single-speed or multi-speed depending on the spa model.
    """

    UNKNOWN = "unknown"
    OFF = "off"
    LOW_SPEED = "lowSpeed"
    HIGH_SPEED = "highSpeed"
    SINGLE_SPEED = "singleSpeed"

    @classmethod
    def build(cls, value: str | None) -> JetSpeed:
        """Parse a raw API string into a JetSpeed.

        Args:
        ----
            value: The raw jet speed string from the API, or None.

        Returns:
        -------
            The matching JetSpeed, or JetSpeed.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _JET_SPEED_MAP.get(value, cls.UNKNOWN)


_JET_SPEED_MAP: dict[str, JetSpeed] = {s.value: s for s in JetSpeed}


class LightColor(Enum):
    """Color setting for a spa light zone.

    Represents the available color options for multi-zone LED lighting.
    """

    UNKNOWN = "unknown"
    OFF = "WHEEL_OFF"
    ON = "WHEEL_ON"
    RED = "RED"
    BLUE = "BLUE"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    WHITE = "WHITE"
    AQUA = "AQUA"
    MAGENTA = "MAGENTA"

    @classmethod
    def build(cls, value: str | None) -> LightColor:
        """Parse a raw API string into a LightColor.

        Case-insensitive matching (real API returns e.g. "BLUE").

        Args:
        ----
            value: The raw color string from the API, or None.

        Returns:
        -------
            The matching LightColor, or LightColor.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _LIGHT_COLOR_MAP.get(value.upper(), cls.UNKNOWN)


_LIGHT_COLOR_MAP: dict[str, LightColor] = {c.value.upper(): c for c in LightColor}


class LightWheelMode(Enum):
    """Mode for the color light wheel loop."""

    UNKNOWN = "unknown"
    OFF = "off"
    ON = "on"
    LOOP_UP = "loopUp"
    LOOP_DOWN = "loopDown"

    @classmethod
    def build(cls, value: str | None) -> LightWheelMode:
        """Parse a raw API string into a LightWheelMode.

        Args:
        ----
            value: The raw light wheel string from the API, or None.

        Returns:
        -------
            The matching LightWheelMode, or LightWheelMode.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _LIGHT_WHEEL_MAP.get(value, cls.UNKNOWN)


_LIGHT_WHEEL_MAP: dict[str, LightWheelMode] = {w.value: w for w in LightWheelMode}


class BrightnessLevel(Enum):
    """Brightness level for the spa logo light.

    The logo light supports a limited set of discrete brightness levels.
    """

    UNKNOWN = "unknown"
    LEVEL_1 = "brightness_level_1"
    LEVEL_2 = "brightness_level_2"
    LEVEL_3 = "brightness_level_3"

    @classmethod
    def build(cls, value: str | None) -> BrightnessLevel:
        """Parse a raw API string into a BrightnessLevel.

        Args:
        ----
            value: The raw brightness string from the API, or None.

        Returns:
        -------
            The matching BrightnessLevel, or BrightnessLevel.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _BRIGHTNESS_MAP.get(value, cls.UNKNOWN)


_BRIGHTNESS_MAP: dict[str, BrightnessLevel] = {b.value: b for b in BrightnessLevel}


class TemperatureUnit(Enum):
    """Unit of temperature measurement used by the spa."""

    UNKNOWN = "unknown"
    FAHRENHEIT = "DegF"
    CELSIUS = "DegC"

    @classmethod
    def build(cls, value: str | None) -> TemperatureUnit:
        """Parse a raw API string into a TemperatureUnit.

        Args:
        ----
            value: The raw temperature unit string from the API, or None.

        Returns:
        -------
            The matching TemperatureUnit, or TemperatureUnit.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _TEMP_UNIT_MAP.get(value, cls.UNKNOWN)


_TEMP_UNIT_MAP: dict[str, TemperatureUnit] = {t.value: t for t in TemperatureUnit}


class SpaFailureState(Enum):
    """Failure state of the spa as reported by diagnostics."""

    UNKNOWN = "unknown"
    OK = "Spa_Ok"

    @classmethod
    def build(cls, value: str | None) -> SpaFailureState:
        """Parse a raw API string into a SpaFailureState.

        Args:
        ----
            value: The raw failure state string from the API, or None.

        Returns:
        -------
            The matching SpaFailureState, or SpaFailureState.UNKNOWN for
            unrecognised values.

        """
        if value is None:
            return cls.UNKNOWN
        return _FAILURE_STATE_MAP.get(value, cls.UNKNOWN)


_FAILURE_STATE_MAP: dict[str, SpaFailureState] = {s.value: s for s in SpaFailureState}
