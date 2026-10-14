"""Bake the shared pier kits. Pure Python; uses the terrain kit GLB writer and also runs inside Blender.

One hammerhead pier stands under each deck joint, on the hex edge two consecutive bridge hexes share, never at a
hex centre. One generator, one profile per kit (`--profile`): `bridge` (bridges/bridge-pier.glb, the default) and
`maglev` (bridges/maglev-pier.glb, the thinner pillar under an elevated maglev beam, whose underside stands in for
the deck's; its part names start `maglev-pier` instead of `bridge-pier`). The sizes below are the bridge profile's. 
Coordinates are board units at hex scale 1 (84 = 30 metres; a deck slab is 18 wide and 1.5 thick).
The origin is the midpoint of the shared hex edge: X runs along that edge (across the deck), Y along the deck axis
towards the neighbour hex, Z is up. The pier is mirror-symmetric in X and Y.

Three parts, each a root mesh node with two named levels, in the kit convention of bridge-terminal.glb:
- cap, `bridge-pier-cap-lodN`: fixed size. Z = 0 is the drawn deck underside; the top is 0.75 up, inside the slab,
  and the tapered soffit ends at Z = -6, the width of the shaft.
- shaft, `bridge-pier-shaft-lodN`: unit height, Z 0..1, no end faces. The renderer stretches it between the
  footing and the cap (overlapping both), so only its length changes; the section never distorts.
- footing, `bridge-pier-footing-lodN`: fixed size. Z = 0 is the floor (ground or bed); a 1 unit lip shows above
  it and 6 units are buried. It reaches 6.5 into each hex, so every hex centre stays 29.5 clear.
UVs and normals follow GpuTerrain.bridgeFace (flat faces, one world-space concrete repeat of 84/5), the rule the
runtime reapplies after placing and stretching the parts. Like the terminal kit, the pier stays out of
manifest.json, whose entries load as LOD-grouped models.
"""
import argparse
import math
import os
from pathlib import Path

from glb_geometry import read_glb, write_glb


REPEAT = 84 / 5
CAP_TOP = .75
# Half extents (X across the deck, Y along it) and heights per kit. The maglev pillar carries the 4 unit wide beam:
# cap 6 x 4, shaft 3.2 square, footing 7 x 7, about a third of the bridge pier across.
PROFILES = {
    'bridge': {'name': 'bridge-pier', 'cap': (8.5, 4.5), 'cap_band': -2, 'cap_soffit': -6,
               'shaft': (5.5, 4), 'shaft_chamfer': 1.5,
               'footing': (8, 6.5), 'footing_lip': 1, 'footing_depth': -6, 'footing_chamfer': .75},
    'maglev': {'name': 'maglev-pier', 'cap': (3, 2), 'cap_band': -1, 'cap_soffit': -2.5,
               'shaft': (1.6, 1.6), 'shaft_chamfer': .5,
               'footing': (3.5, 3.5), 'footing_lip': .6, 'footing_depth': -4, 'footing_chamfer': .3},
}
# Triangles per part at lod0 and lod1. The cap keeps its shape: it is mostly hidden under the deck anyway.
TRIANGLES = {'cap': (20, 20), 'shaft': (16, 8), 'footing': (20, 12)}


def bounds(p):
    cap, shaft, footing = p['cap'], p['shaft'], p['footing']
    return {'cap': ((-cap[0], -cap[1], p['cap_soffit']), (cap[0], cap[1], CAP_TOP)),
            'shaft': ((-shaft[0], -shaft[1], 0), (shaft[0], shaft[1], 1)),
            'footing': ((-footing[0], -footing[1], p['footing_depth']), (footing[0], footing[1], p['footing_lip']))}


def rect(x, y, chamfer=0):
    """A counter-clockwise outline seen from above, optionally with chamfered corners."""
    if not chamfer:
        return [(-x, -y), (x, -y), (x, y), (-x, y)]
    c = chamfer
    return [(-x + c, -y), (x - c, -y), (x, -y + c), (x, y - c), (x - c, y), (-x + c, y), (-x, y - c), (-x, -y + c)]


