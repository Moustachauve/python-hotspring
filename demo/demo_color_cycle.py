"""Demo: Cycle through spa light colors.

This script demonstrates how to cycle through multiple predefined colors on
Light Zone 1 with a 2-second delay between each change. It concludes by
restoring the original color.
"""

import asyncio
import os
import sys

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring
from hotspring.const import LightColor

COLORS = [
    LightColor.RED,
    LightColor.BLUE,
    LightColor.GREEN,
    LightColor.MAGENTA,
    LightColor.AQUA,
]

DELAY = 2  # seconds between color changes


async def main() -> None:
    """Cycle Zone 1 through five colors."""
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to {host}...")
        await spa.update()
        assert spa.spa is not None

        zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
        original_color = zone1.color if zone1 else None
        print(f"Original color: {original_color}\n")

        for color in COLORS:
            print(f"  ✦  Setting → {color.name}")
            await spa.set_light_color(1, color.value)
            await asyncio.sleep(DELAY)

        print(f"\nDone! Restoring original color ({original_color})...")
        if original_color and original_color not in (
            LightColor.UNKNOWN,
            LightColor.OFF,
        ):
            await spa.set_light_color(1, original_color.value)
        print("Finished.")


if __name__ == "__main__":
    asyncio.run(main())
