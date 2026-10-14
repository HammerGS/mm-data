"""Build the imagegen-inspired Martian coral kit through Blender MCP.

Run: runpy.run_path(path)['build'](). Creates an independent scene, preserving
existing Blender work. Export uses the same rigid GLB writer as the fungus kit.
All four mesh levels have a common Z-up origin and 30-unit mature height.
"""
from math import cos, exp, pi, sin
from pathlib import Path
import json
import random
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_foliage_assets import Plant, blender_mesh
from build_fungus_assets import quad, solid_material, tri, tube
from glb_geometry import linear, read_glb, write_glb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/models/board/mars'
REVIEW = ROOT / 'tools/board-models/mars'
SOURCE = ROOT / 'tools/board-mars-corals-expanded.blend'
TEXTURE = ROOT / 'data/models/board/textures/vegetation/mars/coral-mineral-atlas.png'
FORMS = ('finger-spires', 'fan-scalloped', 'tube-grove',
         'finger-crown', 'fan-folded', 'tube-crown',
         'antler-crown', 'plate-terraces', 'brain-lobes',
         'organ-pipes', 'spiral-whorls', 'lattice-spires')
BUDGETS = (16000, 4200, 1000, 240)


def smooth_path(points, radii, steps=5):
    """Round the growth paths before fusing them into a single mineral body."""
    path, sizes = [], []
    for i in range(len(points) - 1):
        a, b, c, d = [Vector(points[max(0, min(len(points)-1, k))]) for k in (i-1, i, i+1, i+2)]
        for j in range(steps):
            t = j / steps
            path.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
            sizes.append(radii[i]*(1-t) + radii[i+1]*t)
    return path + [Vector(points[-1])], sizes + [radii[-1]]


def strand(g, points, radii):
    path, sizes = smooth_path(points, radii)
    tube(g, path, sizes, 'coral', 12)


def shell(g, rings):
    """Join a closed mineral profile, including its small end caps."""
    sides = len(rings[0])
    for row in range(len(rings)-1):
        for j in range(sides):
            k = (j+1) % sides
            quad(g, rings[row][j], rings[row][k], rings[row+1][k], rings[row+1][j], 'coral')
    for ring, reverse in ((rings[0], True), (rings[-1], False)):
        for j in range(1, sides-1):
            pts = (ring[0], ring[j], ring[j+1])
            tri(g, *(reversed(pts) if reverse else pts), 'coral')


def fingers(g, variant):
    rng = random.Random(90 + variant)
    tips = []
    for i in range(6 if variant == 0 else 8):
        angle = i * 2.39996 + variant
        reach = 2.5 + (i % 3) * 1.4
        h = (24, 20, 23, 16, 13, 18, 12, 15)[i]
        start = Vector((cos(angle)*reach*.45, sin(angle)*reach*.45, .2))
        end = Vector((cos(angle)*reach*1.6, sin(angle)*reach*1.6, h))
        middle = start.lerp(end, .57) + Vector((sin(angle)*2.1, cos(angle)*1.5, 0))
        neck = end - Vector((.2*cos(angle), .2*sin(angle), 1.5))
        strand(g, [start, middle*.70 + start*.30, middle, neck,
                   end-Vector((0, 0, .65)), end-Vector((0, 0, .2)), end],
               [1.8, 1.65, 1.6, 1.4, 1.13, .62, .05])
        tips.append(end)
        for j in range(3 if i < 2 else 2 if i < 4 else 1):
            base = start.lerp(end, .32 + j*.21)
            side = angle + (1 if j else -1)*(.65 + rng.random()*.3)
            target = base + Vector((cos(side)*(4+j), sin(side)*(4+j), 5.5 + rng.random()*2))
            strand(g, [base, base.lerp(target, .55), target-Vector((0, 0, 1.0)),
                       target-Vector((0, 0, .4)), target-Vector((0, 0, .12)), target],
                   [1.2, 1.3, 1.13, .88, .48, .05])
            tips.append(target)
    return tips, []


