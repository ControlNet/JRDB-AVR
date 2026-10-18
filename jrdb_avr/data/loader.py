"""Minimal JRDB-AVR dataset loader for the benchmark SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..sdk.observation import (
    _build_observation_result,
    _get_frame_id_for_observation,
    _validate_public_angle,
)

if TYPE_CHECKING:
    from ..sdk.types import ObservationResult


class JRDBAVRDataset:
    """Minimal dataset loader exposing the public observe() entry point."""

    def __init__(self, data_root: str, split: str = "train"):
        self.data_root = Path(data_root)
        self.split = split
        self._cache: dict[str, Any] = {}

        if split == "train":
            self.dataset_dir = self.data_root / "train_dataset_with_activity"
            self.labels_2d_dir = (
                self.dataset_dir / "labels" / "labels_2d_activity_social_stitched"
            )
        elif split == "test":
            self.dataset_dir = self.data_root / "test_dataset_without_labels"
            self.labels_2d_dir = self.dataset_dir / "labels" / "labels_2d_social"
        else:
            raise ValueError(f"split must be 'train' or 'test', got {split!r}")

        self.images_dir = self.dataset_dir / "images"

    def _load_labels_2d(self, sequence: str) -> dict[str, Any]:
        cache_key = f"2d_{sequence}"
        if cache_key not in self._cache:
            label_file = self.labels_2d_dir / f"{sequence}.json"
            if not label_file.is_file():
                raise FileNotFoundError(f"2D labels not found for sequence {sequence!r}")
            with label_file.open("r", encoding="utf-8") as handle:
                self._cache[cache_key] = json.load(handle)
        return self._cache[cache_key]

    def get_frame_ids(self, sequence: str) -> list[str]:
        labels = self._load_labels_2d(sequence)
        frame_map = labels.get("labels")
        if not isinstance(frame_map, dict):
            raise ValueError(f"Sequence {sequence!r} is missing a valid 'labels' map")
        frame_ids = sorted(frame_map.keys())
        if len(frame_ids) == 0:
            raise ValueError(f"Sequence {sequence!r} has no frames in labels")
        return frame_ids

    def get_frame_id_by_index(self, sequence: str, frame_index: int) -> str:
        frame_ids = self.get_frame_ids(sequence)
        if type(frame_index) is not int:
            raise ValueError("frame_index must be an integer")
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if frame_index >= len(frame_ids):
            raise ValueError(
                "frame_index out of range (must be less than number of available frames)"
            )
        return frame_ids[frame_index]

    def get_image_path(self, sequence: str, frame_id: str, camera: str = "stitched") -> str:
        if camera == "stitched":
            return str(self.images_dir / "image_stitched" / sequence / frame_id)
        raise ValueError(f"Unsupported camera for benchmark SDK: {camera!r}")

    def observe(
        self, sequence: str, frame_index: int, angle_deg: float
    ) -> "ObservationResult":
        frame_id = _get_frame_id_for_observation(self, sequence, frame_index)
        _validate_public_angle(angle_deg)
        return _build_observation_result(
            dataset=self,
            sequence=sequence,
            frame_index=frame_index,
            frame_id=frame_id,
            angle_deg=angle_deg,
        )
