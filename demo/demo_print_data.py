"""Demo: Print all spa data.

This script fetches all available data from the spa and prints it
in a structured format.
"""

import asyncio
import os
import sys
import time

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring
from hotspring.exceptions import HotSpringError
from hotspring.models import Spa


def print_identity(s: Spa) -> None:
    """Print identity info."""
    print("\n" + "=" * 20)
    print("  SPA IDENTITY")
    print("=" * 20)
    print(f"Hostname:       {s.info.hostname}")
    print(f"MAC Address:    {s.info.mac_address}")
    print(f"Root Topic:     {s.info.root_topic}")
    print(f"Brand:          {s.info.brand_name} (ID: {s.info.brand_id})")
    print(f"Collection:     {s.info.collection} (ID: {s.info.collection_id})")
    print(f"Model Name:     {s.info.model_name} (ID: {s.info.model_id})")
    print(f"Volume:         {s.info.volume} gallons")
    print(f"SNA Ready:      {s.info.sna_ready}")


def print_heater_and_jets(s: Spa) -> None:
    """Print heater and jets info."""
    print("\n" + "=" * 20)
    print("  HEATER & TEMP")
    print("=" * 20)
    unit = "°F" if "DegF" in str(s.heater.temperature_unit.value) else "°C"
    print(f"Status:       {'ON' if s.heater.is_on else 'OFF'}")
    print(f"Current Temp: {s.heater.current_temperature} {unit}")
    print(f"Set Temp:     {s.heater.set_temperature} {unit}")
    print(f"Heating Mode: {s.heater.heating_mode.value}")
    print(f"Heater Lock:  {s.heater.heater_lock}")
    print(f"Heat Pump:    {s.heater.heatpump_installed}")
    print(f"System Uptime: {s.system_uptime_hours} hrs ({s.system_uptime_seconds} s)")

    print("\n" + "=" * 20)
    print("  JETS & BLOWER")
    print("=" * 20)
    for jet in s.jets.values():
        supported = "/".join(sp.value for sp in jet.supported_speeds)
        extra = ""
        if jet.concurrent_mode:
            extra += " Concurrent=True"
        runtime = (
            f"{jet.on_hours:.2f}h ({jet.on_seconds}s)"
            if jet.on_hours is not None
            else "N/A"
        )
        print(
            f"Jet {jet.jet_id:1}: Available={jet.is_available!s:5} "
            f"SpeedType={jet.speed_type.value:11} State={jet.speed.value:10} "
            f"Supported=[{supported}] Runtime={runtime}{extra}"
        )
    blower_runtime = (
        f"{s.blower.on_hours:.2f}h ({s.blower.on_seconds}s)"
        if s.blower.on_hours is not None
        else "N/A"
    )
    print(
        f"Blower: Status={'ON' if s.blower.is_on else 'OFF':3} "
        f"Enabled={s.blower.is_enabled} Runtime={blower_runtime}"
    )


def print_lighting_and_watercare(s: Spa) -> None:
    """Print lighting and water care info."""
    print("\n" + "=" * 20)
    print("  LIGHTING")
    print("=" * 20)
    for zone in s.light_zones.values():
        print(
            f"Zone {zone.zone_id}: On={zone.is_on!s:5} Color={zone.color.value:10} "
            f"Intensity={zone.intensity} Enabled={zone.is_enabled}"
        )
    print(f"Logo Light:  {s.logo_light.brightness.value}")

    print("\n" + "=" * 20)
    print("  WATER CARE")
    print("=" * 20)
    print(f"System Enabled: {s.water_care.system_enabled}")
    print(f"Output Level:   {s.water_care.level} / 10")
    print(f"Salt Value:     {s.water_care.salt_value}")
    print(f"Cartridge:      {s.water_care.cartridge_installed}")
    print(f"10 Day Timer:   {s.water_care.ten_day_timer}")
    print(f"120 Day Timer:  {s.water_care.one_twenty_day_timer}")

    print("\n" + "=" * 20)
    print("  FRESHWATER IQ")
    print("=" * 20)
    if s.freshwater_iq.installed:
        print(f"PH:             {s.freshwater_iq.ph}")
        print(f"Chlorine:       {s.freshwater_iq.chlorine}")
        print(f"ORP:            {s.freshwater_iq.orp} mV")
        print(f"Conductivity:   {s.freshwater_iq.conductivity}")
        print(f"Sensor Life:    {s.freshwater_iq.sensor_life_percentage}%")
    else:
        print("FreshWater IQ not installed or not reporting.")


