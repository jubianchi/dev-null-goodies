import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"

UNIT_CUBE_VERTICES: list[tuple[float, float, float]] = [
    (0, 0, 0),
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 1, 1),
]

UNIT_CUBE_TRIANGLES: list[tuple[int, int, int]] = [
    (0, 2, 1),
    (0, 3, 2),
    (4, 5, 6),
    (4, 6, 7),
    (0, 1, 5),
    (0, 5, 4),
    (1, 2, 6),
    (1, 6, 5),
    (2, 3, 7),
    (2, 7, 6),
    (3, 0, 4),
    (3, 4, 7),
]


@dataclass
class FixturePart:
    name: str
    extruder: int | None = None
    transform: str = IDENTITY
    vertices: list[tuple[float, float, float]] = field(default_factory=lambda: list(UNIT_CUBE_VERTICES))
    triangles: list[tuple[int, int, int]] = field(default_factory=lambda: list(UNIT_CUBE_TRIANGLES))


@dataclass
class FixtureObject:
    name: str
    parts: list[FixturePart]
    extruder: int = 1
    item_transform: str = IDENTITY


def _mesh_xml(part: FixturePart, object_id: int) -> str:
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in part.vertices)
    triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in part.triangles)
    return (
        f'<object id="{object_id}" type="model"><mesh>'
        f"<vertices>{vertices}</vertices><triangles>{triangles}</triangles>"
        "</mesh></object>"
    )


def write_3mf(
    path: Path,
    objects: list[FixtureObject],
    filament_colours: list[str],
    plates: list[tuple[str, list[str]]] | None = None,
) -> Path:
    ns = (
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"'
    )
    next_id = 1
    resources: list[str] = []
    items: list[str] = []
    settings: list[str] = []
    sub_models: dict[str, str] = {}
    object_ids: dict[str, int] = {}

    for obj in objects:
        sub_path = f"3D/Objects/object_{next_id}.model"
        components: list[str] = []
        meshes: list[str] = []
        parts_settings: list[str] = []
        for part in obj.parts:
            part_id = next_id
            next_id += 1
            meshes.append(_mesh_xml(part, part_id))
            components.append(
                f'<component p:path="/{sub_path}" objectid="{part_id}" transform="{part.transform}"/>'
            )
            extruder = "" if part.extruder is None else f'<metadata key="extruder" value="{part.extruder}"/>'
            parts_settings.append(
                f'<part id="{part_id}" subtype="normal_part">'
                f'<metadata key="name" value="{part.name}"/>{extruder}</part>'
            )
        object_id = next_id
        object_ids[obj.name] = object_id
        next_id += 1
        sub_models[sub_path] = f'<?xml version="1.0"?><model {ns}><resources>{"".join(meshes)}</resources></model>'
        resources.append(f'<object id="{object_id}" type="model"><components>{"".join(components)}</components></object>')
        items.append(f'<item objectid="{object_id}" transform="{obj.item_transform}" printable="1"/>')
        settings.append(
            f'<object id="{object_id}"><metadata key="name" value="{obj.name}"/>'
            f'<metadata key="extruder" value="{obj.extruder}"/>{"".join(parts_settings)}</object>'
        )

    for index, (plate_name, plate_objects) in enumerate(plates or [], start=1):
        instances = "".join(
            f'<model_instance><metadata key="object_id" value="{object_ids[name]}"/></model_instance>'
            for name in plate_objects
        )
        settings.append(
            f'<plate><metadata key="plater_id" value="{index}"/>'
            f'<metadata key="plater_name" value="{plate_name}"/>{instances}</plate>'
        )

    main_model = (
        f'<?xml version="1.0"?><model unit="millimeter" {ns}>'
        f'<resources>{"".join(resources)}</resources><build>{"".join(items)}</build></model>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", main_model)
        for sub_path, content in sub_models.items():
            archive.writestr(sub_path, content)
        archive.writestr("Metadata/model_settings.config", f'<?xml version="1.0"?><config>{"".join(settings)}</config>')
        archive.writestr("Metadata/project_settings.config", json.dumps({"filament_colour": filament_colours}))
    return path
