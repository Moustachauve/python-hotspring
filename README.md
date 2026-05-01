[![GitHub Release][releases-shield]][releases]
[![Python Versions][python-versions-shield]][pypi]
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE)

[![Build Status][build-shield]][build]
[![Code Coverage][codecov-shield]][codecov]

Asynchronous Python client for Hot Spring Connected Spa Kit 2.

> [!WARNING]
> This library is currently in heavy development. Not all features might work
> perfectly, and some features may not be fully tested as they depend on the
> physical hardware available for testing.

## About

This package allows you to control and monitor a Hot Spring spa equipped with the
[Connected Spa Kit 2](https://www.hotspring.com/) programmatically via its local
HTTP API. It communicates with the Home Network Adapter (HNA), which bridges your
home network to the spa's control board over LoRA radio.

It is primarily designed to be used as the communication layer for an official
[Home Assistant](https://www.home-assistant.io/) integration.

### Supported Features

- **Temperature monitoring & control** — Read current/target water temperature,
  set target temperature, change heating modes
- **Jets & blower** — Control jet speeds (off, low, high) across all jet pumps
- **Multi-zone lighting** — Set colors and brightness for up to 4 light zones
  plus the logo light
- **Water care** — Monitor FreshWater IQ salt system metrics (pH, chlorine,
  ORP, sensor life)
- **Diagnostics** — Read voltage, power consumption, and failure states
- **Connection monitoring** — Check LoRA bridge and cloud connectivity status
- **Energy saving schedules** — View configured energy saving time windows
- **Clean cycle** — Start or stop the 10-minute clean cycle

### Compatible Spas

This library works with any Hot Spring, Caldera, or Freeflow spa that supports
the **Connected Spa Kit 2** (compatible with spas from 2014 onwards that use
the IQ2020/Eagle control board).

> [!NOTE]
> This library has been primarily tested on a **Hotspring Hot Spot Relay 2025**.
> Compatibility with other specific models and configurations may vary.

## Installation

```bash
pip install python-hotspring
```

## Usage

```python
import asyncio

from hotspring import HotSpring


async def main() -> None:
    """Show example of controlling your Hot Spring spa."""
    async with HotSpring("192.168.1.100") as spa_client:
        # Get full spa status
        spa = await spa_client.update()
        print(f"Water temperature: {spa.heater.current_temperature}°F")
        print(f"Heater: {'on' if spa.heater.is_on else 'off'}")
        print(f"Heating mode: {spa.heater.heating_mode.name}")

        # Control the spa
        await spa_client.set_temperature(102)
        await spa_client.set_jet(1, "highSpeed")
        await spa_client.set_light_color(1, "Blue")
        await spa_client.set_clean_cycle(enabled=True)


if __name__ == "__main__":
    asyncio.run(main())
```

## Demos

Several demonstration scripts are available in the [demo/](demo/README.md) directory to help you get started with the library and verify connectivity with your spa.

## Architecture

The Hot Spring Connected Spa Kit 2 uses a two-part system:

- **HNA (Home Network Adapter)** — Located inside the home, connects to
  WiFi/Internet and runs the local HTTP API that this library communicates with
- **SNA (Spa Network Adapter)** — Located inside the spa, wired to the IQ2020
  control board via RS485, communicates with the HNA via LoRA radio

All API calls go through the HNA, which relays commands to the spa over LoRA.
Commands typically take 2–5 seconds to process.

## Changelog & Releases

This repository keeps a change log using [GitHub's releases][releases]
functionality.

Releases are based on [Semantic Versioning][semver], and use the format
of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented
based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Contributing

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

Thank you for being involved! :heart_eyes:

## Setting up development environment

This Python project is fully managed using the [Poetry][poetry] dependency
manager.

You need at least:

- Python 3.12+
- [Poetry][poetry-install]

To install all packages, including all development requirements:

```bash
poetry install
```

As this repository uses the [prek][prek] framework, all changes
are linted and tested with each commit. You can run all checks and tests
manually, using the following command:

```bash
poetry run prek run --all-files
```

To run just the Python tests:

```bash
poetry run pytest
```

## Authors & contributors

The original setup of this repository is by @Moustachauve.

The structure of this library is inspired by [python-wled][python-wled] from
@frenck and [pytechnove][pytechnove] from @Moustachauve.

[build-shield]: https://github.com/Moustachauve/python-hotspring/actions/workflows/tests.yaml/badge.svg
[build]: https://github.com/Moustachauve/python-hotspring/actions/workflows/tests.yaml
[codecov-shield]: https://codecov.io/gh/Moustachauve/python-hotspring/branch/main/graph/badge.svg
[codecov]: https://codecov.io/gh/Moustachauve/python-hotspring
[license-shield]: https://img.shields.io/github/license/Moustachauve/python-hotspring.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[poetry-install]: https://python-poetry.org/docs/#installation
[poetry]: https://python-poetry.org
[prek]: https://github.com/j178/prek
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[pypi]: https://pypi.org/project/python-hotspring/
[python-versions-shield]: https://img.shields.io/pypi/pyversions/python-hotspring
[releases-shield]: https://img.shields.io/github/release/Moustachauve/python-hotspring.svg
[releases]: https://github.com/Moustachauve/python-hotspring/releases
[semver]: http://semver.org/spec/v2.0.0.html
[python-wled]: https://github.com/frenck/python-wled
[pytechnove]: https://github.com/Moustachauve/pytechnove/
