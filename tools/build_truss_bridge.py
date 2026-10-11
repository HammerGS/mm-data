"""Run in Blender to bake the truss bridge: the alternative look of a built bridge, a riveted steel pony truss on each
side of the deck. One GLB per exit mask, bridges/truss-exits-NN.glb (NN 00..63), from the same authored outlines as
the standard kit (tools/board-models/bridge-shapes.json, tools/build_bridge_assets.py):

    blender -b --factory-startup --python tools/build_truss_bridge.py [-- --check]

Board units at hex scale 1 (84 = 30 metres, 2.8 per metre), the standard kit's frame: origin at the hex centre on the
deck surface, Z up, exit 0 (north) towards +Y. What stays the standard kit's, so roads, rails, piers, landings, picking
and placement work unchanged: the deck surface (part `bridge-deck`, Z = 0, the very same outline, so road paint and
the rail route builder see the same carriageway), the 1.5 slab under it (soffit Z = -1.5, the piers' cap seat), the
1.5 wide kerb band at 7.5..9 off the carriageway's centre line (the whole footprint stays 18 wide) and the materials
`bridge-deck` (asphalt, replaced by the road material at runtime) and `bridge-structure` (concrete, also used by the
runtime's landings and piers).

The truss stands on that kerb band: the band is the steel bottom chord (Z -2..1.2), and over it a Warren truss with
verticals rises to a top chord at Z = 12.5 (4.5 m), with no overhead bracing, so units on the deck stay in view. The truss
plane is the kerb line offset 0.75 outward (the band's middle). Panel points divide each kerb line between two exit
mouths evenly, about 12 long (a straight hex: 6), always an even count, so every truss starts and ends with a diagonal rising from its
mouth's bottom node: two neighbouring hexes continue one zigzag across their joint. Kerb lines that touch no exit (the
island of a six-way deck, a deck without exits) keep the standard kit's concrete parapet.

A truss end depends on the neighbour, which the exit mask does not know, so each exit's end panels are two named
alternatives besides the body node `truss-exits-NN`: `truss-joint-D` (the top chord over the end panel, a half
vertical on the shared edge and an ordinary diagonal: the truss continues into the next deck) and `truss-end-D` (an
inclined end post: the truss ends at a bank, a landing or an open end). The renderer draws the body and, per exit D,
one of the two (see the scratch note truss-bridge.md). Every vertex stays inside the hex; on a joint the half
verticals, chords and kerb bands of both hexes meet back to back on the shared edge.

The steel is one material, `bridge-steel`, untextured: its colour is the vertex colour, in the colour slot Body (default
oxide red), the convention of the placed cars and rolling stock, so a bridge's chosen colour recolours it with the one
runtime rule (RigidGlb.recolour / glb_geometry.recolour). One LOD, like the standard kit. Like the pier and terminal
kits the files stay out of manifest.json; `--check` validates the shipped files.
"""
from pathlib import Path
import json
import math
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_bridge_assets import inside, triangles
from glb_geometry import colour, read_glb, write_glb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/models/board/bridges'
SHAPES = ROOT / 'tools/board-models/bridge-shapes.json'
REPEAT = 84 / 5  # GpuTerrain.bridgeFace: one world-space concrete repeat
SOFFIT = -1.5  # the standard slab's underside, BoardBridge.SLAB
BAND = (-2.0, 1.2)  # the bottom chord: the kerb band, hanging half a unit below the soffit
TOP = 12.5  # the top chord's top
TOP_CHORD = (1.5, 1.3)  # across the truss plane (the band's width: the footprint stays 18 wide), deep
END_POST = (1.4, 1.3)  # across (narrower than the chord: no coplanar sides), in the truss plane
VERTICAL = (1.1, .8)  # across, along the truss
DIAGONAL = (1.0, .7)  # across, in the truss plane
PANEL = 12  # target panel length; a straight hex gets 6 panels of 12
OFFSET = .75  # the truss plane outside the kerb line
FOOT = .8  # where diagonals start, inside the bottom chord
SEAT = .7  # how far the top chord runs past the nodes where end posts meet it
PARAPET = 2.5  # the standard kit's concrete rail, kept on kerb lines without an exit
# The Body slot: the rail kit's oxide red (the Ironline family the concept art shows) and its paints, plus the classic
# bridge greens and greys.
BODY = '#732417'
PRESETS = [['Oxide red', '#732417'], ['Red', '#a6140a'], ['Orange', '#d1611a'], ['Yellow', '#dba31f'],
           ['Green', '#2e5233'], ['Olive', '#4c5730'], ['Blue', '#24407a'], ['Grey', '#808585'],
           ['Gunmetal', '#3d454c'], ['Silver', '#b8bab8'], ['Cream', '#d6ccab'], ['Black', '#212124']]
