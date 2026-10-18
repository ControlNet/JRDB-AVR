"""Internal stitched-panorama crop helpers for dataset observations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PIL import Image, UnidentifiedImageError

from ..utils.viewpoint import (
    CROP_SIZE,
    STITCHED_HEIGHT,
    STITCHED_WIDTH,
    angle_to_center_pixel,
    angle_to_nearest_viewpoint_id,
    get_crop_metadata,
    normalize_angle_deg,
)
from .errors import (
    ObservationImageError,
    ObservationMissingImageError,
    ObservationValidationError,
    UnsupportedImageGeometryError,
)
from .types import ObservationResult

if TYPE_CHECKING:
    from ..utils.viewpoint import CropMetadata

__all__ = [
    "_get_stitched_image_path",
    "_load_stitched_image_from_path",
    "_assemble_stitched_crop",
    "_build_observation_result",
    "_get_frame_id_for_observation",
    "_validate_public_angle",
]


class StitchedImageDataset(Protocol):
    """Minimal dataset contract needed by the internal crop engine."""

    def get_image_path(self, sequence: str, frame_id: str, camera: str) -> str: ...


class ObservationDataset(StitchedImageDataset, Protocol):
    """Dataset contract required by the public observation API."""

    def get_frame_id_by_index(self, sequence: str, frame_index: int) -> str: ...


def _get_stitched_image_path(
    dataset: StitchedImageDataset, sequence: str, frame_id: str
) -> str:
    """Resolve the stitched panorama path via the dataset loader contract."""

    return dataset.get_image_path(sequence, frame_id, camera="stitched")


def _validate_stitched_image_geometry(
    stitched_image: Image.Image, image_path: str
) -> None:
    """Reject stitched images that do not match the canonical panorama geometry."""

    if stitched_image.width != STITCHED_WIDTH or stitched_image.height != STITCHED_HEIGHT:
        raise UnsupportedImageGeometryError(
            f"Unsupported stitched image geometry for {image_path!r}: expected {(STITCHED_WIDTH, STITCHED_HEIGHT)!r}, got {stitched_image.size!r}"
        )


def _load_stitched_image_from_path(image_path: str) -> Image.Image:
    """Load and fully decode a stitched panorama from disk."""

    path = Path(image_path)
    if not path.is_file():
        raise ObservationMissingImageError(
            f"Stitched panorama not found at {image_path!r}"
        )

    try:
        with Image.open(path) as opened_image:
            _ = opened_image.load()
            stitched_image = opened_image.copy()
    except FileNotFoundError as exc:
        raise ObservationMissingImageError(
            f"Stitched panorama not found at {image_path!r}"
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ObservationImageError(
            f"Failed to decode stitched panorama at {image_path!r}"
        ) from exc

    _validate_stitched_image_geometry(stitched_image, image_path)
    return stitched_image


def _assemble_stitched_crop(
    stitched_image: Image.Image, crop_metadata: CropMetadata
) -> Image.Image:
    """Assemble a deterministic square crop from ordered seam-safe segments."""

    crop_image = Image.new(
        stitched_image.mode, (crop_metadata.crop_size, stitched_image.height)
    )
    for segment in crop_metadata.segments:
        segment_image = stitched_image.crop(
            (
                segment.source_left_px,
                0,
                segment.source_right_px,
                stitched_image.height,
            )
        )
        crop_image.paste(segment_image, (segment.output_left_px, 0))
    return crop_image


def _build_observation_result(
    dataset: StitchedImageDataset,
    sequence: str,
    frame_index: int,
    frame_id: str,
    angle_deg: float,
) -> ObservationResult:
    """Build the internal observation payload for one stitched panorama frame."""

    normalized_angle_deg = normalize_angle_deg(angle_deg)
    center_x_px = angle_to_center_pixel(normalized_angle_deg, STITCHED_WIDTH)
    crop_metadata = get_crop_metadata(center_x_px, CROP_SIZE, STITCHED_WIDTH)
    stitched_image_path = _get_stitched_image_path(dataset, sequence, frame_id)
    stitched_image = _load_stitched_image_from_path(stitched_image_path)
    crop_image = _assemble_stitched_crop(stitched_image, crop_metadata)

    return ObservationResult(
        image=crop_image,
        sequence=sequence,
        frame_index=frame_index,
        frame_id=frame_id,
        input_angle_deg=float(angle_deg),
        normalized_angle_deg=normalized_angle_deg,
        center_x_px=crop_metadata.center_x_px,
        crop_left_px=crop_metadata.crop_left_px,
        crop_right_px=crop_metadata.crop_right_px,
        wraparound=crop_metadata.wraparound,
        nearest_viewpoint_id=angle_to_nearest_viewpoint_id(normalized_angle_deg),
        source_image_path=stitched_image_path,
        source_image_width=stitched_image.width,
        source_image_height=stitched_image.height,
        crop_size=crop_metadata.crop_size,
    )


def _get_frame_id_for_observation(
    dataset: ObservationDataset, sequence: str, frame_index: int
) -> str:
    try:
        return dataset.get_frame_id_by_index(sequence, frame_index)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise ObservationValidationError(
            f"Invalid sequence/frame selection for observation request: sequence={sequence!r}, frame_index={frame_index!r}"
        ) from exc


def _validate_public_angle(angle_deg: float) -> None:
    try:
        _ = normalize_angle_deg(angle_deg)
    except ValueError as exc:
        raise ObservationValidationError(
            f"Invalid angle_deg for observation request: {angle_deg!r}"
        ) from exc