def band(faces, upper, lower, high, low):
    """The walls between two outlines with the same corner count, facing outward."""
    for i in range(len(upper)):
        j = (i + 1) % len(upper)
        faces.append([(*lower[i], low), (*lower[j], low), (*upper[j], high), (*upper[i], high)])


def lid(faces, outline, z, up):
    faces.append([(x, y, z) for x, y in (outline if up else outline[::-1])])


def parts(p, level):
    """The three parts' faces at one level, as convex polygons wound counter-clockwise seen from outside."""
    cap, shaft, footing = [], [], []
    CAP, SHAFT, FOOTING = p['cap'], p['shaft'], p['footing']
    LIP, DEPTH, CHAMFER = p['footing_lip'], p['footing_depth'], p['footing_chamfer']
    lid(cap, rect(*CAP), CAP_TOP, True)
    band(cap, rect(*CAP), rect(*CAP), CAP_TOP, p['cap_band'])
    band(cap, rect(*CAP), rect(SHAFT[0], CAP[1]), p['cap_band'], p['cap_soffit'])
    lid(cap, rect(SHAFT[0], CAP[1]), p['cap_soffit'], False)
    section = rect(*SHAFT, p['shaft_chamfer'] if level == 0 else 0)
    band(shaft, section, section, 1, 0)
    if level == 0:
        inset = rect(FOOTING[0] - CHAMFER, FOOTING[1] - CHAMFER)
        lid(footing, inset, LIP, True)
        band(footing, inset, rect(*FOOTING), LIP, LIP - CHAMFER)
        band(footing, rect(*FOOTING), rect(*FOOTING), LIP - CHAMFER, DEPTH)
    else:
        lid(footing, rect(*FOOTING), LIP, True)
        band(footing, rect(*FOOTING), rect(*FOOTING), LIP, DEPTH)
    lid(footing, rect(*FOOTING), DEPTH, False)
    return {'cap': cap, 'shaft': shaft, 'footing': footing}


def normal_of(a, b, c):
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.sqrt(sum(x * x for x in n))
    return [x / length for x in n] if length > 1e-9 else None


def uv(p, n):
    """GpuTerrain.bridgeFace: tops map (x, -y), walls (along the wall, -z), at one world-space repeat."""
    u = p[0] if abs(n[2]) > .5 or abs(n[0]) <= .5 else p[1]
    v = -p[1] if abs(n[2]) > .5 else -p[2]
    return u / REPEAT, v / REPEAT


def model(root, profile):
    packed, unique, mesh_parts, nodes = [], {}, [], []
    for level in (0, 1):
        for part, faces in parts(profile, level).items():
            name = f'{profile["name"]}-{part}-lod{level}'
            indices = []
            for face in faces:
                n = normal_of(*face[:3])
                for k in range(1, len(face) - 1):
                    for p in (face[0], face[k], face[k + 1]):
                        value = tuple(round(v, 6) for v in (*p, *n, 1, 1, 1, 1, *uv(p, n)))
                        if value not in unique:
                            unique[value] = len(packed) // 12
                            packed.extend(value)
                        indices.append(unique[value])
            mesh_parts.append({'id': name, 'type': 'TRIANGLES', 'indices': indices})
            nodes.append({'id': name, 'parts': [{'meshpartid': name, 'materialid': 'bridge-structure'}]})
    out = root / 'data/models/board/bridges'
    texture = os.path.relpath(root / 'data/models/board/textures/terrain/surfaces/concrete.png', out).replace('\\', '/')
    return {'id': profile['name'], 'version': [0, 1], 'materials': [{'id': 'bridge-structure', 'diffuse': [1, 1, 1], 'textures': [
        {'id': 'bridge-structure', 'filename': texture, 'type': 'DIFFUSE', 'wrapS': 10497, 'wrapT': 10497}]}],
        'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], 'vertices': packed, 'parts': mesh_parts}],
        'nodes': nodes}


