"""Demo: Turn off Jet 1.

This script demonstrates how to turn off a specific jet (Jet 1) by
sending the 'off' command to the spa.
"""

import asyncio
import sys
import os

# Add src to sys.path so we can import hotspring
sys.path.append(os.path.join(os.getcwd(), "src"))

from hotspring import HotSpring
from hotspring.const import JetSpeed

async def main():
    host = "192.168.11.88"
    async with HotSpring(host) as spa:
        print(f"Connecting to spa at {host}...")
        try:
            # It's good practice to update the state first to ensure connectivity
            await spa.update()

            print("Turning off Jet 1...")
            await spa.set_jet(1, JetSpeed.OFF.value)
            print("Command sent successfully.")

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
