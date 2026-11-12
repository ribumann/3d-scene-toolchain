from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Vec3 = tuple[float, float, float]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(StrictModel):
    origin: Literal["observed", "inferred", "assumed", "generated"]
    confidence: float = Field(ge=0, le=1)
    reviewed: bool = False
    source_id: str | None = None
    note: str


class Node(StrictModel):
    id: Identifier
    label: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=100)
    shape: Literal["box", "cylinder", "sphere", "cone", "plane"] = "box"
    position: Vec3
    rotation: Vec3 = (0, 0, 0)
    size: Vec3
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    visible: bool = True
    evidence: Evidence
    asset_id: Identifier | None = None

    @model_validator(mode="after")
    def positive_size(self):
        if any(value <= 0 or value > 10000 for value in self.size):
            raise ValueError("Node dimensions must be positive and at most 10,000 meters")
        return self


class Edge(StrictModel):
    id: Identifier
    source: Identifier
    target: Identifier
    kind: Literal["process", "visitor", "conveyor", "adjacency"]
    points: list[Vec3] = Field(min_length=2, max_length=10000)
    label: str = ""
    evidence: Evidence | None = None


class Asset(StrictModel):
    id: Identifier
    kind: Literal["glb", "ply"]
    uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    node_id: Identifier | None = None
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def local_asset(self):
        if not self.uri.startswith("/api/assets/") or any(
            part in (".", "..") for part in self.uri.split("/")
        ):
            raise ValueError("Assets must use local /api/assets/ paths without traversal")
        if "%" in self.uri or "\\" in self.uri:
            raise ValueError("Asset URI must not contain escaped paths")
        return self


class Source(StrictModel):
    id: Identifier
    kind: str
    filename: str
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Scene(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: Identifier
    case_id: Identifier
    name: str
    description: str
    revision: int = Field(default=1, ge=1)
    units: Literal["meters"] = "meters"
    coordinates: Literal["right-handed-y-up"] = "right-handed-y-up"
    nodes: list[Node] = Field(max_length=10000)
    edges: list[Edge] = Field(default_factory=list, max_length=20000)
    assets: list[Asset] = Field(default_factory=list, max_length=20000)
    sources: list[Source] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def references(self):
        groups = [self.nodes, self.edges, self.assets, self.sources]
        for items in groups:
            if len({item.id for item in items}) != len(items):
                raise ValueError("Duplicate IDs in scene")
        nodes = {node.id for node in self.nodes}
        assets = {asset.id for asset in self.assets}
        sources = {source.id for source in self.sources}
        for edge in self.edges:
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError(f"Edge {edge.id} references an unknown node")
            if edge.evidence and edge.evidence.source_id and edge.evidence.source_id not in sources:
                raise ValueError(f"Edge {edge.id} references an unknown evidence source")
        for node in self.nodes:
            if node.asset_id and node.asset_id not in assets:
                raise ValueError(f"Node {node.id} references an unknown asset")
            if node.evidence.source_id and node.evidence.source_id not in sources:
                raise ValueError(f"Node {node.id} references an unknown source")
        for asset in self.assets:
            if asset.node_id and asset.node_id not in nodes:
                raise ValueError(f"Asset {asset.id} references an unknown node")
        return self


class Case(StrictModel):
    id: Identifier
    title: str
    input_type: Literal["prompt", "photo", "diagram", "plan", "generated"]
    summary: str
    source_filename: str | None = None
    prompt: str = ""
    status: Literal["ready", "awaiting_input"] = "awaiting_input"
    source_url: str | None = None


class JobRequest(StrictModel):
    stages: list[Literal["extract", "blender", "idol"]] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def ordered_stages(self):
        if self.stages != sorted(set(self.stages), key=["extract", "blender", "idol"].index):
            raise ValueError("Stages must be unique and ordered: extract, blender, idol")
        return self


class PromptRequest(StrictModel):
    prompt: str = Field(min_length=5, max_length=10000)