def fan_cells(outline, seeds):
    """Clip Voronoi cells to the fan outline, avoiding rows of mechanical-looking holes."""
    for seed in seeds:
        polygon = list(outline)
        for other in seeds:
            if seed is other:
                continue
            normal = other-seed
            limit = (other.length_squared-seed.length_squared)/2
            clipped = []
            for i, a in enumerate(polygon):
                b = polygon[(i+1) % len(polygon)]
                da, db = a.dot(normal)-limit, b.dot(normal)-limit
                if da <= 0:
                    clipped.append(a)
                if (da < 0) != (db < 0):
                    clipped.append(a.lerp(b, da/(da-db)))
            polygon = clipped
            if not polygon:
                break
        if len(polygon) >= 3:
            yield polygon


def fan(g, variant, lod=0):
    """Wavy mineral fans with irregular pores, rolled edges and branching structural veins."""
    for leaf in range(min(2 if variant == 0 else 3, (3, 3, 2, 1)[lod])):
        scale = (1, .68, .48)[leaf]
        turn = (0, 1.35, -1.1)[leaf] + variant*.27
        rng = random.Random(910 + variant*7 + leaf)
        outline = [Vector((0, 0))]
        for j in range(33):
            a = -1.12+2.24*j/32
            r = 1+.055*sin(a*10+variant)+.018*sin(a*23+leaf)
            outline.append(Vector((18*sin(a)*r, 26*cos(a)*r)))
        seeds = []
        while len(seeds) < (48, 28, 12, 5)[lod]:
            a, r = rng.uniform(-1.12, 1.12), rng.uniform(.10, .97)**.5
            p = Vector((18*sin(a)*r, 26*cos(a)*r))
            if all((p-q).length > (1.5, 2, 3, 4)[lod] for q in seeds):
                seeds.append(p)

        def point(p, offset=0):
            x, z = p
            y = .075*x + .07*x*x/18 + .75*sin(x*.35+z*.19+leaf) + 1.8*(z/26)**2
            y += offset
            x, y, z = x*scale, y*scale, z*scale
            return Vector((x*cos(turn)-y*sin(turn), x*sin(turn)+y*cos(turn), z+1.6))

        for corners in fan_cells(outline, seeds):
            center = sum(corners, Vector((0, 0)))/len(corners)
            # Round polygon corners before shrinking them into a pore; cell sizes/positions are irregular.
            outer = [p.lerp(corners[(i+1) % len(corners)], t) for i, p in enumerate(corners) for t in (0, .5)]
            aperture = rng.uniform(.43, .65)
            inner = [center+((p*.50+outer[i-1]*.25+outer[(i+1) % len(outer)]*.25)-center)*aperture
                     for i, p in enumerate(outer)]
            for i in range(len(outer)):
                n = (i+1) % len(outer)
                quad(g, point(outer[i], .48), point(outer[n], .48), point(inner[n], .34), point(inner[i], .34), 'coral')
                quad(g, point(outer[n], -.48), point(outer[i], -.48), point(inner[i], -.34), point(inner[n], -.34), 'coral')
                quad(g, point(inner[i], .34), point(inner[n], .34), point(inner[n], -.34), point(inner[i], -.34), 'coral')
                quad(g, point(outer[n], .48), point(outer[i], .48), point(outer[i], -.48), point(outer[n], -.48), 'coral')
        for j in range(7 if lod < 2 else 4):
            a = -1.05+j*2.1/(6 if lod < 2 else 3)
            end = Vector((17*sin(a), 25*cos(a)))
            strand(g, [point(Vector((0, 0)), -.1), point(end*.35, -.68),
                       point(end*.68, -.7), point(end*.98, -.55)],
                   [1.0*scale, .75*scale, .52*scale, .10*scale])
    return [], []


