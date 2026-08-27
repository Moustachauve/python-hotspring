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
    print(
        f"Heater Hours: {s.heater.heater_on_hours:.2f} hrs ({s.heater.heater_on_seconds} s)"
    )
    print(f"Heater Lock:  {s.heater.heater_lock}")
    print(f"Heat Pump:    {s.heater.heatpump_installed}")

    print("\n" + "=" * 20)
    print("  JETS & BLOWER")
    print("=" * 20)
    for jet in s.jets:
        supported = "/".join(sp.value for sp in jet.supported_speeds)
        extra = ""
        if jet.concurrent_mode:
            extra += " Concurrent=True"
        print(
            f"Jet {jet.jet_id:1}: Available={jet.is_available!s:5} "
            f"SpeedType={jet.speed_type.value:11} State={jet.speed.value:10} "
            f"Supported=[{supported}] Runtime={jet.on_hours:.2f}h ({jet.on_seconds}s){extra}"
        )
    print(
        f"Blower: Status={'ON' if s.blower.is_on else 'OFF':3} "
        f"Enabled={s.blower.is_enabled}"
    )


def print_lighting_and_watercare(s: Spa) -> None:
    """Print lighting and water care info."""
    print("\n" + "=" * 20)
    print("  LIGHTING")
    print("=" * 20)
    for zone in s.light_zones:
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
    """Print diagnostics info."""
    print("\n" + "=" * 20)
    print("  DIAGNOSTICS (DEBUG)")
    print("=" * 20)
    print(f"Failure State:  {s.diagnostics.spa_failure_state.value}")
    print(f"L1 Volts:       {s.diagnostics.l1_n_volts:.1f} V")
    print(f"L2 Volts:       {s.diagnostics.l2_n_volts:.1f} V")
    print(f"Heater Volts:   {s.diagnostics.heater_volts:.1f} V")
    print(f"Jet 3 Volts:    {s.diagnostics.jet3_volts:.1f} V")
    print(f"Frequency:      {s.diagnostics.power_frequency} Hz")
    print(f"Circ Flow:      {s.diagnostics.circulation_pump_flow_status}")
    print(f"Pressure Switch: {s.diagnostics.pressure_switch_status}")

    print("\n" + "=" * 20)
    print("  RAW TEST METRICS")
    print("=" * 20)
    print(f"Heater Current: {s.test_metrics.heater_current:.2f} A")
    print(f"Jet 3 Current:  {s.test_metrics.jet3_current:.2f} A")
    print(f"Small Loads:    {s.test_metrics.small_loads_current:.2f} A")
    print(f"J1+J2+Blower:   {s.test_metrics.jet1_jet2_blower_current:.2f} A")

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
