"""Strict, explicitly approved photographic reconstruction inputs."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from scene_pipeline.models import Identifier, StrictModel, Vec3

GENERATED_TRIAL_IDS = ("T01", "T02", "T03")
TRIAL_IDS = (*GENERATED_TRIAL_IDS, "R01", "R02", "R03")
VARIANTS = ("baseline", "optimized")
CATEGORIES = Literal["pump", "motor", "tank", "control cabinet", "conveyor", "industrial machine"]


class RepositorySource(StrictModel):
    filename: str = Field(pattern=r"^[TR]0[1-3]\.png$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    url: str
    publication_approved: Literal[True]

    @model_validator(mode="after")
    def immutable_repository_source(self):
        if not re.fullmatch(
            r"https://raw\.githubusercontent\.com/ribumann/3d-scene-toolchain/[a-f0-9]{40}/[A-Za-z0-9_./-]+\.png",
            self.url,
        ) or any(part in (".", "..") for part in self.url.split("/")[3:]):
            raise ValueError("Trial sources require immutable approved repository URLs")
        return self


class TrialSource(RepositorySource):
    kind: Literal["generated-photographic-scene"]
    generator: Literal["Copilot image_generation tool; underlying image model/version not exposed"]
    prompt: str = Field(min_length=1, max_length=12000)


class RealPhotoSource(RepositorySource):
    kind: Literal["licensed-real-photograph"]
    creator: str = Field(min_length=1, max_length=200)
    source_page: str = Field(pattern=r"^https://commons\.wikimedia\.org/wiki/File:[^\s]+$")
    original_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    license: Literal["CC-BY-SA-4.0"]
    license_url: Literal["https://creativecommons.org/licenses/by-sa/4.0/"]
    changes: str = Field(min_length=1, max_length=2000)
    derivative_license: Literal["CC-BY-SA-4.0"]
    derivative_changes: str = Field(min_length=1, max_length=2000)
    limitations: str = Field(min_length=1, max_length=2000)


class ExpectedObject(StrictModel):
    identity: Identifier
    category: CATEGORIES
    count: int = Field(ge=1, le=12)


class ReviewedObject(StrictModel):
    id: Identifier
    identity: Identifier
    category: CATEGORIES
    box: tuple[float, float, float, float]
    reviewed: Literal[True]
    reusable_asset_id: Identifier | None = None

    @model_validator(mode="after")
    def normalized_box(self):
        x, y, width, height = self.box
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("Reviewed boxes use normalized x/y/width/height inside the source")
        return self


class TrialInstance(StrictModel):
    id: Identifier
    object_id: Identifier
    position: Vec3
    rotation: Vec3 = (0, 0, 0)
    size: Vec3

    @model_validator(mode="after")
    def bounded_layout(self):
        if any(value <= 0 or value > 100 for value in self.size) or any(abs(value) > 100 for value in self.position):
            raise ValueError("Trial layouts require bounded positive assumed dimensions")
        return self


class Trial(StrictModel):
    id: Literal["T01", "T02", "T03", "R01", "R02", "R03"]
    title: str = Field(min_length=1, max_length=120)
    source: Annotated[TrialSource | RealPhotoSource, Field(discriminator="kind")]
    detector_phrases: list[CATEGORIES] = Field(min_length=1, max_length=6)
    expected_inventory: list[ExpectedObject] = Field(min_length=1, max_length=12)
    reviewed_objects: list[ReviewedObject] = Field(default_factory=list, max_length=12)
    instances: list[TrialInstance] = Field(default_factory=list, max_length=12)
    layout_kind: Literal["manual-relative-not-metric", "inferred-not-metric"] = "manual-relative-not-metric"

    @model_validator(mode="after")
    def reviewed_references(self):
        if self.source.filename != f"{self.id}.png" or not self.source.url.endswith("/" + self.source.filename):
            raise ValueError("Trial source identity must match its allowlisted filename")
        if self.id.startswith("R") != isinstance(self.source, RealPhotoSource):
            raise ValueError("Real photographs and generated trials require distinct source identities")
        if self.instances and self.layout_kind != "manual-relative-not-metric":
            raise ValueError("Authored instances require an explicit manual layout")
        for records in (self.reviewed_objects, self.instances):
            if len({item.id for item in records}) != len(records):
                raise ValueError("Duplicate reviewed object or instance IDs")
        objects = {item.id: item for item in self.reviewed_objects}
        for instance in self.instances:
            if instance.object_id not in objects:
                raise ValueError("Instance references an unknown reviewed object")
            if sum(item.object_id == instance.object_id for item in self.instances) > 1 and not objects[instance.object_id].reusable_asset_id:
                raise ValueError("Repeated placements require an explicit reusable asset identity")
        if any(item.category not in self.detector_phrases for item in self.reviewed_objects):
            raise ValueError("Reviewed categories must appear in detector phrases")
        return self


class TrialManifest(StrictModel):
    schema_version: Literal[1]
    trials: list[Trial] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_trials(self):
        if len({trial.id for trial in self.trials}) != len(self.trials):
            raise ValueError("Duplicate trial IDs")
        return self


def load_manifest(path: Path):
    if path.is_symlink():
        raise ValueError("Unsafe trial manifest symlink")
    return TrialManifest.model_validate_json(path.read_text())


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
