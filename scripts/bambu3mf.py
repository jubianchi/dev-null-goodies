import json
import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from numpy.typing import NDArray

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
PRODUCTION = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}"
MAIN_MODEL = "3D/3dmodel.model"
MODEL_SETTINGS = "Metadata/model_settings.config"
PROJECT_SETTINGS = "Metadata/project_settings.config"


@dataclass(frozen=True)
class Part:
    name: str
    filament: int
    vertices: NDArray[np.float64]
    triangles: NDArray[np.int64]


@dataclass(frozen=True)
class Model:
    name: str
    parts: tuple[Part, ...]


@dataclass(frozen=True)
class Plate:
    index: int
    name: str
    objects: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    models: tuple[Model, ...]
    filament_colours: tuple[str, ...]
    plates: tuple[Plate, ...] = ()


@dataclass(frozen=True)
class _Mesh:
    vertices: NDArray[np.float64]
    triangles: NDArray[np.int64]


def _transform(value: str | None) -> NDArray[np.float64]:
    matrix = np.eye(4)
    if value:
        matrix[:, :3] = np.array(value.split(), dtype=np.float64).reshape(4, 3)
    return matrix


def _metadata(element: ElementTree.Element, key: str) -> str | None:
    for metadata in element.findall("metadata"):
        if metadata.get("key") == key:
            return metadata.get("value")
    return None


def _meshes(xml: bytes) -> dict[str, _Mesh]:
    meshes: dict[str, _Mesh] = {}
    for obj in ElementTree.fromstring(xml).iter(f"{CORE}object"):
        mesh = obj.find(f"{CORE}mesh")
        if mesh is None:
            continue
        vertices = np.array(
            [(v.get("x"), v.get("y"), v.get("z")) for v in mesh.iter(f"{CORE}vertex")], dtype=np.float64
        ).reshape(-1, 3)
        triangles = np.array(
            [(t.get("v1"), t.get("v2"), t.get("v3")) for t in mesh.iter(f"{CORE}triangle")], dtype=np.int64
        ).reshape(-1, 3)
        meshes[obj.get("id", "")] = _Mesh(vertices, triangles)
    return meshes


def _place(mesh: _Mesh, matrix: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    homogeneous = np.hstack([mesh.vertices, np.ones((len(mesh.vertices), 1))])
    vertices = (homogeneous @ matrix)[:, :3]
    triangles = mesh.triangles[:, ::-1] if np.linalg.det(matrix[:3, :3]) < 0 else mesh.triangles
    return vertices, triangles.copy()


def read_project(path: Path) -> Project:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{path} is not a 3MF archive")

    with zipfile.ZipFile(path) as archive:
        main = ElementTree.fromstring(archive.read(MAIN_MODEL))
        settings = ElementTree.fromstring(archive.read(MODEL_SETTINGS))
        colours = json.loads(archive.read(PROJECT_SETTINGS)).get("filament_colour", [])

        objects_settings = {obj.get("id"): obj for obj in settings.findall("object")}
        resources = {obj.get("id"): obj for obj in main.iter(f"{CORE}object")}
        loaded: dict[str, dict[str, _Mesh]] = {}

        models: list[Model] = []
        for item in main.iter(f"{CORE}item"):
            object_id = item.get("objectid", "")
            obj_settings = objects_settings[object_id]
            default_filament = int(_metadata(obj_settings, "extruder") or 1)
            parts_settings = {part.get("id"): part for part in obj_settings.findall("part")}
            item_matrix = _transform(item.get("transform"))

            parts: list[Part] = []
            for component in resources[object_id].iter(f"{CORE}component"):
                sub_path = posixpath.normpath(component.get(f"{PRODUCTION}path", MAIN_MODEL).lstrip("/"))
                if sub_path not in loaded:
                    loaded[sub_path] = _meshes(archive.read(sub_path))
                part_id = component.get("objectid", "")
                part_settings = parts_settings[part_id]
                vertices, triangles = _place(
                    loaded[sub_path][part_id], _transform(component.get("transform")) @ item_matrix
                )
                parts.append(
                    Part(
                        name=_metadata(part_settings, "name") or part_id,
                        filament=int(_metadata(part_settings, "extruder") or default_filament),
                        vertices=vertices,
                        triangles=triangles,
                    )
                )
            models.append(Model(name=_metadata(obj_settings, "name") or object_id, parts=tuple(parts)))

    names = {object_id: _metadata(obj, "name") or object_id for object_id, obj in objects_settings.items()}
    plates = tuple(
        Plate(
            index=int(_metadata(plate, "plater_id") or position),
            name=_metadata(plate, "plater_name") or "",
            objects=tuple(names[_metadata(instance, "object_id")] for instance in plate.findall("model_instance")),
        )
        for position, plate in enumerate(settings.findall("plate"), start=1)
    )
    return Project(models=tuple(models), filament_colours=tuple(colours), plates=plates)
