"""Demo: Print all spa data.

This script fetches all available data from the spa and prints it
in a structured format.
"""

import asyncio
import os
import sys

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring


async def main() -> None:
    """Print all spa data."""
    # Use the spa IP from your environment or default
    host = os.getenv("HOTSPRING_IP", "192.168.11.88")

    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")
        try:
            await spa.update()
            # Diagnostics/Debug data is often on a separate endpoint
            await spa.update_diagnostics()
        except Exception as err:
            print(f"Error fetching data: {err}")
            return

        s = spa.spa
        if s is None:
            print("Error: Spa object is None after update.")
            return

        print("\n" + "=" * 20)
        print("  SPA IDENTITY")
        print("=" * 20)
        print(f"Model:        {s.info.model}")
        print(f"Hostname:     {s.info.hostname}")
        print(f"MAC Address:  {s.info.mac_address}")
        print(f"SSID:         {s.info.ssid}")
        print(f"SNA Ready:    {s.info.sna_ready}")

        print("\n" + "=" * 20)
        print("  HEATER & TEMP")
        print("=" * 20)
        unit = "°F" if "DegF" in str(s.heater.temperature_unit.value) else "°C"
        print(f"Status:       {'ON' if s.heater.is_on else 'OFF'}")
        print(f"Current Temp: {s.heater.current_temperature} {unit}")
        print(f"Set Temp:     {s.heater.set_temperature} {unit}")
        print(f"Heating Mode: {s.heater.heating_mode.value}")
        print(f"Current Draw: {s.heater.heater_current:.2f} A")
        print(f"Total Runtime: {s.heater.heater_on_seconds} seconds")
        print(f"Heater Lock:  {s.heater.heater_lock}")
        print(f"Heat Pump:    {s.heater.heatpump_installed}")

        print("\n" + "=" * 20)
        print("  JETS & BLOWER")
        print("=" * 20)
        for jet in s.jets:
            print(
                f"Jet {jet.jet_id:1}: Speed={jet.speed.value:10} "
                f"Enabled={str(jet.is_enabled):5} Runtime={jet.on_seconds}s"
            )
        print(f"Blower: Status={'ON' if s.blower.is_on else 'OFF':3} Enabled={s.blower.is_enabled}")

        print("\n" + "=" * 20)
        print("  LIGHTING")
        print("=" * 20)
        for zone in s.light_zones:
            print(
                f"Zone {zone.zone_id}: On={str(zone.is_on):5} Color={zone.color.value:10} "
                f"Intensity={zone.intensity} Enabled={zone.is_enabled}"
            )
        print(f"Logo Light:  {s.logo_light.brightness.value}")

        print("\n" + "=" * 20)
        print("  WATER CARE")
        print("=" * 20)
        print(f"System Enabled: {s.water_care.system_enabled}")
        print(f"Output Level:   {s.water_care.level} / 10")
        print(f"Salt Value:     {s.water_care.salt_value}")
        print(f"Salt Level:     {s.water_care.salt_level}")
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

        print("\n" + "=" * 20)
        print("  DIAGNOSTICS (DEBUG)")
        print("=" * 20)
        print(f"Failure State:  {s.diagnostics.spa_failure_state.value}")
        print(f"L1 Volts:       {s.diagnostics.l1_n_volts} V")
        print(f"L2 Volts:       {s.diagnostics.l2_n_volts} V")
        print(f"Heater Volts:   {s.diagnostics.heater_volts} V")
        print(f"Jet 3 Volts:    {s.diagnostics.jet3_volts} V")
        print(f"Frequency:      {s.diagnostics.power_frequency} Hz")
        print(f"Heater Power:   {s.diagnostics.heater_power} Amps")
        print(f"Jet 1/2/Blower: {s.diagnostics.jet1_jet2_blower_power} Amps")

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


if __name__ == "__main__":
    asyncio.run(main())
