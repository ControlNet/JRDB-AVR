"""Public types for the JRDB-AVR observation SDK contract."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class ObservationResult:
    """Typed payload holding the observation crop and its metadata."""

    image: Image.Image
    sequence: str
    frame_index: int
    frame_id: str
    input_angle_deg: float
    normalized_angle_deg: float
    center_x_px: int
    crop_left_px: int
    crop_right_px: int
    wraparound: bool
    nearest_viewpoint_id: int
    source_image_path: str
    source_image_width: int
    source_image_height: int
    crop_size: int

    def __post_init__(self) -> None:
        if not self.sequence:
            raise ValueError("sequence is required")
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if not (0 <= self.normalized_angle_deg < 360):
            raise ValueError("normalized_angle_deg must be in [0, 360)")
        if self.source_image_width <= 0 or self.source_image_height <= 0:
            raise ValueError("source image dimensions must be positive")
        if self.crop_size <= 0:
            raise ValueError("crop_size must be positive")