# Hex corners and each direction's edge (from, to) in the kit frame; the neighbour across it is OFFSETS[d] away.
CORNER = [(42, 0), (21, 36), (-21, 36), (-42, 0), (-21, -36), (21, -36)]
EDGES = {0: (CORNER[2], CORNER[1]), 1: (CORNER[1], CORNER[0]), 2: (CORNER[0], CORNER[5]),
         3: (CORNER[5], CORNER[4]), 4: (CORNER[4], CORNER[3]), 5: (CORNER[3], CORNER[2])}
OFFSETS = {0: (0, 72), 1: (63, 36), 2: (63, -36), 3: (0, -72), 4: (-63, -36), 5: (-63, 36)}


def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def scale(a, s): return tuple(x * s for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def length(a): return math.sqrt(dot(a, a))
def unit(a): return scale(a, 1 / length(a))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def edge_frame(d):
    """Exit d's edge: its midpoint, the unit along it and the unit pointing into the hex."""
    a, b = EDGES[d]
    along = unit(sub(b, a))
    mid = scale(add(a, b), .5)
    # Perpendicular to the edge (the hex is 84 x 72, not regular: not towards the centre).
    inward = (-along[1], along[0]) if dot((-along[1], along[0]), mid) < 0 else (along[1], -along[0])
    return mid, along, inward


def on_edge(p, d, tolerance=1e-3):
    a, b = EDGES[d]
    t = dot(sub(p, a), sub(b, a)) / dot(sub(b, a), sub(b, a))
    closest = add(a, scale(sub(b, a), t))
    return -1e-6 <= t <= 1 + 1e-6 and length(sub(p, closest)) < tolerance


def exit_of(p, exits):
    found = [d for d in range(6) if exits >> d & 1 and on_edge(p, d)]
    return found[0] if len(found) == 1 else None


def clean(loop):
    result = []
    for p in loop:
        if not result or length(sub(p, result[-1])) > 1e-4:
            result.append(tuple(p))
    while len(result) > 1 and length(sub(result[0], result[-1])) < 1e-4:
        result.pop()
    return result


def chains(shape):
    """The kerb lines between exit mouths: (points, first exit, last exit) along each deck loop."""
    exits, deck = shape['exits'], [clean(loop) for loop in shape['deck']]
    result = []
    for loop in deck:
        count = len(loop)
        mouth = [exit_of(loop[i], exits) is not None and exit_of(loop[i], exits) == exit_of(loop[(i + 1) % count], exits)
                 for i in range(count)]
        if not any(mouth):
            continue  # a closed kerb line: concrete parapet
        start = mouth.index(True)
        i = (start + 1) % count
        while True:
            # loop[i] is the end of a mouth segment: a kerb line runs from here to the next mouth segment.
            points = [loop[i]]
            while not mouth[i]:
                i = (i + 1) % count
                points.append(loop[i])
            if len(points) > 1:
                result.append((points, exit_of(points[0], exits), exit_of(points[-1], exits)))
            i = (i + 1) % count
            if i == (start + 1) % count:
                break
    return result


def offset(points, deck, first, last):
    """The truss plane's line: the kerb line moved OFFSET away from the deck, mitred; its ends slide along the edges."""
    a, b = points[0], points[1]
    left = unit((a[1] - b[1], b[0] - a[0]))
    probe = add(scale(add(a, b), .5), scale(left, 1e-3))
    side = -1 if inside(probe, deck) else 1  # +1: outward is the left normal

    def normal(p, q):
        n = unit((p[1] - q[1], q[0] - p[0]))
        return scale(n, side)

    result = []
    for i, p in enumerate(points):
        if i in (0, len(points) - 1):
            mid = edge_frame(first if i == 0 else last)[0]
            result.append(add(p, scale(unit(sub(p, mid)), OFFSET)))
            continue
        n1, n2 = normal(points[i - 1], p), normal(p, points[i + 1])
        mitre = unit(add(n1, n2))
        result.append(add(p, scale(mitre, OFFSET / max(dot(mitre, n1), .35))))
    return result


def nodes(line):
    """Panel points along the truss line: its ends, a node at each corner, and runs between them in even total."""
    lengths = [length(sub(b, a)) for a, b in zip(line, line[1:])]
    along = [0]
    for value in lengths:
        along.append(along[-1] + value)
    sharp = []
    for i in range(1, len(line) - 1):
        u, w = unit(sub(line[i], line[i - 1])), unit(sub(line[i + 1], line[i]))
        turn = math.degrees(math.acos(max(-1, min(1, dot(u, w)))))
        sharp.append(turn > 30 or turn / ((lengths[i - 1] + lengths[i]) / 2) > 4)
    # Corners: the middle of each cluster of sharp vertices (a filleted corner is one corner).
    corners, i = [], 0
    while i < len(sharp):
        if not sharp[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(sharp) and sharp[j + 1]:
            j += 1
        middle = (along[i + 1] + along[j + 1]) / 2
        corners.append(min(range(i + 1, j + 2), key=lambda k: abs(along[k] - middle)))
        i = j + 1
    stops = [0] + [along[k] for k in corners] + [along[-1]]
    runs = [b - a for a, b in zip(stops, stops[1:])]
    panels = [max(1, round(run / PANEL)) for run in runs]
    if sum(panels) % 2:
        k = max(range(len(runs)), key=lambda r: runs[r] / panels[r])
        panels[k] += 1

    def at(s):
        for k in range(len(lengths)):
            if s <= along[k + 1] + 1e-9 or k == len(lengths) - 1:
                t = 0 if lengths[k] == 0 else (s - along[k]) / lengths[k]
                return add(line[k], scale(sub(line[k + 1], line[k]), max(0, min(1, t))))

    result = [line[0]]
    for start, run, count in zip(stops, runs, panels):
        for k in range(1, count + 1):
            result.append(at(start + run * k / count))
    result[-1] = line[-1]
    return result


class Kit:
    """Packed vertices (12 floats), a colour slot per vertex and indexed triangles per part."""

    def __init__(self):
        self.packed, self.slots, self.unique, self.parts = [], [], {}, {}

    def face(self, part, points, steel=False, normal=None):
        """A planar convex polygon, counter-clockwise seen from outside (or turned to `normal`)."""
        n = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        for k in range(3, len(points)):
            if length(n) > 1e-9:
                break
            n = cross(sub(points[k - 1], points[0]), sub(points[k], points[0]))
        if length(n) < 2e-4:
            return  # also the slivers the triangulation leaves along an outline folded back on an exit edge
        n = unit(n)
        if normal is not None and dot(n, normal) < 0:
            points, n = points[::-1], scale(n, -1)
        rgb = colour(BODY) if steel else (1, 1, 1)
        indices = []
        for p in points:
            # GpuTerrain.bridgeFace: tops map (x, -y), walls (along the wall, -z), one world-space repeat.
            u = p[0] if abs(n[2]) > .5 or abs(n[0]) <= .5 else p[1]
            v = -p[1] if abs(n[2]) > .5 else -p[2]
            value = tuple(round(c, 6) for c in (*p, *n, *rgb, 1, u / REPEAT, v / REPEAT))
            key = value + (steel,)
            if key not in self.unique:
                self.unique[key] = len(self.slots)
                self.packed.extend(value)
                self.slots.append(1 if steel else 0)
            indices.append(self.unique[key])
        target = self.parts.setdefault(part, [])
        for k in range(1, len(indices) - 1):
            target.extend((indices[0], indices[k], indices[k + 1]))

    def cap(self, part, loops, z, up, steel=False):
        for a, b, c in triangles(loops):
            self.face(part, [(*p, z) for p in ((a, b, c) if up else (a, c, b))], steel)

    def walls(self, part, loops, low, high, steel=False):
        """Vertical walls around `loops`, facing out of them. A segment is split
        where other outline vertices lie on it: the authored outlines fold back along some exit edges (a zero-width
        sliver over part of a segment), so only the part with the band on one side gets a wall."""
        corners = [tuple(p) for loop in loops for p in loop]
        for loop in loops:
            for a0, b0 in zip(loop, loop[1:] + loop[:1]):
                span = sub(b0, a0)
                if length(span) < 1e-5:
                    continue
                cuts = {0, 1}
                for p in corners:
                    t = dot(sub(p, a0), span) / dot(span, span)
                    if 1e-6 < t < 1 - 1e-6 and length(sub(p, add(a0, scale(span, t)))) < 1e-4:
                        cuts.add(t)
                cuts = sorted(cuts)
                for t0, t1 in zip(cuts, cuts[1:]):
                    self.wall(part, loops, add(a0, scale(span, t0)), add(a0, scale(span, t1)), low, high, steel)

    def wall(self, part, loops, a, b, low, high, steel):
        if length(sub(b, a)) < 1e-5:
            return
        n = unit((b[1] - a[1], a[0] - b[0]))
        mid = scale(add(a, b), .5)
        out, back = inside(add(mid, scale(n, 1e-4)), loops), inside(sub(mid, scale(n, 1e-4)), loops)
        if out == back:
            return  # a zero-width boundary between coinciding outlines
        if out:
            n = scale(n, -1)
        self.face(part, [(*a, low), (*b, low), (*b, high), (*a, high)], steel, (*n, 0))

    def member(self, part, a, b, across, size, caps=(False, False), clip=(None, None)):
        """A steel prism along a -> b: `size` is (width across, depth); `across` a horizontal unit (the truss plane's
        normal). clip[i] = (point, normal): that end is cut to a vertical plane (an exit edge)."""
        axis = unit(sub(b, a))
        depth = unit(cross(axis, across))
        w, h = size[0] / 2, size[1] / 2
        corners = [(w, h), (-w, h), (-w, -h), (w, -h)]

        def ring(end, plane):
            points = [add(add(end, scale(across, x)), scale(depth, y)) for x, y in corners]
            if plane is not None:
                p0, n = plane
                points = [add(q, scale(axis, dot(sub(p0, q), n) / dot(axis, n))) for q in points]
            return points

        lower, upper = ring(a, clip[0]), ring(b, clip[1])
        centre = scale(add(a, b), .5)
        for k in range(4):
            quad = [lower[k], lower[(k + 1) % 4], upper[(k + 1) % 4], upper[k]]
            middle = scale(add(add(quad[0], quad[1]), add(quad[2], quad[3])), .25)
            out = sub(middle, add(centre, scale(axis, dot(sub(middle, centre), axis))))
            self.face(part, quad, True, out)
        if caps[0]:
            self.face(part, lower, True, scale(axis, -1))
        if caps[1]:
            self.face(part, upper, True, axis)


def horizontal_normal(u):
    """The horizontal unit perpendicular to the direction u (x, y[, z])."""
    return unit((-u[1], u[0], 0))


def truss(kit, line, first, last):
    """One truss over the truss line: the body's members in `bridge-steel`, each end panel's two alternatives in
    `truss-joint-D` and `truss-end-D` (D the exit at that end)."""
    points = nodes(line)
    n = len(points) - 1
    assert n >= 2 and n % 2 == 0, (n, line)
    low, high = BAND[1], TOP - TOP_CHORD[1]  # the bottom chord's top, the top chord's bottom
    centre = TOP - TOP_CHORD[1] / 2

    def p3(i, z):
        return (*points[i], z)

    def tangent(i):
        a, b = points[max(0, i - 1)], points[min(n, i + 1)]
        return unit(sub(b, a))

    ends = {0: first, n: last}
    planes = {0: edge_frame(first), n: edge_frame(last)}

    def plane(i):
        mid, along, inward = planes[i]
        return (*mid, 0), (*inward, 0)

    # Top chord, body: nodes 1..n-1; each segment overlaps its neighbours past the shared node.
    for i in range(1, n - 1):
        a, b = p3(i, centre), p3(i + 1, centre)
        u = unit(sub(b, a))
        before = SEAT if i == 1 else extension(points, i, TOP_CHORD[0])
        after = SEAT if i + 1 == n - 1 else extension(points, i + 1, TOP_CHORD[0])
        kit.member('bridge-steel', sub(a, scale(u, before)), add(b, scale(u, after)), horizontal_normal(u), TOP_CHORD,
                   caps=(i == 1, i + 1 == n - 1))
    # Verticals at the body nodes, between the chords.
    for i in range(1, n):
        vertical(kit, 'bridge-steel', points[i], tangent(i), low, high)
    # Diagonals of the inner panels: panel k rises from node k when k is even.
    for k in range(1, n - 1):
        diagonal(kit, 'bridge-steel', points, k)
    # The end panels.
    for i, inner in ((0, 1), (n, n - 1)):
        d = ends[i]
        edge = points[i]
        mid, along, inward = planes[i]
        joint, end = f'truss-joint-{d}', f'truss-end-{d}'
        # Joint: the top chord to the edge, a half vertical on it, an ordinary diagonal from the edge's bottom node.
        a, b = p3(inner, centre), p3(i, centre)
        u = unit(sub(b, a))
        kit.member(joint, sub(a, scale(u, .5)), add(b, scale(u, 1)), horizontal_normal(u), TOP_CHORD,
                   caps=(False, True), clip=(None, plane(i)))
        half = [add(edge, scale(along, s * VERTICAL[0] / 2)) for s in (-1, 1)]
        half += [add(q, scale(inward, VERTICAL[1] / 2)) for q in half[::-1]]
        middle = add(edge, scale(inward, VERTICAL[1] / 4))
        for k in range(4):
            a2, b2 = half[k], half[(k + 1) % 4]
            kit.face(joint, [(*a2, low), (*b2, low), (*b2, high), (*a2, high)], True,
                     (*sub(scale(add(a2, b2), .5), middle), 0))
        foot = add(edge, scale(inward, .7))
        diagonal_member(kit, joint, (*foot, FOOT), p3(inner, centre))
        # End: an inclined end post from the band just inside the edge up into the top chord.
        foot = add(edge, scale(inward, .9))
        a, b = (*foot, .3), p3(inner, centre)  # its foot's corners stay inside the band and the hex
        kit.member(end, a, b, horizontal_normal(sub(b, a)), END_POST)


def extension(points, i, width):
    """How far a chord segment runs past node i so the outside of a corner closes."""
    if i <= 0 or i >= len(points) - 1:
        return .3
    u, w = unit(sub(points[i], points[i - 1])), unit(sub(points[i + 1], points[i]))
    turn = math.acos(max(-1, min(1, dot(u, w))))
    return .3 + width / 2 * math.tan(min(turn, math.radians(75)) / 2)


def vertical(kit, part, point, t, low, high):
    across = horizontal_normal(t)
    along = (*t, 0)
    w, h = VERTICAL[0] / 2, VERTICAL[1] / 2
    ring = [add(add((*point, 0), scale(across, x)), scale(along, y)) for x, y in ((w, h), (-w, h), (-w, -h), (w, -h))]
    for k in range(4):
        a, b = ring[k], ring[(k + 1) % 4]
        out = sub(scale(add(a, b), .5), (*point, 0))
        kit.face(part, [(a[0], a[1], low), (b[0], b[1], low), (b[0], b[1], high), (a[0], a[1], high)], True, out)


def diagonal(kit, part, points, k):
    low, centre = FOOT, TOP - TOP_CHORD[1] / 2
    if k % 2 == 0:
        a, b = (*points[k], low), (*points[k + 1], centre)
    else:
        a, b = (*points[k], centre), (*points[k + 1], low)
    diagonal_member(kit, part, a, b)


def diagonal_member(kit, part, a, b):
    kit.member(part, a, b, horizontal_normal(sub(b, a)), DIAGONAL)


def model(shape):
    exits, asset = shape['exits'], 'bridges/truss-exits-%02d' % shape['exits']
    kit = Kit()
    deck = shape['deck']
    # The standard deck surface and its slab underside.
    kit.cap('bridge-deck', deck, 0, True)
    kit.cap('bridge-structure', deck, SOFFIT, False)
    # The slab's ends across each exit mouth; everything else of the slab's side is the kerb band.
    for loop in deck:
        loop = clean(loop)
        for a, b in zip(loop, loop[1:] + loop[:1]):
            d = exit_of(a, exits)
            if d is not None and d == exit_of(b, exits):
                mid, along, inward = edge_frame(d)
                kit.face('bridge-structure', [(*a, SOFFIT), (*b, SOFFIT), (*b, 0), (*a, 0)], False, (*scale(inward, -1), 0))
    # Kerb bands: steel bottom chords where they reach an exit, the standard concrete parapet elsewhere.
    rails = shape['rails']
    for loop in rails:
        loops = [loop]
        touches = any(exit_of(p, exits) is not None for p in loop)
        if touches:
            kit.cap('bridge-steel', loops, BAND[1], True, True)
            kit.cap('bridge-steel', loops, BAND[0], False, True)
            kit.walls('bridge-steel', loops, BAND[0], BAND[1], True)
        else:
            kit.cap('bridge-structure', loops, PARAPET, True)
            kit.cap('bridge-structure', loops, SOFFIT, False)
            kit.walls('bridge-structure', loops, SOFFIT, PARAPET)
    for points, first, last in chains(shape):
        truss(kit, offset(points, deck, first, last), first, last)
    roles = {'bridge-deck': 'roads/asphalt.png', 'bridge-structure': 'sculpt/concrete.png', 'bridge-steel': None}
    file = OUT / (Path(asset).name + '.glb')
    materials = []
    for role, filename in roles.items():
        material = {'id': role, 'diffuse': [1, 1, 1]}
        if filename:
            texture = os.path.relpath(ROOT / 'data/models/board/textures' / filename, OUT).replace('\\', '/')
            material['textures'] = [{'id': role, 'filename': texture, 'type': 'DIFFUSE', 'wrapS': 10497, 'wrapT': 10497}]
        materials.append(material)
    name = Path(asset).name
    order = ['bridge-deck', 'bridge-structure', 'bridge-steel']
    nodes_out = [{'id': name, 'parts': [{'meshpartid': part, 'materialid': part} for part in order if kit.parts.get(part)]}]
    for d in range(6):
        for kind in ('joint', 'end'):
            part = f'truss-{kind}-{d}'
            if kit.parts.get(part):
                nodes_out.append({'id': part, 'parts': [{'meshpartid': part, 'materialid': 'bridge-steel'}]})
    data = {'id': name, 'version': [0, 1], 'materials': materials,
            'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], 'vertices': kit.packed,
                        'slots': kit.slots, 'parts': [{'id': part, 'type': 'TRIANGLES', 'indices': indices}
                                                      for part, indices in kit.parts.items() if indices]}],
            'nodes': nodes_out}
    write_glb(file, levels={0: data}, extras={'mmColourSlots': [{'name': 'Body', 'colour': BODY, 'presets': PRESETS}]})
    return file


