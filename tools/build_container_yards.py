"""Build the seaport container yards (a look of the woods cover) and the seaport props they are made of.

A yard skin draws the cover of a woods hex as a container yard; the woods keep every rule. Its stacks are as high as
the cover: 3 tiers (1 level) on foliage, 6 (2 levels) on light and heavy woods, 9 (3 levels) on ultra-heavy woods, and
its density follows the cover too. A skin is one layout drawn whole and turned by the look's rotation (30 degree
steps): its containers are one baked mesh (yard/<level>-<layout>.glb) and its cranes and vehicles are rows on the
props below (yard/skins.json, the layouts.json row format). Every layout's containers lie inside the hex's inscribed
dodecagon, less a lane, so each rotation step fits the hex; a quay crane's boom reaches one hex beyond its own, over
the neighbour the boom points at.

Props (palette objects, also the skins' parts): a container and stacks of two and three (colour slots), the quay
crane, a crane boom segment (one hex long; segments chain end to end in front of a quay crane), the yard gantry (6 and
9 tier clearance), a straddle carrier, a reach stacker and a yard truck.

Units are board px (a hex is 84 x 72, a level 18), Z up, +Y north, the hex centre at the origin. A container is the
legacy seaport box (13.2 x 5.8) 6.0 high, so three tiers make one level.

Run with Blender: blender --background --factory-startup --python tools/build_container_yards.py
"""
import json
import random
import sys
from math import cos, radians, sin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_scenery_assets import BOARD, DARK, GLASS, STEEL, WHITE, YELLOW, Mesh, container_grabber, export_mesh
from glb_geometry import colour_text
from mathutils import Vector

YARD = 'scenery/seaport/yard/'
LENGTH, WIDTH, TIER = 13.2, 5.8, 6.0
# Stack heights per cover level: the woods' height (foliage elevation) in levels of three tiers.
TIERS = {'foliage': 3, 'light': 6, 'heavy': 6, 'ultra': 9}
# The containers stay this far inside the hex's inscribed dodecagon (apothem 36): lanes between yard hexes.
REACH = 33.0
FRAME = .6
# The legacy seaport's container colours (sampled from its sprites), with their share of the legacy boxes.
PAINT = {'Oxide red': ((.47, .23, .23), 11), 'Red': ((.58, .30, .29), 9), 'Rust': ((.53, .33, .25), 8),
         'Tan': ((.60, .42, .28), 8), 'Mustard': ((.55, .46, .24), 3), 'Navy': ((.27, .30, .40), 12),
         'Blue': ((.30, .43, .55), 10), 'Green': ((.19, .42, .32), 6), 'Grey': ((.44, .44, .45), 6),
         'Silver': ((.56, .57, .57), 8), 'White': ((.83, .84, .83), 3)}
PRESETS = [[name, colour_text(value)] for name, (value, _) in PAINT.items()]

# Quay crane: the boom runs along +Y to the hex side (Y = 36); truss panels are 4.5 long, so every boom piece's joints
# lie on one grid along the boom and segments chain seamlessly. BOOM is the bottom chord, the trolley rail.
BOOM, BOOM_DEPTH, BOOM_HALF, PANEL = 41.0, 3.5, 2.4, 4.5
LEGS_X, LEGS_Y, APEX = 8.5, (6.0, 24.0), 53.0
SEGMENT = 72.0  # one hex along a side direction


def shade(c, k):
    return tuple(min(1.0, v * k) for v in c)


def paint(rng):
    names = list(PAINT)
    return PAINT[rng.choices(names, [PAINT[n][1] for n in names])[0]][0]