def print_diagnostics(s: Spa) -> None:
    """Print power and diagnostics info."""
    print("\n" + "=" * 20)
    print("  POWER & CURRENT")
    print("=" * 20)
    print(f"Supported:      {s.power.supported}")
    print(f"Total Power:    {s.power.total_power} VA/W")
    print(
        f"Small Loads:    {s.power.small_loads_power} W ({s.power.small_loads_current} A)"
    )
    print(
        f"J1+J2+Blower:   {s.power.jet1_jet2_blower_power} VA "
        f"({s.power.jet1_jet2_blower_current} A)"
    )
    print(f"Heater:         {s.power.heater_power} W ({s.power.heater_current} A)")
    print(f"Jet 3:          {s.power.jet3_power} VA ({s.power.jet3_current} A)")

    print("\n" + "=" * 20)
    print("  DIAGNOSTICS (DEBUG)")
    print("=" * 20)
    print(f"Failure State:  {s.diagnostics.spa_failure_state.value}")
    print(f"L2 >= 256V:     {s.diagnostics.l2_voltage_above_256v}")
    print(f"Jet 3 Volts:    {s.diagnostics.jet3_volts} V")
    print(
        f"Filter 1 / 2:   {s.diagnostics.filter_1_minutes} / {s.diagnostics.filter_2_minutes} min"
    )
    print(f"Frequency Flag: {s.diagnostics.power_frequency}")
    print(f"Circ Flow:      {s.diagnostics.circulation_pump_flow_status}")
    print(f"Pressure Switch: {s.diagnostics.pressure_switch_status}")

    print("\n" + "=" * 20)
    print("  CALIBRATION METRICS")
    print("=" * 20)
    print(f"Heater Test:    {s.test_metrics.heater_test_status}")
    print(f"Temp Offset:    {s.test_metrics.temp_offset}")
    print(f"Vsense Cal:     {s.test_metrics.vsense_cal}")

    print("\n" + "=" * 20)
    print("  VERSIONS")
    print("=" * 20)
    print(f"Control Box:    {s.versions.control_box}")
    print(f"WiFi Dongle:    {s.versions.wifi_dongle}")
    print(f"FWSS:           {s.versions.fwss}")
    print(f"FWIQ:           {s.versions.fwiq}")


async def main() -> None:
    """Print all spa data and performance metrics."""
    # Use the spa IP from your environment or default
    host = os.getenv("HOTSPRING_IP", "192.168.11.88")

    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")

        # 1. Tier 1 & 2: Initial Cold Sync (Status + Static Identity)
        t0 = time.perf_counter()
        try:
            await spa.update()
        except HotSpringError as err:
            print(f"Error fetching data: {err}")
            return
        t_initial = time.perf_counter() - t0

        # 2. Tier 1: Warm Poll (Routine status update with cached identity)
        t0 = time.perf_counter()
        try:
            await spa.update()
        except HotSpringError as err:
            print(f"Error on second update: {err}")
            return
        t_cached = time.perf_counter() - t0

        # 3. Tier 3: Extended Diagnostics (/addDebugData)
        t_diag: float | None = None
        try:
            t0 = time.perf_counter()
            await spa.update_diagnostics()
            t_diag = time.perf_counter() - t0
        except HotSpringError as err:
            print(f"Diagnostics endpoint not available: {err}")

        # 4. Tier 3: Extended Water Care (/getFWIQData)
        t_water: float | None = None
        try:
            t0 = time.perf_counter()
            await spa.update_water_care()
            t_water = time.perf_counter() - t0
        except HotSpringError:
            pass

        s = spa.spa
        if s is None:
            print("Error: Spa object is None after update.")
            return

        # Print structured spa data
        print_identity(s)
        print_heater_and_jets(s)
        print_lighting_and_watercare(s)
        if t_diag is not None:
            print_diagnostics(s)

        # Print performance benchmark summary
        print("\n" + "=" * 55)
        print("  POLLING PERFORMANCE BENCHMARK")
        print("=" * 55)
        print(f"  1. Cold Sync (Tier 1 Status + Tier 2 Identity): {t_initial:.3f} s")
        speedup = (
            f"({t_initial / t_cached:.1f}x faster!)" if 0 < t_cached < t_initial else ""
        )
        print(
            f"  2. Warm Poll (Tier 1 Fast Status Loop):        {t_cached:.3f} s  {speedup}"
        )
        if t_diag is not None:
            print(f"  3. Extended Diagnostics (Tier 3 /addDebugData): {t_diag:.3f} s")
        if t_water is not None:
            print(f"  4. Extended Water Care (Tier 3 /getFWIQData):   {t_water:.3f} s")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
