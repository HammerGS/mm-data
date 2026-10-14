"""Run with Blender --background --python tools/prepare_tree_lods.py -- impostors [names...].

Shared branch-card helpers support the shrub, orchard and volcanic foliage
generators. The command adds LOD3 to existing plant GLBs: three textured cards
carrying unlit renders of LOD0, while preserving their three mesh levels.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_geometry import read_glb, write_glb

import copy
import json
import math
import random

import bpy
import numpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

BOARD = Path(__file__).resolve().parents[1] / 'data/models/board'
IMPOSTORS = 'textures/vegetation/impostors'
# Pixels per card face; the game draws the cards only below TreeLod's smallest threshold.
PANEL = 128

# Subtle species pigments separate crowns from the olive meadow without new textures
# or materials. Baked vertex colour is also captured by the distant impostor.
CROWN_TINTS = {
    'tree': (.74, .91, .84), 'tree-broad': (.69, .86, .82),
    'tree-slender': (.85, .97, .89), 'tree-forked': (.77, .94, .97),
    'tree-layered': (.80, .87, .73),
    'birch': (.87, .98, .91), 'birch-tall': (.78, .94, 1.0),
    'birch-spreading': (.94, .97, .82), 'birch-young': (.84, 1.0, .87),
    'willow': (.78, .88, .97), 'willow-broad': (.87, .94, 1.0),
    'pine': (.80, .93, 1.0), 'pine-tall': (.76, .90, .95),
    'pine-broad': (.90, .97, .88), 'pine-slender': (.75, .90, 1.0),
    'pine-layered': (.86, .92, .92),
}


def geometry(model):
    """Weld positions for topology only; retain the authored per-corner data."""
    vertices, shared, faces, corners = [], {}, [], []
    mesh = model['meshes'][0]
    source = mesh['vertices']
    for part in mesh['parts']:
        for offset in range(0, len(part['indices']), 3):
            attributes = [source[i * 12:i * 12 + 12] for i in part['indices'][offset:offset + 3]]
            face = []
            for vertex in attributes:
                # Simplification operates in the tree's original proportions.
                point = tuple(vertex[:3])
                if point not in shared:
                    shared[point] = len(vertices)
                    vertices.append(Vector(point))
                face.append(shared[point])
            faces.append(face)
            corners.append((part['id'], attributes))
    return vertices, faces, corners


def pack(source, name, corners):
    model = copy.deepcopy(source)
    vertices, shared, parts = [], {}, {}
    for role, triangle in corners:
        indices = parts.setdefault(role, [])
        for vertex in triangle:
            key = tuple(vertex)
            if key not in shared:
                shared[key] = len(vertices) // 12
                vertices.extend(vertex)
            indices.append(shared[key])
    model['id'] = name
    model['meshes'] = [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], 'vertices': vertices,
                        'parts': [{'id': role, 'type': 'TRIANGLES', 'indices': indices}
                                  for role, indices in parts.items()]}]
    model['nodes'] = [{'id': name, 'parts': [{'meshpartid': role, 'materialid': role} for role in parts]}]
    return model


def decimated(vertices, faces, keys, budget):
    """Blender's collapse decimation of faces to about budget triangles, each as its corners, material key and normal."""
    mesh = bpy.data.meshes.new('Tree screen-size detail')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    order = {key: index for index, key in enumerate(dict.fromkeys(keys))}
    for role, color in order:
        mesh.materials.append(bpy.data.materials.new(role))
    for polygon, key in zip(mesh.polygons, keys):
        polygon.material_index = order[key]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    modifier = obj.modifiers.new('Tree screen-size detail', 'DECIMATE')
    modifier.ratio = min(1, budget / len(faces))
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    mesh = obj.data
    mesh.calc_loop_triangles()
    keys = list(order)
    result = [([mesh.vertices[index].co.copy() for index in triangle.vertices], keys[triangle.material_index],
               triangle.normal.copy()) for triangle in mesh.loop_triangles]
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return result


