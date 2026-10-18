import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

# Constants for stitched panoramic images
STITCHED_WIDTH = 3760
STITCHED_HEIGHT = 480
CROP_SIZE = 480
VIEWPOINT_STEP_DEG = 10
NUM_VIEWPOINTS = 36


@dataclass(frozen=True)
class CropSegment:
    source_left_px: int
    source_right_px: int
    output_left_px: int
    output_right_px: int

    def __post_init__(self) -> None:
        if self.source_left_px < 0 or self.source_right_px < 0:
            raise ValueError("CropSegment source bounds must be non-negative")
        if self.output_left_px < 0 or self.output_right_px < 0:
            raise ValueError("CropSegment output bounds must be non-negative")

        source_width = self.source_right_px - self.source_left_px
        output_width = self.output_right_px - self.output_left_px
        if source_width <= 0:
            raise ValueError(
                "CropSegment source_right_px must be greater than source_left_px"
            )
        if output_width <= 0:
            raise ValueError(
                "CropSegment output_right_px must be greater than output_left_px"
            )
        if source_width != output_width:
            raise ValueError(
                "CropSegment source and output widths must match exactly"
            )


@dataclass(frozen=True)
class CropMetadata:
    center_x_px: int
    crop_left_px: int
    crop_right_px: int
    crop_size: int
    wraparound: bool
    wrap_direction: Literal["none", "left", "right"]
    segments: tuple[CropSegment, ...]

    def __post_init__(self) -> None:
        if self.crop_size <= 0:
            raise ValueError(f"crop_size must be positive, got {self.crop_size!r}")
        if self.crop_right_px - self.crop_left_px != self.crop_size:
            raise ValueError(
                "crop_right_px - crop_left_px must equal crop_size exactly"
            )
        if self.wrap_direction not in {"none", "left", "right"}:
            raise ValueError(
                f"wrap_direction must be 'none', 'left', or 'right', got {self.wrap_direction!r}"
            )
        if len(self.segments) == 0:
            raise ValueError("segments must not be empty")

        expected_output_left = 0
        for segment in self.segments:
            if segment.output_left_px != expected_output_left:
                raise ValueError("segments must cover the crop contiguously in output order")
            expected_output_left = segment.output_right_px

        if expected_output_left != self.crop_size:
            raise ValueError("segments must reconstruct the crop size exactly once")
        if self.wraparound and self.wrap_direction == "none":
            raise ValueError("wrap_direction must be explicit when wraparound is True")
        if (not self.wraparound) and self.wrap_direction != "none":
            raise ValueError("wrap_direction must be 'none' when wraparound is False")
        if self.wrap_direction == "none" and len(self.segments) != 1:
            raise ValueError("non-wrap crops must contain exactly one segment")
        if self.wrap_direction in {"left", "right"} and len(self.segments) != 2:
            raise ValueError("wrap crops must contain exactly two ordered segments")


def _validate_angle_deg(angle_deg: object) -> float:
    if isinstance(angle_deg, bool):
        raise ValueError(f"angle_deg must be a finite number, got {angle_deg!r}")
    if not isinstance(angle_deg, int | float):
        raise ValueError(f"angle_deg must be a finite number, got {angle_deg!r}")

    angle_value = float(angle_deg)
    if not math.isfinite(angle_value):
        raise ValueError(f"angle_deg must be finite, got {angle_deg!r}")
    return angle_value


def _validate_image_width(image_width: object) -> int:
    if isinstance(image_width, bool) or not isinstance(image_width, int):
        raise ValueError(f"image_width must be a positive integer, got {image_width!r}")
    if image_width <= 0:
        raise ValueError(f"image_width must be a positive integer, got {image_width!r}")
    return image_width


def _validate_center_x(center_x: object, image_width: int) -> int:
    valid_image_width = _validate_image_width(image_width)
    if isinstance(center_x, bool) or not isinstance(center_x, int):
        raise ValueError(
            f"center_x must be an integer pixel within the stitched image, got {center_x!r}"
        )
    if center_x < 0 or center_x >= valid_image_width:
        raise ValueError(
            f"center_x must be within [0, {valid_image_width}), got {center_x!r}"
        )
    return center_x


