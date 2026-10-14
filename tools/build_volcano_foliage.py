"""Author the approved ImageGen cinder trees and a separate level-one thicket.

Run prepare_textures() with the bundled Python, then build() through Blender MCP.
The shared tree baker owns mesh budgets, alpha-tested crowns and far impostors.
Only this kit's independent scene and files are created; existing scenes are kept.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'data/models/board'
REVIEW = ROOT / 'tools/board-models/volcano'
TEXTURES = BOARD / 'textures/vegetation/volcano'
NAMES = ('tree-volcano-crown', 'tree-volcano-forked', 'tree-volcano-spire', 'foliage-volcano')
sys.path.insert(0, str(ROOT / 'tools'))


def prepare_textures():
    """Use the existing foliage baker; keep both unmodified ImageGen sources.

    Relief is an artistic estimate from source luminance, not measured scan data.
    The shared packed map stores cavity, roughness and transmission, in that order.
    """
    import numpy as np
    from PIL import Image
    from prepare_foliage_cutouts import bake, leaf_maps
    from texture_helpers import blur, display_rgb, normal_map, periodic, resize_linear_rgb

    TEXTURES.mkdir(parents=True, exist_ok=True)
    leaves = bake(REVIEW / 'cinder-cutout.png')
    maps = {'cinder-cutout': leaves,
            **leaf_maps('cinder-cutout', bake(REVIEW / 'cinder-cutout.png', linear_color=False))}
    # Thick dry lichen has little transmission; the source is predominantly red.
    maps['cinder-cutout-surface'][:, :, 1] = 210
    maps['cinder-cutout-surface'][:, :, 2] = 12
    with Image.open(REVIEW / 'cinder-bark.png') as source:
        color = np.asarray(source.convert('RGB').resize((512, 512), Image.Resampling.LANCZOS)) / 255.0
        pigment = np.clip(periodic(resize_linear_rgb(source, (512, 512))), 0, 1)
    # Numeric relief/cavity keep their original source estimate; only color filtering changes.
    color = np.clip(periodic(color), 0, 1)
    light = color @ np.array([.2126, .7152, .0722])
    relief = blur(light, 1.5) - blur(light, 12)
    cavity = np.clip(1 - np.maximum(blur(light, 4) - light, 0), .75, 1)
    maps.update({'cinder-bark': np.rint(display_rgb(pigment) * 255).clip(0, 255).astype(np.uint8),
                 'cinder-bark-normal': normal_map(relief, .04),
                 'cinder-bark-surface': np.rint(np.stack(
                     (cavity, np.full_like(light, .92), np.zeros_like(light)), axis=-1) * 255).astype(np.uint8)})
    for name, pixels in maps.items():
        Image.fromarray(pixels).save(TEXTURES / (name + '.png'))
    return {name: list(pixels.shape) for name, pixels in maps.items()}


def source_plant(name):
    """Independent silhouettes: broad crown, split fan, craggy spire and basal shrub."""
    from math import cos, sin
    from mathutils import Vector
    from build_foliage_assets import Plant
    from build_fungus_assets import tube

    plant = Plant()
    if name == 'foliage-volcano':
        # Several low arching stems rise from the same tight root and spread sideways.
        # This is authored at shrub proportions, not a vertically compressed tall tree.
        for i in range(7):
            a = i * 2.399963
            end = Vector((cos(a) * (8 + i % 3), sin(a) * (7 + i % 2), 5 + i % 3 * 1.2))
            knee = end * .55 + Vector((0, 0, 1.5))
            tube(plant, [(0, 0, 0), (.3*cos(a), .3*sin(a), 2), knee, end],
                 [.8, .65, .45, .12], 'bark-volcano', 7)
            plant.lobe(end, (5.5, 4.8, 4.8), role='leaves')
        plant.lobe((0, 0, 3.5), (5.5, 5, 3), role='leaves')
        return plant
    if name.endswith('forked'):
        tube(plant, [(0, 0, 0), (.6, -.3, 4), (-.4, .2, 9)], [2.1, 1.6, 1.15], 'bark-volcano', 9)
        for i, sign in enumerate((-1, 1)):
            tube(plant, [(-.4, .2, 8), (sign*3, i-1, 14), (sign*6, i*2-1, 21)],
                 [1.15, .85, .27], 'bark-volcano', 8)
        for i in range(8):
            a = i * 2.399963
            sign = -1 if i % 2 else 1
            start = Vector((sign*3, -.5, 14 + i % 3))
            end = Vector((sign*7 + cos(a)*4, sin(a)*6, 20 + i % 3*2))
            tube(plant, [start, start.lerp(end, .55) + Vector((0, 0, 1)), end],
                 [.65, .42, .09], 'bark-volcano', 6)
            plant.lobe(end, (5.2, 4.6, 4.5), role='leaves')
    elif name.endswith('spire'):
        path = [(0, 0, 0), (.4, .2, 5), (-.8, .1, 11), (.5, -.5, 18), (-.5, 0, 26)]
        tube(plant, path, [2.5, 2, 1.7, 1.2, .30], 'bark-volcano', 10)
        for i in range(9):
            a = i * 2.399963
            z = 5.5 + i*2.25
            radius = 3.8 - i*.20
            end = Vector((cos(a)*radius, sin(a)*radius, z+1.4))
            tube(plant, [(0, 0, z-2), (end.x*.65, end.y*.65, z), end],
                 [.75, .45, .12], 'bark-volcano', 6)
            plant.lobe(end, (4.0-i*.10, 3.8-i*.08, 4.2), role='leaves')
        plant.lobe((-.5, 0, 26), (3, 3, 4.8), role='leaves')
    else:
        path = [(0, 0, 0), (.8, -.3, 4), (-.4, .4, 10), (-2, .5, 16), (0, 0, 23)]
        tube(plant, path, [2.2, 1.7, 1.2, .85, .28], 'bark-volcano', 9)
        for i in range(8):
            a = i * 2.399963
            start = Vector((-.8, .3, 9 + i % 3*3))
            end = Vector((cos(a)*(7+i % 3), sin(a)*(7+i % 2), 18+i % 3*3))
            tube(plant, [start, start.lerp(end, .48) - Vector((0, 0, 1)), end],
                 [.9, .6, .10], 'bark-volcano', 7)
            plant.lobe(end, (5.7, 5.1, 4.7), role='leaves')
        plant.lobe((0, 0, 25), (5, 4.5, 5), role='leaves')
    return plant


def smooth_bark(model):
    """Average the decimated trunk's shared-position normals, retaining every UV seam."""
    from mathutils import Vector
    mesh = model['meshes'][0]
    data = mesh['vertices']
    normals = {}
    indices = next(p['indices'] for p in mesh['parts'] if p['id'] == 'bark-volcano')
    for i in range(0, len(indices), 3):
        points = [Vector(data[index*12:index*12+3]) for index in indices[i:i+3]]
        normal = (points[1]-points[0]).cross(points[2]-points[0])
        for point in points:
            key = tuple(point)
            normals[key] = normals.get(key, Vector()) + normal
    for index in set(indices):
        offset = index*12
        key = tuple(Vector(data[offset:offset+3]))
        normal = normals[key]
        # Opposed decimated faces can cancel at a shared position. Keep each corner's
        # original oriented face normal instead of replacing it with a zero vector.
        if normal.length_squared > 0:
            data[offset+3:offset+6] = list(normal.normalized())