def parts(count, faces):
    """The faces of each connected part of a plant: its trunk, a skirt of needles, a frond."""
    root = list(range(count))

    def find(vertex):
        while root[vertex] != vertex:
            root[vertex] = root[root[vertex]]
            vertex = root[vertex]
        return vertex

    for face in faces:
        for vertex in face[1:]:
            root[find(vertex)] = find(face[0])
    groups = {}
    for index, face in enumerate(faces):
        groups.setdefault(find(face[0]), []).append(index)
    return list(groups.values())


def simplified(source, name, budget):
    vertices, faces, corners = geometry(source)
    keys = [(role, tuple(attributes[0][6:10])) for role, attributes in corners]
    triangles = decimated(vertices, faces, keys, budget)
    result = []
    low = Vector(tuple(min(point[i] for point in vertices) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in vertices) for i in range(3)))
    for points, (role, color), normal in triangles:
        n = normal.normalized()
        attributes = []
        for point in points:
            # All levels share the near model's coordinate system and bounds.
            point = Vector(tuple(max(low[i], min(high[i], point[i])) for i in range(3)))
            if abs(normal.z) >= max(abs(normal.x), abs(normal.y)):
                uv = (point.x, point.y)
            else:
                uv = (point.x if abs(normal.y) > abs(normal.x) else point.y, point.z)
            repeat = 4 if role.startswith('bark') else 8 if name.startswith('birch') else 12
            attributes.append(tuple(round(v, 6) for v in
                                    (point.x, point.y, point.z, *n, *color, uv[0] / repeat, uv[1] / repeat)))
        result.append((role, attributes))
    assert len(result) <= budget, (name, len(result), budget)
    return pack(source, name, result)


