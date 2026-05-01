"""Demo: Set Light Zone 1 to Red.

This script demonstrates how to set a specific light zone to a target color
(RED) at maximum intensity (5). It also shows how to poll for the update
after a short delay.
"""

import asyncio
import os
import sys

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring
from hotspring.const import LightColor
from hotspring.exceptions import HotSpringError


async def main() -> None:
    """Run demo to set light red."""
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")
        try:
            await spa.update()
            assert spa.spa is not None

            # Find current color for Zone 1
            zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
            print(f"Current color for Zone 1: {zone1.color if zone1 else 'Unknown'}")

            print("Setting Light Zone 1 to RED (Intensity 5)...")
            # set_light_color(zone, color, intensity=5, light_wheel="off")
            await spa.set_light_color(1, LightColor.RED.value)

            print("Waiting 5 seconds for spa to process and HNA to poll...")
            await asyncio.sleep(5)

            await spa.update()
            assert spa.spa is not None
            zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
            print(f"New color for Zone 1: {zone1.color if zone1 else 'Unknown'}")

            if zone1 and zone1.color == LightColor.RED:
                print("Success: Light is now RED.")
            else:
                print(
                    "Note: Reported color has not changed yet. This is common due to the LoRA bridge polling interval."
                )

        except HotSpringError as e:
            print(f"A HotSpring error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