def preview_material(role):
    """Lit editable Blender materials using the same albedo, alpha and normal maps."""
    import bpy
    material = bpy.data.materials.new('Volcano / ' + role)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .85
    texture = 'cinder-bark' if role == 'bark-volcano' else 'cinder-cutout'
    color = nodes.new('ShaderNodeTexImage')
    color.image = bpy.data.images.load(str(TEXTURES / (texture + '.png')), check_existing=True)
    color.extension = 'REPEAT' if role == 'bark-volcano' else 'EXTEND'
    links.new(color.outputs['Color'], shader.inputs['Base Color'])
    if role != 'bark-volcano':
        threshold = nodes.new('ShaderNodeMath')
        threshold.operation = 'GREATER_THAN'
        threshold.inputs[1].default_value = .5
        links.new(color.outputs['Alpha'], threshold.inputs[0])
        links.new(threshold.outputs[0], shader.inputs['Alpha'])
        material.surface_render_method = 'DITHERED'
    detail = nodes.new('ShaderNodeTexImage')
    detail.image = bpy.data.images.load(str(TEXTURES / (texture + '-normal.png')), check_existing=True)
    detail.image.colorspace_settings.name = 'Non-Color'
    detail.extension = color.extension
    normal = nodes.new('ShaderNodeNormalMap')
    links.new(detail.outputs['Color'], normal.inputs['Color'])
    links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    return material


