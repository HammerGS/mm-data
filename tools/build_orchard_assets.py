"""Build six apple-tree forms and their snow forms with the board's three mesh LODs.

Run Blender --background --python tools/build_orchard_assets.py.
ImageGen's unmodified 2x2 atlases supply bark and apple-skin panels. The shared
branch-cutout baker replaces the closed crown envelopes with realistic foliage.
Reuse the understory authoring primitives and rigid GLB exporter; no runtime generator.
"""
from math import cos, sin, pi
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_foliage_assets import Plant, blender_mesh, export_model
from glb_geometry import write_glb
from prepare_tree_lods import branch_crowns, counts as mesh_counts

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'data/models/board'
BUDGETS = (480, 240, 96)
# Ring width/depth, crown height, lobe width/depth/height, trunk lean.
FORMS = {
    'round': (7, 6.5, 19, 6.8, 6.2, 6.6, 0),
    'spreading': (9, 7, 17, 7.3, 6.4, 5.5, -.8),
    'upright': (5.7, 5, 20, 5.7, 5.2, 7.8, .4),
    'vase': (8, 7.2, 19, 5.8, 5.2, 6.4, 0),
    'leaning': (7.8, 6, 18, 6.2, 5.8, 6.4, 2.7),
    'young': (5.7, 5.2, 19.5, 5.3, 5, 6.8, -.6),
}


def tree(form, lod, snow):
    plant = Plant()
    rx, ry, z, lx, ly, lz, lean = FORMS[form]
    phase = list(FORMS).index(form) * .63
    root = Vector((0, 0, 0))
    fork = Vector((lean * .45, 0, 9))
    plant.branch(root, fork, .95, coarse=lod == 2)
    centers = []
    for i in range(5):
        angle = i * 2*pi/5 + phase
        center = Vector((lean + rx*cos(angle), ry*sin(angle), z + (i % 3 - 1)*1.1))
        centers.append(center)
        plant.branch(fork, center, .48, coarse=lod == 2)
        plant.lobe(center, (lx, ly, lz), coarse=lod == 2, snow=snow)
    # A vase has an open centre; the other forms carry a higher central leader.
    if form != 'vase':
        center = Vector((lean, 0, z + 4))
        centers.append(center)
        plant.lobe(center, (lx*.92, ly*.92, lz), coarse=lod == 2, snow=snow)
    if lod == 0:
        for i in range(16):
            angle = i * 2.399963 + phase
            center = centers[i % len(centers)]
            direction = Vector((cos(angle), sin(angle), .12 + (i % 3)*.08))
            start = center + Vector((direction.x*lx*.65, direction.y*ly*.65, (i % 5 - 2)*1.1))
            plant.leaf(start, start + direction*2.8, .82)
    # Real hanging fruit at near/middle range; the far canopy retains fruit in its albedo.
    for i in range((14, 6, 0)[lod]):
        angle = i * 2.399963 + phase
        center = centers[i % len(centers)]
        fruit = center + Vector((cos(angle)*lx*.86, sin(angle)*ly*.86, -1.4 - i % 3*.6))
        plant.lobe(fruit, (.72, .72, .78), coarse=True, panel=3, role='fruit')
    assert len(plant.faces) <= BUDGETS[lod], (form, lod, len(plant.faces))
    return plant


def materials(name):
    result = {}
    atlas = bpy.data.images.load(str(BOARD / f'textures/vegetation/orchard/{name}.png'), check_existing=True)
    for role in ('leaves', 'bark', 'fruit', 'snow'):
        material = bpy.data.materials.new(f'{name}-{role}')
        material['role'] = role
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Roughness'].default_value = .88
        texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = (bpy.data.images.load(str(BOARD / 'textures/vegetation/snow.png'), check_existing=True)
                         if role == 'snow' else atlas)
        texture.extension = 'EXTEND'
        material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
        result[role] = material
    return result


def build():
    scene = bpy.data.scenes.new('Orchard trees')
    manifest_path = BOARD / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    summary = {}
    for index, form in enumerate(FORMS):
        name = f'orchard-{form}'
        mats = materials(name)
        for snow in (False, True):
            asset = name + ('-snow' if snow else '')
            objects = [blender_mesh(scene, f'{asset}-lod{lod}', tree(form, lod, snow), mats) for lod in range(3)]
            # A shared frame prevents tree size/root jumps when the renderer switches LOD.
            low = min(v.co.z for v in objects[0].data.vertices)
            high = max(v.co.z for v in objects[0].data.vertices)
            scale = 30 / (high - low)
            levels, counts = {}, []
            for lod, obj in enumerate(objects):
                for vertex in obj.data.vertices:
                    vertex.co.z -= low
                    vertex.co *= scale
                obj.data.update()
                model = export_model(obj, name)
                for material in model['materials']:
                    material['textures'][0]['filename'] = ('textures/vegetation/snow.png' if material['id'] == 'snow'
                        else f'textures/vegetation/orchard/{name}.png')
                levels[lod] = model
                counts.append({'node': f'{asset}-lod{lod}', 'triangles': len(obj.data.polygons),
                               'vertices': len(model['meshes'][0]['vertices']) // 12})
                obj.location = (index*44, -(lod + (3 if snow else 0))*44, 0)
                obj['lod'] = lod
                obj['variant'] = asset
            levels = branch_crowns(levels[0], asset, retained_levels=levels)
            counts = [{'node': f'{asset}-lod{lod}', **mesh_counts(model)} for lod, model in levels.items()]
            write_glb(BOARD / f'{asset}.glb', levels=levels)
            manifest[asset] = {'mesh': f'{asset}.glb', 'triangles': counts[0]['triangles'],
                'vertices': counts[0]['vertices'], 'generator': 'tools/build_orchard_assets.py',
                'texture': f'textures/vegetation/orchard/{name}.png', 'lods': counts}
            summary[asset] = [entry['triangles'] for entry in counts]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    for image in bpy.data.images:
        if image.source == 'FILE':
            image.filepath = bpy.path.relpath(image.filepath, start=str(ROOT / 'tools'))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'tools/board-orchards.blend'), copy=True)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    build()