def _validate_crop_size(crop_size: object) -> int:
    if isinstance(crop_size, bool) or not isinstance(crop_size, int):
        raise ValueError(f"crop_size must be a positive integer, got {crop_size!r}")
    if crop_size <= 0:
        raise ValueError(f"crop_size must be a positive integer, got {crop_size!r}")
    return crop_size


def _validate_step_deg(step_deg: object) -> int:
    if isinstance(step_deg, bool) or not isinstance(step_deg, int):
        raise ValueError(
            f"step_deg must be a positive integer divisor of 360, got {step_deg!r}"
        )
    if step_deg <= 0:
        raise ValueError(
            f"step_deg must be a positive integer divisor of 360, got {step_deg!r}"
        )
    if 360 % step_deg != 0:
        raise ValueError(f"step_deg must divide 360 evenly, got {step_deg!r}")
    return step_deg


def _round_half_up_non_negative(value: float) -> int:
    if value < 0:
        raise ValueError(f"value must be non-negative, got {value!r}")
    return math.floor(value + 0.5)


def normalize_angle_deg(angle_deg: float) -> float:
    angle_value = _validate_angle_deg(angle_deg)
    return angle_value % 360.0


def angle_to_center_pixel(angle_deg: float, image_width: int) -> int:
    normalized_angle_deg = normalize_angle_deg(angle_deg)
    valid_image_width = _validate_image_width(image_width)

    pixels_per_deg = valid_image_width / 360
    center_x = _round_half_up_non_negative(normalized_angle_deg * pixels_per_deg)
    return center_x % valid_image_width


def angle_to_nearest_viewpoint_id(
    angle_deg: float, step_deg: int = VIEWPOINT_STEP_DEG
) -> int:
    normalized_angle_deg = normalize_angle_deg(angle_deg)
    valid_step_deg = _validate_step_deg(step_deg)

    num_viewpoints = 360 // valid_step_deg
    viewpoint_index = _round_half_up_non_negative(normalized_angle_deg / valid_step_deg)
    return viewpoint_index % num_viewpoints


def viewpoint_to_center_pixel(
    viewpoint_id: int,
    step_deg: int = VIEWPOINT_STEP_DEG,
    image_width: int = STITCHED_WIDTH,
) -> int:
    """Convert viewpoint_id (0-35) to center x-coordinate in stitched image.

    Args:
        viewpoint_id: Viewpoint index (0-35 for 36 viewpoints at 10° steps)
        step_deg: Degrees per viewpoint step (default: 10)
        image_width: Width of stitched image in pixels (default: 3760)

    Returns:
        Center x-coordinate in pixels
    """
    pixels_per_deg = image_width / 360
    return int(viewpoint_id * step_deg * pixels_per_deg)


def pixel_to_viewpoint(
    x_pixel: int, step_deg: int = VIEWPOINT_STEP_DEG, image_width: int = STITCHED_WIDTH
) -> int:
    """Convert pixel coordinate to nearest viewpoint_id.

    Args:
        x_pixel: X-coordinate in pixels
        step_deg: Degrees per viewpoint step (default: 10)
        image_width: Width of stitched image in pixels (default: 3760)

    Returns:
        Nearest viewpoint_id (0-35)
    """
    pixels_per_deg = image_width / 360
    degrees = (x_pixel / pixels_per_deg) % 360
    viewpoint_id = int(round(degrees / step_deg)) % NUM_VIEWPOINTS
    return viewpoint_id


def get_crop_bounds(
    center_x: int, crop_size: int = CROP_SIZE, image_width: int = STITCHED_WIDTH
) -> tuple[int, int]:
    """Get crop bounds centered at x-coordinate.

    Returns (left, right) coordinates. If left < 0 or right > image_width,
    wrap-around handling is needed at render time.

    Args:
        center_x: Center x-coordinate
        crop_size: Size of crop in pixels (default: 480)
        image_width: Width of stitched image in pixels (default: 3760)

    Returns:
        Tuple of (left, right) x-coordinates
    """
    _ = image_width
    half = crop_size // 2
    return center_x - half, center_x + half