def build():
    import bpy
    from mathutils import Vector
    from build_foliage_assets import blender_mesh, export_model
    from glb_geometry import write_glb
    from prepare_tree_lods import branch_crowns, counts, cutout_material, impostors, unlit_mesh

    scene = bpy.data.scenes.new('Volcanic cinder trees')
    bpy.context.window.scene = scene
    materials = {}
    for role in ('bark-volcano', 'leaves'):
        material = bpy.data.materials.new('Volcano authoring / ' + role)
        material['role'] = role
        materials[role] = material
    runtime_materials = {role: preview_material(role) for role in ('bark-volcano', 'canopy-cutout')}
    manifest_path = BOARD / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    report = {}
    for column, name in enumerate(NAMES):
        obj = blender_mesh(scene, name + '-envelope', source_plant(name), materials)
        low = min(v.co.z for v in obj.data.vertices)
        high = max(v.co.z for v in obj.data.vertices)
        height = 18 if name.startswith('foliage-') else 30
        for vertex in obj.data.vertices:
            vertex.co.z -= low
            vertex.co *= height/(high-low)
        obj.data.update()
        source = export_model(obj, 'volcano')
        source['materials'] = [{'id': 'bark-volcano', 'diffuse': [1, 1, 1], 'textures': [
            {'id': 'bark-volcano', 'type': kind,
             'filename': 'textures/vegetation/volcano/cinder-bark' + suffix + '.png'}
            for kind, suffix in (('DIFFUSE', ''), ('NORMAL', '-normal'), ('AMBIENT', '-surface'))]}]
        levels = branch_crowns(source, name)
        obj.location = (column*44, 70, 0)
        obj.hide_render = True
        obj.hide_set(True)
        entries = []
        for lod, model in levels.items():
            model['materials'] = [source['materials'][0], cutout_material('canopy-cutout', 'volcano/cinder-cutout')]
            smooth_bark(model)
            data = unlit_mesh(model, f'{name}-lod{lod}', {})
            data.materials.clear()
            roles = [part['id'] for part in model['meshes'][0]['parts']]
            for role in roles:
                data.materials.append(runtime_materials[role])
            # unlit_mesh emits faces grouped by part; restore indices after clearing its unlit materials.
            face = 0
            for index, part in enumerate(model['meshes'][0]['parts']):
                for _ in range(len(part['indices'])//3):
                    data.polygons[face].material_index = index
                    data.polygons[face].use_smooth = True
                    face += 1
            vertices = model['meshes'][0]['vertices']
            data.normals_split_custom_set([vertices[index*12+3:index*12+6]
                                           for part in model['meshes'][0]['parts'] for index in part['indices']])
            runtime = bpy.data.objects.new(f'{name}-lod{lod}', data)
            scene.collection.objects.link(runtime)
            runtime.location = (column*44, lod*38, 0)
            runtime.hide_render = lod != 0
            runtime['lod'] = lod
            entries.append({'node': model['nodes'][0]['id'], **counts(model)})
        write_glb(BOARD / (name + '.glb'), levels=levels)
        manifest[name] = {'mesh': name + '.glb', **counts(levels[0]), 'generator': 'tools/build_volcano_foliage.py',
                          'source': 'tools/board-models/volcano/concept.png', 'lods': entries}
        report[name] = {'lods': entries, 'height': height}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    impostors(set(NAMES))
    # The unlit impostor baker temporarily reads raw albedo. Restore the lit scene's
    # sRGB input after baking, otherwise the editable preview looks washed out.
    for name in ('cinder-bark', 'cinder-cutout'):
        bpy.data.images.load(str(TEXTURES / (name + '.png')), check_existing=True).colorspace_settings.name = 'sRGB'
    manifest = json.loads(manifest_path.read_text())
    for name in NAMES:
        report[name]['lods'] = manifest[name]['lods']
    REVIEW.mkdir(parents=True, exist_ok=True)
    (REVIEW / 'mesh-report.json').write_text(json.dumps(report, indent=2) + '\n')

    ground = bpy.data.materials.new('Volcano review ash')
    ground.diffuse_color = (.24, .25, .26, 1)
    ground.use_nodes = True
    ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.24, .25, .26, 1)
    ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = 1
    mesh = bpy.data.meshes.new('Volcano review ground')
    mesh.from_pydata([(-80, -110, -.05), (220, -110, -.05), (220, 130, -.05), (-80, 130, -.05)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new('Volcano review ground', mesh)
    mesh.materials.append(ground)
    scene.collection.objects.link(floor)
    camera = bpy.data.objects.new('Volcano review camera', bpy.data.cameras.new('Volcano review camera'))
    scene.collection.objects.link(camera)
    camera.location = (100, -180, 108)
    camera.rotation_euler = (Vector((65, 2, 12))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 175
    scene.camera = camera
    world = bpy.data.worlds.new('Volcano daylight')
    world.use_nodes = True
    world.node_tree.nodes.get('Background').inputs[0].default_value = (.60, .66, .75, 1)
    world.node_tree.nodes.get('Background').inputs[1].default_value = .65
    scene.world = world
    light = bpy.data.objects.new('Volcano soft daylight', bpy.data.lights.new('Volcano soft daylight', 'AREA'))
    scene.collection.objects.link(light)
    light.location = (15, -45, 115)
    light.rotation_euler = (Vector((65, 0, 10))-light.location).to_track_quat('-Z', 'Y').to_euler()
    light.data.energy = 180000
    light.data.shape = 'DISK'
    light.data.size = 85
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = 1800, 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    bpy.context.view_layer.update()
    bpy.data.libraries.write(str(REVIEW / 'volcanic-cinder-trees.blend'), {scene},
                             path_remap='RELATIVE_ALL', fake_user=True)
    return report


if __name__ == '__main__':
    print(json.dumps(prepare_textures() if '--textures' in sys.argv else build()))
