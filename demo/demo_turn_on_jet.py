"""Demo: Turn on Jet 1.

This script demonstrates how to turn on a specific jet (Jet 1) at
a specific speed (LOW_SPEED).
"""

import asyncio
import os
import sys

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

# pylint: disable=wrong-import-position
from hotspring import HotSpring
from hotspring.const import JetSpeed
from hotspring.exceptions import HotSpringError


async def main() -> None:
    """Run demo to turn on jet."""
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")
        try:
            # It's good practice to update the state first to ensure connectivity
            await spa.update()
            assert spa.spa is not None

            print("Turning on Jet 1 at low speed...")
            await spa.set_jet(1, JetSpeed.LOW_SPEED.value)
            print("Command sent successfully.")

        except HotSpringError as e:
            print(f"A HotSpring error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