def panel(g, o, a, b, c, kind='plain'):
    """One container face: corner o, edges a (across) and b (up or along), outward normal a x b. A dark frame
    outlines it (the seams between containers); long sides are corrugated and the door end has its locking bars."""
    o, a, b = Vector(o), Vector(a), Vector(b)
    fa, fb = min(.3, FRAME / a.length), min(.3, FRAME / b.length)

    def quad(s0, t0, s1, t1, colour):
        g.face([o + a * s0 + b * t0, o + a * s1 + b * t0, o + a * s1 + b * t1, o + a * s0 + b * t1], colour)

    dark = shade(c, .48)
    quad(0, 0, 1, fb, dark); quad(0, 1 - fb, 1, 1, dark)
    quad(0, fb, fa, 1 - fb, dark); quad(1 - fa, fb, 1, 1 - fb, dark)
    if kind == 'side':
        cuts = [fa + (1 - 2 * fa) * i / 7 for i in range(8)]
        for i in range(7): quad(cuts[i], fb, cuts[i + 1], 1 - fb, shade(c, .8) if i % 2 else c)
    elif kind == 'door':
        bars = [(.27, .2), (.5, .35), (.73, .2)]
        s = fa
        for at, width in bars:
            w = width / a.length / 2
            quad(s, fb, at - w, 1 - fb, c); quad(at - w, fb, at + w, 1 - fb, dark); s = at + w
        quad(s, fb, 1 - fa, 1 - fb, c)
    else: quad(fa, fb, 1 - fa, 1 - fb, c)


def stacks(g, cells, x0=0.0, y0=0.0):
    """Container stacks on a grid: cells maps (column, bay) to the stack's colours, bottom first. Columns are WIDTH
    apart along X from x0, bays LENGTH apart along Y (the containers' long axis) from y0; faces hidden by a
    neighbour are left out."""
    hw, hl = WIDTH / 2, LENGTH / 2
    for (i, j), colours in cells.items():
        x, y = x0 + i * WIDTH, y0 + j * LENGTH
        for t, c in enumerate(colours):
            z = t * TIER

            def open_(di, dj): return len(cells.get((i + di, j + dj), ())) <= t
            if open_(1, 0): panel(g, (x + hw, y - hl, z), (0, LENGTH, 0), (0, 0, TIER), c, 'side')
            if open_(-1, 0): panel(g, (x - hw, y + hl, z), (0, -LENGTH, 0), (0, 0, TIER), c, 'side')
            if open_(0, 1): panel(g, (x + hw, y + hl, z), (-WIDTH, 0, 0), (0, 0, TIER), c, 'door')
            if open_(0, -1): panel(g, (x - hw, y - hl, z), (WIDTH, 0, 0), (0, 0, TIER), c)
        panel(g, (x - hw, y - hl, len(colours) * TIER), (WIDTH, 0, 0), (0, LENGTH, 0), colours[-1])


def inside(points, keep=None):
    """Whether every point lies in the dodecagon (apothem REACH) and, when given, in the keep area."""
    for x, y in points:
        if any(x * cos(radians(a)) + y * sin(radians(a)) > REACH + 1e-6 for a in range(0, 360, 30)): return False
        if keep and not keep(x, y): return False
    return True


def block(g, rng, x, y, columns, bays, height, angle=0, keep=None):
    """A block of stacks centred at (x, y), its containers along the block's Y turned by `angle`. Cells outside the
    hex's dodecagon or the keep area are left out; height(column, bay, rng) gives a stack's tiers (0 for none)."""
    turn = radians(angle)
    cells = {}
    for i in range(columns):
        for j in range(bays):
            u, v = (i - (columns - 1) / 2) * WIDTH, (j - (bays - 1) / 2) * LENGTH
            corners = [(u + su * WIDTH / 2, v + sv * LENGTH / 2) for su in (-1, 1) for sv in (-1, 1)]
            corners = [(x + a * cos(turn) - b * sin(turn), y + a * sin(turn) + b * cos(turn)) for a, b in corners]
            tiers = height(i, j, rng) if inside(corners, keep) else 0
            if tiers <= 0: continue
            colours = [paint(rng)]
            for _ in range(tiers - 1):
                # A third of the containers sit on one of their line's: runs of a colour, as in real stacks.
                colours.append(colours[-1] if rng.random() < .3 else paint(rng))
            cells[(i, j)] = colours
    g.place(lambda m: stacks(m, cells, -(columns - 1) / 2 * WIDTH, -(bays - 1) / 2 * LENGTH), x=x, y=y, angle=angle)
    return sum(len(c) for c in cells.values())


