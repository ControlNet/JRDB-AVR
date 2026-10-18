"""JRDB-AVR observation SDK exception hierarchy."""

from __future__ import annotations


__all__ = [
    "ObservationSDKError",
    "ObservationValidationError",
    "ObservationImageError",
    "UnsupportedImageGeometryError",
    "ObservationMissingImageError",
]


class ObservationSDKError(Exception):
    """Base class for all Observation SDK failures."""


class ObservationValidationError(ObservationSDKError):
    """Raised when a public observation input violates the contract."""


class ObservationImageError(ObservationSDKError):
    """Raised when stitched panorama images cannot be decoded or validated."""


class UnsupportedImageGeometryError(ObservationImageError):
    """Raised when the stitched image does not match the expected geometry."""


class ObservationMissingImageError(ObservationImageError):
    """Raised when the requested stitched panorama file is missing."""