def trumpets(g, variant):
    mouths = []
    for i in range(6 if variant == 0 else 7):
        angle = i*2.39996 + variant*.8
        spread = 0 if i == 0 else 5.0 + (i % 2)*1.7
        h = (24, 15, 19, 11, 17, 8, 12)[i]
        radius = (5.0, 3.8, 4.1, 3.6, 3.9, 2.8, 3.3)[i]
        origin = Vector((cos(angle)*spread, sin(angle)*spread, .2))
        bend = Vector((cos(angle)*4, sin(angle)*4, 0))
        profile = ((.70, 0), (.72, .08), (.61, .20), (.50, .38), (.53, .53), (.70, .72), (.94, .89),
                   (1.10, .98), (1.12, 1.025), (1.06, 1.055), (.96, 1.06), (.86, 1.025),
                   (.77, .94), (.57, .78), (.39, .58), (.22, .39), (.02, .28))
        rings, sides = [], 72
        for r, z in profile:
            ring = []
            for j in range(sides):
                a = j*2*pi/sides
                ripple = 1+.085*sin(5*a+i)+.04*sin(9*a-i)+.018*sin(17*a+z*3)
                wave = (.034*sin(3*a+i)+.012*sin(7*a-i))*min(z, 1)**4
                ring.append(origin + bend*z*z + Vector((radius*r*cos(a)*ripple,
                            radius*r*sin(a)*ripple, h*(z+wave))))
            rings.append(ring)
        shell(g, rings)
        mouths.append((origin + bend + Vector((0, 0, h)), radius, h, origin, bend))
    return [], mouths


def antlers(g):
    """Open, twice-forked staghorns rather than the original blunt finger thicket."""
    tips = []
    for i in range(5):
        a = i*2.39996 + .3
        axis = Vector((cos(a), sin(a), 0))
        side = Vector((-sin(a), cos(a), 0))
        start = axis*1.6 + Vector((0, 0, .3))
        fork = axis*(3.6+i*.55) + Vector((0, 0, (12, 10, 9, 7, 8)[i]))
        top = axis*(6+i*.75) + Vector((0, 0, (29, 24, 21, 18, 22)[i]))
        strand(g, [start, start.lerp(fork, .55)-side*.7, fork, fork.lerp(top, .55), top],
               [2.0, 1.65, 1.2, .75, .08])
        tips.append(top)
        for j in range(3):
            root = fork.lerp(top, .12+j*.23)
            direction = side*(1 if j % 2 else -1)
            tip = root + direction*(4.6-j*.65) + axis*1.0 + Vector((0, 0, 4.8-j*.3))
            joint = root.lerp(tip, .55)
            strand(g, [root, joint, tip], [.9-j*.13, .60-j*.08, .06])
            twig = joint + axis*1.8 + Vector((0, 0, 3.2))
            strand(g, [joint, joint.lerp(twig, .5), twig], [.46, .30, .05])
            tips.extend((tip, twig))
    return tips, []


def plates(g):
    """Thick ruffled shelves with radial mineral ribs and staggered heights."""
    for i, (x, y, h, radius) in enumerate(((0, 1, 25, 8.2), (-4, 0, 17, 9),
                                          (4, 3, 21, 8), (5, -3, 12, 9),
                                          (-5, -3, 8, 7.5), (0, 5, 6, 6))):
        origin = Vector((x, y, h))
        strand(g, [(x*.25, y*.25, .5), (x*.7, y*.7, h*.55), origin], [2.5, 1.9, 2.3])
        # Underside grows out of the stem; the upper surface returns to the centre.
        profile = ((.06, -.55), (.24, -.48), (.45, -.42), (.68, -.38), (.86, -.34),
                   (1, -.22), (1.02, 0), (1, .26), (.85, .32), (.65, .32),
                   (.42, .32), (.20, .32), (.015, .30))
        rings = []
        for r, z in profile:
            ring = []
            for j in range(112):
                a = j*2*pi/112
                scallop = 1+.075*sin(a*7+i)+.028*sin(a*13-i)
                wave = (1.0*sin(a*5+i)+.42*sin(a*11-i))*r**3
                ribs = .20*sin(a*29 + r*3)*r
                ring.append(origin + Vector((radius*r*cos(a)*scallop,
                                             radius*r*sin(a)*scallop*.88,
                                             z + 1.3*r*r + wave + ribs)))
            rings.append(ring)
        shell(g, rings)
    return [], []


def brains(g):
    """Three fused domes with an actual sculpted labyrinth, visible without a normal map."""
    for i, (center, radii) in enumerate((((0, 2.5, 12), (6.8, 6, 13)),
                                       ((-5.2, -3, 7.5), (5.6, 5, 8.2)),
                                       ((6, -.5, 9), (5.3, 4.8, 10)))):
        rings = []
        for row in range(97):
            t = .001 + (pi-.002)*row/96
            ring = []
            for col in range(144):
                a = col*2*pi/144
                field = sin(t*13 + 2.6*sin(a*3+t*1.5+i) + .7*sin(a*7-t*3))
                ridge = 1.15*exp(-field*field*6)*sin(t)**.35
                ripple = .05*sin(a*9+t*13+i)
                ring.append(Vector(center) + Vector(((radii[0]+ridge+ripple)*sin(t)*cos(a),
                                                     (radii[1]+ridge+ripple)*sin(t)*sin(a),
                                                     (radii[2]+ridge)*cos(t))))
            rings.append(ring)
        shell(g, rings)
    return [], []