# ---- Vehicles and cranes ----------------------------------------------------------------------------------------

def stack(g, tiers):
    """A stack of `tiers` containers, each container's paint its own colour slot (bottom first)."""
    names, paints = ('Bottom', 'Middle', 'Top')[3 - tiers:], ('Navy', 'Oxide red', 'Silver')[3 - tiers:]
    g.colour_slots = [{'name': n, 'colour': colour_text(PAINT[p][0]), 'presets': PRESETS} for n, p in zip(names, paints)]
    for t, p in enumerate(paints):
        g.slot = t + 1
        g.place(lambda m: stacks(m, {(0, 0): [PAINT[p][0]]}), z=t * TIER)
    g.slot = 0


def wheels(g, x, y, length=2.6):
    g.box((x, y, .8), (1.4, length, 1.6), DARK)


def yard_truck(g):
    """A terminal tractor and its chassis carrying one container (colour slot 1) along Y, cab at +Y."""
    g.colour_slots = [{'name': 'Container', 'colour': colour_text(PAINT['Blue'][0]), 'presets': PRESETS}]
    g.box((0, -1.5, 1.5), (3.4, 15.0, .8), DARK)
    for y in (-7, -4.6, 7.4):
        for x in (-1.6, 1.6): wheels(g, x, y, 1.8)
    g.box((0, 8.6, 2.6), (4.0, 3.6, 3.6), (.86, .64, .12))
    g.box((0, 10.45, 3.3), (3.4, .1, 1.5), GLASS)
    g.slot = 1
    g.place(lambda m: stacks(m, {(0, 0): [PAINT['Blue'][0]]}), y=-1.5, z=1.9)
    g.slot = 0


def straddle_carrier(g):
    """A straddle carrier over one container lane (along Y): four legs on wheels, a top frame with the cab, and the
    spreader holding a container under it. Clears three tiers."""
    top = 3 * TIER + 9.5
    for x in (-4.4, 4.4):
        g.box((x, 0, 1.1), (1.6, 15.0, 1.2), YELLOW)
        for y in (-6.4, -2.2, 2.2, 6.4): wheels(g, x, y, 1.8)
        for y in (-6.4, 6.4): g.beam((x, y, 1.6), (x, y, top), 1.1, YELLOW, 4)
        g.beam((x, -6.4, 3.0), (x, 6.4, top - 2.5), .55, YELLOW, 4)
        g.box((x, 0, top + .9), (1.4, 15.0, 1.8), YELLOW)
    for y in (-6.4, 6.4): g.box((0, y, top + .9), (10.2, 1.4, 1.6), YELLOW)
    g.box((0, -3.0, top + 2.6), (5.0, 5.0, 1.8), WHITE)
    g.box((3.0, 6.0, top + 2.4), (2.6, 2.6, 2.6), WHITE)
    g.box((4.32, 6.0, top + 2.6), (.1, 2.2, 1.5), GLASS)
    for y in (-3, 3):
        for x in (-1.5, 1.5): g.beam((x, y, top), (x, y, top - 7.3), .14, DARK, 4)
    g.place(container_grabber, z=top - 8.3, angle=90)
    g.place(lambda m: stacks(m, {(0, 0): [PAINT['Silver'][0]]}), z=top - 8.3 - TIER)


def reach_stacker(g):
    """A reach stacker along Y (forks to +Y) with its telescopic boom raised and a container across its spreader."""
    g.box((0, -1, 2.2), (6.8, 17.0, 2.6), (.86, .64, .12))
    g.box((0, -9.2, 3.4), (6.8, 2.8, 3.8), DARK)
    for y in (-5.5, 5.5):
        for x in (-3.7, 3.7): g.box((x, y, 1.4), (1.6, 3.0, 2.8), DARK)
    g.box((-1.6, 0.5, 5.6), (3.0, 3.6, 4.2), WHITE)
    g.box((-1.6, 2.35, 6.2), (2.6, .1, 2.2), GLASS)
    g.beam((1.8, -7.0, 5.5), (1.8, 9.5, 17.5), 2.0, (.86, .64, .12), 4)
    g.beam((1.8, -1.0, 3.6), (1.8, 2.5, 10.0), 1.3, STEEL, 4)
    g.place(container_grabber, x=1.8, y=10.2, z=15.6)
    g.place(lambda m: stacks(m, {(0, 0): [PAINT['Rust'][0]]}), x=1.8, y=10.2, z=15.6 - TIER, angle=90)


