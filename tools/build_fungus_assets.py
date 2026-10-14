"""Author the Fungal Crevasse concept-B kit in Blender.

Run with Blender MCP: runpy.run_path(path)['build']().
Only creates its own scenes and files. Source meshes use board units and Z up;
the existing rigid GLB writer handles axis and color conversion. Ground forms
root at zero; cliff forms mount at local Y=0, facing -Y, with Z pointing up.
This is an art kit; it does not change terrain rules or select assets at runtime.
"""
from collections import defaultdict
from math import atan2, cos, pi, sin
from pathlib import Path
import json
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_foliage_assets import Plant, blender_mesh
from glb_geometry import linear, read_glb, write_glb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/models/board/fungus'
REVIEW = ROOT / 'tools/board-models/fungus'
SOURCE = ROOT / 'tools/board-fungus.blend'
ATLAS = ROOT / 'data/models/board/textures/vegetation/fungus/fungus-organic-atlas.png'
COLORS = {
    'stem': (.34, .19, .23), 'skin': (.56, .25, .22),
    'rim': (.83, .45, .23), 'rim-dark': (.68, .31, .20),
    'flesh': (.35, .10, .17), 'gill': (.46, .17, .20),
    'pore': (.20, .075, .13), 'cyan': (.30, .60, .64),
    'cyan-tip': (.55, .76, .75),
    'spore': (.65, .32, .22),
}
TINTS = {'stem':(.72,.58,.65), 'skin':(.96,.85,.86), 'rim':(1,.97,.93),
         'rim-dark':(.87,.82,.80), 'flesh':(.70,.53,.65), 'gill':(.76,.60,.70),
         'pore':(.38,.27,.34), 'spore':(.92,.85,.83)}
FORMS = {
    'cup-chalice': 'tree', 'cup-trumpet': 'tree',
    'cup-frilled': 'tree', 'cup-forked': 'tree',
    'spore-round': 'rounded', 'spore-pear': 'rounded', 'spore-cluster': 'rounded',
    'cliff-shelf': 'cliff', 'cliff-tiered': 'cliff',
    'cliff-cups': 'cliff', 'cliff-mycelium': 'cliff',
    'scatter-cups': 'scatter', 'scatter-buds': 'scatter',
    'scatter-spores': 'scatter', 'scatter-mixed': 'scatter',
}


def tri(g, a, b, c, role):
    if (Vector(b)-Vector(a)).cross(Vector(c)-Vector(a)).length_squared < 1e-18:
        return
    g.face([a, b, c], 0, role)


def quad(g, a, b, c, d, role):
    tri(g, a, b, c, role)
    tri(g, a, c, d, role)


def tube(g, points, radii, role, sides=6):
    """Closed tapered strand; used for roots and the hanging cliff mycelium."""
    rings = []
    for i, p in enumerate(points):
        p = Vector(p)
        direction = Vector(points[min(i+1, len(points)-1)]) - Vector(points[max(0, i-1)])
        direction.normalize()
        side = direction.cross(Vector((.123, .973, .195))).normalized()
        up = direction.cross(side).normalized()
        rings.append([p + radii[i] * (side*cos(j*2*pi/sides) + up*sin(j*2*pi/sides))
                      for j in range(sides)])
    for i in range(len(rings)-1):
        for j in range(sides):
            k = (j+1) % sides
            quad(g, rings[i][j], rings[i][k], rings[i+1][k], rings[i+1][j], role)
    for j in range(1, sides-1):
        tri(g, rings[0][0], rings[0][j+1], rings[0][j], role)
        tri(g, rings[-1][0], rings[-1][j], rings[-1][j+1], role)


