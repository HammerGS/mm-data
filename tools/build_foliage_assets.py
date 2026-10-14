"""Author level-one understory in Blender, then export the board's rigid three-LOD GLBs.

Run through Blender MCP with runpy.run_path(...), or Blender --background --python.
The eight imagegen atlases are unmodified inputs. No trees are imported or scaled down.
Low branch cards reuse the shared tree foliage materials, LOD baker and impostors.
The original biome atlases remain the source for stems and fused cactus pads.
"""
from collections import defaultdict
import json
from math import cos, sin, pi
from pathlib import Path
from random import Random
import sys

import bmesh
import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_geometry import write_glb
from prepare_tree_lods import (append_cutout, branch_crowns, counts as model_counts, cutout_material,
                               pack, round_cactus, unlit_mesh)

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'data/models/board'
FAMILIES = ('temperate', 'highland', 'rocky', 'wetland', 'desert', 'jungle', 'barren', 'snow')
BUDGETS = (480, 240, 96)


def atlas_uv(panel, uv):
    # Inset every panel so mip filtering cannot sample a neighbouring material.
    return (panel % 2 * .5 + .04 + uv[0] * .42, panel // 2 * .5 + .04 + uv[1] * .42)


class Plant:
    def __init__(self):
        self.faces = []

    def face(self, points, panel, role='leaves', uv=None, back=False):
        uv = uv or [(0, 1), (1, 1), (.5, 0)]
        points = [Vector(p) for p in points]
        self.faces.append((points, [atlas_uv(panel, p) for p in uv], role))
        if back:
            self.faces.append((list(reversed(points)), [atlas_uv(panel, p) for p in reversed(uv)], role))

    def branch(self, start, end, radius=.32, panel=2, role='bark', coarse=False):
        a, b = Vector(start), Vector(end)
        direction = (b - a).normalized()
        side = direction.cross(Vector((0, 1, .13))).normalized()
        up = direction.cross(side).normalized()
        rings = [[p + r * (side * cos(i * 2*pi/3) + up * sin(i * 2*pi/3)) for i in range(3)]
                 for p, r in ((a, radius), (b, radius * .35))]
        self.face(list(reversed(rings[0])), panel, role)
        if coarse:
            for i in range(3):
                self.face([rings[0][i], rings[0][(i+1) % 3], b], panel, role)
            return
        self.face(rings[1], panel, role)
        for i in range(3):
            j = (i + 1) % 3
            self.face([rings[0][i], rings[0][j], rings[1][j]], panel, role, [(0, 1), (1, 1), (1, 0)])
            self.face([rings[0][i], rings[1][j], rings[1][i]], panel, role, [(0, 1), (1, 0), (0, 0)])

    def leaf(self, start, end, width, panel=1):
        a, b = Vector(start), Vector(end)
        side = (b - a).cross(Vector((0, 0, 1))).normalized() * width
        middle = a.lerp(b, .48)
        ridge = middle + Vector((0, 0, width * .24))
        ring = [a, middle + side, b, middle - side]
        uv = [(.5, 1), (1, .52), (.5, 0), (0, .52)]
        for i in range(4):
            j = (i + 1) % 4
            self.face([ring[i], ring[j], ridge], panel, uv=[uv[i], uv[j], (.5, .52)], back=True)

    def lobe(self, center, radii, coarse=False, panel=0, snow=False, role='leaves'):
        bm = bmesh.new()
        if coarse:
            bmesh.ops.create_uvsphere(bm, u_segments=4, v_segments=2, radius=1)
        else:
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.normal_update()
        for face in bm.faces:
            points = [Vector(tuple(center[k] + v.co[k] * radii[k] for k in range(3))) for v in face.verts]
            normal = (points[1] - points[0]).cross(points[2] - points[0]).normalized()
            axes = sorted(range(3), key=lambda k: abs(normal[k]))[:2]
            uv = [tuple(v.co[k] * .5 + .5 for k in axes) for v in face.verts]
            cap = snow and normal.z > .22
            self.face(points, 3 if cap else panel, 'snow' if cap else role, uv)
        bm.free()


def shrub(family, lod):
    g = Plant()
    wet = family == 'wetland'
    needle = family in ('highland', 'snow')
    centers = [(0, 0, 10.8)] + [(10.1*cos(i*2*pi/6), 8.7*sin(i*2*pi/6), 7.2 + (i % 3)*1.0) for i in range(6)]
    for i, center in enumerate(centers):
        radii = (6.4, 5.3, 5.5 if wet else 4.1)
        g.lobe(center, radii, lod == 2, snow=family == 'snow')
    for i in range(8 if lod == 0 else 7):
        center = Vector(centers[i % len(centers)])
        g.branch((center.x * .2, center.y * .2, .45), center, .45 if wet else .55, coarse=lod == 2)
    for i in range((32, 5, 1)[lod]):
        angle = i * 2.399963
        center = Vector(centers[i % len(centers)])
        direction = Vector((cos(angle), sin(angle), .2 + (i % 4)*.12))
        start = center + direction * 2.5
        length = 5.3 if wet else 4.6 if needle else 4.0
        panel = 3 if family == 'highland' and i % 5 == 0 else 1
        g.leaf(start, start + direction * length, .65 if wet or needle else 1.7, panel)
    return g


def jungle(lod):
    g = Plant()
    for i in (range(16) if lod == 0 else range(9) if lod == 1 else (0, 4, 7, 14)):
        angle = i * 2.399963
        radius = 2.8 + i % 3
        start = Vector((cos(angle)*radius, sin(angle)*radius, 3.5 + i % 4 * 1.8))
        end = Vector((cos(angle)*(13 + i % 4), sin(angle)*(13 + i % 4), 5.5 + i % 5 * 2.4))
        g.leaf(start, end, 3.1 + i % 3 * .4)
        g.branch((cos(angle)*.5, sin(angle)*.5, .35), start, .28)
    for i in range((6, 3, 1)[lod]):
        angle = i * 2.399963 + .8
        radial = Vector((cos(angle), sin(angle), 0))
        side = Vector((-sin(angle), cos(angle), 0))
        root = Vector((cos(angle)*.4, sin(angle)*.4, .35))
        tip = radial*14 + Vector((0, 0, 8))
        g.branch(root, tip, .18)
        pairs = (7, 5, 6)[lod]
        for j in range(pairs):
            t = .18 + .7*j/pairs
            a = root.lerp(tip, t)
            b = root.lerp(tip, t + .7/pairs)
            for sign in (-1, 1):
                c = a + side * sign * (3.6*(1-t) + .5) + radial * 2.0 + Vector((0, 0, -.45))
                g.face([a, b, c], 3, back=True)
    return g


def closed_connected(mesh):
    """The cactus is a single welded, closed body, including every pad joint."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    assert all(edge.is_manifold for edge in bm.edges), 'Open cactus joint'
    pending = [next(iter(bm.verts))]
    visited = set()
    while pending:
        vertex = pending.pop()
        if vertex not in visited:
            visited.add(vertex)
            pending.extend(edge.other_vert(vertex) for edge in vertex.link_edges)
    assert len(visited) == len(bm.verts), 'Detached cactus pad'
    bm.free()


def desert():
    # Child bases start inside a parent's upper rim, and grow away along that rim.
    # Boolean fusion removes the internal surfaces and makes real fleshy joints.
    pads = [
        ((0, 0, .2), (0, 0, 5.2), 4.0, 0),
        ((0, 0, 4.35), (.7, .4, 10.4), 4.2, .45),
        ((-1.2, 0, 3.4), (-4.8, -1.2, 7.9), 3.8, -.45),
        ((-4.3, -1.05, 7.35), (-5.4, -3.1, 13.0), 3.6, 1.05),
        ((1.2, 0, 3.4), (5.2, 1.5, 7.6), 4.0, .7),
        ((4.65, 1.3, 7.05), (6.3, 4.6, 12.1), 3.8, 1.8),
        ((.63, .36, 9.72), (-1.1, 1.2, 15.4), 3.6, 1.3),
        ((0, -.35, 3.4), (-.4, -4.6, 8.0), 4.1, .2),
        ((-.35, -4.03, 7.42), (2.4, -6.7, 13.1), 3.9, -.8),
        ((0, .36, 3.3), (-2.4, 4.9, 7.4), 4.0, .4),
        ((-2.04, 4.22, 6.78), (-4.2, 6.8, 12.1), 3.7, 1.9),
    ]
    old_scene = bpy.context.window.scene
    work = bpy.data.scenes.new('Cactus fusion')
    bpy.context.window.scene = work
    frames = []
    body = None
    try:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=.45, depth=1.9, location=(0, 0, .25))
        body = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for start, end, width, twist in pads:
            a, b = Vector(start), Vector(end)
            along = (b-a).normalized()
            across = Quaternion(along, twist) @ Vector((along.z, 0, -along.x)).normalized()
            depth = along.cross(across).normalized()
            center = a.lerp(b, .5)
            half = (b-a).length / 2
            frames.append((center, across, along, width/2, half, depth))
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1)
            for vertex in bm.verts:
                x, y, z = vertex.co
                vertex.co = center + across*x*width/2 + depth*y*.65 + along*z*half
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            mesh = bpy.data.meshes.new('Cactus pad')
            bm.to_mesh(mesh)
            bm.free()
            pad = bpy.data.objects.new('Cactus pad', mesh)
            work.collection.objects.link(pad)
            bpy.ops.object.select_all(action='DESELECT')
            body.select_set(True)
            bpy.context.view_layer.objects.active = body
            modifier = body.modifiers.new('Fleshy pad union', 'BOOLEAN')
            modifier.operation = 'UNION'
            modifier.solver = 'EXACT'
            modifier.object = pad
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            bpy.data.objects.remove(pad, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            closed_connected(body.data)
        body.data.calc_loop_triangles()
        original_count = len(body.data.loop_triangles)
        plants = []
        for budget in BUDGETS:
            obj = bpy.data.objects.new('Cactus LOD', body.data.copy())
            work.collection.objects.link(obj)
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new('Cactus screen detail', 'DECIMATE')
            modifier.ratio = min(1, (budget-2) / original_count)
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            # Decimation can shorten the basal stem. Restore only its ground contact,
            # tapering the correction to zero below the first pad; the crown stays put.
            floor, shoulder = -.7, .2
            lowest = min(vertex.co.z for vertex in obj.data.vertices)
            assert lowest < shoulder, 'Cactus lost its basal stem'
            for vertex in obj.data.vertices:
                if vertex.co.z < shoulder:
                    vertex.co.z = floor + (vertex.co.z-lowest) * (shoulder-floor) / (shoulder-lowest)
            obj.data.update()
            closed_connected(obj.data)
            obj.data.calc_loop_triangles()
            plant = Plant()
            for triangle in obj.data.loop_triangles:
                points = [obj.data.vertices[i].co.copy() for i in triangle.vertices]
                middle = sum(points, Vector())/3
                center, across, along, width, half, _ = min(frames, key=lambda f:
                    ((middle-f[0]).dot(f[1])/f[3])**2 + ((middle-f[0]).dot(f[2])/f[4])**2
                    + ((middle-f[0]).dot(f[5])/.65)**2)
                uv = [(max(0, min(1, .5+(p-center).dot(across)/(2*width))),
                       max(0, min(1, .5-(p-center).dot(along)/(2*half)))) for p in points]
                plant.face(points, 1, 'cactus', uv)
            assert len(plant.faces) <= budget, (len(plant.faces), budget)
            plants.append(plant)
        return plants
    finally:
        bpy.context.window.scene = old_scene
        for obj in list(work.objects):
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.data.scenes.remove(work)


def barren(lod):
    g = Plant()
    endpoints = []
    count = 8
    for i in range(count):
        angle = i * 2.399963
        root = Vector((cos(angle)*2, sin(angle)*2, .4))
        knee = Vector((cos(angle)*7, sin(angle)*7, 6 + i % 3))
        tip = Vector((cos(angle)*14, sin(angle)*14, 10 + i % 4 * 2))
        # Keep every major branch at distance; triangular cones spend fewer faces on each branch's roundness.
        g.branch(root, knee, .70 if lod == 2 else .55, coarse=lod == 2)
        g.branch(knee, tip, .40 if lod == 2 else .31, coarse=lod == 2)
        endpoints.append((knee, tip, angle))
    for i in range((26, 8, 1)[lod]):
        knee, tip, angle = endpoints[i % count]
        start = knee.lerp(tip, .25 + i % 3 * .2)
        end = start + Vector((cos(angle + 1.1)*4, sin(angle + 1.1)*4, 2.5))
        g.branch(start, end, .18 if lod == 2 else .14, coarse=lod == 2)
    for i in range((15, 5, 1)[lod]):
        knee, tip, angle = endpoints[i % count]
        start = knee.lerp(tip, .65)
        g.leaf(start, start + Vector((cos(angle)*2.5, sin(angle)*2.5, -.6)), .55)
    return g


def blender_mesh(scene, name, plant, materials):
    mesh = bpy.data.meshes.new(name)
    vertices, shared, faces = [], {}, []
    for points, _, _ in plant.faces:
        indices = []
        for point in points:
            key = tuple(point)
            if key not in shared:
                shared[key] = len(vertices)
                vertices.append(point)
            indices.append(shared[key])
        faces.append(indices)
    mesh.from_pydata(vertices, [], faces)
    uv = mesh.uv_layers.new(name='UVMap')
    roles = sorted({role for _, _, role in plant.faces})
    for role in roles:
        mesh.materials.append(materials[role])
    for face, (_, coords, role) in zip(mesh.polygons, plant.faces):
        face.material_index = roles.index(role)
        for loop, point in zip(face.loop_indices, coords):
            uv.data[loop].uv = (point[0], 1 - point[1])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def export_model(obj, family):
    mesh = obj.data
    mesh.calc_loop_triangles()
    vertices, shared, parts = [], {}, defaultdict(list)
    for tri in mesh.loop_triangles:
        role = mesh.materials[tri.material_index]['role']
        for loop in tri.loops:
            point = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv = mesh.uv_layers.active.data[loop].uv
            vertex = tuple(round(v, 6) for v in (*point, *tri.normal, 1, 1, 1, 1, uv.x, 1-uv.y))
            if vertex not in shared:
                shared[vertex] = len(vertices) // 12
                vertices.extend(vertex)
            parts[role].append(shared[vertex])
    path = f'textures/vegetation/shrubs/{family}.png'
    return {'id': obj.name, 'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'],
             'vertices': vertices, 'parts': [{'id': role, 'type': 'TRIANGLES', 'indices': indices}
                                          for role, indices in parts.items()]}],
            'materials': [{'id': role, 'diffuse': [1, 1, 1], 'textures': [
                {'id': role, 'type': kind, 'filename': path.replace('.png', suffix + '.png'),
                 'wrapS': 33071, 'wrapT': 33071}
                for kind, suffix in (('DIFFUSE', ''), ('NORMAL', '-normal'), ('AMBIENT', '-surface'))]}
                          for role in parts],
            'nodes': [{'id': obj.name, 'parts': [{'meshpartid': role, 'materialid': role} for role in parts]}]}


def fern_crowns(source):
    """Bent fern sprays: broad bases, tapered tips and open leaflets instead of solid leaf diamonds."""
    levels = {}
    material = cutout_material('canopy-cutout', 'fern-cutout')
    for lod, (sprays, segments) in enumerate(((28, 4), (18, 3), (12, 2))):
        result = []
        rng = Random(1374)
        for i in range(sprays):
            angle = i * 2.399963
            outward = Vector((cos(angle), sin(angle), 0))
            side = Vector((-sin(angle), cos(angle), 0))
            root = outward * rng.uniform(.2, 3)
            reach, rise = rng.uniform(11, 16), rng.uniform(10, 16)
            width = rng.uniform(6, 8) * (1, 1.3, 1.65)[lod]
            for j in range(segments):
                points = []
                normals = []
                for t, sign in ((j / segments, -1), (j / segments, 1),
                                ((j + 1) / segments, 1), ((j + 1) / segments, -1)):
                    center = root + outward * reach * t
                    center.z = rise * (1.5 * t - .5 * t*t)
                    points.append(center + side * sign * width / 2)
                    normals.append((Vector((0, 0, 1)) + outward * .35).normalized())
                append_cutout(result, 'canopy-cutout', points,
                              ((0, 1-j/segments), (1, 1-j/segments),
                               (1, 1-(j+1)/segments), (0, 1-(j+1)/segments)),
                              ((0, 1, 2), (0, 2, 3)), normals)
        model = pack(source, f'foliage-jungle-lod{lod}', result)
        model['materials'] = [material]
        levels[lod] = model
    # All levels share the near model's shape and scale, not a camera-dependent fit.
    height = max(levels[0]['meshes'][0]['vertices'][2::12])
    for model in levels.values():
        data = model['meshes'][0]['vertices']
        for i in range(0, len(data), 12):
            for axis in range(3):
                data[i + axis] *= 18 / height
    return levels


def build(source_path=None):
    scene = bpy.data.scenes.new('Level-one foliage')
    scene.unit_settings.system = 'NONE'
    manifest_path = BOARD / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    summary = {}
    for index, family in enumerate(FAMILIES):
        image = bpy.data.images.load(str(ROOT / 'tools/foliage-sources/shrubs/jungle.png' if family == 'jungle'
            else BOARD / f'textures/vegetation/shrubs/{family}.png'), check_existing=True)
        materials = {}
        for role in ('leaves', 'bark', 'cactus', 'snow'):
            material = bpy.data.materials.new(f'foliage-{family}-{role}')
            material['role'] = role
            material.use_nodes = True
            nodes = material.node_tree.nodes
            shader = nodes.get('Principled BSDF')
            shader.inputs['Roughness'].default_value = .88
            texture = nodes.new('ShaderNodeTexImage')
            texture.image = image
            texture.extension = 'EXTEND'
            material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
            materials[role] = material
        levels, objects, counts = {}, [], []
        desert_plants = desert() if family == 'desert' else None
        for lod in range(3):
            plant = jungle(lod) if family == 'jungle' else desert_plants[lod] if family == 'desert' else barren(lod) if family == 'barren' else shrub(family, lod)
            assert 0 < len(plant.faces) <= BUDGETS[lod], (family, lod, len(plant.faces))
            objects.append(blender_mesh(scene, f'foliage-{family}-mesh{lod}', plant, materials))
        # All three levels share one coordinate system and a single uniform authoring normalization.
        low = min(v.co.z for v in objects[0].data.vertices)
        high = max(v.co.z for v in objects[0].data.vertices)
        scale = 18 / (high - low)
        for lod, obj in enumerate(objects):
            for v in obj.data.vertices:
                v.co.z -= low
                v.co *= scale
            obj.data.update()
            levels[lod] = export_model(obj, family)
            counts.append({'node': f'foliage-{family}-lod{lod}', 'triangles': len(obj.data.polygons),
                           'vertices': len(levels[lod]['meshes'][0]['vertices']) // 12})
            # Layout only affects the editable source; exported vertices stay at their common root.
            obj.location = ((index % 4)*52, -(index // 4)*170 - lod*48, 0)
            obj['lod'] = lod
            obj['family'] = family
        name = f'foliage-{family}'
        if family == 'jungle':
            levels = fern_crowns(levels[0])
        elif family == 'barren':
            levels = branch_crowns(levels[0], name, levels)
        elif family not in ('desert', 'barren'):
            levels = branch_crowns(levels[0], name)
        elif family == 'desert':
            for model in levels.values():
                round_cactus(model)
        # Keep the authored forms as inspectable source envelopes; show the exported cards beside them.
        for lod, model in levels.items():
            obj = bpy.data.objects.new(f'{name}-runtime{lod}', unlit_mesh(model, f'{name}-runtime{lod}', {}))
            scene.collection.objects.link(obj)
            obj.location = ((index % 4)*52, -(index // 4)*170 - lod*48, 26)
            obj['lod'] = lod
        counts = [{'node': f'{name}-lod{lod}', **model_counts(model)} for lod, model in levels.items()]
        write_glb(BOARD / (name + '.glb'), levels=levels)
        manifest[name] = {'mesh': name + '.glb', 'triangles': counts[0]['triangles'],
                          'vertices': counts[0]['vertices'], 'generator': 'tools/build_foliage_assets.py',
                          'texture': f'textures/vegetation/shrubs/{family}.png', 'lods': counts}
        if family == 'jungle':
            manifest[name].pop('texture')  # The exported fern uses its actual cutout material.
        summary[name] = [entry['triangles'] for entry in counts]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    bpy.data.libraries.write(str(source_path or ROOT / 'tools/board-foliage.blend'), {scene}, fake_user=True)
    return scene, summary


if __name__ == '__main__':
    scene, summary = build()
    print(json.dumps(summary))