def organs(g):
    """Narrow open chimneys; cylindrical walls distinguish them from the trumpet kit."""
    mouths = []
    for i, h in enumerate((28, 22, 24, 19, 15, 23, 12, 17, 10, 14, 8)):
        a = i*2.39996
        spread = 0 if i == 0 else 3.5+(i % 3)*1.8
        origin = Vector((cos(a)*spread, sin(a)*spread, .25))
        bend = Vector((cos(a)*1.7, sin(a)*1.7, 0))
        radius = 2.05+(i % 3)*.18
        profile = ((1.2, 0), (1.02, .08), (.92, .25), (.88, .50), (.94, .75),
                   (1, .96), (1.02, 1), (.98, 1.025), (.78, 1.025), (.74, .99),
                   (.68, .87), (.62, .70), (.02, .60))
        rings = []
        for r, z in profile:
            ring = []
            for j in range(64):
                angle = j*2*pi/64
                flutes = 1+.035*sin(angle*13+i)+.018*sin(angle*21+z*4)
                rim = .010*sin(angle*5+i)*z**4
                ring.append(origin+bend*z*z+Vector((radius*r*cos(angle)*flutes,
                                                    radius*r*sin(angle)*flutes, h*(z+rim))))
            rings.append(ring)
        shell(g, rings)
        mouths.append((origin+bend+Vector((0, 0, h)), radius, h, origin, bend))
    return [], mouths


def spirals(g):
    """Three open crozier curls with a continuous tapered mineral body."""
    tips = []
    for scale, turn, offset in ((1, .10, (0, 2, 0)), (.72, -.65, (-5, -2, 0)),
                                (.60, 1.20, (5, -1, 0))):
        axis = Vector((cos(turn), sin(turn), 0))
        side = Vector((-sin(turn), cos(turn), 0))
        base = Vector(offset)
        points = [base+Vector((0, 0, .3)), base+axis*3*scale+Vector((0, 0, 7*scale)),
                  base+axis*6.7*scale+Vector((0, 0, 13*scale))]
        radii = [3*scale, 2.75*scale, 2.55*scale]
        for j in range(81):
            t = j/80
            angle = t*1.85*pi
            radius = (7.4-6.2*t)*scale
            points.append(base + axis*(cos(angle)*radius) + side*(.7*sin(angle)*scale)
                          + Vector((0, 0, 18*scale+sin(angle)*radius)))
            radii.append(scale*(2.5*(1-t)**.70+.06))
        tube(g, points, radii, 'coral', 24)
        tips.append(points[-1])
    return tips, []


def lattice(g, lod=0):
    """A volumetric basket with jagged spires and irregular cellular windows."""
    outline = [Vector(p) for p in ((0, 1), (8, 0), (15, 1), (16, 17), (13, 23),
                                  (11, 18), (8, 29), (5, 21), (2, 25), (0, 18))]
    rng = random.Random(771)
    seeds = [Vector((rng.uniform(.3, 15.7), rng.uniform(1, 25))) for _ in range((34, 20, 10, 5)[lod])]
    for panel in range(3):
        turn = panel*2*pi/3

        def point(p):
            u, z = p
            x, y = u-8, 4.8 + .65*sin(u*.5+z*.3+panel)
            taper = .70+.30*sin(min(1, z/25)*pi)
            return Vector(((x*cos(turn)-y*sin(turn))*taper,
                           (x*sin(turn)+y*cos(turn))*taper, z+1))

        for polygon in fan_cells(outline, seeds):
            # Shared Voronoi edges fuse into rounded ribs, leaving genuinely open windows.
            for j, a in enumerate(polygon):
                b = polygon[(j+1) % len(polygon)]
                middle = a.lerp(b, .5)
                radius = (.58, .75, .92, 1.12)[lod]
                strand(g, [point(a), point(middle), point(b)], [radius, radius*.88, radius])
    return [], []


