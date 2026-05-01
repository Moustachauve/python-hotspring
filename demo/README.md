# HotSpring Spa Control Demos

This directory contains several demonstration scripts for the `python-hotspring` library. These scripts show how to interact with a physical HotSpring spa using the Home Network Adapter (HNA).

## Prerequisites

Ensure you have the library's dependencies installed:

```bash
poetry install
```

## Running the Demos

All demos should be run from the root directory of the project using `poetry run python`. This ensures that the `src` directory is correctly added to the Python path.

Example:

```bash
poetry run python demo/demo_color_cycle.py
```

## Available Demos

- **`demo_color_cycle.py`**: Cycles Light Zone 1 through 5 different colors (Red, Blue, Green, Magenta, Aqua) with 2-second intervals.
- **`demo_set_light_red.py`**: Sets Light Zone 1 to the color Red at maximum intensity.
- **`demo_turn_off_all_lights.py`**: Turns off every enabled light zone on the spa.
- **`demo_turn_on_jet.py`**: Turns on Jet 1 at low speed.
- **`demo_turn_off_jet.py`**: Turns off Jet 1.
- **`demo_full_test.py`**: A comprehensive test script that verifies both temperature and lighting controls, reverting changes afterward.

## Configuration

The demos are pre-configured with the host IP `192.168.11.88`. If your spa has a different IP address, you will need to update the `host` variable at the top of each script.