def yard_gantry(g, tiers):
    """A rubber-tyred yard gantry straddling a block six containers wide (along Y), clearing `tiers` tiers plus a
    lifted container; its trolley hoists a container over the block."""
    clear = tiers * TIER + 8.5
    span = 6 * WIDTH / 2 + 2.6
    for x in (-span, span):
        g.box((x, 0, 1.0), (1.8, 17.0, 1.4), YELLOW)
        for y in (-7.0, -4.6, 4.6, 7.0): wheels(g, x, y, 2.0)
        for y in (-6.5, 6.5): g.beam((x, y, 1.7), (x, y, clear), 1.3, YELLOW, 4)
        g.beam((x, -6.5, 2.4), (x, 6.5, clear - 2.0), .6, YELLOW, 4)
        g.beam((x, 6.5, 2.4), (x, -6.5, clear - 2.0), .6, YELLOW, 4)
    for y in (-6.5, 6.5):
        g.box((0, y, clear + 1.6), (2 * span + 1.6, 1.6, 3.2), YELLOW)
    g.box((span - 1.5, 0, clear + 4.4), (4.0, 8.0, 2.6), WHITE)
    trolley = -WIDTH * 1.5
    g.box((trolley, 0, clear + 3.6), (5.0, 15.2, 1.2), STEEL)
    g.box((trolley + 2.6, -5.0, clear - 1.4), (2.4, 2.6, 2.6), WHITE)
    g.box((trolley + 3.85, -5.0, clear - 1.2), (.1, 2.2, 1.6), GLASS)
    lift = tiers * TIER + 1.2
    for y in (-3, 3):
        for x in (-1.5, 1.5): g.beam((trolley + x, y, clear + 3.0), (trolley + x, y, lift + 1.4), .14, DARK, 4)
    g.place(container_grabber, x=trolley, z=lift, angle=90)


def boom(g, start, end):
    """The quay crane's boom truss from Y = start to end (multiples of PANEL): two Warren girders with posts at
    every joint; the diagonals alternate with the joint's index along the boom, so chained pieces continue it."""
    top = BOOM + BOOM_DEPTH
    joints = [start + PANEL * k for k in range(round((end - start) / PANEL) + 1)]
    for x in (-BOOM_HALF, BOOM_HALF):
        g.box((x, (start + end) / 2, BOOM - .3), (.7, end - start, .6), YELLOW)
        g.box((x, (start + end) / 2, top), (.55, end - start, .5), YELLOW)
        for a, b in zip(joints, joints[1:]):
            low, high = (a, b) if round(a / PANEL) % 2 == 0 else (b, a)
            g.beam((x, low, BOOM), (x, high, top), .3, YELLOW, 4)
        for y in joints: g.beam((x, y, BOOM), (x, y, top), .3, YELLOW, 4)
    for y in joints:
        g.beam((-BOOM_HALF, y, BOOM - .3), (BOOM_HALF, y, BOOM - .3), .35, YELLOW, 4)
        g.beam((-BOOM_HALF, y, top), (BOOM_HALF, y, top), .3, YELLOW, 4)


def crane_boom(g):
    """One hex of boom, centred: segments chain end to end in front of a quay crane's boom."""
    boom(g, -SEGMENT / 2, SEGMENT / 2)