def get_crop_segments(
    center_x: int, crop_size: int = CROP_SIZE, image_width: int = STITCHED_WIDTH
) -> tuple[CropSegment, ...]:
    valid_image_width = _validate_image_width(image_width)
    valid_crop_size = _validate_crop_size(crop_size)
    valid_center_x = _validate_center_x(center_x, valid_image_width)
    if valid_crop_size > valid_image_width:
        raise ValueError(
            f"crop_size must be less than or equal to image_width, got {valid_crop_size!r} > {valid_image_width!r}"
        )

    left, right = get_crop_bounds(valid_center_x, valid_crop_size, valid_image_width)
    if left < 0:
        wrapped_left = left + valid_image_width
        first_output_right = valid_image_width - wrapped_left
        return (
            CropSegment(
                source_left_px=wrapped_left,
                source_right_px=valid_image_width,
                output_left_px=0,
                output_right_px=first_output_right,
            ),
            CropSegment(
                source_left_px=0,
                source_right_px=right,
                output_left_px=first_output_right,
                output_right_px=valid_crop_size,
            ),
        )
    if right > valid_image_width:
        wrapped_right = right - valid_image_width
        first_output_right = valid_image_width - left
        return (
            CropSegment(
                source_left_px=left,
                source_right_px=valid_image_width,
                output_left_px=0,
                output_right_px=first_output_right,
            ),
            CropSegment(
                source_left_px=0,
                source_right_px=wrapped_right,
                output_left_px=first_output_right,
                output_right_px=valid_crop_size,
            ),
        )
    return (
        CropSegment(
            source_left_px=left,
            source_right_px=right,
            output_left_px=0,
            output_right_px=valid_crop_size,
        ),
    )


def get_crop_metadata(
    center_x: int, crop_size: int = CROP_SIZE, image_width: int = STITCHED_WIDTH
) -> CropMetadata:
    valid_image_width = _validate_image_width(image_width)
    valid_crop_size = _validate_crop_size(crop_size)
    valid_center_x = _validate_center_x(center_x, valid_image_width)
    if valid_crop_size > valid_image_width:
        raise ValueError(
            f"crop_size must be less than or equal to image_width, got {valid_crop_size!r} > {valid_image_width!r}"
        )

    left, right = get_crop_bounds(valid_center_x, valid_crop_size, valid_image_width)
    segments = get_crop_segments(valid_center_x, valid_crop_size, valid_image_width)
    if left < 0:
        wrap_direction: Literal["none", "left", "right"] = "left"
    elif right > valid_image_width:
        wrap_direction = "right"
    else:
        wrap_direction = "none"

    return CropMetadata(
        center_x_px=valid_center_x,
        crop_left_px=left,
        crop_right_px=right,
        crop_size=valid_crop_size,
        wraparound=wrap_direction != "none",
        wrap_direction=wrap_direction,
        segments=segments,
    )


def is_bbox_visible_in_viewpoint(
    bbox: Sequence[float],
    viewpoint_id: int,
    step_deg: int = VIEWPOINT_STEP_DEG,
    crop_size: int = CROP_SIZE,
    image_width: int = STITCHED_WIDTH,
) -> bool:
    """Check if bbox center falls within viewpoint's crop area.

    Handles wrap-around at image edges (viewpoint 0 and 35 are adjacent).

    Args:
        bbox: Bounding box as [x, y, width, height]
        viewpoint_id: Viewpoint index (0-35)
        step_deg: Degrees per viewpoint step (default: 10)
        crop_size: Size of crop in pixels (default: 480)
        image_width: Width of stitched image in pixels (default: 3760)

    Returns:
        True if bbox center is visible in viewpoint crop, False otherwise
    """
    # Calculate bbox center x-coordinate
    bbox_center_x = bbox[0] + bbox[2] / 2

    # Get viewpoint crop bounds
    center_x = viewpoint_to_center_pixel(viewpoint_id, step_deg, image_width)
    left, right = get_crop_bounds(center_x, crop_size, image_width)

    # Handle wrap-around: if crop spans image boundary
    if left < 0:
        # Crop wraps around left edge
        # Visible if: bbox_center_x in [left + width, width) OR bbox_center_x in [0, right)
        wrapped_left = left + image_width
        return bbox_center_x >= wrapped_left or bbox_center_x < right
    if right > image_width:
        # Crop wraps around right edge
        # Visible if: bbox_center_x in [left, width) OR bbox_center_x in [0, right - width)
        wrapped_right = right - image_width
        return bbox_center_x >= left or bbox_center_x < wrapped_right
    return left <= bbox_center_x < right