def cup(g, center=(0, 0, 0), height=30, radius=10, phase=0, lod=0,
        lean=.09, frill=.035, short=False, tiny=False):
    """One closed body: flared root, bent stem, hollow bowl and rolled lip."""
    count = 8 if tiny else (96, 32, 12)[lod]
    profile = [(.30, 0), (.19, .065), (.13, .26), (.23, .46),
               (.42, .63), (.68, .82), (.93, .97), (1.01, 1.005),
               (1.025, 1.025), (.985, 1.04), (.925, 1.005),
               (.68, .84), (.41, .67), (.14, .54), (.03, .535)]
    if tiny:
        indices = [0, 3, 6, 8, 10, 14]
    elif lod == 1:
        indices = [0, 1, 2, 3, 5, 6, 8, 10, 11, 12, 14]
    elif lod == 2:
        indices = [0, 2, 3, 6, 8, 10, 12, 14]
    else:
        indices = list(range(len(profile)))
    samples = [(float(i), *profile[i]) for i in indices]
    if lod == 0 and not tiny:
        # Interpolated flesh around the rolled lip keeps it rounded in the mesh itself.
        samples = []
        for i in range(len(profile)-1):
            p0, p1, p2, p3 = [Vector(profile[max(0, min(len(profile)-1, k))]) for k in (i-1,i,i+1,i+2)]
            for t in (0, .5):
                p = .5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
                samples.append((i+t, max(.015,p.x), max(0,p.y)))
        samples.append((14.,*profile[-1]))
    rings = []
    for index, r, z in samples:
        ring = []
        for j in range(count):
            angle = j*2*pi/count
            ripple = 1 + .075*sin(3*angle+phase) + .033*cos(5*angle-phase)
            ripple += (.013 if index >= 10 and lod == 0 else 0) * (1 if j % 4 == 1 else -1)
            # Long, shallow external growth folds break the smooth funnel silhouette.
            ripple += .015*sin(17*angle + z*4 + phase) * min(1, z*2)
            wave = frill * sin(5*angle+phase) * min(z, 1)**5
            wave += frill*.4*sin(3*angle-phase) * min(z, 1)**3
            zz = z + wave
            if short:
                zz = z*.7 + max(0, z-.46)*.55
            # Raised folds inside the flesh, visible in profile as well as by color.
            rib = .024 * (1 if j % 4 == 1 else 0) if 10.5 <= index <= 13.5 and lod == 0 else 0
            point = Vector((radius*r*ripple*cos(angle) + height*lean*z*z,
                            radius*r*ripple*sin(angle)*.91 + height*.025*sin(z*pi+phase),
                            height*(zz+rib))) + Vector(center)
            ring.append(point)
        rings.append(ring)
    for i in range(len(rings)-1):
        index = samples[i][0]
        for j in range(count):
            role = ('stem' if index < 3 else 'skin' if index < 6 else
                    ('rim-dark' if j % 7 == 0 else 'rim') if index < 10 else
                    ('gill' if j % 4 in (0, 1) else 'flesh'))
            quad(g, rings[i][j], rings[i][(j+1) % count],
                 rings[i+1][(j+1) % count], rings[i+1][j], role)
    for ring, reverse, role in ((rings[0], True, 'stem'), (rings[-1], False, 'flesh')):
        for j in range(1, count-1):
            points = [ring[0], ring[j], ring[j+1]]
            tri(g, *reversed(points), role) if reverse else tri(g, *points, role)
    if lod < 2 and not short:
        for j in range(3):
            angle = phase + j*2*pi/3
            c = Vector(center)
            tube(g, [c + Vector((cos(angle)*radius*.53, sin(angle)*radius*.53, height*.008)),
                     c + Vector((cos(angle)*radius*.22, sin(angle)*radius*.22, height*.10)),
                     c + Vector((height*lean*.06, 0, height*.30))],
                 [radius*.045, radius*.085, radius*.025], 'skin', 5 if lod == 0 else 3)


