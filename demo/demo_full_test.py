"""Demo: Full command test suite.

This script performs a comprehensive test of various spa control commands:
1. Temperature: Read, increment, verify, and revert.
2. Lighting: Read color, set to RED, verify, and revert.

It's a useful utility to verify that the library is communicating correctly
with the physical hardware.
"""

import asyncio
import sys
import os

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

from hotspring import HotSpring


async def main():
    async with HotSpring("192.168.11.88") as spa:
        print("Fetching spa state...")
        await spa.update()

        print(f"Current Temperature: {spa.spa.heater.current_temperature}")
        print(f"Set Temperature: {spa.spa.heater.set_temperature}")

        target = spa.spa.heater.set_temperature
        if target is not None:
            new_target = target + 1
            if new_target > 104:
                new_target = target - 1

            print(f"Setting temperature to {new_target}...")
            await spa.set_temperature(int(new_target))
            print("Temperature set command sent.")

            await asyncio.sleep(2)

            await spa.update()
            print(f"New Set Temperature: {spa.spa.heater.set_temperature}")

            print(f"Reverting temperature to {target}...")
            await spa.set_temperature(int(target))
            print("Temperature reverted.")

        print("\nTesting light color...")
        # Get current color first
        zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
        current_color = zone1.color if zone1 else None
        print(f"Current color: {current_color}")

        print("Setting light to RED...")
        await spa.set_light_color(1, "red")

        await asyncio.sleep(2)
        await spa.update()
        zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
        print(f"New color: {zone1.color if zone1 else None}")

        if current_color and current_color.value != "unknown":
            print(f"Reverting color to {current_color.value}...")
            await spa.set_light_color(1, current_color.value)


if __name__ == "__main__":
    asyncio.run(main())
