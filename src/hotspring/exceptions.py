"""Exceptions for Hot Spring Connected Spa Kit 2."""


class HotSpringError(Exception):
    """Generic Hot Spring exception."""


class HotSpringConnectionError(HotSpringError):
    """Hot Spring connection exception."""


class HotSpringConnectionTimeoutError(HotSpringConnectionError):
    """Hot Spring connection timeout exception."""


class HotSpringNotReadyError(HotSpringError):
    """Hot Spring SNA not ready exception.

    Raised when the LoRA bridge between the HNA (house) and SNA (spa)
    is not connected. Commands will fail and status data may be stale.
    """


class HotSpringCommandError(HotSpringError):
    """Hot Spring command error exception.

    Raised when a command sent to the spa is rejected or fails.
    """


class HotSpringInvalidDeviceError(HotSpringError):
    """Hot Spring invalid device exception.

    Raised when attempting to connect to or command an unsupported device.
    """


class HotSpringSNADetectedError(HotSpringInvalidDeviceError):
    """Hot Spring SNA detected exception.

    Raised when connecting to a Spa Network Adapter (SNA) instead of
    the Home Network Adapter (HNA). The HNA must be used as the API bridge.
    """