def quay_crane(g):
    """A ship-to-shore crane: its portal stands in the hex half the boom points to (+Y), the boom runs from the
    backreach over the yard to the hex side; one crane boom segment beyond continues it over the quay."""
    land, water = LEGS_Y
    portal = BOOM - .9
    for x in (-LEGS_X, LEGS_X):
        for y in LEGS_Y:
            g.box((x, y, .8), (4.8, 2.2, 1.6), DARK)
            g.beam((x, y, 1.6), (x, y, portal), 1.4, YELLOW, 4)
        g.beam((x, land, 9.0), (x, water, 9.0), .9, YELLOW, 4)
        g.beam((x, land, 9.0), (x, water, portal - 1.5), .6, YELLOW, 4)
        g.box((x, (land + water) / 2, portal), (1.2, water - land + 2.4, 1.6), YELLOW)
        # The A-frame: front and rear struts meet at the apex above the waterside legs.
        g.beam((x, water, portal), (x * .25, water - 3.5, APEX), .9, YELLOW, 4)
        g.beam((x, land, portal), (x * .25, water - 4.5, APEX), .9, YELLOW, 4)
    for y in LEGS_Y: g.box((0, y, portal), (2 * LEGS_X + 1.2, 1.2, 1.4), YELLOW)  # inside the side girders' faces
    g.box((0, water - 4.0, APEX), (2 * LEGS_X * .25 + 1.0, 1.6, 1.0), YELLOW)
    boom(g, -9.0, 36.0)
    for x in (-1, 1):
        # Forestays to the boom's end at the hex side, backstays to the backreach.
        g.beam((x * LEGS_X * .25, water - 4.0, APEX), (x * BOOM_HALF, 36.0, BOOM + BOOM_DEPTH), .4, YELLOW, 4)
        g.beam((x * LEGS_X * .25, water - 4.0, APEX), (x * BOOM_HALF, -9.0, BOOM + BOOM_DEPTH), .4, YELLOW, 4)
    g.box((0, -4.5, BOOM + BOOM_DEPTH + 2.4), (8.0, 7.0, 4.4), WHITE)
    g.box((0, -4.5, BOOM + BOOM_DEPTH + 4.7), (8.4, 7.4, .3), STEEL)
    # Trolley and cab on the boom's rails, hoisting a container out over the quay side.
    g.box((0, 30.5, BOOM - .9), (5.4, 4.0, 1.2), STEEL)
    g.box((2.9, 30.5, BOOM - 3.0), (2.4, 2.8, 2.6), WHITE)
    g.box((2.9, 31.95, BOOM - 2.8), (2.0, .1, 1.6), GLASS)
    lift = 2 * TIER + 4.5
    for y in (28.9, 32.1):
        for x in (-1.5, 1.5): g.beam((x, y, BOOM - 1.4), (x, y, lift + 1.4), .14, DARK, 4)
    g.place(container_grabber, y=30.5, z=lift)
    g.place(lambda m: stacks(m, {(0, 0): [PAINT['Blue'][0]]}), y=30.5, z=lift - TIER, angle=90)


# ---- Props and skins ----------------------------------------------------------------------------------------------

def container(g):
    """A single container along Y, its paint colour slot 1."""
    g.colour_slots = [{'name': 'Paint', 'colour': colour_text(PAINT['Oxide red'][0]), 'presets': PRESETS}]
    g.slot = 1
    stacks(g, {(0, 0): [PAINT['Oxide red'][0]]})
    g.slot = 0


# Props: (draw, palette label, snap connectors [x, y, z, heading] in hex width/height and levels, or None).
PROPS = {
    'container': (container, 'Container', None),
    'container-stack-2': (lambda g: stack(g, 2), 'Container stack, two high', None),
    'container-stack-3': (lambda g: stack(g, 3), 'Container stack, three high', None),
    'quay-crane': (quay_crane, 'Quay crane', [[0, .5, BOOM / 18, 90]]),
    'crane-boom': (crane_boom, 'Crane boom segment', [[0, .5, BOOM / 18, 90], [0, -.5, BOOM / 18, 270]]),
    'yard-gantry': (lambda g: yard_gantry(g, TIERS['heavy']), 'Yard gantry', None),
    'yard-gantry-tall': (lambda g: yard_gantry(g, TIERS['ultra']), 'Yard gantry, tall', None),
    'straddle-carrier': (straddle_carrier, 'Straddle carrier', None),
    'reach-stacker': (reach_stacker, 'Reach stacker', None),
    'yard-truck': (yard_truck, 'Yard truck', None),
}