def shape(name, lod=0):
    g = Plant()
    variant = FORMS.index(name)//3
    family = name.split('-')[0]
    if family == 'fan':
        tips, mouths = fan(g, variant, lod)
    elif family in ('finger', 'tube'):
        tips, mouths = {'finger': fingers, 'tube': trumpets}[family](g, variant)
    elif family == 'lattice':
        tips, mouths = lattice(g, lod)
    else:
        tips, mouths = {'antler': antlers, 'plate': plates, 'brain': brains,
                        'organ': organs, 'spiral': spirals}[family](g)
    # Fused low encrustation, without a woody trunk or a circular display base in the export.
    rng = random.Random(121 + variant)
    g.lobe((0, 0, .48), (5.7, 5.0, .95), role='coral')
    for i in range(40):
        a, r = rng.random()*2*pi, rng.random()*7.3
        size = (.35+rng.random()) * (1.8 if i < 16 else .8)
        g.lobe((cos(a)*r, sin(a)*r, .38+rng.random()*.7),
               (size*1.4, size, size*.8), role='coral')
    return g, family, tips, mouths


def mineral_texture():
    """The imagegen material atlas is an unmodified, reproducible authoring input."""
    image = bpy.data.images.load(str(TEXTURE), check_existing=False)
    image.pack()
    return image


def material(image):
    mat = solid_material('Mars / mineral coral', (.8, .7, .6), .93)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    color = nodes.new('ShaderNodeVertexColor')
    color.layer_name = 'Coral color'
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    multiply = nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1
    links.new(color.outputs['Color'], multiply.inputs[1])
    links.new(texture.outputs['Color'], multiply.inputs[2])
    links.new(multiply.outputs[0], nodes.get('Principled BSDF').inputs['Base Color'])
    return mat


