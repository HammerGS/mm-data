"""Rebuild the road tunnel portal in Blender. Leaves existing scenes untouched.

Run with Blender --background --python tools/build_tunnel_asset.py, or runpy
through Blender MCP. Dimensions are board units: Z up, +Y into the cliff.
The opening has half-width 9.5, spring height 6 and a 9.5-radius arch.
BoardTunnel clips the terrain to this same opening; keep those dimensions in sync.
"""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_geometry import linear, write_glb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/models/board'
SOURCE = ROOT / 'tools/board-models'
SCENE = bpy.data.scenes.new('Road tunnel portal')
PARTS = {}


def part(name, color, texture):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .92
    image = bpy.data.images.load(str(OUT / 'textures' / texture), check_existing=True)
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    colors = mat.node_tree.nodes.new('ShaderNodeVertexColor')
    colors.layer_name = 'Color'
    multiply = mat.node_tree.nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1
    mat.node_tree.links.new(node.outputs['Color'], multiply.inputs[1])
    mat.node_tree.links.new(colors.outputs['Color'], multiply.inputs[2])
    mat.node_tree.links.new(multiply.outputs[0], shader.inputs['Base Color'])
    PARTS[name] = {'mat': mat, 'texture': texture, 'color': color, 'verts': [], 'faces': [], 'colors': []}


part('tunnel-portal', (.94, .94, .92), 'scenery/tunnel-concrete.png')
part('tunnel-wings', (.94, .94, .92), 'scenery/tunnel-concrete.png')
part('tunnel-lining', (.72, .72, .70), 'scenery/tunnel-concrete.png')
part('tunnel-floor', (1, 1, 1), 'roads/asphalt.png')


def face(role, points, shade=1):
    p = PARTS[role]
    first = len(p['verts'])
    p['verts'].extend(points)
    p['faces'].append(tuple(range(first, first + len(points))))
    p['colors'].append(shade)


def box(x0, x1, y0, y1, z0, z1):
    v = [(x0,y0,z0), (x1,y0,z0), (x1,y1,z0), (x0,y1,z0),
         (x0,y0,z1), (x1,y0,z1), (x1,y1,z1), (x0,y1,z1)]
    for indices in [(0,4,7,3), (1,2,6,5), (0,1,5,4), (3,7,6,2), (4,5,6,7), (0,3,2,1)]:
        face('tunnel-portal', [v[i] for i in indices])


# The bevel has real thickness. The arch's 16 segments match the terrain aperture.
N, R, SPRING = 16, 9.5, 6
inner = [(R*math.cos(i*math.pi/N), SPRING+R*math.sin(i*math.pi/N)) for i in range(N+1)]
outer = [(11.25*math.cos(i*math.pi/N), SPRING+11.25*math.sin(i*math.pi/N)) for i in range(N+1)]
for i in range(N):
    a,b = inner[i:i+2]
    c,d = outer[i:i+2]
    face('tunnel-portal', [(a[0],0,a[1]), (c[0],.3,c[1]), (d[0],.3,d[1]), (b[0],0,b[1])])
    face('tunnel-portal', [(c[0],.3,c[1]), (c[0],.3,18.5), (d[0],.3,18.5), (d[0],.3,d[1])], .94)
# One shell, without box faces overlapping the interior lining. The external
# sides and roof extend the full depth so the portal also slots into sloped rock.
for s in (-1,1):
    for x0,x1,y0,z1 in ((9.5,11.25,0,6),(11.25,13,.3,18.5)):
        points = [(s*x0,y0,0),(s*x1,.3,0),(s*x1,.3,z1),(s*x0,y0,z1)]
        face('tunnel-portal', points if s == 1 else points[::-1])
    face('tunnel-portal', [(s*13,.3,0),(s*13,18,0),(s*13,18,18.5),(s*13,.3,18.5)][::s])
box(-13.3,13.3,-.05,18,18.5,19.2)
# Flared wing walls carry the cut into the approach, outside the unchanged road width.
for s in (-1,1):
    a,b,c,d = (s*11.25,.3,0),(s*16,-6,0),(s*16,-6,3.5),(s*11.25,.3,8)
    back = [(x+s*1.4,y,z) for x,y,z in (a,b,c,d)]
    for points in ((a,b,c,d), back[::-1], (d,c,back[2],back[3]), (b,back[1],back[2],c)):
        face('tunnel-wings', list(points) if s == 1 else list(points)[::-1])
# Four bays interpolate a continuous fade into the unlit interior.
contour = [(R,0)] + inner + [(-R,0)]
for near,far in zip((0,4,8,12),(4,8,12,18)):
    for a,b in zip(contour,contour[1:]):
        face('tunnel-lining', [(a[0],near,a[1]),(b[0],near,b[1]),(b[0],far,b[1]),(a[0],far,a[1])])