def row(asset, x=0.0, y=0.0, angle=0.0, colours=None):
    out = {'asset': asset, 'position': [round(x, 4), round(y, 4), 0.0], 'rotation': round(angle, 4), 'scale': 1.0}
    if colours: out['colours'] = colours
    return out


def heights(tiers, full, low, empty=0.0, edge=None):
    """A stack height rule: `full` of the stacks are `tiers` high, the rest 1 to `low` tiers lower; `edge` (columns)
    are lower more often, `empty` of the slots stay free."""
    def height(i, j, rng):
        if rng.random() < empty: return 0
        share = full * (.6 if edge and i in edge else 1)
        return tiers if rng.random() < share else max(1, tiers - rng.randint(1, low))
    return height


# Light cover's rows: three double rows (legacy seaport rows were double rows too), lanes between them.
LIGHT_ROWS = (-20.3, 0.0, 20.3)


def crane_yard(g, rng, mirrored):
    """Light cover with a quay crane: rows along N-S, the boom 60 degrees clockwise (NE), or anticlockwise (SE) when
    mirrored; the containers fill the half behind the portal."""
    boom_angle = -60.0 if not mirrored else -120.0  # the crane's turn: its +Y boom toward NE or SE
    d = (cos(radians(boom_angle + 90)), sin(radians(boom_angle + 90)))
    keep = lambda x, y: x * d[0] + y * d[1] < -.5
    n = 0
    # Double rows packed behind the portal (the rows of light cover would leave single stacks at the cut).
    for x in (-26.1, -10.3, 5.5, 21.3):
        n += block(g, rng, x, 0, 2, 5, heights(TIERS['light'], .7, 2, .04), keep=keep)
    return n, [row(YARD + 'quay-crane', angle=boom_angle),
               row(YARD + 'crane-boom', SEGMENT * d[0], SEGMENT * d[1], boom_angle),
               # A yard truck under the hoisted container, heading along the quay.
               row(YARD + 'yard-truck', 30.5 * d[0] + 1.5 * d[1], 30.5 * d[1] - 1.5 * d[0], boom_angle - 90,
                   [colour_text(PAINT['Tan'][0])])]


def layout(name):
    """The baked containers of one skin layout and its prop rows."""
    rng = random.Random(name)
    g = Mesh(); g.role = 'containers'
    rows = []
    if name == 'foliage-rows':
        n = sum(block(g, rng, x, y, 2, 2, heights(TIERS['foliage'], .45, 2, .12)) for x, y in
                ((-19, 12), (-19, -16), (0, 19), (0, -9), (19, 12), (19, -16)))
    elif name == 'foliage-scattered':
        n = 0
        for x, y, columns, angle in ((-20, 13, 1, 0), (-23, -12, 2, 0), (-6, 23, 1, 90), (2, 2, 2, 90),
                                     (-2, -22, 1, 90), (18, 17, 2, 0), (22, -8, 1, 0), (12, -24, 1, 90)):
            n += block(g, rng, x, y, columns, 1, heights(TIERS['foliage'], .4, 2), angle)
        rows.append(row(YARD + 'reach-stacker', -9.5, -6.0, 60.0))
    elif name == 'light-rows':
        n = sum(block(g, rng, x, 0, 2, 5, heights(TIERS['light'], .62, 2, .05)) for x in LIGHT_ROWS)
        rows.append(row(YARD + 'yard-truck', 10.15, -4.0, 0.0, [colour_text(PAINT['Green'][0])]))
    elif name in ('light-quay-crane', 'light-quay-crane-mirrored'):
        n, rows = crane_yard(g, rng, name.endswith('mirrored'))
    elif name == 'light-yard-gantry':
        n = block(g, rng, 0, 0, 6, 3, heights(TIERS['light'], .75, 2, .06))
        n += sum(block(g, rng, x, 0, 1, 5, heights(TIERS['light'], .5, 3, .1)) for x in (-27.5, 27.5))
        rows += [row(YARD + 'yard-gantry', 0, -6.6), row(YARD + 'yard-truck', -21.0, 14.0, 0.0)]
    elif name == 'heavy-rows':
        n = sum(block(g, rng, x, 0, 3, 5, heights(TIERS['heavy'], .9, 1, .02)) for x in (-23.2, 0.0, 23.2))
    elif name == 'heavy-yard-gantry':
        n = block(g, rng, 0, 0, 6, 5, heights(TIERS['heavy'], .88, 1, .02))
        n += sum(block(g, rng, x, 0, 1, 5, heights(TIERS['heavy'], .8, 2, .05)) for x in (-27.5, 27.5))
        rows.append(row(YARD + 'yard-gantry', 0, 6.6))
    elif name == 'ultra-rows':
        n = sum(block(g, rng, x, 0, 5, 5, heights(TIERS['ultra'], .78, 2, .0, edge=(0, 4))) for x in (-16.5, 16.5))
    elif name == 'ultra-yard-gantry':
        n = block(g, rng, 0, 0, 6, 5, heights(TIERS['ultra'], .82, 2, .0))
        n += sum(block(g, rng, x, 0, 1, 5, heights(TIERS['ultra'], .7, 3)) for x in (-27.5, 27.5))
        rows.append(row(YARD + 'yard-gantry-tall', 0, -6.6))
    else: raise ValueError(name)
    return g, n, [row(YARD + name)] + rows


