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
            unrecognized values.

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
            unrecognized values.

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
    CUSTOM = "CUSTOM"
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

        Case-insensitive matching (real API returns e.g. "BLUE", "custom").

        Args:
        ----
            value: The raw color string from the API, or None.

        Returns:
        -------
            The matching LightColor, or LightColor.UNKNOWN for
            unrecognized values.

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
            unrecognized values.

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
            unrecognized values.

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
            unrecognized values.

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
            unrecognized values.

        """
        if value is None:
            return cls.UNKNOWN
        return _FAILURE_STATE_MAP.get(value, cls.UNKNOWN)


_FAILURE_STATE_MAP: dict[str, SpaFailureState] = {s.value: s for s in SpaFailureState}


class SpaBrand(Enum):
    """Brand of the spa (e.g. HotSpring, Caldera)."""

    UNKNOWN = "Unknown"
    HOTSPRING = "HotSpring"
    CALDERA = "Caldera"

    @classmethod
    def build(cls, value: str | int | None) -> SpaBrand:
        """Parse a raw API string or integer into a SpaBrand.

        Args:
        ----
            value: The raw brand ID from the API, or None.

        Returns:
        -------
            The matching SpaBrand enum.

        """
        if value is None:
            return cls.UNKNOWN
        try:
            val_int = int(str(value).strip())
        except ValueError:
            return cls.UNKNOWN

        if val_int == 0:
            return cls.HOTSPRING
        if val_int == 1:
            return cls.CALDERA
        return cls.UNKNOWN


SPA_COLLECTION_MAP: dict[tuple[int, int], str] = {
    # HotSpring (Brand 0)
    (0, 0): "HighLife",
    (0, 1): "Limelight",
    (0, 2): "Hot Spot",
    # Caldera (Brand 1)
    (1, 1): "Utopia",
    (1, 3): "Paradise",
    (1, 4): "Vacanza",
}

SPA_MODEL_MAP: dict[tuple[int, int, int], str] = {
    # Brand 0: HotSpring | Collection 0: HighLife
    (0, 0, 0): "HotSpring HighLife",
    (0, 0, 1): "HighLife Jetsetter",
    (0, 0, 2): "HighLife Jetsetter Canada",
    (0, 0, 3): "HighLife Jetsetter LX",
    (0, 0, 4): "HighLife Prodigy",
    (0, 0, 5): "HighLife Sovereign",
    (0, 0, 6): "HighLife Aria",
    (0, 0, 7): "HighLife Envoy",
    (0, 0, 8): "HighLife Vanguard",
    (0, 0, 9): "HighLife Grandee",
    (0, 0, 10): "HighLife Jetsetter International",
    (0, 0, 11): "HighLife Jetsetter LX International",
    (0, 0, 12): "HighLife Prodigy International",
    (0, 0, 13): "HighLife Sovereign International",
    (0, 0, 14): "HighLife Aria International",
    (0, 0, 15): "HighLife Envoy International",
    (0, 0, 16): "HighLife Vanguard International",
    (0, 0, 17): "HighLife Grandee International",
    # Brand 0: HotSpring | Collection 1: Limelight
    (0, 1, 0): "HotSpring Limelight",
    (0, 1, 1): "Limelight Beam",
    (0, 1, 2): "Limelight Beam II",
    (0, 1, 3): "Limelight Beam International",
    (0, 1, 4): "Limelight Beam Canada",
    (0, 1, 5): "Limelight Strobe",
    (0, 1, 6): "Limelight Strobe International",
    (0, 1, 7): "Limelight Flair",
    (0, 1, 8): "Limelight Flair International",
    (0, 1, 9): "Limelight Flash",
    (0, 1, 10): "Limelight Flash International",
    (0, 1, 11): "Limelight Pulse",
    (0, 1, 12): "Limelight Pulse International",
    (0, 1, 13): "Limelight Prism",
    (0, 1, 14): "Limelight Prism International",
    # Brand 0: HotSpring | Collection 2: Hot Spot
    (0, 2, 0): "Hot Spot Sx",
    (0, 2, 1): "Hot Spot Tx",
    (0, 2, 2): "Hot Spot Pace",
    (0, 2, 3): "Hot Spot Stride",
    (0, 2, 4): "Hot Spot Relay",
    (0, 2, 5): "Hot Spot Rhythm",
    (0, 2, 6): "Hot Spot Sx",
    (0, 2, 7): "Hot Spot Tx",
    (0, 2, 8): "Hot Spot Propel",
    (0, 2, 9): "Hot Spot Stride",
    (0, 2, 10): "Hot Spot Relay",
    (0, 2, 11): "Hot Spot Rhythm",
    # Brand 1: Caldera | Collection 1: Utopia
    (1, 1, 0): "Caldera Utopia",
    (1, 1, 1): "Utopia Ravello International",
    (1, 1, 2): "Utopia Niagara International",
    (1, 1, 3): "Utopia Tahitian International",
    (1, 1, 4): "Utopia Florence International",
    (1, 1, 5): "Utopia Geneva International",
    (1, 1, 6): "Utopia Cantabria International",
    (1, 1, 7): "Utopia Ravello",
    (1, 1, 8): "Utopia Niagara",
    (1, 1, 9): "Utopia Tahitian",
    (1, 1, 10): "Utopia Florence",
    (1, 1, 11): "Utopia Geneva",
    (1, 1, 12): "Utopia Cantabria",
    # Brand 1: Caldera | Collection 3: Paradise
    (1, 3, 0): "Caldera Paradise",
    (1, 3, 1): "Paradise Kauai",
    (1, 3, 2): "Paradise Kauai International",
    (1, 3, 3): "Paradise Martinique",
    (1, 3, 4): "Paradise Martinique International",
    (1, 3, 5): "Paradise Makena",
    (1, 3, 6): "Paradise Makena International",
    (1, 3, 7): "Paradise Salina",
    (1, 3, 8): "Paradise Salina International",
    (1, 3, 9): "Paradise Reunion",
    (1, 3, 10): "Paradise Reunion International",
    (1, 3, 11): "Paradise Seychelles",
    (1, 3, 12): "Paradise Seychelles International",
    # Brand 1: Caldera | Collection 4: Vacanza
    (1, 4, 0): "Vacanza Aventine",
    (1, 4, 1): "Vacanza Tarino",
    (1, 4, 2): "Vacanza Capitolo",
    (1, 4, 3): "Vacanza Celio",
    (1, 4, 4): "Vacanza Platino",
    (1, 4, 5): "Vacanza Vanto",
    (1, 4, 6): "Vacanza Marino",
    (1, 4, 7): "Vacanza Tarino_can",
    (1, 4, 8): "Vacanza Aventine",
    (1, 4, 9): "Vacanza Tarino",
    (1, 4, 10): "Vacanza Capitolo",
    (1, 4, 11): "Vacanza Celio",
    (1, 4, 12): "Vacanza Marino",
    (1, 4, 13): "Vacanza Platino",
    (1, 4, 14): "Vacanza Vanto",
}


def resolve_spa_model(
    brand_raw: str | int | None,
    collection_raw: str | int | None,
    model_raw: str | int | None,
) -> tuple[SpaBrand, str, str]:
    """Resolve raw API brand, collection, and model IDs to human-readable strings.

    Args:
    ----
        brand_raw: Raw brand string or int from API (e.g. "0" or "1").
        collection_raw: Raw collection string or int from API (e.g. "1").
        model_raw: Raw model string or int from API (e.g. "4").

    Returns:
    -------
        Tuple of (SpaBrand enum, collection name, model name).

    """
    brand = SpaBrand.build(brand_raw)

    try:
        brand_id = int(str(brand_raw)) if brand_raw is not None else -1
        collection_id = int(str(collection_raw)) if collection_raw is not None else -1
        model_id = int(str(model_raw)) if model_raw is not None else -1
    except ValueError:
        return (brand, "Unknown", "Unknown")

    collection = SPA_COLLECTION_MAP.get((brand_id, collection_id), "Unknown")
    model_name = SPA_MODEL_MAP.get((brand_id, collection_id, model_id), "Unknown")

    return (brand, collection, model_name)
