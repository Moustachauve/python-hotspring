"""Demo: Cycle through spa light colors and brightness levels.

This script demonstrates how to:
1. Cycle through predefined colors on Light Zone 1.
2. Step through all discrete brightness levels (1 to 5).
3. Restore the original color and brightness.
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
    LightColor.YELLOW,
    LightColor.WHITE,
    LightColor.MAGENTA,
    LightColor.AQUA,
]

DELAY = 2  # seconds between changes


async def main() -> None:
    """Cycle Zone 1 through colors and brightness levels."""
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to {host}...")
        await spa.update()
        assert spa.spa is not None

        zone1 = next((z for z in spa.spa.light_zones if z.zone_id == 1), None)
        original_color = zone1.color if zone1 else LightColor.BLUE
        original_intensity = zone1.intensity if zone1 else 5
        original_is_on = zone1.is_on if zone1 else False
        original_red = zone1.c_red if zone1 else 0
        original_green = zone1.c_green if zone1 else 0
        original_blue = zone1.c_blue if zone1 else 0
        print(
            f"Original state: Color={original_color}, Intensity={original_intensity}, "
            f"IsOn={original_is_on}\n"
        )

        print("--- Step 1: Cycling through Colors ---")
        for color in COLORS:
            print(f"  ✦  Setting Color → {color.name}")
            await spa.set_light_color(1, color)
            await asyncio.sleep(DELAY)

        print("\n--- Step 2: Cycling through Brightness Levels (1 to 5) ---")
        for level in range(1, 6):
            print(f"  ✦  Setting Brightness → Level {level}/5")
            await spa.set_light_brightness(1, level)
            await asyncio.sleep(DELAY)

        print("\n--- Step 3: Restoring Original State ---")
        if original_color == LightColor.CUSTOM:
            print(
                f"  ✦  Restoring Custom RGB → "
                f"({original_red}, {original_green}, {original_blue})"
            )
            await spa.set_light_rgb(
                1, original_red, original_green, original_blue
            )
        elif original_color != LightColor.UNKNOWN:
            print(f"  ✦  Restoring Color → {original_color.name}")
            await spa.set_light_color(1, original_color)
        if original_is_on:
            print(f"  ✦  Restoring Brightness → {original_intensity}")
            await spa.set_light_brightness(1, original_intensity)
        else:
            print("  ✦  Turning Zone 1 Off...")
            await spa.turn_off_light(1)

        print("Finished.")


if __name__ == "__main__":
    asyncio.run(main())
