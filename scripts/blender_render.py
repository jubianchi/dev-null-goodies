import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bambu3mf import Model, read_project  # noqa: E402

MILLIMETRE = 0.001
VIEW_DIRECTION = Vector((0.35, -1.0, 1.1)).normalized()
FRAMING_MARGIN = 1.15


def srgb_to_linear(hex_colour: str) -> tuple[float, float, float, float]:
    srgb = np.array([int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)])
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    return (*linear.tolist(), 1.0)


def clear_scene() -> None:
    for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for datablock in list(collection):
            collection.remove(datablock)


def setup_scene(samples: int, width: int, height: int) -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Khronos PBR Neutral"

    world = bpy.data.worlds.new("world")
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (1, 1, 1, 1)
    background.inputs["Strength"].default_value = 0.25
    scene.world = world
    return scene


def filament_material(index: int, colour: str) -> bpy.types.Material:
    material = bpy.data.materials.new(f"filament-{index}")
    shader = material.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = srgb_to_linear(colour)
    shader.inputs["Roughness"].default_value = 0.45
    return material


def merge_overlapping_shells(obj: bpy.types.Object) -> None:
    union = obj.modifiers.new("union", "BOOLEAN")
    union.operation = "UNION"
    union.solver = "EXACT"
    union.operand_type = "COLLECTION"
    union.collection = bpy.data.collections.get("empty") or bpy.data.collections.new("empty")
    union.use_self = True
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    merged = bpy.data.meshes.new_from_object(evaluated)
    obj.modifiers.remove(union)
    previous, obj.data = obj.data, merged
    bpy.data.meshes.remove(previous)
    merged.shade_flat()


def add_model(scene: bpy.types.Scene, model: Model, colours: tuple[str, ...]) -> np.ndarray:
    vertices = np.concatenate([part.vertices for part in model.parts])
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    offset = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    materials: dict[int, bpy.types.Material] = {}

    for part in model.parts:
        if part.filament not in materials:
            materials[part.filament] = filament_material(part.filament, colours[part.filament - 1])
        mesh = bpy.data.meshes.new(part.name)
        mesh.from_pydata(((part.vertices - offset) * MILLIMETRE).tolist(), [], part.triangles.tolist())
        mesh.validate()
        mesh.materials.append(materials[part.filament])
        obj = bpy.data.objects.new(part.name, mesh)
        scene.collection.objects.link(obj)
        merge_overlapping_shells(obj)

    return (np.array([low, high]) - offset) * MILLIMETRE


def add_light(scene: bpy.types.Scene, name: str, direction: Vector, distance: float, energy: float, size: float) -> None:
    light = bpy.data.lights.new(name, type="AREA")
    light.energy = energy
    light.size = size
    obj = bpy.data.objects.new(name, light)
    obj.location = direction.normalized() * distance
    obj.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    obj.visible_camera = False
    scene.collection.objects.link(obj)


def add_camera(scene: bpy.types.Scene, bounds: np.ndarray) -> None:
    rotation = (-VIEW_DIRECTION).to_track_quat("-Z", "Y")
    right = np.array(rotation @ Vector((1, 0, 0)))
    up = np.array(rotation @ Vector((0, 1, 0)))
    corners = np.array([[x, y, z] for x in bounds[:, 0] for y in bounds[:, 1] for z in bounds[:, 2]])
    across, along = corners @ right, corners @ up
    aspect = scene.render.resolution_x / scene.render.resolution_y

    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    camera.data.type = "ORTHO"
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.ortho_scale = max(np.ptp(across), np.ptp(along) * aspect) * FRAMING_MARGIN
    camera.data.clip_end = 1000
    centre = right * (across.max() + across.min()) / 2 + up * (along.max() + along.min()) / 2
    camera.location = Vector(centre.tolist()) + VIEW_DIRECTION * float(np.max(np.ptp(corners, axis=0))) * 10
    camera.rotation_euler = rotation.to_euler()
    scene.collection.objects.link(camera)
    scene.camera = camera


def render(source: Path, output: Path, samples: int, width: int, height: int) -> None:
    project = read_project(source)
    output.mkdir(parents=True, exist_ok=True)
    scene = setup_scene(samples, width, height)
    for model in project.models:
        clear_scene()
        bounds = add_model(scene, model, project.filament_colours)
        size = float(np.max(bounds[1] - bounds[0]))
        add_light(scene, "key", Vector((0.6, -0.8, 1.4)), size * 2, 150 * size**2, size)
        add_light(scene, "fill", Vector((-1.0, -0.4, 0.6)), size * 2, 40 * size**2, size * 1.5)
        add_camera(scene, bounds)
        scene.render.filepath = str(output / f"{model.name}.png")
        bpy.ops.render.render(write_still=True)
        print(scene.render.filepath)


if __name__ == "__main__":
    source, output, samples, width, height = sys.argv[sys.argv.index("--") + 1 :]
    render(Path(source), Path(output), int(samples), int(width), int(height))