def validate(path, p):
    NAME = p['name']
    mesh = read_glb(path)
    names = {f'{NAME}-{part}-lod{level}' for part in TRIANGLES for level in (0, 1)}
    assert {node['id'] for node in mesh['nodes']} == names, 'Expected the cap, shaft and footing at two levels'
    assert all(not node['children'] and len(node['parts']) == 1 for node in mesh['nodes']), 'Kit shapes are root meshes'
    assert [m['id'] for m in mesh['materials']] == ['bridge-structure'], 'One concrete material'
    texture = mesh['materials'][0]['textures'][0]
    assert (path.parent / texture['filename']).resolve() == (path.parents[1] / 'textures/terrain/surfaces/concrete.png').resolve()
    assert texture['wrapS'] == texture['wrapT'] == 10497, 'Concrete repeats'
    geometry = mesh['meshes'][0]
    vertices = geometry['vertices']
    triangles = {}
    for part in geometry['parts']:
        kind, level = part['id'][len(NAME) + 1:].rsplit('-lod', 1)
        indices = part['indices']
        count = len(indices) // 3
        assert count == TRIANGLES[kind][int(level)], (part['id'], count)
        triangles[part['id']] = count
        points = [tuple(vertices[i * 12:i * 12 + 3]) for i in indices]
        low, high = bounds(p)[kind]
        for axis in range(3):
            values = [p[axis] for p in points]
            assert abs(min(values) - low[axis]) < 1e-5 and abs(max(values) - high[axis]) < 1e-5, (part['id'], axis)
        # The runtime turns the pier by the joint direction only: both mirror images must be the same mesh.
        assert {(-x, y, z) for x, y, z in points} == set(points) == {(x, -y, z) for x, y, z in points}, part['id']
        edges, volume = {}, 0
        for offset in range(0, len(indices), 3):
            corner = [vertices[i * 12:i * 12 + 12] for i in indices[offset:offset + 3]]
            a, b, c = (tuple(v[:3]) for v in corner)
            n = normal_of(a, b, c)
            assert n is not None, f'Degenerate pier face: {part["id"]}'
            for v in corner:
                assert all(abs(v[3 + i] - n[i]) < 1e-4 for i in range(3)), f'Flat normals: {part["id"]}'
                assert all(abs(c - 1) < 1e-6 for c in v[6:10]), f'White vertex colour: {part["id"]}'
                assert all(abs(x - y) < 1e-5 for x, y in zip(v[10:12], uv(v[:3], n))), f'World UVs: {part["id"]}'
            volume += sum(a[i] * (b[(i + 1) % 3] * c[(i + 2) % 3] - b[(i + 2) % 3] * c[(i + 1) % 3]) for i in range(3)) / 6
            for edge in ((a, b), (b, c), (c, a)):
                edges[edge] = edges.get(edge, 0) + 1
            if kind == 'shaft':
                centre = [(a[i] + b[i] + c[i]) / 3 for i in range(2)]
                assert n[2] == 0 and n[0] * centre[0] + n[1] * centre[1] > 0, 'Shaft walls must face outward'
        if kind != 'shaft':
            assert volume > 0, f'Pier winding must face outward: {part["id"]}'
            assert all(count == 1 and edges.get((b, a)) == 1 for (a, b), count in edges.items()), f'Closed: {part["id"]}'
    # Stretched along Z only, the shaft must have no end faces: its ends stay inside the cap and the footing.
    return {'mesh': str(path), 'triangles': [sum(c for n, c in triangles.items() if n.endswith(f'-lod{level}'))
                                             for level in (0, 1)], 'parts': triangles, 'bytes': path.stat().st_size}


def build(root, profile='bridge'):
    p = PROFILES[profile]
    path = root / 'data/models/board/bridges' / (p['name'] + '.glb')
    write_glb(path, model(root, p))
    return validate(path, p)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate the shipped asset without rewriting it.')
    parser.add_argument('--profile', choices=sorted(PROFILES), default='bridge', help='The kit to build or check.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    p = PROFILES[args.profile]
    path = root / 'data/models/board/bridges' / (p['name'] + '.glb')
    print(validate(path, p) if args.check else build(root, args.profile))