def counts(model):
    mesh = model['meshes'][0]
    return {'triangles': sum(len(part['indices']) // 3 for part in mesh['parts']),
            'vertices': len(mesh['vertices']) // 12}


def stem_section(vertices, faces, height):
    """Centre of the authored stem at a height, including its bends, not its overall bounding box."""
    low = min(p.z for p in vertices)
    high = max(p.z for p in vertices)
    z = max(low + .0001, min(high - .0001, height))
    crossing = []
    for face in faces:
        for i in range(3):
            a, b = vertices[face[i]], vertices[face[(i + 1) % 3]]
            if min(a.z, b.z) <= z <= max(a.z, b.z) and abs(a.z - b.z) > 1e-6:
                crossing.append(a.lerp(b, (z - a.z) / (b.z - a.z)))
    assert crossing, ('Stem has no section', height)
    return Vector(((min(p.x for p in crossing) + max(p.x for p in crossing)) / 2,
                   (min(p.y for p in crossing) + max(p.y for p in crossing)) / 2, height))


def cutout_material(role, texture):
    return {'id': role, 'diffuse': [1, 1, 1], 'alphaTest': .5, 'textures': [
        {'id': role, 'type': kind, 'filename': f'textures/vegetation/{texture}{suffix}.png',
         'wrapS': 33071, 'wrapT': 33071}
        for kind, suffix in (('DIFFUSE', ''), ('NORMAL', '-normal'), ('AMBIENT', '-surface'))]}


def append_cutout(result, role, points, uvs, triangles, normals=None, tint=1):
    color = (tint, tint, tint) if isinstance(tint, (int, float)) else tint
    for indices in triangles:
        normal = (points[indices[1]] - points[indices[0]]).cross(points[indices[2]] - points[indices[0]])
        if normal.length < 1e-6:
            continue
        normal.normalize()
        attributes = [tuple(round(v, 6) for v in
                            (*points[j], *(normals[j] if normals else normal), *color, 1, *uvs[j]))
                      for j in indices]
        result.append((role, attributes))
        # Explicit backs retain the same botanical normal, as the existing canopy lighting expects.
        result.append((role, list(reversed(attributes))))


def branch_crowns(source, name, retained_levels=None):
    """Replace closed leaf shells with bounded branch cards, keeping the authored trunk and crown envelopes.

    All three mesh levels use the same source silhouette and seed. The original
    CC0 authoring file stays untouched. Explicit backs work in every existing
    depth/shadow pass. Standard glTF MASK materials keep every level opaque.
    """
    if not name.startswith(('tree', 'pine', 'birch', 'willow', 'orchard-', 'foliage-')) or name.startswith('tree-dead'):
        return None
    vertices, faces, corners = geometry(source)
    leaves = [face for face, (role, _) in zip(faces, corners) if not solid(role)]
    if not leaves:
        return None
    envelopes = []
    for group in parts(len(vertices), leaves):
        points = [vertices[i] for j in group for i in leaves[j]]
        low = Vector(tuple(min(p[k] for p in points) for k in range(3)))
        high = Vector(tuple(max(p[k] for p in points) for k in range(3)))
        if (high - low).length > .5:
            envelopes.append(((low + high) / 2, (high - low) / 2))
    low = Vector(tuple(min(p[k] for face in leaves for p in (vertices[i] for i in face)) for k in range(3)))
    high = Vector(tuple(max(p[k] for face in leaves for p in (vertices[i] for i in face)) for k in range(3)))
    bark = pack(source, name, [corner for corner in corners if solid(corner[0])])
    stem_vertices, stem_faces, _ = geometry(bark)
    pine = name.startswith('pine')
    shrub = name.startswith('foliage-')
    texture = ('conifer' if pine or name in ('foliage-highland', 'foliage-snow') else
               'shrub' if shrub else 'broadleaf') + ('-snow' if name.endswith('-snow') else '') + '-cutout'
    role = 'canopy-snow-cutout' if name.endswith('-snow') else 'canopy-cutout'
    material = cutout_material(role, texture)
    seed = sum((i + 1) * ord(c) for i, c in enumerate(name.removesuffix('-snow')))
    levels = {}
    for level, (budget, cards) in enumerate(((480, 88), (240, 42), (96, 15))):
        rng = random.Random(seed)
        if retained_levels is None:
            model = simplified(bark, f'{name}-lod{level}', budget - cards * 4)
        else:
            # These plant LODs already author their own branch and fruit counts. Keep those exactly,
            # assigning only the remaining budget to leaves instead of decimating individual apples.
            retained = retained_levels[level]
            _, _, parts_to_keep = geometry(retained)
            model = pack(retained, f'{name}-lod{level}', [p for p in parts_to_keep if solid(p[0])])
            cards = min(cards, (budget - counts(model)['triangles']) // 4)
            assert cards > 0, (name, level, 'No remaining foliage budget')
        _, _, result = geometry(model)
        for i in range(cards):
            if pine:
                t = (i + .5) / cards
                angle = i * 2.399963 + rng.uniform(-.12, .12)
                radius = max(high.x - low.x, high.y - low.y) * .49 * (1 - t) ** .75
                outward = Vector((math.cos(angle), math.sin(angle), 0))
                right = Vector((-outward.y, outward.x, rng.uniform(-.55, .55))).normalized()
                up = (outward + Vector((0, 0, .25 + t * .7))).normalized()
                length = radius * 1.15 + .8
                centre = stem_section(stem_vertices, stem_faces, low.z + t * (high.z - low.z))
                centre += up * length * .4
                width = length * (1.05 if level == 0 else 1.4 if level == 1 else 2.2)
                normal = (outward * .45 + Vector((0, 0, .8))).normalized()
            else:
                centre, extent = rng.choices(envelopes, weights=[e.length_squared for _, e in envelopes])[0]
                angle = i * 2.399963
                z = rng.uniform(-.85, .95)
                radial = Vector((math.cos(angle) * math.sqrt(1 - z * z),
                                 math.sin(angle) * math.sqrt(1 - z * z), z))
                centre = centre + Vector(tuple(radial[k] * extent[k] * .65 for k in range(3)))
                normal = (radial + Vector((0, 0, .45))).normalized()
                right = Vector((-math.sin(angle), math.cos(angle), rng.uniform(-.3, .3))).normalized()
                up = normal.cross(right).normalized()
                # Broadleaf sprays form lobes; willow cards droop from those same authored lobes.
                if name.startswith('willow'):
                    up = Vector((radial.x * .25, radial.y * .25, -1)).normalized()
                width = max(2.5, extent.length * (.8 if level == 0 else 1.05 if level == 1 else 1.9 if shrub else 1.5))
                length = width * (1.25 if name.startswith(('willow', 'birch')) else .95)
            # Fewer distant branches cover the same envelope; length as well as width must bridge their gaps.
            if pine and level == 2:
                length *= 1.3
            points = [centre + right * x * width + up * y * length
                      for x, y in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5))]
            # Never expand foliage beyond the captured source bounds or its route/structure clearance.
            points = [Vector(tuple(max(low[k], min(high[k], p[k])) for k in range(3))) for p in points]
            shade = rng.uniform(.88, 1.0)
            pigment = (1, 1, 1) if name.endswith('-snow') else CROWN_TINTS.get(name, {
                'foliage-temperate': (.86, .98, .84), 'foliage-wetland': (.83, 1, .89),
                'foliage-rocky': (.92, .91, .78), 'foliage-highland': (.80, .94, .86),
                'foliage-barren': (.92, .70, .43)
            }.get(name, (1, 1, 1)))
            tint = tuple(shade * channel for channel in pigment)
            append_cutout(result, role, points, ((0, 1), (1, 1), (1, 0), (0, 0)),
                          ((0, 1, 2), (0, 2, 3)), [normal] * 4, tint)
        model['materials'] = [m for m in source['materials'] if solid(m['id'])] + [material]
        model['nodes'] = [{'id': f'{name}-lod{level}', 'parts': [
            {'meshpartid': m['id'], 'materialid': m['id']} for m in model['materials']]}]
        levels[level] = pack(model, f'{name}-lod{level}', result)
        # A clipped branch tip must not shorten the normalized catalog height, which placement uses at every LOD.
        data = levels[level]['meshes'][0]['vertices']
        bottom = min(data[2::12])
        scale = max(point.z for point in vertices) / (max(data[2::12]) - bottom)
        for vertex in range(0, len(data), 12):
            data[vertex + 2] = (data[vertex + 2] - bottom) * scale
        assert counts(levels[level])['triangles'] <= budget
    return levels


def round_cactus(model):
    """Shade the cactus's round stems smoothly; retain every joint, silhouette and texture seam."""
    mesh = model['meshes'][0]
    data, normals = mesh['vertices'], {}
    for part in mesh['parts']:
        if part['id'] != 'cactus':
            continue
        for offset in range(0, len(part['indices']), 3):
            indices = part['indices'][offset:offset + 3]
            points = [Vector(data[i * 12:i * 12 + 3]) for i in indices]
            normal = (points[1] - points[0]).cross(points[2] - points[0])
            for point in points:
                normals.setdefault(tuple(point), Vector())
                normals[tuple(point)] += normal
        for index in set(part['indices']):
            start = index * 12
            normal = normals[tuple(Vector(data[start:start + 3]))].normalized()
            data[start + 3:start + 6] = list(normal)


def solid(role):
    """Roles the game lights as solid rather than as a canopy (GpuTerrain.foliage)."""
    return role.startswith('bark') or role in ('cactus', 'fruit')


def material_roles(model):
    """A split variant can rename a material while retaining the original meshpart ID."""
    roles = {}
    def visit(node):
        for part in node.get('parts', []):
            roles[part['meshpartid']] = part['materialid']
        for child in node.get('children', []):
            visit(child)
    for node in model['nodes']:
        visit(node)
    return roles


def unlit_material(role, filename, images, *, linear_colors=False):
    """Unlit pigment; the impostor bake filters sRGB textures in linear light.

    The default preserves the separate legacy builder-preview input contract.
    """
    material = bpy.data.materials.new(role)
    material.use_nodes = True
    material.use_backface_culling = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    if filename not in images:
        # The bake owns its image copies; never change a builder's existing image color space.
        images[filename] = bpy.data.images.load(str(BOARD / filename), check_existing=not linear_colors)
        images[filename].colorspace_settings.name = 'sRGB' if linear_colors else 'Non-Color'
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = images[filename]
    texture.interpolation = 'Linear'
    color = nodes.new('ShaderNodeVertexColor')
    color.layer_name = 'Color'
    product = nodes.new('ShaderNodeVectorMath')
    product.operation = 'MULTIPLY'
    links.new(texture.outputs['Color'], product.inputs[0])
    links.new(color.outputs['Color'], product.inputs[1])
    albedo = product.outputs[0]
    # Snow uses its authored texture and vertex pigment, just like the runtime foliage shader.
    emission = nodes.new('ShaderNodeEmission')
    links.new(albedo, emission.inputs['Color'])
    output = nodes.new('ShaderNodeOutputMaterial')
    if role.endswith('-cutout'):
        threshold = nodes.new('ShaderNodeMath')
        threshold.operation = 'GREATER_THAN'
        threshold.inputs[1].default_value = .5
        links.new(texture.outputs['Alpha'], threshold.inputs[0])
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(threshold.outputs[0], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])
        if hasattr(material, 'surface_render_method'):
            material.surface_render_method = 'DITHERED'
        elif hasattr(material, 'blend_method'):
            material.blend_method = 'CLIP'
    else:
        links.new(emission.outputs[0], output.inputs['Surface'])
    return material