def spore(g, center, radii, phase=0, lod=0, pear=False):
    """Rounded reticulate shell with real recessed pore openings, not a wire cage."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2 if lod == 0 else 1, radius=1)
    for v in bm.verts:
        p = v.co.copy()
        v.co = (p + Vector((sin(p.y*9+phase), sin(p.z*8-phase), sin(p.x*7+phase)))*.045).normalized()
    bm.normal_update()
    def shape(v, thickness=1):
        x, y, z = v
        taper = 1 - (.22*(z+1)*.5 if pear else 0)
        wobble = 1 + (.07*sin(4*atan2(y, x)+phase) + .035*sin(z*8+phase))*(1-z*z)
        return Vector((x*radii[0]*taper*wobble*thickness,
                       y*radii[1]*taper*wobble*thickness,
                       z*radii[2]*thickness)) + Vector(center)
    for vertex in bm.verts:
        normal = vertex.co.normalized()
        side = normal.cross(Vector((.11, .96, .21))).normalized()
        up = normal.cross(side)
        corners = [face.calc_center_median().normalized() for face in vertex.link_faces]
        corners.sort(key=lambda p: atan2(p.dot(up), p.dot(side)))
        if lod == 0:
            corners = [(p.lerp(corners[(j+1) % len(corners)], t)).normalized()
                       for j,p in enumerate(corners) for t in (0,.333333,.666667)]
        middle = sum(corners, Vector()).normalized()
        # A broad raised network and bevel converge into each dark pore.
        aperture = .62 + .14*(.5+.5*sin(normal.x*8+normal.z*11+phase))
        holes = [(p*aperture + middle*(1-aperture)).normalized() for p in corners]
        if lod == 0:
            holes = [(p*.50 + holes[j-1]*.25 + holes[(j+1) % len(holes)]*.25).normalized()
                     for j,p in enumerate(holes)]
        inner = [(p*(aperture-.07) + middle*(1.07-aperture)).normalized() for p in corners]
        for j in range(len(corners)):
            k = (j+1) % len(corners)
            quad(g, shape(corners[j]), shape(corners[k]), shape(holes[k], 1.018),
                 shape(holes[j], 1.018), 'spore')
            if lod < 2:
                quad(g, shape(holes[j], 1.018), shape(holes[k], 1.018),
                     shape(inner[k], .84), shape(inner[j], .84), 'spore')
                tri(g, shape(inner[j], .84), shape(inner[k], .84), shape(middle, .74), 'pore')
            else:
                tri(g, shape(holes[j], 1.018), shape(holes[k], 1.018), shape(middle, .78), 'pore')
    bm.free()


def shelf_point(center, width, reach, phase, r, z, a):
    """Shared bracket surface for the shell and the attached mycelium roots."""
    scallop = 1 + .075*sin(a*7+phase) + .025*cos(a*13+phase) + .013*sin(a*23)
    return Vector((cos(a)*width*.5*r*scallop,
                   -sin(a)*reach*r*scallop + .12,
                   z*reach*.60 + r*r*.16*sin(a*5+phase))) + Vector(center)


def shelf(g, center, width=9, reach=5, phase=0, lod=0):
    """Thick semicircular bracket; the straight rear edge embeds into a cliff."""
    n = (48, 16, 8)[lod]
    profile = [(0, -.28), (.40, -.24), (.77, -.18), (1, -.04),
               (1.02, .13), (.96, .25), (.72, .49), (.35, .57), (0, .37)]
    if lod == 2:
        profile = [profile[j] for j in (0, 2, 3, 5, 6, 8)]
    rings = []
    for r, z in profile:
        ring = []
        for j in range(n+1):
            a = pi*j/n
            ring.append(shelf_point(center, width, reach, phase, r, z, a))
        rings.append(ring)
    for i in range(len(rings)-1):
        for j in range(n):
            role = ('gill' if j % 2 else 'flesh') if i < 2 else (
                   'rim' if i in (3, 4) else 'skin' if i > 5 else 'rim-dark')
            quad(g, rings[i][j], rings[i][j+1], rings[i+1][j+1], rings[i+1][j], role)
    # Seal both straight mounting sides (r=0 rings are shared along the middle).
    for edge in (0, n):
        strip = [ring[edge] for ring in rings]
        for j in range(1, len(strip)-1):
            tri(g, strip[0], strip[j], strip[j+1], 'stem')


def shape(name, lod):
    g = Plant()
    if name == 'cup-chalice':
        cup(g, height=30, radius=10.8, phase=.4, lod=lod)
    elif name == 'cup-trumpet':
        cup(g, height=30, radius=8.7, phase=2.1, lod=lod, lean=-.13, frill=.025)
        if lod < 2:
            cup(g, (2.8, -.8, .1), height=11, radius=3.5, phase=1.5, lod=min(2, lod+1), short=True)
    elif name == 'cup-frilled':
        cup(g, height=24, radius=12.7, phase=3.8, lod=lod, lean=.025, frill=.075)
    elif name == 'cup-forked':
        cup(g, (-2.5, 0, 0), height=30, radius=8.4, phase=.7, lod=lod, lean=-.08)
        cup(g, (2.1, 1.3, .1), height=21.8, radius=6.9, phase=3.1, lod=min(lod+1, 2), lean=.20)
    elif name == 'spore-round':
        spore(g, (0, 0, 8.2), (8.5, 7.5, 8.2), lod=lod)
    elif name == 'spore-pear':
        spore(g, (1, 0, 10), (8.9, 8, 10), phase=2, lod=lod, pear=True)
    elif name == 'spore-cluster':
        for c, r, p in [((0, 1.2, 7), (7, 6.7, 7), .4),
                        ((-6, -2, 4.6), (4.6, 4.3, 4.6), 1.6),
                        ((5.5, -2.5, 3.9), (3.9, 3.7, 3.9), 3)]:
            spore(g, c, r, p, lod=min(2, lod+(0 if p == .4 else 1)))
    elif name == 'cliff-shelf':
        shelf(g, (0, 0, 0), width=12, reach=6.2, phase=.4, lod=lod)
    elif name == 'cliff-tiered':
        for c, w, r, p in [((-1.5, 0, 3.8), 9, 5, 1), ((2, 0, .2), 11, 5.5, 2),
                           ((-2.3, 0, -3.3), 7.5, 4.2, 4)]:
            shelf(g, c, w, r, p, lod)
    elif name == 'cliff-cups':
        # Side-emerging bent stems remain connected to their wall roots.
        for j in range(3 if lod < 2 else 2):
            x, z = (j-1)*3.6, (1-j)*2.4
            base = Vector((x, -2.1, z))
            tube(g, [(x, .16, z-.6), (x, -1.3, z-.6), base],
                 [.48, .43, .55], 'stem', (8, 5, 4)[lod])
            cup(g, base, height=4.7+j*.6, radius=2.9, phase=j*1.7,
                lod=min(lod+1, 2), lean=.045, short=True)
    elif name == 'cliff-mycelium':
        center, width, reach, phase = (0, 0, -.5), 7.7, 2.9, 2.2
        shelf(g, center, width, reach, phase, lod=min(lod+1, 2))
        # The same curved gill surface owns every root. Lower LODs retain a subset of these exact roots.
        for i in range(0, 17, (1, 2, 4)[lod]):
            a = pi*(.12 + .76*i/16)
            root = shelf_point(center, width, reach, phase, .72, -.19, a)
            root.z += .13  # Start inside the flesh, never above it or beside its outline.
            drop = 4.8 + 3.4*(.5+.5*sin(i*2.3))
            points = [root, root+Vector((.22*sin(i), -.12, -drop*.25)),
                      root+Vector((.4*sin(i+1), -.28, -drop*.65)),
                      root+Vector((.55*sin(i+2), -.20, -drop))]
            tube(g, points, [.14, .13, .075, .018], 'cyan-tip' if i % 3 else 'cyan',
                 (5, 4, 3)[lod])
            if lod == 0 and i % 2 == 0:
                start = Vector(points[1])
                tube(g, [start, start+Vector((.55, -.10, -.5)), start+Vector((.8, -.18, -1.6))],
                     [.10, .075, .015], 'cyan', 4)
    elif name == 'scatter-cups':
        for i, (x, y, h) in enumerate([(-.55, 0, 1.7), (.5, .18, 2.4), (.05, -.55, 1.1)]):
            cup(g, (x, y, 0), h, h*.40, i*1.8, lod=2, short=True, tiny=True)
    elif name == 'scatter-buds':
        for i in range(5):
            a = i*2.39996
            cup(g, (cos(a)*.8, sin(a)*.7, 0), .7+i*.18, .35+i*.055,
                i*1.2, lod=2, short=True, tiny=True)
    elif name == 'scatter-spores':
        spore(g, (-.55, .10, .85), (.83, .78, .85), phase=.6, lod=2)
        spore(g, (.65, -.13, .50), (.50, .48, .50), phase=2.8, lod=2)
    elif name == 'scatter-mixed':
        cup(g, (-.4, .2, 0), 2.1, .71, .8, lod=2, short=True, tiny=True)
        cup(g, (.5, -.28, 0), 1.1, .43, 3, lod=2, short=True, tiny=True)
        spore(g, (.7, .6, .53), (.52, .48, .53), lod=2)
    else:
        raise ValueError(name)
    return g


def mesh_model(obj):
    """Export the actual Blender UVs, corner normals and shared material atlas."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    vertices, shared, parts = [], {}, defaultdict(list)
    for face in mesh.loop_triangles:
        role = mesh.materials[face.material_index]['role']
        part = 'mycelium' if role.startswith('cyan') else 'fungus'
        color = COLORS[role] if part == 'mycelium' else TINTS[role]
        for loop in face.loops:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co
            n = mesh.corner_normals[loop].vector
            uv = mesh.uv_layers.active.data[loop].uv
            vertex = tuple(round(v, 7) for v in (*p, *n, *color, 1, uv.x, 1-uv.y))
            if vertex not in shared:
                shared[vertex] = len(vertices)//12
                vertices.extend(vertex)
            parts[part].append(shared[vertex])
    texture = {'id':'fungus-atlas', 'type':'DIFFUSE',
               'filename':'../textures/vegetation/fungus/'+ATLAS.name, 'wrapS':33071,'wrapT':33071}
    return {'id': obj.name, 'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'],
             'vertices': vertices, 'parts': [{'id':part,'type':'TRIANGLES','indices':indices}
                                            for part,indices in parts.items()]}],
            'materials': [{'id':part,'diffuse':[1,1,1],
                           **({'textures':[texture]} if part == 'fungus' else {})} for part in parts],
            'nodes': [{'id':obj.name,'parts':[{'meshpartid':part,'materialid':part} for part in parts]}]}