def build():
    shapes = json.loads(SHAPES.read_text())
    assert sorted(shape['exits'] for shape in shapes) == list(range(64))
    report = {}
    for shape in sorted(shapes, key=lambda s: s['exits']):
        file = model(shape)
        report[file.stem] = validate(file, shape)
    return report


def standard(exits):
    return ROOT / 'data/models/board' / ('bridge.glb' if exits == 9 else 'bridges/bridge-exits-%02d.glb' % exits)


def triangles_of(mesh, part):
    """A part's triangles with area, rounded (the standard kit keeps the zero-area slivers this kit drops)."""
    values = mesh['vertices']
    indices = next(p['indices'] for p in mesh['parts'] if p['id'] == part)
    result = []
    for k in range(0, len(indices), 3):
        a, b, c = (tuple(values[i * 12:i * 12 + 3]) for i in indices[k:k + 3])
        if length(cross(sub(b, a), sub(c, a))) >= 2e-4:
            result.append(tuple(tuple(round(v, 4) for v in p) for p in (a, b, c)))
    return result


def in_hex(p, tolerance=1e-4):
    for a, b in EDGES.values():
        # EDGES run clockwise seen from above: the inside is on each edge's right.
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) > tolerance * length(sub(b, a)):
            return False
    return True


def on_plane(p, d, tolerance=1e-4):
    mid, along, inward = edge_frame(d)
    return abs(dot(sub(p[:2], mid), inward)) < tolerance