def unlit_mesh(model, name, images, *, linear_colors=False):
    """LOD0 with one vertex per corner, so every authored colour and texture coordinate survives."""
    mesh = model['meshes'][0]
    source = mesh['vertices']
    textures = {material['id']: material['textures'][0]['filename'] for material in model['materials']}
    bound_roles = material_roles(model)
    vertices, faces, colors, uvs, roles = [], [], [], [], []
    for part in mesh['parts']:
        for offset in range(0, len(part['indices']), 3):
            faces.append((len(vertices), len(vertices) + 1, len(vertices) + 2))
            roles.append(bound_roles[part['id']])
            for index in part['indices'][offset:offset + 3]:
                vertex = source[index * 12:index * 12 + 12]
                vertices.append(vertex[:3])
                # The impostor path reads original linear glTF RGB; builder previews retain their input domain.
                colors.append(vertex[6:10])
                uvs.append((vertex[10], 1 - vertex[11]))
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    color = data.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv = data.uv_layers.new(name='UV')
    for polygon in data.polygons:
        for loop in polygon.loop_indices:
            color.data[loop].color = colors[data.loops[loop].vertex_index]
            uv.data[loop].uv = uvs[data.loops[loop].vertex_index]
    materials = {}
    for polygon, role in zip(data.polygons, roles):
        if role not in materials:
            materials[role] = len(data.materials)
            data.materials.append(unlit_material(role, textures[role], images, linear_colors=linear_colors))
        polygon.material_index = materials[role]
    data.update()
    return data


