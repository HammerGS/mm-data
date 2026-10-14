"""Build the two rough-terrain variants with the shared rigid GLB writer.

Run with Python; no Blender or image generation is required. Coordinates are
Z-up board units, with footprints inside BoardFeatures' clearance radii:
three units for standing stumps, six for teeth and fallen wood, before placement scaling.
Existing board concrete and bark textures are reused.
"""
from collections import defaultdict
import json
from math import cos, sin, pi, hypot
from pathlib import Path

from glb_geometry import write_glb
from unit_model_geometry import Geometry, cross, normal, sub

OUT = Path(__file__).resolve().parents[1] / 'data/models/board/rough'
MATERIALS = {
    'concrete': ((.86, .84, .78), 'scenery/tunnel-concrete.png'),
    'bark': ((.64, .53, .42), 'vegetation/bark.png'),
    'char': ((.26, .25, .23), 'vegetation/bark.png'),
    'wood': ((.65, .48, .29), None),
    'heart': ((.40, .29, .17), None),
}


def export(name, geometry):
    vertices, shared, parts = [], {}, defaultdict(list)
    for tri, _, role in geometry.faces:
        n = normal(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])))
        axes = sorted(range(3), key=lambda axis: abs(n[axis]))[:2]
        for p in tri:
            assert hypot(p[0], p[1]) <= (3 if name == 'charred-stump' else 6), (name, 'exceeds route clearance', p)
            assert p[2] >= -1e-6, (name, 'below base', p)
            # Trunk grain follows its length; upright stumps use the vertical bark direction.
            uv = (p[axes[0]] / 4, p[axes[1]] / 4)
            if name in ('felled-trunk', 'fallen-stump') and role in ('bark', 'char'):
                uv = ((p[1] if abs(n[2]) > abs(n[1]) else p[2]) / 4, p[0] / 4)
            vertex = tuple(round(v, 7) for v in (*p, *n, 1, 1, 1, 1, *uv))
            if vertex not in shared:
                shared[vertex] = len(vertices) // 12
                vertices.extend(vertex)
            parts[role].append(shared[vertex])
    materials = []
    for role in parts:
        color, texture = MATERIALS[role]
        mat = {'id': role, 'diffuse': list(color)}
        if texture:
            mat['textures'] = [{'id': role, 'type': 'DIFFUSE', 'filename': '../textures/' + texture}]
        materials.append(mat)
    model = {'id': name, 'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'],
             'vertices': vertices, 'parts': [{'id': role, 'type': 'TRIANGLES', 'indices': indices}
                                           for role, indices in parts.items()]}],
             'materials': materials,
             'nodes': [{'id': name, 'parts': [{'meshpartid': role, 'materialid': role} for role in parts]}]}
    OUT.mkdir(parents=True, exist_ok=True)
    write_glb(OUT / (name + '.glb'), levels={0: model})
    print(f'{name}: {len(geometry.faces)} triangles')
    return {'triangles': len(geometry.faces), 'vertices': len(vertices) // 12}


def tooth():
    g = Geometry()
    # Square, broad concrete foot and flat narrow crown, with small bevels on the cast edges.
    g.box((0, 0, 2.3), (6.4, 6.4, 4.6), group='root', material='concrete', bevel=.08, taper=.30)
    return g


def trunk():
    g = Geometry()
    # Broken trunk with taper, a splintered tip and several severed branches; no upright leafy canopy.
    g.beam((-5, 0, 1), (4.8, .18, .68), 1.9, group='root', material='bark', sides=9, taper=.46)
    g.beam((-1.8, .15, 1.1), (-.1, 2.8, .85), .65, group='root', material='char', sides=6, taper=.38)
    g.beam((1.4, 0, .9), (2.5, -2.3, .55), .50, group='root', material='char', sides=5, taper=.32)
    g.beam((-.5, 0, 1.1), (.3, -.35, 2.15), .48, group='root', material='char', sides=5, taper=.45)
    # Exposed end grain makes the fallen cylinder read as wood rather than another rock.
    g.faces = [(tri, group, 'wood' if abs(normal(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])))[0]) > .96
                else role) for tri, group, role in g.faces]
    # A smaller end-grain inset suggests the heartwood without a new texture.
    disk = [(-5.004, .50 * cos(i * 2*pi/9), 1 + .50 * sin(i * 2*pi/9)) for i in range(9)]
    g.face(list(reversed(disk)), group='root', material='heart')
    return g


def stump():
    g = Geometry()
    n = 9
    low, top, inner = [], [], []
    for i in range(n):
        angle = i * 2*pi/n
        radius = 1.3 + (i % 3) * .12
        z = 3.5 + (i * 7 % 5) * .25
        low.append((radius * 1.2 * cos(angle), radius * 1.2 * sin(angle), 0))
        top.append((radius * .72 * cos(angle), radius * .72 * sin(angle), z))
        inner.append((radius * .39 * cos(angle), radius * .39 * sin(angle), z - .5))
    g.face(list(reversed(low)), group='root', material='char')
    for i in range(n):
        j = (i + 1) % n
        g.face([low[i], low[j], top[j], top[i]], group='root', material='char')
        g.face([top[i], top[j], inner[j], inner[i]], group='root', material='wood')
        g.face([inner[i], inner[j], (0, 0, 2.6)], group='root', material='char')
    for angle in (0, 1.4, 2.8, 4.3, 5.4):
        # Charred root flares end in the ground, using the existing tapered prism helper.
        root = Geometry()
        root.prism([(-.4, -.35), (2.9, -.16), (2.9, .16), (-.4, .35)], 0, .95,
                   group='root', material='char', taper=.10)
        g.extend(root, angle=angle, group='root')
    return g


def fallen_stump():
    g = stump()
    # Reuse the broken rim, bark and roots at the standing trunk's board-scale proportions.
    # Tip the broken end slightly down so it rests near the ground with the upturned roots.
    c, s = cos(pi / 15), sin(pi / 15)
    g.faces = [(tuple((p[2] * 2.2 * c - p[0] * s, p[1], -p[2] * 2.2 * s - p[0] * c)
                     for p in tri), group, role) for tri, group, role in g.faces]
    points = [p for tri, _, _ in g.faces for p in tri]
    centre = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    floor = min(p[2] for p in points)
    g.faces = [(tuple((p[0] - centre, p[1], p[2] - floor) for p in tri), group, role)
               for tri, group, role in g.faces]
    return g


if __name__ == '__main__':
    manifest_file = OUT.parent / 'manifest.json'
    manifest = json.loads(manifest_file.read_text())
    for name, geometry in [('dragon-tooth', tooth()), ('felled-trunk', trunk()), ('charred-stump', stump()),
                           ('fallen-stump', fallen_stump())]:
        manifest['rough/' + name] = export(name, geometry)
    manifest_file.write_text(json.dumps(manifest, indent=2) + '\n')