def select(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def simplify(obj, budget):
    select(obj)
    obj.data.calc_loop_triangles()
    count = len(obj.data.loop_triangles)
    if count > budget:
        mod = obj.modifiers.new('Authored mesh budget', 'DECIMATE')
        mod.ratio = budget/count
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.update()


def color_at(p, family, tips, mouths):
    blend = lambda a, b, t: tuple(x*(1-t)+y*t for x, y in zip(a, b))
    # Pigment and fine pores come from the atlas. Vertex tint supplies gentle growth/crevice variation only.
    base = (.98, .97, .94)
    if family in ('finger', 'antler', 'spiral'):
        distance = min((p-tip).length for tip in tips)
        pigment = (.57, .83, .78) if family == 'spiral' else (1, .82, .66)
        base = blend(base, pigment, max(0, 1-distance/3.0)*.75)
    elif family in ('fan', 'plate', 'lattice'):
        base = blend((.83, .80, .83), base, max(0, min(1, p.z/30)))
    else:
        for center, radius, height, origin, bend in mouths:
            z = (p.z-origin.z)/height
            axis = origin+bend*z*z
            distance = (Vector((p.x, p.y, 0))-Vector((axis.x, axis.y, 0))).length
            if z > .72 and distance < radius*1.15:
                rim = max(0, min(1, (z-.77)/.22))
                base = blend(base, (.70, .91, .86), rim*.55)
                # Recessed inside walls retain depth under the game's simple diffuse material.
                if distance < radius*.68 and z < .97:
                    base = blend(base, (.39, .43, .40), .65)
                break
    dust = max(0, 1-p.z/7)*.23
    return blend(base, (1, .79, .61), dust)


def finish(obj, family, tips, mouths, normalization):
    mesh = obj.data
    uv = mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
    colors = mesh.color_attributes.new(name='Coral color', type='FLOAT_COLOR', domain='CORNER')
    low, scale = normalization
    # Sample color in the original sculpture's coordinates, identical for all detail levels.
    for face in mesh.polygons:
        dominant = max(range(3), key=lambda k: abs(face.normal[k]))
        axes = (0, 1) if dominant == 2 else (0, 2) if dominant == 1 else (1, 2)
        center = face.center
        basal = center.z < 3.9 + .65*sin(center.x*1.7+center.y*2.1)
        panel = 3 if basal else {'finger': 0, 'antler': 0, 'brain': 0, 'spiral': 0,
                                'fan': 1, 'plate': 1, 'lattice': 1, 'tube': 2, 'organ': 2}[family]
        for loop in face.loop_indices:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co
            source = p/scale + Vector((0, 0, low))
            color = color_at(source, family, tips, mouths)
            colors.data[loop].color = (*[linear(c) for c in color], 1)
            u = max(0, min(1, (p[axes[0]]+20)/40))
            v = max(0, min(1, p.z/30 if axes[1] == 2 else (p[axes[1]]+20)/40))
            uv.data[loop].uv = (panel % 2*.5+.012+u*.476, (1-panel//2)*.5+.012+v*.476)


def mesh_model(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    vertices, shared, indices = [], {}, []
    from glb_geometry import display
    for face in mesh.loop_triangles:
        for loop in face.loops:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co
            normal = mesh.corner_normals[loop].vector
            color = mesh.color_attributes['Coral color'].data[loop].color
            uv = mesh.uv_layers.active.data[loop].uv
            vertex = tuple(round(v, 7) for v in (*p, *normal, *(display(v) for v in color[:3]), 1, uv.x, 1-uv.y))
            if vertex not in shared:
                shared[vertex] = len(vertices)//12
                vertices.extend(vertex)
            indices.append(shared[vertex])
    return {'id': obj.name, 'meshes': [{'attributes': ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'],
            'vertices': vertices, 'parts': [{'id': 'coral', 'type': 'TRIANGLES', 'indices': indices}]}],
            'materials': [{'id': 'coral', 'diffuse': [1, 1, 1], 'textures': [{'id': 'mineral-pores',
                'type': 'DIFFUSE', 'filename': '../textures/vegetation/mars/coral-mineral-atlas.png',
                'wrapS': 33071, 'wrapT': 33071}]}],
            'nodes': [{'id': obj.name, 'parts': [{'meshpartid': 'coral', 'materialid': 'coral'}]}]}


def review(scene, assets):
    sand = solid_material('Mars / display soil', (.48, .24, .13))
    center = Vector((0, (len(assets)-1)//3*22.5, 10))
    for index, objects in enumerate(assets.values()):
        x, y = (index % 3-1)*38, (index//3)*45
        for obj in objects:
            obj.location = (x, y, 0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=19, depth=1.5, location=(x, y, -.85))
        plinth = bpy.context.object
        plinth.name = 'Display only / hex soil'
        plinth.data.materials.append(sand)
    world = bpy.data.worlds.new('Mars / review sky')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.22, .28, .36, 1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .6
    scene.world = world
    for name, location, energy, size in (('Key', (20, -40, 100), 210000, 75),
                                         ('Fill', (-70, 10, 55), 110000, 65)):
        light = bpy.data.lights.new('Mars / '+name, 'AREA')
        light.energy, light.shape, light.size = energy, 'DISK', size
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = Vector(location) + Vector((0, center.y-20, 0))
        obj.rotation_euler = (center-obj.location).to_track_quat('-Z', 'Y').to_euler()
    camera = bpy.data.objects.new('Mars / kit overview', bpy.data.cameras.new('Mars / kit overview'))
    scene.collection.objects.link(camera)
    camera.location = center + Vector((35, -155, 165))
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type, camera.data.ortho_scale, camera.data.clip_end = 'ORTHO', 195, 1000
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    scene.render.filepath = str(REVIEW/'coral-library-expanded.png')


def weather_surface(obj, seed):
    """Sculpt shallow mineral pits into the near mesh; lower meshes simplify the same surface."""
    mesh = obj.data
    mesh.update()
    rng = random.Random(seed)
    candidates = [v for v in mesh.vertices if v.co.z > 2]
    chosen = rng.sample(candidates, min(650, len(candidates)))
    pores = [(v.co.copy(), rng.uniform(.28, .65), rng.uniform(.07, .18)) for v in chosen]
    tree = KDTree(len(pores))
    for i, (center, _, _) in enumerate(pores):
        tree.insert(center, i)
    tree.balance()
    normals = [v.normal.copy() for v in mesh.vertices]
    for vertex, normal in zip(mesh.vertices, normals):
        p = vertex.co.copy()
        displacement = .025*sin(p.x*7+p.y*3)*sin(p.z*5-p.y*8)
        for _, i, distance in tree.find_range(p, .72):
            _, radius, depth = pores[i]
            d = distance/radius
            displacement -= depth*exp(-d*d*4)
            displacement += depth*.17*exp(-(d-.8)**2*25)
        vertex.co += normal*displacement
    mesh.update()


def sculpt(scene, name, mat, lod=0):
    g, family, tips, mouths = shape(name, lod)
    obj = blender_mesh(scene, name+'-mesh'+str(lod), g, {'coral': mat})
    select(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    remesh = obj.modifiers.new('Fuse coral tissue', 'REMESH')
    remesh.mode, remesh.voxel_size, remesh.use_remove_disconnected = 'VOXEL', .13 if lod == 0 else .20, False
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    smooth = obj.modifiers.new('Round mineral growth', 'SMOOTH')
    smooth.factor, smooth.iterations = .6, 3
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    if lod == 0:
        weather_surface(obj, 1973+FORMS.index(name))
    return obj, family, tips, mouths


def build():
    if bpy.context.mode != 'OBJECT':
        raise RuntimeError('The existing scene must be in Object mode.')
    scene = bpy.data.scenes.new('Mars / mineral coral library')
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'NONE'
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    mat = material(mineral_texture())
    collections = []
    for lod in range(4):
        collection = bpy.data.collections.new('Mars / LOD'+str(lod))
        scene.collection.children.link(collection)
        collection.hide_render = lod != 0
        collections.append(collection)
    assets, report = {}, {}
    for name in FORMS:
        print('Authoring Mars coral: '+name, flush=True)
        obj, family, tips, mouths = sculpt(scene, name, mat)
        low = min(v.co.z for v in obj.data.vertices)
        high = max(v.co.z for v in obj.data.vertices)
        scale = 30/(high-low)
        for v in obj.data.vertices:
            v.co.z -= low
            v.co *= scale
        simplify(obj, BUDGETS[0])
        objects = [obj]
        for lod in range(1, 4):
            if family in ('fan', 'lattice'):
                # Fewer pores at distance preserve open silhouettes without a topology floor on decimation.
                child, _, _, _ = sculpt(scene, name, mat, lod)
                for v in child.data.vertices:
                    v.co.z -= low
                    v.co *= scale
            else:
                child = bpy.data.objects.new(name+'-mesh'+str(lod), obj.data.copy())
                scene.collection.objects.link(child)
            simplify(child, BUDGETS[lod])
            objects.append(child)
        levels, counts = {}, []
        for lod, piece in enumerate(objects):
            # Keep the root and full cover height exact even after decimation.
            z0, z1 = min(v.co.z for v in piece.data.vertices), max(v.co.z for v in piece.data.vertices)
            for v in piece.data.vertices:
                v.co.z = (v.co.z-z0)*30/(z1-z0)
            piece.data.update()
            finish(piece, family, tips, mouths, (low, scale))
            levels[lod] = mesh_model(piece)
            count = len(levels[lod]['meshes'][0]['parts'][0]['indices'])//3
            counts.append(count)
            assert 0 < count <= BUDGETS[lod] + 4, (name, lod, count)
            piece['family'], piece['lod'], piece['attachment'] = family, lod, 'Ground root Z=0'
            scene.collection.objects.unlink(piece)
            collections[lod].objects.link(piece)
        write_glb(OUT/(name+'.glb'), levels=levels)
        for lod, count in enumerate(counts):
            data = read_glb(OUT/(name+'.glb'), lod)
            assert sum(len(p['indices'])//3 for m in data['meshes'] for p in m['parts']) == count
        report[name] = {'triangles': counts, 'height': 30,
                        'bounds': [[round(fn(v.co[k] for v in obj.data.vertices), 4) for k in range(3)] for fn in (min, max)]}
        assets[name] = objects
    for lod in range(1, 4):
        collections[lod].hide_viewport = True
    review(scene, assets)
    bpy.context.view_layer.update()
    bpy.data.libraries.write(str(SOURCE), {scene}, path_remap='RELATIVE_ALL', fake_user=True, compress=True)
    (REVIEW/'mesh-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return {'scene': scene.name, 'source': str(SOURCE), 'assets': report, 'render': scene.render.filepath}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