face('tunnel-lining', [(x,18,z) for x,z in contour])
# The approach reaches Y=3 (the shared hex edge). Underlap it slightly: this
# lattice's angled hex edges are not quite perpendicular to the road axis.
# The tiny recessed lip avoids both cracks and coplanar fighting. Keep the 15-unit carriageway
# unchanged through the portal; the remaining opening width is concrete verge.
for near,far in zip((2.75,6,10,14),(6,10,14,18)):
    lip = -.02 if near == 2.75 else 0
    face('tunnel-floor', [(-7.5,near,lip),(7.5,near,lip),(7.5,far,0),(-7.5,far,0)])
    for x0,x1 in ((-R,-7.5),(7.5,R)):
        face('tunnel-lining', [(x0,near,lip),(x1,near,lip),(x1,far,0),(x0,far,0)])

packed, parts, materials, objects = [], [], [], []
for role,p in PARTS.items():
    mesh = bpy.data.meshes.new(role)
    mesh.from_pydata(p['verts'], [], p['faces'])
    mesh.update()
    mesh.materials.append(p['mat'])
    obj = bpy.data.objects.new(role, mesh)
    SCENE.collection.objects.link(obj)
    objects.append(obj)
    uv = mesh.uv_layers.new(name='UVMap')
    colors = mesh.color_attributes.new(name='Color', type='FLOAT_COLOR', domain='CORNER')
    display_colors = []
    for polygon in mesh.polygons:
        n = polygon.normal
        for loop in polygon.loop_indices:
            v = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = ((v.y if abs(n.x) > .7 else v.x)/6, (v.y if abs(n.z) > .7 else v.z)/6)
            shade = p['colors'][polygon.index]
            if role == 'tunnel-floor':
                # The visible road enters the arch before fading into darkness.
                shade *= .015 + .985 * (1 - min(1, max(0, (v.y - 6) / 12)))**1.65
            elif role == 'tunnel-lining':
                shade *= .015 + .9 * (1 - min(1, max(0, v.y / 18)))**1.65
            color = tuple(c * shade for c in p['color'])
            display_colors.append((*color, 1))
            colors.data[loop].color = (*(linear(c) for c in color), 1)
    mesh.calc_loop_triangles()
    indices = []
    for t in mesh.loop_triangles:
        for v,l in zip(t.vertices,t.loops):
            indices.append(len(packed)//12)
            packed.extend((*mesh.vertices[v].co, *t.normal, *display_colors[l], *uv.data[l].uv))
    parts.append({'id':role,'type':'TRIANGLES','indices':indices})
    materials.append({'id':role,'diffuse':[1,1,1], 'textures':[{'id':role,'filename':'textures/'+p['texture'],
                      'type':'DIFFUSE','wrapS':10497,'wrapT':10497}]})
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)
# Initialize the new view layer before Blender copies it into the source file.
SCENE.view_layers[0].update()
bpy.data.libraries.write(str(SOURCE/'road-tunnel.blend'), {SCENE}, path_remap='RELATIVE_ALL')
manifest_file = OUT / 'manifest.json'
manifest = json.loads(manifest_file.read_text())
stats = {}
# Both exports share the same editable geometry. Only the freestanding wing
# walls are omitted at suspended bridge ends; there is no second asset builder.
for name,winged in (('road-tunnel',True),('road-tunnel-bridge',False)):
    selected = [p for p in parts if winged or p['id'] != 'tunnel-wings']
    vertices, export_parts = [], []
    for p in selected:
        indices = []
        for i in p['indices']:
            indices.append(len(vertices)//12)
            vertices.extend(packed[i*12:(i+1)*12])
        export_parts.append({**p, 'indices':indices})
    model = {'id':name,'version':[0,1],
             'materials':[m for m in materials if winged or m['id'] != 'tunnel-wings'],
             'meshes':[{'attributes':['POSITION','NORMAL','COLOR','TEXCOORD0'],
                        'vertices':vertices,'parts':export_parts}],
             'nodes':[{'id':name,'parts':[{'meshpartid':p['id'],'materialid':p['id']} for p in selected]}]}
    write_glb(OUT/(name+'.glb'), levels={0:model})
    stats[name] = {'triangles':sum(len(p['indices'])//3 for p in selected),'vertices':len(vertices)//12,
                  'opening_width':R*2,'opening_height':SPRING+R,'depth':18,'wing_walls':winged,
                  'road_width':15,'road_start':2.75,'road_end':18}
    (SOURCE/(name+'.json')).write_text(json.dumps(stats[name],indent=2)+'\n')
    manifest[name] = stats[name]
manifest_file.write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps(stats))