def validate(path, shape):
    """The deck matches the standard kit's; every vertex in the hex; nodes, materials and the colour slot as specified;
    each closed part faces outward; across every joint the faces on the shared edge meet the neighbour's."""
    exits = shape['exits']
    data = read_glb(path)
    mesh = data['meshes'][0]
    values = mesh['vertices']
    names = {node['id'] for node in data['nodes']}
    body = path.stem
    expected = {body} | {f'truss-{kind}-{d}' for d in range(6) if exits >> d & 1 for kind in ('joint', 'end')
                         if chains(shape)}
    assert names == expected, (path.name, sorted(names ^ expected))
    assert data['extras']['mmColourSlots'] == [{'name': 'Body', 'colour': BODY, 'presets': PRESETS}], path
    roles = {m['id'] for m in data['materials']}
    assert roles == {'bridge-deck', 'bridge-structure', 'bridge-steel'}, roles
    reference = read_glb(standard(exits))['meshes'][0]
    assert sorted(triangles_of(mesh, 'bridge-deck')) == sorted(triangles_of(reference, 'bridge-deck')), \
        f'The deck surface must stay the standard kit\'s: {path.name}'
    zs = values[2::12]
    assert abs(min(zs) - (BAND[0] if chains(shape) else SOFFIT)) < 1e-5, path
    assert abs(max(zs) - (TOP if chains(shape) else PARAPET)) < 1e-5, path
    slots = mesh.get('slots', [0] * (len(values) // 12))
    for part in mesh['parts']:
        steel = part['id'] not in ('bridge-deck', 'bridge-structure')
        volume = 0
        for k in range(0, len(part['indices']), 3):
            corner = [values[i * 12:i * 12 + 12] for i in part['indices'][k:k + 3]]
            a, b, c = (tuple(v[:3]) for v in corner)
            n = cross(sub(b, a), sub(c, a))
            assert length(n) > 1e-9, f'Degenerate face: {path.name} {part["id"]}'
            volume += dot(a, cross(b, c)) / 6
            for v, i in zip(corner, part['indices'][k:k + 3]):
                assert in_hex(v[:3]), f'Outside the hex: {path.name} {part["id"]} {v[:3]}'
                assert slots[i] == (1 if steel else 0), f'Colour slot: {path.name} {part["id"]}'
                if steel:
                    assert all(abs(x - y) < 2e-3 for x, y in zip(v[6:9], colour(BODY))), 'Body colour'
        if part['id'] != 'bridge-deck':
            assert volume > 0, f'Faces must point outward: {path.name} {part["id"]}'
    # Joints: on each exit edge the faces of the body and its joint alternative, moved into the neighbour's frame,
    # coincide with those of the neighbour's straight deck on its opposite edge.
    sections = {}
    for d in range(6):
        if not exits >> d & 1:
            continue
        sections[d] = edge_faces(data, mesh, body, d)
    return {'triangles': len([i for p in mesh['parts'] for i in p['indices']]) // 3, 'vertices': len(values) // 12,
            'nodes': len(names), 'sections': {d: len(faces) for d, faces in sections.items()}, 'bytes': path.stat().st_size,
            '_sections': sections}


def edge_faces(data, mesh, body, d):
    """The faces of the body and exit d's joint alternative that lie on exit d's edge, as (along, z) triangles."""
    values = mesh['vertices']
    keep = {body, f'truss-joint-{d}'}
    parts = {p['meshpartid'] for node in data['nodes'] if node['id'] in keep for p in node['parts']}
    mid, along, inward = edge_frame(d)
    result = []
    for part in mesh['parts']:
        if part['id'] not in parts:
            continue
        for k in range(0, len(part['indices']), 3):
            points = [tuple(values[i * 12:i * 12 + 3]) for i in part['indices'][k:k + 3]]
            if all(on_plane(p, d) for p in points):
                result.append([(dot(sub(p[:2], mid), along), p[2]) for p in points])
    return result


def covered(point, faces, tolerance=.02):
    for a, b, c in faces:
        signs = []
        for p, q in ((a, b), (b, c), (c, a)):
            edge = sub(q, p)
            signs.append((edge[0] * (point[1] - p[1]) - edge[1] * (point[0] - p[0])) / max(length(edge), 1e-9))
        if all(s >= -tolerance for s in signs) or all(s <= tolerance for s in signs):
            return True
    return False


def check_joints(report):
    """Across every joint the two hexes' faces on the shared edge cover the same area: each exit's section against
    the straight neighbour's opposite one (the shared edge runs the other way round in the neighbour)."""
    for name, entry in report.items():
        for d, faces in entry['_sections'].items():
            straight = 'truss-exits-%02d' % (1 << d | 1 << (d + 3) % 6)
            other = [[(-s, z) for s, z in face] for face in report[straight]['_sections'][(d + 3) % 6]]
            for one, two in ((faces, other), (other, faces)):
                for face in one:
                    centre = tuple(sum(p[i] for p in face) / 3 for i in range(2))
                    for probe in [centre] + [tuple((2 * centre[i] + p[i]) / 3 for i in range(2)) for p in face]:
                        assert covered(probe, two), f'Joint {name} exit {d}: {probe}'
    for entry in report.values():
        entry.pop('_sections')


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if '--check' in args:
        shapes = {s['exits']: s for s in json.loads(SHAPES.read_text())}
        report = {('truss-exits-%02d' % e): validate(OUT / ('truss-exits-%02d.glb' % e), shapes[e]) for e in range(64)}
    else:
        report = build()
    check_joints(report)
    counts = [entry['triangles'] for entry in report.values()]
    print(json.dumps({'truss_models': len(report), 'min_triangles': min(counts), 'max_triangles': max(counts),
                      'straight': report['truss-exits-09'], 'bytes': sum(e['bytes'] for e in report.values())}),
          flush=True)
