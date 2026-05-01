"""Demo: Turn off all light zones.

This script demonstrates how to turn off all enabled light zones on the spa.
It iterates through the zones found in the spa state and sends a turn-off
command to each one.
"""

import asyncio
import os
import sys

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring
from hotspring.exceptions import HotSpringError


async def main() -> None:
    """Run demo to turn off all lights."""
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")
        try:
            await spa.update()
            assert spa.spa is not None

            enabled_zones = [z for z in spa.spa.light_zones if z.is_enabled]
            print(f"Found {len(enabled_zones)} enabled light zones.")

            for zone in enabled_zones:
                print(f"Turning off Light Zone {zone.zone_id}...")
                await spa.turn_off_light(zone.zone_id)
                # Small delay between commands is good for the bridge (just to
                # be safe, not sure it's required)
                await asyncio.sleep(0.5)

            print("All turn-off commands sent.")

        except HotSpringError as e:
            print(f"A HotSpring error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