def bounds(model):
    vertices = model['meshes'][0]['vertices']
    return [min(vertices[i::12]) for i in range(3)], [max(vertices[i::12]) for i in range(3)]


def crown(model, low, high):
    """Height of the cap: the canopy's mean height, or the middle of a plant without one."""
    mesh = model['meshes'][0]
    heights = [mesh['vertices'][index * 12 + 2] for part in mesh['parts'] if not solid(part['id'])
               for index in part['indices']]
    return sum(heights) / len(heights) if heights else (low[2] + high[2]) / 2


# The board camera looks down at trees, so the vertical cards show the plant from this elevation: the canopy then
# covers the trunk as it would in three dimensions, while the cap alone shows from straight above.
ELEVATION = math.radians(30)
# The turns that bring each card's face toward a camera at -y: the front and side faces, each turned about the
# plant's axis before it tips toward the camera (tipping first would roll the side view), then the top.
FACES = tuple((Matrix.Rotation(ELEVATION, 3, 'X') @ Matrix.Rotation(turn, 3, 'Z')).to_euler()
              for turn in (0, -math.pi / 2)) + (Euler((math.pi / 2, 0, 0)),)


def framing(turn, low, high):
    """The square panel framing the turned plant: its size and centre, in the camera's right and up axes."""
    rotation = turn.to_matrix()
    corners = [rotation @ Vector((x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1])
               for z in (low[2], high[2])]
    lowest = Vector((min(c.x for c in corners), 0, min(c.z for c in corners)))
    highest = Vector((max(c.x for c in corners), 0, max(c.z for c in corners)))
    # A little margin keeps the dilated rim inside its own panel.
    return max(highest.x - lowest.x, highest.z - lowest.z) * 1.04, (lowest + highest) / 2