# Skin layouts per cover level (the woods' foliage elevation 1, light, heavy, ultra-heavy woods).
LAYOUTS = {'foliage': ['foliage-rows', 'foliage-scattered'],
           'light': ['light-rows', 'light-quay-crane', 'light-quay-crane-mirrored', 'light-yard-gantry'],
           'heavy': ['heavy-rows', 'heavy-yard-gantry'],
           'ultra': ['ultra-rows', 'ultra-yard-gantry']}


def check_fit(name, rows, meshes):
    """Every part of a skin but its quay crane lies within the hex's inscribed circle, so all twelve rotation steps
    keep it inside the hex (the crane's boom reaches over the neighbour hex by design)."""
    for r in rows:
        if r['asset'] in (YARD + 'quay-crane', YARD + 'crane-boom'): continue
        v, (x, y, _), turn = meshes[r['asset']].vertices, r['position'], radians(r['rotation'])
        reach = max(((x + v[i] * cos(turn) - v[i + 1] * sin(turn)) ** 2 + (y + v[i] * sin(turn) + v[i + 1] * cos(turn))
                     ** 2) ** .5 for i in range(0, len(v), 12))
        assert reach <= 36.0, '%s: %s reaches %.1f px from the hex centre' % (name, r['asset'], reach)


def build():
    """Export the props and skins; return their sizes and the props' palette cards (data/board-editor/blueprint.json
    assets)."""
    report, meshes, cards = {}, {}, []
    for name, (function, label, connectors) in PROPS.items():
        g = Mesh(); g.role = 'containers' if name.startswith('container') else 'machinery'
        function(g)
        export_mesh(YARD + name, g)
        meshes[YARD + name] = g
        report[name] = len(g.vertices) // 12
        cards.append({'id': YARD + name, 'label': label, 'kind': 'prop', 'group': 'Seaport'})
        if connectors:
            cards[-1]['snap'] = {'set': 'crane-boom', 'radius': .06, 'angleTolerance': 2,
                                 'connectors': [[round(v, 4) for v in c] for c in connectors]}
    skins = {}
    for level, names in LAYOUTS.items():
        for name in names:
            g, n, rows = layout(name)
            meshes[YARD + name] = g
            check_fit(name, rows, meshes)
            export_mesh(YARD + name, g)
            skins[name] = rows
            report[name] = {'vertices': len(g.vertices) // 12, 'containers': n}
    path = BOARD / 'scenery/seaport/yard/skins.json'
    path.write_text(json.dumps(skins, indent=2) + '\n')
    report['cards'] = cards
    return report


if __name__ == '__main__':
    print(json.dumps(build(), indent=1))