def apply_uvs(obj):
    mesh = obj.data
    low = min(v.co.z for v in mesh.vertices)
    high = max(v.co.z for v in mesh.vertices)
    for face in mesh.polygons:
        role = mesh.materials[face.material_index]['role']
        panel = 3 if role == 'spore' else 2 if role in ('flesh','gill','pore') else 1 if role.startswith('rim') else 0
        points = [mesh.vertices[mesh.loops[loop].vertex_index].co for loop in face.loop_indices]
        coords = []
        for p in points:
            if obj['family'] == 'cliff' or role == 'spore' or 'spore' in obj.name:
                dominant = max(range(3), key=lambda k:abs(face.normal[k]))
                axes = (0,1) if dominant == 2 else (0,2) if dominant == 1 else (1,2)
                # Small per-face patches avoid crossing an atlas boundary at a wrap seam.
                coords.append((p[axes[0]]/19+.5, p[axes[1]]/19+.5))
            else:
                u = atan2(p.y, p.x)/(2*pi)+.5
                v = (p.z-low)/max(1e-6,high-low)
                if role in ('flesh','gill'):
                    v = (v-.47)*1.85
                coords.append((u,v))
        for axis in range(2):
            values = [p[axis] for p in coords]
            base = int(min(values)//1)
            adjusted = [v-base for v in values]
            if axis == 0 and obj['family'] != 'cliff' and max(values)-min(values) > .5:
                adjusted = [1 if v < .5 else v for v in values]
            coords = [tuple(max(.0,min(1.,adjusted[i])) if k == axis else uv[k] for k in range(2))
                      for i,uv in enumerate(coords)]
        for loop, uv in zip(face.loop_indices, coords):
            mesh.uv_layers.active.data[loop].uv = (panel % 2*.5+.014+uv[0]*.472,
                                                   (1-panel//2)*.5+.014+uv[1]*.472)


def materials():
    mats = {}
    atlas = bpy.data.images.load(str(ATLAS), check_existing=True)
    atlas.pack()
    for role, color in COLORS.items():
        mat = bpy.data.materials.new('Fungus B / '+role)
        mat['role'] = role
        mat.diffuse_color = (*[linear(c) for c in color], 1)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = mat.diffuse_color
        shader.inputs['Roughness'].default_value = .87
        if role in TINTS:
            texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texture.image = atlas
            texture.extension = 'EXTEND'
            tint = mat.node_tree.nodes.new('ShaderNodeMixRGB')
            tint.blend_type = 'MULTIPLY'
            tint.inputs[0].default_value = 1
            tint.inputs[2].default_value = (*[linear(c) for c in TINTS[role]],1)
            mat.node_tree.links.new(texture.outputs['Color'],tint.inputs[1])
            mat.node_tree.links.new(tint.outputs[0],shader.inputs['Base Color'])
        mats[role] = mat
    return mats


def solid_material(name, color, roughness=.85):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*[linear(c) for c in color], 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = roughness
    return mat


def box(scene, name, location, scale, mat):
    # Standard primitive creation uses Blender's operator, in the active new scene.
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def text_object(scene, body, location, size, mat, rotation=(0, 0, 0)):
    curve = bpy.data.curves.new(body, 'FONT')
    curve.body = body
    curve.size = size
    curve.align_x = 'CENTER'
    curve.extrude = 0
    obj = bpy.data.objects.new(body, curve)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    curve.materials.append(mat)
    return obj


def setup_review(scene, assets):
    """Display copies use transforms; authoring meshes and GLBs keep their roots."""
    stage = bpy.data.collections.new('Display only / plinths and labels')
    scene.collection.children.link(stage)
    slate = solid_material('Display / violet slate', (.18, .18, .235))
    stone = solid_material('Display / cliff rock', (.28, .245, .32))
    ink = solid_material('Display / pale lettering', (.72, .78, .79))
    floor = solid_material('Display / background', (.10, .12, .16))
    # Four strips, seen from above and the front. Each has its own review camera too.
    rows = {'tree': 3, 'rounded': 2, 'cliff': 1, 'scatter': 0}
    counter = defaultdict(int)
    positions = {}
    for name, family in FORMS.items():
        col = counter[family]
        counter[family] += 1
        x, y = (col-1.5)*36, rows[family]*49
        positions[name] = (x, y)
        obj = assets[name][0]
        factor = 1 if family == 'tree' else 1.25 if family == 'rounded' else 1.9 if family == 'cliff' else 7
        obj.location = (x, y, 1.2 + (17 if family == 'cliff' else 0))
        obj.scale = (factor,)*3
        box(scene, 'Display / '+name+' plinth', (x, y, 0), (32, 31, 2), slate)
        text_object(scene, name.replace('cliff-', '').replace('scatter-', '').upper(),
                    (x, y-13.8, 1.06), 1.65, ink)
        if family == 'cliff':
            box(scene, 'Display / '+name+' wall', (x, y+1.65, 12), (29, 3, 24), stone)
    box(scene, 'Display / floor', (0, 78, -1.5), (500, 600, 1), floor)
    # Title and row labels are flat on the display, facing the same camera as models.
    text_object(scene, 'FUNGAL CREVASSE / FORM LIBRARY B', (0, 207, 0), 3.2, ink)
    for family, row in rows.items():
        label = {'tree':'CUP / TREE FORMS', 'rounded':'ROUNDED SPORE FORMS',
                 'cliff':'CLIFF GROWTH / ATTACHMENT PLANE Y=0',
                 'scatter':'GROUND SCATTER / ENLARGED FOR REVIEW'}[family]
        text_object(scene, label, (0, row*49-21, .2), 2.0, ink)
    scene.world = bpy.data.worlds.new('Fungus B / studio world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.19, .22, .28, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6
    for name, position, power, size, color in [
        ('Key', (-60, -10, 135), 230000, 85, (1, .86, .75)),
        ('Fill', (65, 110, 110), 170000, 100, (.72, .84, 1)),
        ('Rim', (-40, 215, 95), 200000, 75, (1, .62, .37))]:
        data = bpy.data.lights.new('Fungus B / '+name, 'AREA')
        data.energy, data.shape, data.size, data.color = power, 'DISK', size, color
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0, 85, 0))-obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras = {}
    def camera(name, target, offset, ortho, width, height):
        data = bpy.data.cameras.new(name)
        data.type = 'ORTHO'
        data.ortho_scale = ortho
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = Vector(target)+Vector(offset)
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()
        obj['resolution'] = [width, height]
        cameras[name] = obj
        return obj
    scene.camera = camera('Overview', (0, 90, 6), (8, -175, 205), 205, 1600, 1800)
    for family, row in rows.items():
        offset = (15,-130,55) if family == 'cliff' else (8,-110,100)
        camera(family.title()+' detail', (0, row*49, 12 if family == 'cliff' else 10),
               offset, 151, 1800, 680)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    for obj in list(scene.collection.objects):
        if obj.name.startswith('Display /') or obj.type == 'FONT':
            scene.collection.objects.unlink(obj)
            stage.objects.link(obj)
    return cameras


def build():
    if bpy.context.mode != 'OBJECT':
        raise RuntimeError('Switch the existing scene to Object mode before building the kit.')
    scene = bpy.data.scenes.new('Fungal Crevasse / B shapes')
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'NONE'
    mats = materials()
    assets, report = {}, {}
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    lod_collections = []
    for level in range(3):
        collection = bpy.data.collections.new('Fungus B / LOD'+str(level))
        scene.collection.children.link(collection)
        collection.hide_render = level != 0
        collection.hide_viewport = level != 0
        lod_collections.append(collection)
    for name, family in FORMS.items():
        objects = []
        for lod in range(1 if family == 'scatter' else 3):
            obj = blender_mesh(scene, name+'-mesh'+str(lod), shape(name, lod), mats)
            # Correct orientation once at the mesh boundary, keeping closed cups/cell walls.
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
            invalid = [f for f in bm.faces if f.calc_area() < 1e-10]
            if invalid:
                bmesh.ops.delete(bm, geom=invalid, context='FACES_ONLY')
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
            bm.free()
            for face in obj.data.polygons:
                face.use_smooth = True
            obj.data.update()
            scene.collection.objects.unlink(obj)
            lod_collections[lod].objects.link(obj)
            obj['family'], obj['lod'] = family, lod
            obj['attachment'] = 'Y=0, outward -Y, up Z' if family == 'cliff' else 'ground root Z=0'
            objects.append(obj)
        # One common normalization for every LOD keeps all levels registered.
        if family in ('tree', 'rounded', 'scatter'):
            low = min(v.co.z for v in objects[0].data.vertices)
            high = max(v.co.z for v in objects[0].data.vertices)
            target = 30 if family == 'tree' else 18 if family == 'rounded' else 2.4
            scale = target/(high-low)
            for obj in objects:
                lod_low = min(v.co.z for v in obj.data.vertices)
                for vertex in obj.data.vertices:
                    vertex.co.z -= lod_low
                    vertex.co *= scale
                obj.data.update()
        for obj in objects:
            apply_uvs(obj)
        levels = {lod: mesh_model(obj) for lod, obj in enumerate(objects)}
        write_glb(OUT / (name+'.glb'), levels=levels)
        counts = [sum(len(p['indices'])//3 for m in data['meshes'] for p in m['parts']) for data in levels.values()]
        bounds = [[round(fn(v.co[k] for v in objects[0].data.vertices), 5) for k in range(3)] for fn in (min, max)]
        report[name] = {'family':family, 'lod_triangles':counts, 'bounds_z_up':bounds,
                        'attachment':objects[0]['attachment'], 'glb':str((OUT/(name+'.glb')).relative_to(ROOT)),
                        'materials':len(levels[0]['materials']), 'textures':1,
                        'atlas':'../textures/vegetation/fungus/'+ATLAS.name}
        # Offline round trip checks the same writer/reader boundary used by other board kits.
        for lod, count in enumerate(counts):
            imported = read_glb(OUT / (name+'.glb'), lod)
            actual = sum(len(p['indices'])//3 for m in imported['meshes'] for p in m['parts'])
            assert actual == count and actual > 0, (name, lod, actual, count)
        assets[name] = objects
    cameras = setup_review(scene, assets)
    bpy.context.view_layer.update()
    report_path = REVIEW/'mesh-report.json'
    report_path.write_text(json.dumps({'status':'fungus theme GLB kit; runtime uses cover, cliff and scatter families',
        'source':str(SOURCE), 'units':'board units, Z up; one hex 84 x 72; level height 18',
        'generator':'tools/build_fungus_assets.py', 'assets':report}, indent=2)+'\n')
    # Save this independent scene, including its dependencies, without copying unrelated scenes.
    bpy.data.libraries.write(str(SOURCE), {scene}, path_remap='RELATIVE_ALL', fake_user=True, compress=True)
    return {'scene':scene.name, 'source':str(SOURCE), 'assets':report, 'cameras':list(cameras)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