def dilate(rgba, passes=8):
    """Spread edge colours into transparent texels, so filtering and mipmaps never darken the cutout's rim."""
    rgb, filled = rgba[..., :3].copy(), rgba[..., 3] > 0
    for _ in range(passes):
        if filled.all():
            break
        for shift in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            take = ~filled & numpy.roll(filled, shift, (0, 1))
            rgb[take] = numpy.roll(rgb, shift, (0, 1))[take]
            filled |= take
    return numpy.concatenate([rgb, rgba[..., 3:]], axis=2)


def render_faces(scene, model, name, images, panels):
    """One render of LOD0 turned toward the camera three times, each face filling its own square panel."""
    data = unlit_mesh(model, name, images, linear_colors=True)
    objects = []
    for panel, (turn, (size, centre)) in enumerate(zip(FACES, panels)):
        obj = bpy.data.objects.new(f'{name}-face{panel}', data)
        scene.collection.objects.link(obj)
        obj.rotation_euler = turn
        obj.scale = (1 / size,) * 3
        obj.location = (panel - 1 - centre.x / size, 0, -centre.z / size)
        objects.append(obj)
    path = BOARD / IMPOSTORS / (name + '.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for material in list(data.materials):
            bpy.data.materials.remove(material)
        bpy.data.meshes.remove(data)
    # Standard already encoded this PNG once. Dilation only copies encoded texels, never averages them.
    rendered = bpy.data.images.load(str(path), check_existing=False)
    rendered.colorspace_settings.name = 'Non-Color'
    pixels = numpy.array(rendered.pixels[:], dtype=numpy.float32).reshape(PANEL, 3 * PANEL, 4)
    bpy.data.images.remove(rendered)
    pixels = numpy.concatenate([dilate(pixels[:, i * PANEL:(i + 1) * PANEL]) for i in range(3)], axis=1)
    atlas = bpy.data.images.new(name + '-impostor', 3 * PANEL, PANEL, alpha=True)
    atlas.colorspace_settings.name = 'Non-Color'
    atlas.pixels = pixels.ravel().tolist()
    atlas.filepath_raw = str(path)
    atlas.file_format = 'PNG'
    atlas.save()
    bpy.data.images.remove(atlas)


def shown_normal(model, toward):
    """The mean lighting normal of the surfaces LOD0 turns toward a camera, weighted by their projected area."""
    mesh = model['meshes'][0]
    vertices = mesh['vertices']
    total = Vector()
    for part in mesh['parts']:
        for offset in range(0, len(part['indices']), 3):
            corners = [vertices[i * 12:i * 12 + 12] for i in part['indices'][offset:offset + 3]]
            a, b, c = (Vector(corner[:3]) for corner in corners)
            shown = (b - a).cross(c - a).dot(toward) / 2
            if shown > 0:
                total += sum((Vector(corner[3:6]) for corner in corners), Vector()) * shown
    return total.normalized()


# The sun directions the board's lighting spans: three elevations all round.
SUNS = [Vector((math.cos(turn) * math.cos(elevation), math.sin(turn) * math.cos(elevation), math.sin(elevation)))
        for elevation in map(math.radians, (30, 50, 70)) for turn in (i * math.pi / 4 for i in range(8))]


def lighting(model, toward):
    """How the surfaces LOD0 shows toward a camera take the sun, as terrain-foliage.frag lights them over the board's
    sun directions: the share of direct light that gets past the plant's own leaves and branches, and the share of
    what shows that is bark, cactus or snow, which take light straight on where leaves scatter it around. A card
    standing inside its crown cannot take that shade from the shadow map, which would shade it with its own cards."""
    vertices, faces, corners = geometry(model)
    bound_roles = material_roles(model)
    corners = [(bound_roles[part], attributes) for part, attributes in corners]
    tree = BVHTree.FromPolygons(vertices, faces, all_triangles=True)
    cutouts = {}
    for material in model['materials']:
        if not material['id'].endswith('-cutout'):
            continue
        image = bpy.data.images.load(str(BOARD / material['textures'][0]['filename']), check_existing=True)
        pixels = numpy.empty(len(image.pixels), dtype=numpy.float32)
        image.pixels.foreach_get(pixels)
        cutouts[material['id']] = pixels.reshape(image.size[1], image.size[0], 4)[:, :, 3]

    def covered(index, point):
        role, attributes = corners[index]
        if role not in cutouts:
            return True
        a, b, c = (vertices[v] for v in faces[index])
        ab, ac, ap = b - a, c - a, point - a
        denominator = ab.dot(ab) * ac.dot(ac) - ab.dot(ac) ** 2
        if abs(denominator) < 1e-9:
            return False
        u = (ac.dot(ac) * ap.dot(ab) - ab.dot(ac) * ap.dot(ac)) / denominator
        v = (ab.dot(ab) * ap.dot(ac) - ab.dot(ac) * ap.dot(ab)) / denominator
        uv = [attributes[0][k] * (1 - u - v) + attributes[1][k] * u + attributes[2][k] * v for k in (10, 11)]
        alpha = cutouts[role]
        x = max(0, min(alpha.shape[1] - 1, int(uv[0] * alpha.shape[1])))
        y = max(0, min(alpha.shape[0] - 1, int((1 - uv[1]) * alpha.shape[0])))
        return alpha[y, x] > .5

    def blocked(point, direction):
        # Offline alpha-aware rays prevent transparent card rectangles from darkening the distant impostor.
        for _ in range(len(faces)):
            hit, _, index, _ = tree.ray_cast(point, direction)
            if hit is None:
                return False
            if covered(index, hit):
                return True
            point = hit + direction * .002
        return False

    lit = total = hard = seen = 0
    for index, (face, (role, attributes)) in enumerate(zip(faces, corners)):
        a, b, c = (vertices[i] for i in face)
        normal = (b - a).cross(c - a)
        shown = normal.dot(toward) / 2
        if shown <= 0:
            continue
        normal.normalize()
        leaves = not solid(role) and role not in ('snow', 'canopy-snow-cutout')
        for u, v in ((1 / 3, 1 / 3), (2 / 3, 1 / 6), (1 / 6, 2 / 3), (1 / 6, 1 / 6)):
            point = a + (b - a) * u + (c - a) * v + normal * .01
            # A point behind the plant's nearer parts does not show on the card.
            if not covered(index, point) or blocked(point, toward):
                continue
            seen += shown
            hard += 0 if leaves else shown
            for sun in SUNS:
                weight = shown * max(0, .6 * normal.dot(sun) + .4 if leaves else normal.dot(sun))
                total += weight
                if weight and not blocked(point, sun):
                    lit += weight
    return (lit / total if total else 1), (hard / seen if seen else 0)


def impostor(scene, model, name, images):
    """LOD3: two crossed vertical cards and a horizontal cap through the crown, textured with unlit orthographic
    renders of LOD0 from the front, the side and above. Fixed in the plant's frame, it draws, shadows and picks like
    any mesh; seen from above, only the cap shows. Each face has a back, as the game culls back faces."""
    low, high = bounds(model)
    cap = crown(model, low, high)
    panels = [framing(turn, low, high) for turn in FACES]
    render_faces(scene, model, name, images, panels)
    vertices, indices = [], []
    corners = (((low[0], 0, low[2]), (high[0], 0, low[2]), (high[0], 0, high[2]), (low[0], 0, high[2])),
               ((0, low[1], low[2]), (0, high[1], low[2]), (0, high[1], high[2]), (0, low[1], high[2])),
               ((low[0], low[1], cap), (high[0], low[1], cap), (high[0], high[1], cap), (low[0], high[1], cap)))
    for panel, (quad, turn, (size, centre)) in enumerate(zip(corners, FACES, panels)):
        rotation = turn.to_matrix()
        # Each side is lit like the surfaces its render shows, by their mean normal: not straight up (a sky-facing
        # card outshines a cactus's walls) and constant across the side (a normal that varied across a flat card
        # would darken the half turned from the light while it stays in view). The back shows the same render
        # mirrored, so its normal mirrors through the card.
        toward = rotation.transposed() @ Vector((0, -1, 0))
        front = shown_normal(model, toward)
        # The colour carries how the card takes the sun: the share its plant's own leaves let through, and how much of
        # what it shows is bark, cactus or snow.
        sunlit, hard = lighting(model, toward)
        plane = (Vector(quad[1]) - Vector(quad[0])).cross(Vector(quad[2]) - Vector(quad[0])).normalized()
        for side, normal in enumerate((front, front - 2 * front.dot(plane) * plane)):
            base = len(vertices) // 12
            for point in quad:
                # Each corner maps to where the render placed it, in the camera's right and up axes.
                seen = rotation @ Vector(point)
                u = (panel + .5 + (seen.x - centre.x) / size) / 3
                v = .5 - (seen.z - centre.z) / size
                vertices.extend(round(value, 6) for value in (*point, *normal, sunlit, hard, 1, 1, u, v))
            indices.extend((base, base + 2, base + 1, base, base + 3, base + 2) if side
                           else (base, base + 1, base + 2, base, base + 2, base + 3))
    asset = f'{name}-lod3'
    return {'id': asset,
            'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], 'vertices': vertices,
                        'colorData': True,
                        'parts': [{'id': 'impostor', 'type': 'TRIANGLES', 'indices': indices}]}],
            'nodes': [{'id': asset, 'parts': [{'meshpartid': 'impostor', 'materialid': 'impostor'}]}],
            'materials': [{'id': 'impostor', 'diffuse': [1, 1, 1], 'alphaTest': .5, 'textures': [
                {'id': 'impostor', 'type': 'DIFFUSE', 'filename': f'{IMPOSTORS}/{name}.png',
                 'wrapS': 33071, 'wrapT': 33071}]}]}


