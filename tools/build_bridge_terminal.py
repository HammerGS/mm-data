"""Bake the shared bridge end block. Pure Python; uses the terrain kit GLB writer.

Coordinates use board units (84 = 30 metres): X points out of the carriageway,
Y runs from the full-height rail to the bank, and Z is height above the deck.
The two root meshes follow the same named-LOD convention as the terrain rock kits.
"""
import argparse
import math
from pathlib import Path

from glb_geometry import read_glb, write_glb


NAME = 'bridge-terminal'
METRE = 84 / 30


def model():
    packed, parts, nodes = [], [], []
    width = 1.5 + .3 * METRE
    for level, bevel in enumerate((.035 * METRE, 0)):
        rings = []
        for y, height in ((0, 2.5 + .1 * METRE), (.32 * METRE, 2.5 + .1 * METRE),
                          (1.5 * METRE, .08 * METRE)):
            profile = [(0, 0), (width, 0), (width, height), (0, height)] if not bevel else [
                (0, 0), (width, 0), (width, height - bevel), (width - bevel, height),
                (bevel, height), (0, height - bevel)]
            rings.append([(x, y, z) for x, z in profile])
        faces = []
        count = len(rings[0])
        for a, b in zip(rings, rings[1:]):
            for i in range(count):
                j = (i + 1) % count
                faces.extend(((a[i], b[i], b[j]), (a[i], b[j], a[j])))
        for i in range(1, count - 1):
            faces.extend(((rings[0][0], rings[0][i], rings[0][i + 1]),
                          (rings[-1][0], rings[-1][i + 1], rings[-1][i])))
        indices = []
        for a, b, c in faces:
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            length = math.sqrt(sum(n * n for n in normal))
            normal = [n / length for n in normal]
            for p in (a, b, c):
                uv = ((p[1] if abs(normal[0]) > .7 else p[0]) / (84 / 5),
                      -(p[1] if abs(normal[2]) > .7 else p[2]) / (84 / 5))
                indices.append(len(packed) // 12)
                packed.extend((*p, *normal, 1, 1, 1, 1, *uv))
        name = f'{NAME}-lod{level}'
        parts.append({'id': name, 'type': 'TRIANGLES', 'indices': indices})
        nodes.append({'id': name, 'parts': [{'meshpartid': name, 'materialid': 'bridge-structure'}]})
    return {'id': NAME, 'materials': [{'id': 'bridge-structure', 'diffuse': [1, 1, 1], 'textures': [
        {'id': 'bridge-structure', 'filename': 'textures/terrain/surfaces/concrete.png', 'type': 'DIFFUSE'}]}],
        'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], 'vertices': packed, 'parts': parts}],
        'nodes': nodes}


def validate(path):
    mesh = read_glb(path)
    assert {node['id'] for node in mesh['nodes']} == {f'{NAME}-lod0', f'{NAME}-lod1'}
    geometry = mesh['meshes'][0]
    vertices = geometry['vertices']
    for part, expected in zip(geometry['parts'], (32, 20)):
        assert len(part['indices']) // 3 == expected, part['id']
        edges, volume = {}, 0
        for offset in range(0, len(part['indices']), 3):
            a, b, c = [tuple(vertices[i * 12:i * 12 + 3]) for i in part['indices'][offset:offset + 3]]
            normal = ((b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
                      (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                      (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
            assert sum(n * n for n in normal) > 1e-8, 'Degenerate terminal face'
            volume += sum(a[i] * normal[i] for i in range(3)) / 6
            for edge in ((a, b), (b, c), (c, a)):
                edges[edge] = edges.get(edge, 0) + 1
        assert volume > 0, 'Terminal winding must face outward'
        assert all(count == 1 and edges.get((b, a)) == 1 for (a, b), count in edges.items()), 'Terminal must be closed'
    texture = mesh['materials'][0]['textures'][0]['filename']
    assert (path.parent / texture).is_file(), texture
    return {'mesh': str(path), 'triangles': [32, 20], 'bytes': path.stat().st_size}


def build(root):
    path = root / 'data/models/board' / (NAME + '.glb')
    write_glb(path, model())
    return validate(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate the shipped asset without rewriting it.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(validate(root / 'data/models/board' / (NAME + '.glb')) if args.check else build(root))