def impostors(only=None):
    """Add or refresh LOD3 of every plant with detail levels, keeping its other levels as they are."""
    manifest = json.loads((BOARD / 'manifest.json').read_text())
    old_scene = bpy.context.window.scene
    scene = bpy.data.scenes.new('MegaMek plant impostors')
    bpy.context.window.scene = scene
    images = {}
    try:
        camera = bpy.data.objects.new('Impostor camera', bpy.data.cameras.new('Impostor camera'))
        scene.collection.objects.link(camera)
        camera.data.type = 'ORTHO'
        camera.data.sensor_fit = 'HORIZONTAL'
        camera.data.ortho_scale = 3
        camera.data.clip_end = 1000
        camera.location = (0, -100, 0)
        camera.rotation_euler = (math.pi / 2, 0, 0)
        scene.camera = camera
        scene.render.engine = 'BLENDER_EEVEE'
        scene.render.resolution_x, scene.render.resolution_y = 3 * PANEL, PANEL
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.filter_size = 1.0
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.color_depth = '8'
        # Linear unlit pigment becomes an ordinary sRGB PNG; no tone map, exposure or artistic grade.
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.view_settings.use_curve_mapping = False
        if hasattr(scene, 'eevee'):
            scene.eevee.taa_render_samples = 16
        for name, entry in manifest.items():
            if 'lods' not in entry or only is not None and name not in only:
                continue
            path = BOARD / (name + '.glb')
            levels = {level: read_glb(path, level, linear_colors=True) for level in range(min(3, len(entry['lods'])))}
            for model in levels.values():
                model['materials'] = [material for material in model['materials'] if material['id'] != 'impostor']
            levels[3] = impostor(scene, levels[0], name, images)
            entry['lods'] = entry['lods'][:3] + [{'node': f'{name}-lod3', **counts(levels[3])}]
            write_glb(path, levels=levels, linear_colors=True, extras=levels[0].get('extras'))
            print(name, [lod['triangles'] for lod in entry['lods']], flush=True)
        (BOARD / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    finally:
        bpy.context.window.scene = old_scene
        bpy.data.scenes.remove(scene)
        for image in images.values():
            bpy.data.images.remove(image)


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    stage = arguments[0] if arguments else 'impostors'
    only = set(arguments[1:]) or globals().get('ONLY')
    if stage != 'impostors':
        raise SystemExit('Only the impostors stage is supported; legacy tree generation has been removed.')
    impostors(only)
