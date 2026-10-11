"""Build the tile scenery catalog in an isolated Blender scene through MCP.

A tileset image's key (scenery/<image path>) decodes through layouts.json to
meshes named by topic (roofs/, parks/, pools/, ...; see SHARED and NAMES). All dimensions
are tile pixels, Z-up, with the supporting ground at Z=0. Original images and
existing Blender scenes are preserved. Run build() via execute_blender_code.
"""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from math import cos, sin, pi, radians, ceil
from pathlib import Path
import json
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import tessellate_polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_board_tiles import declarations
from glb_geometry import colour, colour_text, linear, read_glb, recolour, write_glb

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT/'data/models/board'
REVIEW = ROOT/'tools/board-models/scenery'
YELLOW = (.88, .62, .08)
STEEL = (.38, .43, .46)
DARK = (.12, .16, .19)
CONCRETE = (.59, .58, .53)
GLASS = (.13, .30, .50)
WHITE = (.80, .82, .79)
WOOD = (.43, .26, .13)
WATER = (.13, .49, .65)
# Authored identities are independent of their current paint values.
CAR_PAINT = {
    'silver': (.72, .72, .72), 'gray': (.44, .44, .44), 'white': (.82, .82, .82),
    'blue': (.08, .17, .65), 'steel': (.33, .41, .52), 'azure': (.14, .36, .60),
    'orange': (.60, .38, .13), 'olive': (.48, .44, .10), 'yellow': (.72, .69, .08),
    'teal': (.14, .56, .54), 'pink': (.48, .24, .36), 'purple': (.56, .14, .51),
    'green': (.08, .67, .10), 'red': (.65, .08, .04), 'maroon': (.33, .07, .06),
    'mustard': (.5, .42, .1), 'turquoise': (.15, .45, .5), 'magenta': (.56, .13, .35),
    'ochre': (.45, .38, .18),
}
# Colour slots (glb_geometry.write_glb): the parked car's paint is slot 1; any paint is its colour, red its default.
CAR_SLOTS=[{'name':'Paint','colour':colour_text(CAR_PAINT['red']),
            'presets':[[paint.capitalize(),colour_text(value)] for paint,value in CAR_PAINT.items()]}]
# A pool basin's wall, coping, deck and water are slots 1-4; a pond is a pool with the natural colours.
POOL_COLOURS={'Pool':((.62,.76,.76),WHITE,(.64,.60,.51),(.88,.95,.98)),
              'Pond':((.39,.46,.24),(.39,.46,.24),(.39,.46,.24),(.58,.78,.67))}
POOL_SLOTS=[{'name':name,'colour':colour_text(POOL_COLOURS['Pool'][i]),
             'presets':[[style,colour_text(values[i])] for style,values in POOL_COLOURS.items()]}
            for i,name in enumerate(('Wall','Coping','Deck','Water'))]
POND=[colour_text(value) for value in POOL_COLOURS['Pond']]


class Mesh:
    def __init__(self, shared=None):
        self.vertices, self.parts = [], defaultdict(list)
        # Each vertex's colour slot (0 none) while `slot` is set, and the slots' definitions.
        self.slots, self.slot, self.colour_slots = [], 0, None
        self.components = []
        self.shared = shared
        self.materials = {'scenery': {'id': 'scenery', 'diffuse': [1, 1, 1]}}
        self.transform = Matrix.Identity(4)
        self.role = 'scenery'
        # Where a recentred canonical's origin lay when it was authored; rows add it back.
        self.origin = Vector((0, 0, 0))

    def face(self, points, color, role=None, uv=None):
        role = role or self.role
        self.materials.setdefault(role, {'id':role, 'diffuse':[1,1,1]})
        p = [self.transform @ Vector(v) for v in points]
        n = (p[1]-p[0]).cross(p[2]-p[0]).normalized()
        if n.length < .5: return
        start = len(self.vertices)//12
        for i, v in enumerate(p):
            self.vertices.extend([*v, *n, *color, 1, *(uv[i] if uv else (v.x/12, v.y/12))])
        self.slots.extend([self.slot]*len(p))
        for i in range(1, len(p)-1): self.parts[role].extend((start, start+i, start+i+1))

    def box(self, center, size, color, angle=0):
        x, y, z = center
        a, b, c = [v/2 for v in size]
        turn = radians(angle)
        points = [(x+u*cos(turn)-v*sin(turn), y+u*sin(turn)+v*cos(turn), z+w)
                  for u, v, w in ((-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),
                                  (-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c))]
        for ids in ((3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)):
            self.face([points[i] for i in ids], color)

    def beam(self, a, b, width, color, sides=6):
        a, b = Vector(a), Vector(b)
        d = (b-a).normalized()
        side = d.cross(Vector((.173,.917,.317))).normalized()
        up = d.cross(side).normalized()
        rings = [[p+(side*cos(i*2*pi/sides)+up*sin(i*2*pi/sides))*width/2 for i in range(sides)] for p in (a,b)]
        self.face(list(reversed(rings[0])), color)
        self.face(rings[1], color)
        for i in range(sides):
            j = (i+1)%sides
            self.face([rings[0][i], rings[0][j], rings[1][j], rings[1][i]], color)

    def cylinder(self, x, y, z, radius, height, color, sides=16):
        # Upright caps and ring() share the same XY phase; beam() chooses an arbitrary radial basis.
        rings=[[(x+radius*cos(i*2*pi/sides),y+radius*sin(i*2*pi/sides),h)
                for i in range(sides)] for h in (z,z+height)]
        self.face(list(reversed(rings[0])),color)
        self.face(rings[1],color)
        for i in range(sides):
            j=(i+1)%sides
            self.face([rings[0][i],rings[0][j],rings[1][j],rings[1][i]],color)

    def ellipsoid(self, center, size, color, sides=10, rows=5, floor=None):
        x,y,z = center
        def p(a,b):
            height=z+size[2]*cos(b)
            return (x+size[0]*cos(a)*sin(b), y+size[1]*sin(a)*sin(b),
                    max(floor,height) if floor is not None else height)
        for row in range(rows):
            for i in range(sides):
                a,b=i*2*pi/sides,(i+1)*2*pi/sides
                u,v=row*pi/rows,(row+1)*pi/rows
                points=[p(a,u),p(a,v),p(b,v),p(b,u)]
                if row==0: points=points[:3]
                elif row==rows-1: points=[points[0],points[1],points[3]]
                self.face(points,color)

    def ring(self, x, y, z, outer, inner, height, color, sides=24):
        for i in range(sides):
            a,b=i*2*pi/sides,(i+1)*2*pi/sides
            def p(r,t,h):return (x+r*cos(t),y+r*sin(t),z+h)
            self.face([p(outer,a,0),p(outer,b,0),p(outer,b,height),p(outer,a,height)],color)
            self.face([p(inner,b,0),p(inner,a,0),p(inner,a,height),p(inner,b,height)],color)
            self.face([p(outer,a,height),p(outer,b,height),p(inner,b,height),p(inner,a,height)],color)

    def place(self, function, x=0, y=0, z=0, angle=0, scale=1, role=None, asset_name=None, colours=None, **kwargs):
        """`colours` replace the placed mesh's slot colours (a row's "colours"; a preview recolours its vertices)."""
        old=self.transform.copy(); old_role=self.role
        if role is not None:self.role=role
        self.transform @= Matrix.Translation((x,y,z)) @ Matrix.Rotation(radians(angle),4,'Z') @ Matrix.Scale(scale,4)
        if function is car and kwargs.get('paint','red')!='red':
            # Every paint is the one car mesh with its paint slot's colour.
            colours=[colour_text(CAR_PAINT[kwargs.pop('paint')])]
        if self.shared is not None and function in SHARED:
            # Shared identities are authored, never derived from mutable geometry or paint values.
            key=asset_name or SHARED[function]
            if function is car:key='vehicles/car'
            elif kwargs and asset_name is None:
                raise ValueError('Parameterized shared '+function.__name__+' requires an explicit asset_name')
            if self.role!='scenery':key+='-'+self.role
            asset='scenery/'+key
            if asset not in self.shared:
                component=Mesh();component.role=self.role
                function(component,**kwargs)
                if function in CANONICAL:recentre(component)
                self.shared[asset]=component
            self.component(asset,self.transform @ Matrix.Translation(self.shared[asset].origin),colours=colours)
        else:
            start=len(self.slots)
            function(self, **kwargs)
            self.recolour(start,colours)
        self.transform=old; self.role=old_role

    def recolour(self, start, colours):
        """Replace the slot colours of the vertices from `start` on, as a row's colours replace them at runtime."""
        for index in range(start,len(self.slots)) if colours else ():
            slot=self.slots[index]
            if slot and slot<=len(colours) and colours[slot-1]:
                at=index*12
                self.vertices[at+6:at+9]=recolour(self.vertices[at+6:at+9],colour(self.colour_slots[slot-1]['colour']),
                                                  colour(colours[slot-1]))

    def instance(self, asset, function, angle, stretch=(1,1,1), base_angle=0, **kwargs):
        """A rotated or stretched duplicate of a legacy mesh is a row on that mesh; previews bake it.

        `function` draws the mesh unrotated; `asset` is it baked at `base_angle`, so the row turns by the difference.
        `stretch` scales the mesh's own axes before that turn, on top of the row's uniform scale.
        """
        turn=Matrix.Rotation(radians(angle-base_angle),4,'Z')
        if self.shared is not None:
            self.component(asset,self.transform @ turn,stretch)
            return
        old=self.transform.copy()
        self.transform@=turn @ Matrix.Diagonal((*stretch,1)) @ Matrix.Rotation(radians(base_angle),4,'Z')
        self.place(function,**kwargs)
        self.transform=old

    def component(self, asset, transform, stretch=(1,1,1), colours=None):
        # Rows carry no kind: the shared 'tree-broad' slot is the only tree, everything else is scenery.
        scale=transform.to_scale()
        assert max(scale)-min(scale)<.00001, 'Composition components use uniform scale; per-axis factors are stretch'
        assert min(stretch)>0, 'Stretch factors are positive'
        angles=transform.to_euler()
        assert abs(angles.x)+abs(angles.y)<.00001, 'Board components rotate about their ground normal'
        row={'asset':asset,'position':[round(v,6) for v in transform.to_translation()],
             'rotation':round(angles.z*180/pi,6),'scale':round(scale.x,6)}
        if any(abs(v-1)>1e-9 for v in stretch):row['stretch']=[round(v,6) for v in stretch]
        if colours:row['colours']=list(colours)
        self.components.append(row)

    def texture(self, role, filename):
        self.materials[role]={'id':role,'diffuse':[1,1,1],
                              'textures':[{'id':role,'type':'DIFFUSE','filename':'textures/'+filename,
                                           'minFilter':9987,'magFilter':9729,'wrapS':10497,'wrapT':10497}]}

    def smooth(self, role):
        indices=set(self.parts[role]);normals=defaultdict(lambda:Vector((0,0,0)))
        for index in indices:
            at=index*12;key=tuple(round(v,5) for v in self.vertices[at:at+3])
            normals[key]+=Vector(self.vertices[at+3:at+6])
        for index in indices:
            at=index*12;key=tuple(round(v,5) for v in self.vertices[at:at+3])
            self.vertices[at+3:at+6]=normals[key].normalized()

    def library_row(self, asset, transform, colours=None):
        """A row on a prebuilt mesh under data/models/board; an editable preview bakes its geometry."""
        if self.shared is not None:
            self.component(asset,self.transform @ transform,colours=colours)
            return
        data=library(asset);mesh=data['meshes'][0]
        values=mesh['vertices'];start=len(self.vertices)//12
        transform=self.transform @ transform;normals=transform.to_3x3().inverted().transposed()
        for i in range(0,len(values),12):
            v=values[i:i+12]
            self.vertices.extend([*(transform @ Vector(v[:3])),*(normals @ Vector(v[3:6])).normalized(),*v[6:]])
        self.slots.extend(mesh.get('slots',[0]*(len(values)//12)))
        self.colour_slots=data['extras'].get('mmColourSlots',self.colour_slots)
        self.recolour(start,colours)
        self.parts[self.role].extend(start+i for p in mesh['parts'] for i in p['indices'])

    def tree(self, x, y, size=12, variant=0):
        # Trees are ordinary composition components, using the catalog's normalized 30-unit height.
        if self.shared is not None:
            transform=self.transform @ Matrix.Translation((x,y,0)) @ Matrix.Rotation(variant*1.71,4,'Z') @ Matrix.Scale(size/30,4)
            self.component('tree-broad',transform)
            return
        # Editable Blender previews reuse the shared tree kit too; no tree geometry enters scenery GLBs.
        data=library('tree-broad',2)
        values=data['meshes'][0]['vertices']
        positions=[values[i:i+3] for i in range(0,len(values),12)]
        low=min(p[2] for p in positions)
        height=max(p[2] for p in positions)-low
        transform=self.transform @ Matrix.Translation((x,y,-low*size/height)) @ Matrix.Rotation(variant*1.71,4,'Z') @ Matrix.Scale(size/height,4)
        normals=transform.to_3x3().inverted().transposed()
        start=len(self.vertices)//12
        for i in range(0,len(values),12):
            v=values[i:i+12]
            self.vertices.extend([*(transform @ Vector(v[:3])),*(normals @ Vector(v[3:6])).normalized(),*v[6:]])
        self.slots.extend([0]*(len(values)//12))
        roles={p['meshpartid']:p['materialid'] for n in walk(data['nodes']) for p in n.get('parts',[])}
        for mat in data['materials']: self.materials[mat['id']]=mat
        for part in data['meshes'][0]['parts']:
            self.parts[roles[part['id']]].extend(start+i for i in part['indices'])

    def data(self, name):
        parts=[{'id':r,'type':'TRIANGLES','indices':indices} for r,indices in self.parts.items()]
        assert len(self.slots)*12==len(self.vertices),'One colour slot per vertex'
        return {'id':name,'meshes':[{'attributes':['POSITION','NORMAL','COLOR','TEXCOORD0'],
                                    'vertices':self.vertices,'parts':parts,'slots':self.slots}],
                'materials':deepcopy([self.materials[role] for role in self.parts if self.parts[role]]),
                'nodes':[{'id':name,'parts':[{'meshpartid':r,'materialid':r} for r in self.parts]}]}


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get('children',[]))


@lru_cache(None)
def library(name, level=0): return read_glb(BOARD/(name+'.glb'),level)


def asset_id(name):
    return 'scenery/'+Path(name).with_suffix('').as_posix()


def recentre(mesh, xy=True):
    """Ground a mesh at Z=0 and, for a canonical component, centre its XY bounds on the origin.

    Runtime grounds a whole legacy SCENERY mesh but places layout rows as authored, so a
    canonical carries the grounding itself and its rows keep only the XY offset (mesh.origin).
    """
    v=mesh.vertices
    shift=[(min(v[k::12])+max(v[k::12]))/2 if xy else 0 for k in (0,1)]+[min(v[2::12])]
    for i in range(0,len(v),12):
        for k in range(3):v[i+k]-=shift[k]
    mesh.origin=Vector((shift[0],shift[1],0))


def skylight(g, width=34, length=60, rows=5):
    g.box((0,0,.8),(width+2,length+2,1.6),CONCRETE)
    for x in range(2):
        for y in range(rows):
            px=(x-.5)*width/2
            py=(y-(rows-1)/2)*length/rows
            # A shallow pitched glass lantern with a central ridge, not photovoltaic cells.
            left=px-width/4+.4; right=px+width/4-.4
            def top(xx):return 2.0+(1-abs(xx)/(width/2))*3.4
            a,b=py-length/rows/2+.4,py+length/rows/2-.4
            g.face([(left,a,top(left)),(right,a,top(right)),(right,b,top(right)),(left,b,top(left))],
                   tuple(c*(.88+.07*((x+y)%3)) for c in GLASS))
    for x in (-width/2,0,width/2):
        z=2.0+(1-abs(x)/(width/2))*3.4
        g.beam((x,-length/2,z),(x,length/2,z),.6,WHITE,4)
    for y in range(rows+1):
        py=-length/2+y*length/rows
        for x in (-1,1):g.beam((0,py,5.4),(x*width/2,py,2.0),.65,STEEL,4)
    for y in (-length/2,length/2):
        g.face([(-width/2,y,1.5),(width/2,y,1.5),(width/2,y,2),(0,y,5.4),(-width/2,y,2)],GLASS)


def car(g, paint='red'):
    # The paint is its slot's colour to the 8-bit step, so a row's paint replaces it exactly.
    color=colour(colour_text(CAR_PAINT[paint]))
    g.colour_slots=CAR_SLOTS
    g.slot=1
    g.box((0,0,1.5),(4.3,9.0,2),color)
    g.slot=0
    g.box((0,-.2,2.8),(3.8,4.3,1.6),GLASS)
    g.slot=1
    g.box((0,-.2,3.65),(3.9,2.6,.4),color)
    g.slot=0
    for y in (-2.8,2.8):
        for x in (-2.05,2.05):g.beam((x-.35,y,.9),(x+.35,y,.9),1.8,DARK,8)
    for x in (-1.5,1.5):
        g.box((x,4.52,1.8),(1.0,.15,.6),WHITE)
        g.box((x,-4.52,1.8),(.85,.15,.5),(.65,.06,.03))


def parking_barrier(g):
    # Fixed roadside concrete barrier, seated on its broad foot. The source's
    # hazard markings are paint on the prism, not separate hovering panels.
    profile=[(-1.4,0),(1.4,0),(1.4,.28),(.55,2.1),(-.55,2.1),(-1.4,.28)]
    role='parking-barrier'
    g.texture(role,'sculpt/concrete.png')

    def face(points,color):
        g.face(points,color,role,[((y+x-24)/8,(x-24+z)/3) for x,y,z in points])

    def cut(points,level,side):
        result=[]
        for a,b in zip(points,points[1:]+points[:1]):
            da=a[0]-24+a[1]+a[2]-level;db=b[0]-24+b[1]+b[2]-level
            inside=da*side>=0
            if inside:result.append(a)
            if inside!=(db*side>=0):
                t=da/(da-db)
                result.append(tuple(a[i]+(b[i]-a[i])*t for i in range(3)))
        return result

    ends=[[(24+x,y,z) for x,z in profile] for y in (-12.5,12.5)]
    face(ends[0],CONCRETE);face(list(reversed(ends[1])),CONCRETE)
    for i in range(len(profile)):
        j=(i+1)%len(profile)
        points=[ends[0][i],ends[1][i],ends[1][j],ends[0][j]]
        if i not in (2,3,4):
            face(points,CONCRETE)
            continue
        # Clip alternating color regions into the existing three upper faces;
        # every paint vertex remains exactly on the concrete surface.
        phase=[x-24+y+z for x,y,z in points]
        for stripe in range(int(min(phase)//3.1),int(max(phase)//3.1)+1):
            painted=cut(cut(points,stripe*3.1,1),(stripe+1)*3.1,-1)
            if len(painted)>=3:face(painted,DARK if stripe%2 else YELLOW)


def container(g, color=(.44,.19,.14)):
    g.box((0,0,3.2),(13.2,5.8,6.4),color)
    for x in range(-6,7,2):
        for y in (-2.95,2.95):g.box((x,y,3.3),(.25,.20,5.8),tuple(min(.9,c*1.18) for c in color))
    for y in (-1.7,1.7):g.beam((6.67,y,.6),(6.67,y,5.7),.22,STEEL,4)
    g.box((6.70,0,3.2),(.12,.15,6.1),DARK)


def container_grabber(g):
    # Horizontal spreader, with four corner twistlocks. Its origin is the bottom
    # of the locks, so the entire assembly stays above the selected roof.
    for y in (-2.35,2.35):g.box((0,y,.92),(12.5,.48,.65),YELLOW)
    for x in (-5.9,5.9):
        g.box((x,0,.92),(.6,5.2,.65),YELLOW)
        for y in (-2.35,2.35):
            g.box((x,y,.35),(.55,.55,.7),DARK)
            g.box((x,y,.82),(.8,.8,.4),YELLOW)
    g.box((0,0,1.05),(4.8,1.2,.75),YELLOW)
    for x in (-1.65,1.65):g.box((x,0,1.62),(.55,.8,.4),STEEL)


def gantry_support(g):
    for x in (-6,6):
        for y in (9,17):
            g.box((x,y,.6),(2.3,3.8,1.2),DARK)
            g.beam((x,y,1.2),(x*.88,y,23.5),1.05,STEEL,4)
        g.beam((x,9,7.5),(x*.88,17,22),.6,YELLOW,4)
    g.box((0,13,23.8),(14,11,1.6),STEEL)
    g.box((0,11.5,26),(9,6,3.4),WHITE)
    g.box((0,14.55,26.4),(7,.15,1.8),GLASS)
    g.box((0,11.5,27.85),(9.5,6.5,.3),STEEL)
    for x in (-6.5,6.5):
        g.beam((x,17,24.6),(x,33,24.6),.5,YELLOW,4)
        g.beam((x,17,24.6),(x,23,30.5),.5,YELLOW,4)
    g.beam((-6.5,33,24.6),(6.5,33,24.6),.5,YELLOW,4)


def gantry_boom(g, half_span, tip):
    # Both sections use the same rail section and elevation. The joint's crossbar
    # belongs to the tip only; there are no duplicate faces along the exposed joint.
    start,end,height=(-half_span if tip else 1.5),half_span,28
    segments=ceil((end-start)/6)
    for x in (-1.65,1.65):
        for z,width in ((height,.48),(height+3,.40)):
            g.beam((x,start,z),(x,end,z),width,YELLOW,4)
        for i in range(segments):
            a=start+(end-start)*i/segments; b=start+(end-start)*(i+1)/segments
            g.beam((x,a,height),(x,b,height+3),.27,YELLOW,4)
            g.beam((x,a,height+3),(x,b,height),.27,YELLOW,4)
    for i in range(segments+(1 if tip else 0)):
        y=start+(end-start)*i/segments
        g.beam((-1.65,y,height),(1.65,y,height),.35,YELLOW,4)
    if tip:
        g.box((0,14,27.7),(4.2,3,.6),DARK)
        # The suspended grabber lies along the boom; cables attach to its lifting eyes.
        for y in (12.35,15.65):
            for x in (-.35,.35):g.beam((x,y,27.4),(x,y,12.1),.13,DARK,4)
        g.place(container_grabber,y=14,z=10.28,angle=90)


def crane(g):
    # Compact crawler-mounted construction crane with a triangular lattice boom.
    for x in (-4.5,4.5):
        g.box((x,0,1.3),(2.6,12,2.6),DARK)
        for y in (-4,-2,0,2,4):g.box((x,y,2.7),(2.8,.6,.3),STEEL)
    g.cylinder(0,0,2.3,4.8,1.5,STEEL)
    g.box((0,-1,6),(9,9,5),YELLOW)
    g.box((3,1,7.3),(3.1,4.2,3.2),GLASS)
    g.box((3,1,9),(3.6,4.6,.4),YELLOW)
    g.box((0,-5.6,6),(6,.25,2.5),DARK)
    points=[(-2,2,6),(2,2,6),(0,2,9)]
    end=[(-.7,29,16),(.7,29,16),(0,29,18)]
    for a,b in zip(points,end):g.beam(a,b,.7,YELLOW,4)
    for i in range(7):
        t,u=i/7,(i+1)/7
        for j in range(3):
            a=Vector(points[j]).lerp(Vector(end[j]),t)
            b=Vector(points[(j+1)%3]).lerp(Vector(end[(j+1)%3]),u)
            g.beam(a,b,.38,YELLOW,4)
    g.beam((0,29,17),(0,29,6),.20,DARK)
    g.box((0,29,5.5),(1.8,1.5,2),YELLOW)
    for i in range(5):
        a,b=(i-2)*pi/5,(i-1)*pi/5
        g.beam((sin(a),29,3.5-cos(a)),(sin(b),29,3.5-cos(b)),.4,STEEL)
    for i in range(3):g.box((-14+i*1.7,-9,.6),(1.3,12,1.2),(.65,.25,.08))


def bulldozer(g):
    for x in (-5,5):g.box((x,0,1.6),(3.3,15,3.2),DARK)
    g.box((0,0,4.1),(9,10,4),YELLOW)
    g.box((-2,0,7.5),(5,5,4),GLASS)
    g.box((-2,0,9.6),(5.6,5.6,.5),YELLOW)
    for x in (-4,4):g.beam((x,0,2.5),(x,11,2.5),1,YELLOW,4)
    g.box((0,12,3.2),(16,2,5.7),YELLOW)
    g.box((0,13,1),(16,.8,1),STEEL)


def site_debris(g, n):
    """Construction site n's scattered concrete chunks, seeded per site."""
    rng=random.Random(143+n)
    for i in range(35):
        x,y=rng.uniform(6,23),rng.uniform(-24,-14)
        g.ellipsoid((x,y,.65),(1.2,.8,.6),CONCRETE,5,3)


def excavation(g):
    soil=(.51,.43,.18)
    g.box((-5,0,.3),(33,48,.6),(.28,.25,.13))
    for x in (-23,14):g.box((x,0,3),(6,54,6),soil)
    # End banks meet the side banks; overlapping coplanar tops would flicker at their corners.
    g.box((-4.5,24.5,3),(31,5,6),soil)
    g.box((-4.5,-24.5,1.5),(31,5,3),soil)
    for i in range(4):g.ellipsoid((22+i%2*3,-18+i*10,1.5),(8,7,4),soil,8,3,floor=0)
    for x,y in ((-13,15),(-6,20),(-18,22)):g.ring(x,y,.5,2.5,1.7,4,CONCRETE,12)
    for i in range(3):g.box((-14+i*2,-17,1),(1.3,12,1.3),(.7,.28,.07),35)


def shelter(g, floor=True):
    for x in (-11,11):
        for y in (-4,4):g.beam((x,y,0),(x,y,7),.65,STEEL,4)
    if floor:g.box((0,0,.3),(26,12,.6),CONCRETE)
    g.box((0,0,7),(26,12,.7),WHITE)
    for x in range(-12,13,4):g.beam((x,-6,7.6),(x,6,7.6),.4,STEEL,4)
    g.box((0,2,1.8),(19,2,.5),WOOD)


def grandstand(g):
    # Four open tiers face local -X, toward the pool. Only the frame touches
    # the ground; there is no platform hiding the underlying biome.
    seats=(.50,.57,.62)
    for row in range(4):
        x=-3+row*1.8;height=.3+row*1.1
        g.box((x-.55,0,height),(.95,28.5,.25),STEEL)
        g.box((x+.15,0,height+.9),(.9,27,.28),seats)
        for y in (-10,10):
            g.beam((x+.15,y,.2+(x+3.95)*.6),(x+.15,y,height+.76),.3,STEEL,4)
    for y in (-10,0,10):
        g.beam((-3.8,y,.2),(3.2,y,4.4),.38,STEEL,4)
        g.beam((3.2,y,.2),(3.2,y,4.4),.38,STEEL,4)
        g.box((-.3,y,.19),(7,.38,.38),STEEL)
        g.beam((3.2,y,4.2),(3.2,y,6),.25,STEEL,4)
    g.beam((3.2,-14,6),(3.2,14,6),.25,STEEL,4)
    for y in (-14,14):
        g.beam((-3.8,y,2),(3.2,y,6),.25,STEEL,4)
        g.beam((-3.8,y,.15),(-3.8,y,2),.25,STEEL,4)


def concrete_pipe(g):
    g.ring(0,0,0,2.6,1.8,4,CONCRETE,12)


def garden_bed(g):
    g.box((0,-18,.5),(39,34,1),(.22,.32,.10))
    for x in (-20,20):g.box((x,-18,1),(1,35,2),CONCRETE)
    for y in (-35,-1):g.box((0,y,1),(41,1,2),CONCRETE)


def curve(points, steps=6):
    """A closed authored Catmull-Rom outline, not the jagged boundary of individual sprite pixels."""
    result=[]
    for i in range(len(points)):
        a,b,c,d=[Vector(points[(i+j)%len(points)]) for j in (-1,0,1,2)]
        for k in range(steps):
            t=k/steps
            result.append(tuple(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)))
    return result


def round_rectangle(width, length, radius=3):
    result=[]
    for x,y,start in ((width/2-radius,length/2-radius,0),(-width/2+radius,length/2-radius,90),
                      (-width/2+radius,-length/2+radius,180),(width/2-radius,-length/2+radius,270)):
        for i in range(9):
            a=radians(start+i*90/8)
            result.append((x+radius*cos(a),y+radius*sin(a)))
    return result


def pool_shape(variant):
    if variant==2:
        return curve([(-7,27),(8,28),(17,20),(13,10),(5,2),(6,-9),(9,-21),(1,-27),(-11,-22),(-16,-10),(-14,4),(-18,17)])
    points=[]
    for i in range(96):
        t=i*2*pi/96
        if variant==1:x,y=17*cos(t)+10*cos(2*t)-4,23*sin(t)
        elif variant==3:
            radius=21+4*cos(3*(t-pi/2));x,y=radius*cos(t),radius*sin(t)+3
        else:
            a,b=23*cos(t),17*sin(t)*(1+.5*cos(2*t))
            x,y=a*cos(-pi/5)-b*sin(-pi/5),a*sin(-pi/5)+b*cos(-pi/5)
        points.append((x,y))
    return points


def pool_basin(g, outline, deck=True, plinth=0):
    """One continuous closed coping/deck shell, with bevels, inner walls and recessed water.

    plinth extends the outer wall that far below the basin's foot, for a basin raised on a plinth. The wall, coping,
    deck and water are colour slots 1-4 (POOL_SLOTS): a pond is this basin with the 'Pond' colours.
    """
    g.colour_slots=POOL_SLOTS
    wall,coping,surround,surface=(colour(colour_text(value)) for value in POOL_COLOURS['Pool'])
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(outline,outline[1:]+outline[:1])) < 0:
        outline=list(reversed(outline))
    normals=[]
    for i,p in enumerate(outline):
        before=(Vector(p)-Vector(outline[i-1])).normalized()
        after=(Vector(outline[(i+1)%len(outline)])-Vector(p)).normalized()
        n1=Vector((before.y,-before.x));n2=Vector((after.y,-after.x))
        normal=(n1+n2).normalized()
        normals.append(normal/max(.5,normal.dot(n1)))
    # Offset samples share indices across every ring, so there are no separate rim pieces or open joins.
    profile=[(0,0),(0,1.25),(.25,1.55),(1.75,1.55),(2,1.25),(2,.38)]
    if deck:profile += [(5,.38),(5,0)]
    else:profile += [(2,0)]+([(2,-plinth)] if plinth else [])
    rings=[[(x+n.x*offset,y+n.y*offset,z) for (x,y),n in zip(outline,normals)] for offset,z in profile]
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for ring in rings:
        for i,a in enumerate(ring):
            b=ring[(i+1)%len(ring)]
            for j in range(i+2,len(ring)):
                if i==0 and j==len(ring)-1:continue
                c,d=ring[j],ring[(j+1)%len(ring)]
                if cross(a,b,c)*cross(a,b,d)<-1e-8 and cross(c,d,a)*cross(c,d,b)<-1e-8:
                    raise ValueError('Pool outline offset intersects itself')
    for role in ('pool-water','pool-coping','pool-deck','pool-wall'):
        g.materials.setdefault(role,{'id':role,'diffuse':[1,1,1]})
    # One shared opaque, mipmapped surface in the ordinary prop pass; no animated-water/depth pass.
    g.materials['pool-water']['textures']=[{'id':'pool-water','type':'DIFFUSE',
        'filename':'textures/pool-water.png','minFilter':9987,'magFilter':9729,'wrapS':10497,'wrapT':10497}]
    for band,first in enumerate(rings):
        second=rings[(band+1)%len(rings)]
        role='pool-wall' if band==0 else 'pool-coping' if band<4 else 'pool-deck'
        color=wall if band==0 else coping if band<4 else surround
        g.slot=1 if band==0 else 2 if band<4 else 3
        for i in range(len(outline)):
            j=(i+1)%len(outline)
            shade=1-.025*((i//4)%2) if band in (2,5) else 1
            g.face([first[i],second[i],second[j],first[j]],tuple(c*shade for c in color),role)
    water=[Vector((x,y,.75)) for x,y in outline]
    for indices in tessellate_polygon([water]):
        points=[water[i] for i in indices]
        if (points[1]-points[0]).cross(points[2]-points[0]).z<0:points.reverse()
        uv=[((g.transform @ p).x/84+.5,(g.transform @ p).y/84+.5) for p in points]
        g.slot=4
        g.face(points,surface,'pool-water',uv)
    g.slot=0


def inside_outline(x,y,outline):
    inside=False
    for a,b in zip(outline,outline[1:]+outline[:1]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def ledge(g):
    # Tapered parapet at one hex edge; the adjacent variants rotate this exact profile.
    p=[(-37,-8,0),(37,-8,0),(21,-36,0),(-21,-36,0),(-37,-8,10),(37,-8,10),(30,-20,10),(-30,-20,10)]
    # This edge outline runs clockwise, opposite to box(). Keep every face outward
    # so backface culling draws the body as well as its narrow cap trim.
    for ids in ((3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)):
        g.face([p[i] for i in reversed(ids)],CONCRETE)
    g.beam((-37,-8,10.3),(37,-8,10.3),.8,WHITE,4)


def bevel(g):
    outer=[(-33,-13,1),(33,-13,1),(22,-32,1),(-22,-32,1)]
    inner=[(-29,-15,6),(29,-15,6),(20,-29,2),(-20,-29,2)]
    # Glazed trapezoid with a tall inner edge and sloping pane, matching the edge roof family.
    g.face(list(reversed(inner)),GLASS)
    for i in range(4):
        j=(i+1)%4
        g.face([outer[i],inner[i],inner[j],outer[j]],STEEL)
        g.beam(inner[i],inner[j],.7,WHITE,4)


def roof_grille(g):
    g.box((0,0,3),(15,22,6),STEEL)
    for y in range(-9,11,3):g.box((0,y,6.3),(14,.8,.6),WHITE)


def chimney_stack(g):
    g.ring(0,0,0,7.5,5.8,13,CONCRETE,8)
    g.ring(0,0,12.5,8,5.5,1.5,WHITE,8)
    g.cylinder(0,0,.1,5.7,.3,DARK,8)


def roof_vent(g):
    """The legacy stack sprites show a slatted grille beside a chimney stack: two separate objects."""
    g.place(roof_grille,x=-12)
    g.place(chimney_stack,x=16)


def pool(g, circular=False, small=False, plinth=0):
    outline=[(18*cos(i*pi/32),18*sin(i*pi/32)) for i in range(64)] if circular else round_rectangle(25,45,2)
    pool_basin(g,outline,deck=not small,plinth=plinth)
    if small:g.cylinder(0,0,.75,2,7,CONCRETE)


def hex_plaza(g):
    """The square family's planted hexagonal plaza."""
    g.cylinder(0,0,.05,25,.8,(.22,.34,.12),6)
    g.ring(0,0,0,26,24,1.4,CONCRETE,6)


def fountain(g):
    """Square1's round fountain. Its outer wall reaches the ground: the plaza hides that plinth, bare ground shows it."""
    g.place(pool,z=.9,circular=True,small=True,plinth=.9)


def garden(g, variant=0):
    if variant==0:
        g.place(hex_plaza)
        g.place(fountain)
    else:hex_plaza(g)
    if variant==3:
        g.ring(0,0,.8,14,12,1.5,CONCRETE,6)
        g.cylinder(0,0,1,12,.2,WATER,6)
    for i in range(6):
        a=i*pi/3+pi/6
        x,y=25*cos(a),25*sin(a)
        if variant in (1,2,4):
            g.cylinder(x,y,0,2.4,7,CONCRETE,6)
            g.cylinder(x,y,7,2.9,.9,WHITE,6)
        elif variant==0:g.tree(x,y,8,i)
    if variant==2:g.ring(0,0,1,20,18,2.5,(.16,.27,.09),6)
    if variant in (4,5):
        for i in range(24):
            a=i*2.39996;r=5+(i%4)*4
            g.ellipsoid((r*cos(a),r*sin(a),1.4),(1.5,1.5,1),(.57,.12,.27) if i%2 else (.85,.63,.18),6,3)


def bench(g):
    g.box((0,0,1),(4.5,1.4,.4),WOOD)
    for x in (-1.5,1.5):g.beam((x,0,0),(x,0,1),.4,STEEL,4)


def table_frame(g):
    g.box((0,0,2.2),(4.5,4.5,.6),WHITE)
    for x in (-1.5,1.5):
        for y in (-1.5,1.5):g.beam((x,y,0),(x,y,2),.35,STEEL,4)


def picnic_table(g):
    g.place(table_frame)
    for y in (-4,4):g.place(bench,y=y)


def pillar(g):
    g.cylinder(0,0,0,3.8,7,CONCRETE,6)
    g.cylinder(0,0,7,4.4,.9,WHITE,6)


def pool_deck(g, shape, islands=()):
    """A sport pool's paved surround, with the source's planted islands; the basins are separate objects."""
    if shape==1:g.box((0,0,.15),(33,70,.3),CONCRETE)
    else:g.cylinder(0,0,0,33,.3,CONCRETE,32)
    clusters=[]
    for x,y in islands:
        # Overlapping islands have coplanar tops that z-fight: trees within one island's reach share one.
        near=next((c for c in clusters if any(Vector((x-a,y-b)).length<7.6 for a,b in c)),None)
        if near is None:clusters.append([(x,y)])
        else:near.append((x,y))
    for members in clusters:
        centre=sum((Vector(m) for m in members),Vector((0,0)))/len(members)
        radius=3.2+max((Vector(m)-centre).length for m in members)
        # The planted pool islands need dry support above the basin waterline.
        g.ring(centre.x,centre.y,.1,radius+.6,radius,1.5,WHITE,24)
        g.cylinder(centre.x,centre.y,1.2,radius,.4,(.23,.29,.12),24)


def landscape(g, n):
    sides=6 if n==1 else 32
    g.cylinder(0,0,0,32,.8,(.18,.29,.11),sides)
    g.ring(0,0,.6,32,30,1.5,CONCRETE,sides)
    g.ring(0,0,.8,24,22,1.4,CONCRETE,sides)
    g.ring(0,0,.8,9,7,1.5,CONCRETE,24)
    g.cylinder(0,0,1,7,.2,WATER,24)
    for i in range(4 if n<4 else 8):
        a=i*360/(4 if n<4 else 8)
        g.box((19*cos(radians(a)),19*sin(radians(a)),.9),(23,3.8,.2),CONCRETE,a)
    for i in range(80):
        a=i*2.39996;r=12+(i%4)*4
        if abs(sin(a*2))<.3:continue
        g.ellipsoid((r*cos(a),r*sin(a),1.2),(.75,.75,.65),(.7,.16,.15) if i%2 else (.8,.7,.12),5,3)


# Legacy decode canonicals: one mesh per real object, recentred and grounded. Layout rows place
# them with the same angles and offsets that baked their rotated legacy variants.
CANONICAL=(bevel, ledge, roof_grille, chimney_stack, skylight, garden_bed, pillar, picnic_table, hex_plaza, fountain,
           crane, bulldozer, site_debris)
# Livestock placements of the legacy herd images; the animals are prebuilt meshes (tools/extract_herd_animals.py).
HERDS_BY_STEM={Path(name).name:rows for name,rows in json.loads((ROOT/'tools/farm-herds.json').read_text()).items()}
# Coats that differ only in colour are one mesh (tools/farm-coats.json): a coat is that mesh and its slot colours, none
# for the mesh's own coat.
COATS={coat:(family,None if index==0 else colours)
       for family,entry in json.loads((ROOT/'tools/farm-coats.json').read_text()).items()
       for index,(coat,_,colours) in enumerate(entry['coats'])}


def orbital_gun(g):
    g.cylinder(0,0,0,24,1.5,CONCRETE,32)
    g.ring(0,0,1.5,23,21,1.0,STEEL,32)
    g.cylinder(0,0,1.5,11,3,DARK,16)
    g.box((-2,0,7),(18,18,6),STEEL)
    g.box((-11,0,5),(8,13,7),DARK)
    for y in (-5,5):
        g.beam((3,y,8),(23,y,10),3.2,STEEL,8)
        g.beam((19,y,9.6),(25,y,10.2),3.8,DARK,8)
        g.box((2,y,10.5),(6,4,1),CONCRETE)
    for x in (-18,-13,-8):
        for y in (-13,13):
            g.box((x,y,3.8),(4,4,4),STEEL)
            for offset in (-1,0,1):g.box((x+offset,y,5.95),(.35,3,.3),DARK)
    for y in (-10,10):g.box((1,y,8),(5,.4,1.3),(.6,.10,.06))


def debris_face(g, points, role, color=(.93,.93,.93)):
    """Dominant-plane UVs keep fracture cuts textured too; atlas islands never bleed into each other."""
    normal=(Vector(points[1])-Vector(points[0])).cross(Vector(points[2])-Vector(points[0]))
    axis=max(range(3),key=lambda k:abs(normal[k]));axes=[k for k in range(3) if k!=axis]
    uv=[(p[axes[0]],p[axes[1]]) for p in points]
    atlas={'rubble-timber':(0,0),'rubble-brick':(1,0),'rubble-steel':(0,1),
           'fortified-bags':(1,1),'fortified-seams':(1,1)}
    if role in atlas:
        column,row=atlas[role]
        low=[min(p[k] for p in uv) for k in (0,1)];high=[max(p[k] for p in uv) for k in (0,1)]
        uv=[(column*.5+.015+.47*(p[0]-low[0])/max(.001,high[0]-low[0]),
             row*.5+.015+.47*(p[1]-low[1])/max(.001,high[1]-low[1])) for p in uv]
    else:uv=[(u/10,v/10) for u,v in uv]
    g.face(points,color,role,uv)


def rubble(g, variant=0, path=False):
    """Structure-type debris: timber, masonry, reinforced slabs, hardened slabs, wall remnants."""
    rng=random.Random(119+variant)
    for role in ('timber','brick','steel'):g.texture('rubble-'+role,'scenery/demolition-materials.png')
    g.texture('rubble-concrete','sculpt/concrete.png')
    for role in ('rubble-fines','rubble-fracture'):g.texture(role,'scenery/demolition-fines.png')
    # Loose fines form irregular shallow heaps, never a hex plinth. Cleared variants
    # have two independent heaps and an actual 18-pixel corridor through every mesh.
    lobes=[(-20,0,10,28),(20,0,10,28)] if path else [(0,0,32,30)]
    peak=(3.0,4.0,5.4,6.2,3.8)[variant]*(.65 if path else 1)
    def ground(x,y):
        return max(peak*max(0,1-((x-cx)/rx)**2-((y-cy)/ry)**2)**1.5 for cx,cy,rx,ry in lobes)
    for cx,cy,rx,ry in lobes:
        rings=[]
        for fraction in (.025,.3,.6,.82,1):
            ring=[]
            for i in range(48):
                angle=i*2*pi/48;edge=1-.045*sin(angle*7+.3)-.025*cos(angle*13)
                x=cx+rx*fraction*edge*cos(angle);y=cy+ry*fraction*edge*sin(angle)
                ring.append((x,y,max(0,ground(x,y)) if fraction<1 else 0))
            rings.append(ring)
        for inner,outer in zip(rings,rings[1:]):
            for i in range(48):
                j=(i+1)%48;debris_face(g,[inner[i],outer[i],outer[j],inner[j]],'rubble-fines',(.88,.87,.85))
        debris_face(g,rings[0],'rubble-fines',(.88,.87,.85))

    def fragment(x,y,size,role,tilt=None,rebar=0,lift=0):
        length,width,depth=size
        turn=Euler(tilt or (rng.uniform(-.35,.35),rng.uniform(-.4,.4),rng.uniform(0,2*pi))).to_matrix()
        # Chipped corners retain a slab/plank silhouette, with independently broken ends.
        fractured=role=='rubble-concrete' and length>5
        outline=([(-.5,-.24),(-.27,-.5),(.36,-.46),(.5,.04),(.14,.5),(-.4,.38)] if fractured else
                 [(-.5,-.30),(-.38,-.5),(.34,-.5),(.5,-.31),(.5,.30),(.35,.5),(-.35,.5),(-.5,.30)])
        outline=[(a*length*rng.uniform(.86,1.06),b*width*rng.uniform(.9,1.05)) for a,b in outline]
        if fractured:
            jagged=[]
            for a,b in zip(outline,outline[1:]+outline[:1]):
                jagged.extend([a,((a[0]+b[0])*.5+rng.uniform(-.3,.3)*depth,
                                   (a[1]+b[1])*.5+rng.uniform(-.3,.3)*depth)])
            outline=jagged
        count=len(outline)
        local=[Vector((a,b,z*depth+rng.uniform(-.10,.10)*depth)) for z in (-.5,.5) for a,b in outline]
        points=[turn@p for p in local]
        # Both the corridor and the tile envelope constrain the complete transformed fragment.
        if path:
            margin=depth*.35 if fractured else 0
            if x<0:x=min(x,-9.15-margin-max(p.x for p in points))
            else:x=max(x,9.15+margin-min(p.x for p in points))
        if any((x+p.x)**2/38**2+(y+p.y)**2/33**2>1 for p in points):return
        base=lift+max(ground(x+p.x,y+p.y)-p.z for p in points[:count])
        points=[p+Vector((x,y,base)) for p in points]
        tint=rng.uniform(.72,1.03);color=(tint,tint,tint)
        for cap in (list(reversed(points[:count])),points[count:]):
            for triangle in tessellate_polygon([cap]):debris_face(g,[cap[i] for i in triangle],role,color)
        middle=[(points[i]+points[i+count])*.5+turn@Vector((rng.uniform(-.22,.22)*depth,
                rng.uniform(-.22,.22)*depth,rng.uniform(-.1,.1)*depth)) for i in range(count)] if fractured else None
        for i in range(count):
            j=(i+1)%count
            if fractured:
                for a,b in ((points[:count],middle),(middle,points[count:])):
                    for triangle in ([a[i],a[j],b[j]],[a[i],b[j],b[i]]):
                        debris_face(g,triangle,'rubble-fracture',tuple(v*.92 for v in color))
            else:debris_face(g,[points[i],points[j],points[j+count],points[i+count]],role,tuple(v*.9 for v in color))
        if rebar:
            old=g.role;g.role='rubble-steel'
            for n in range(rebar):
                yy=(n-(rebar-1)/2)*width/(rebar+1)
                rod=[Vector((length*.20,yy,0)),Vector((length*.64,yy,.1)),Vector((length*.80,yy+.35,.65))]
                rod=[turn@p+Vector((x,y,base)) for p in rod]
                for p in rod:p.z=max(p.z,ground(p.x,p.y)+.12)
                if path and any(abs(p.x)<9.15 for p in rod):continue
                for a,b in zip(rod,rod[1:]):
                    # A fixed point inside the steel island avoids bleeding other atlas materials onto thin rods.
                    first=len(g.vertices)
                    g.beam(a,b,.16,(.34,.22,.13),5)
                    for at in range(first,len(g.vertices),12):g.vertices[at+10:at+12]=(.24,.73)
            g.role=old

    # A few large, recognisable broken members establish the pile's construction origin.
    for i in range((11,14,17,15,7)[variant]):
        angle=i*2.399963;radius=6+12*(i%5)/4
        x,y=radius*cos(angle),radius*sin(angle)
        if path:x=(-1 if i%2 else 1)*rng.uniform(18,22);y=rng.uniform(-20,20)
        role='rubble-concrete';rebar=0
        if variant==0:
            role='rubble-timber' if i<8 else 'rubble-concrete'
            size=(rng.uniform(11,19),rng.uniform(1.3,2.5),rng.uniform(.7,1.3)) if i<8 else (9,6,1)
        elif variant==1:size=(rng.uniform(7,12),rng.uniform(4,8),rng.uniform(.9,1.8))
        elif variant==2:size=(rng.uniform(10,18),rng.uniform(5,10),rng.uniform(1.4,2.4));rebar=3
        elif variant==3:size=(rng.uniform(11,19),rng.uniform(6,11),rng.uniform(2.6,4.1));rebar=4
        else:size=(rng.uniform(8,13),rng.uniform(3,6),rng.uniform(.7,1.2))
        fragment(x,y,size,role,rebar=rebar)
    # Chipped masonry and aggregate, with a broad size distribution rather than uniform boxes.
    for i in range(125):
        x,y=rng.uniform(-31,31),rng.uniform(-29,29)
        if (x/31)**2+(y/29)**2>1 or path and abs(x)<11:continue
        size=rng.uniform(.5,2.6)
        role='rubble-brick' if variant in (0,1,4) and i%3 else 'rubble-concrete'
        fragment(x,y,(size*1.7,size,size*.65),role)
    # Torn I-section flanges and webs distinguish the reinforced building/bridge families.
    if variant in (2,3):
        positions=[g.vertices[i:i+3] for i in range(0,len(g.vertices),12)]
        solid=[indices[i:i+3] for role,indices in g.parts.items() if role!='rubble-steel'
               for i in range(0,len(indices),3)]
        support=BVHTree.FromPolygons(positions,solid,all_triangles=True)
        for i in range(4):
            x,y=(-18+12*i,rng.uniform(-13,13)) if not path else ((-1 if i%2 else 1)*21,-13+8*i)
            heading=rng.uniform(0,2*pi) if not path else pi/2+rng.uniform(-.18,.18)
            turn=Euler((rng.uniform(-.3,.3),rng.uniform(-.2,.2),heading)).to_matrix()
            length=rng.uniform(13,19)
            cross=[(-1.4,-1.3),(1.4,-1.3),(1.4,-.98),(.18,-.98),(.18,.98),(1.4,.98),
                   (1.4,1.3),(-1.4,1.3),(-1.4,.98),(-.18,.98),(-.18,-.98),(-1.4,-.98)]
            points=[turn@Vector((xx,b,c)) for xx in (-length/2,length/2) for b,c in cross]
            def support_height(p):
                hit,_,_,_=support.ray_cast(Vector((x+p.x,y+p.y,100)),Vector((0,0,-1)))
                return max(ground(x+p.x,y+p.y),hit.z if hit is not None else 0)-p.z
            base=max(support_height(p) for p in points)
            points=[p+Vector((x,y,base)) for p in points]
            for cap in (list(reversed(points[:12])),points[12:]):
                for triangle in tessellate_polygon([cap]):debris_face(g,[cap[i] for i in triangle],'rubble-steel')
            for j in range(12):
                k=(j+1)%12;debris_face(g,[points[j],points[k],points[k+12],points[j+12]],'rubble-steel')
    # Remaining bonded courses make wall rubble distinct from the slab-heavy families.
    if variant in (1,4):
        for segment in range(3 if variant==4 else 2):
            x,y=(-14+14*segment,(-1 if segment%2 else 1)*13) if not path else ((-1 if segment%2 else 1)*22,-12+12*segment)
            rows=(5 if variant==4 else 3)-segment%2
            for row in range(rows):
                for brick in range(max(1,5-row)):
                    fragment(x+(brick-2)*3.2+(row%2)*1.6,y+row*.45,
                             (3.15,1.65,1.4),'rubble-brick',tilt=(.12,.05,0),lift=row*1.3)
    g.smooth('rubble-fines')


def sandbag(g, length=6.8, width=3.8, height=1.6, tint=.9):
    rings=[]
    for x,bulge in ((-.5,.55),(-.38,.94),(0,1),(.38,.94),(.5,.55)):
        ring=[]
        for i in range(8):
            angle=i*2*pi/8;c,s=cos(angle),sin(angle)
            ring.append((x*length,(1 if c>=0 else -1)*abs(c)**.60*width*.5*bulge,
                         height*.5+(1 if s>=0 else -1)*abs(s)**.65*height*.5*bulge))
        rings.append(ring)
    color=(tint,tint,tint)
    debris_face(g,list(reversed(rings[0])),'fortified-bags',color)
    debris_face(g,rings[-1],'fortified-bags',color)
    for a,b in zip(rings,rings[1:]):
        for i in range(8):
            j=(i+1)%8;debris_face(g,[a[i],a[j],b[j],b[i]],'fortified-bags',color)
    # A thin pinched lip follows the seam on either side; it is not a second coplanar skin.
    for side in (-1,1):
        for a,b in zip(rings,rings[1:]):
            i=0 if side>0 else 4
            p,q=Vector(a[i]),Vector(b[i]);p.y+=side*.025;q.y+=side*.025
            debris_face(g,[p,q,q+Vector((0,0,.08)),p+Vector((0,0,.08))],'fortified-seams',(tint*.72,)*3)


def fortified(g):
    rng=random.Random(217)
    for role in ('fortified-bags','fortified-seams'):g.texture(role,'scenery/demolition-materials.png')
    # The source depicts a low sandbag perimeter with open terrain in the middle.
    # Alternate courses use half bags at their ends, avoiding aligned vertical joints.
    for i in range(6):
        a,b=i*pi/3,(i+1)*pi/3
        p,q=Vector((28*cos(a),28*sin(a),0)),Vector((28*cos(b),28*sin(b),0))
        for row in range(3):
            slots=[(3.5+7*n,6.8) for n in range(4)] if row%2==0 else [(1.75,3.3),(7,6.8),(14,6.8),(21,6.8),(26.25,3.3)]
            for distance,length in slots:
                v=p.lerp(q,distance/28)
                g.place(sandbag,x=v.x,y=v.y,z=row*1.5,angle=i*60+120+rng.uniform(-1.1,1.1),
                        length=length,width=3.8,height=1.6,tint=rng.uniform(.76,1.02))
    g.smooth('fortified-bags')


def maglev_piece(g, name):
    """A row on a maglev piece: tools/build_maglev_assets.py owns the platform and vehicle meshes, their ride height
    over the route's rail and the train stamps, so rows on a route stay at Z=0."""
    g.library_row('scenery/maglev/'+name,Matrix.Identity(4))


def maglev_vehicle(g, cab=True):
    """Two cars and their gangway coupler; the cab's nose points to +Y."""
    g.place(maglev_piece,y=-17,name='wagon')
    g.place(maglev_piece,y=17,name='cab' if cab else 'wagon')
    g.place(maglev_piece,name='coupler')


# The legacy maglev sprites (fluff/maglev*.gif, 84x72 px), measured: the route's heading (0 runs N/S, -60 NE/SW and
# 60 NW/SE, +Y then pointing N, NE or NW), the platform's side (-1 left of +Y, 1 right), the train piece and the parked
# cars as (x, y, paint) in that frame, east of the route and turned 60 degrees clockwise from it. A three-hex train is
# a cab hex, a middle hex and a tail hex: maglevtrain1-3 from N to S with the nose N ('cab'), maglevtrain4-6 from SW
# to NE with the nose SW ('cab-reversed').
MAGLEV={
    'maglevtrack1':(0,0,None,()), 'maglevtrack2':(-60,0,None,()), 'maglevtrack3':(60,0,None,()),
    'maglevstation1':(0,-1,None,((17,14,'teal'),(17,2,'silver'),(17,-7,'ochre'),(17,-19,'white'))),
    'maglevstation2':(-60,-1,None,((19.8,13.4,'teal'),(19.6,-16.1,'red'))),
    'maglevstation3':(60,1,None,()),
    'maglevtrain1':(0,0,'cab',((19,-9.5,'silver'),(19,-19,'gray'))),
    'maglevtrain2':(0,-1,'wagons',((19.6,26.1,'steel'),(19.5,14,'silver'),(20.7,-5.6,'yellow'),(20.6,-15.9,'pink'))),
    'maglevtrain3':(0,0,'wagons',((20,-6.2,'yellow'),)),
    'maglevtrain4':(-60,0,'cab-reversed',()),
    'maglevtrain5':(-60,-1,'wagons',((20.3,13.3,'maroon'),(19,-5.2,'silver'),(19.7,-16.1,'red'))),
    'maglevtrain6':(-60,0,'wagons',((18.8,3.4,'magenta'),)),
}
# A route marker's sides (N=1, NE=2, SE=4, S=8, SW=16, NW=32) by heading.
MAGLEV_SIDES={0:9,-60:18,60:36}


def maglev(g, stem):
    angle,platform,train,cars=MAGLEV[stem]
    # The route marker names no mesh: the client draws its rail from the stored sides. The straight beam mesh that
    # only the legacy render drew (gone since batch 9) is no longer exported.
    if g.shared is not None:
        g.component('scenery/maglev/route',g.transform @ Matrix.Rotation(radians(angle),4,'Z'))
        g.components[-1]['connections']=MAGLEV_SIDES[angle]
    if platform:g.place(maglev_piece,x=15*platform*cos(radians(angle)),y=15*platform*sin(radians(angle)),angle=angle,
                        name='platform')
    if train:g.place(maglev_vehicle,angle=angle+(180 if train=='cab-reversed' else 0),cab=train!='wagons')
    for x,y,paint in cars:
        g.place(car,x=x*cos(radians(angle))-y*sin(radians(angle)),y=x*sin(radians(angle))+y*cos(radians(angle)),
                angle=angle-60,scale=.75,paint=paint)


# The red lens of the landing beacons, lights and crossing lamps.
LAMP=(.85,.07,.025)


# The landing lights of the heli pads fluff/heli1-3 (measured on the sprites): the pad centre, where
# tools/build_board_decals.py places the pad decal (HELI_PADS), and the lights' directions; each light stands
# HELI_LIGHT_RADIUS px from the centre, turned to its direction.
HELI_LIGHTS={'heli1':((-3,-5),(60,)),'heli2':((0,-.5),(0,60,120,180,240,300)),'heli3':((-3,5),(-60,))}
HELI_LIGHT_RADIUS=34


def landing_light(g):
    """A heli pad's landing light (the lamp boxes of fluff/heli1-3): a rust housing on a darker base band and a red
    lens dome. Origin at the base centre, a side facing +X."""
    rust=(.56,.25,.20)
    g.box((0,0,.25),(7,7,.5),tuple(c*.62 for c in rust))
    g.box((0,0,1.5),(7,7,2),rust)
    # The lens's lower half stays inside the housing, as the beacons' lens does.
    g.ellipsoid((0,0,2.5),(2.2,2.2,1.5),LAMP,16,5)


def crossing_signal(g):
    """A level-crossing signal (the lamp marks of hq_fluff/rail_road01-06): a steel mast on a concrete footing, a
    St Andrew's cross on top and two red lamps under hoods on a black backplate, all facing +Y. Origin at the base."""
    g.box((0,0,.2),(1.4,1.4,.4),CONCRETE)
    g.box((0,0,5.2),(.4,.4,9.6),STEEL)
    g.box((0,.3,7.4),(2.6,.2,1),DARK)
    for x in (-.75,.75):
        g.beam((x,.4,7.4),(x,.5,7.4),.7,LAMP,12)
        g.box((x,.62,7.82),(.9,.44,.08),DARK)
    # Two boards crossed at 45 degrees, red with a white face, the second just in front of the first.
    old=g.transform.copy()
    for i,angle in enumerate((45,-45)):
        g.transform=old @ Matrix.Translation((0,.26+.1*i,9.5)) @ Matrix.Rotation(radians(angle),4,'Y')
        g.box((0,0,0),(3.4,.06,.6),(.70,.06,.05))
        g.box((0,.03,0),(3.0,.04,.34),WHITE)
    g.transform=old


# The legacy rail sprites hq_fluff/rail00-63 (FLUFF 10:0-63): the token is the route's side mask, so each key decodes
# to one route marker with those sides, and the client builds the track from them (rail00, no sides, takes its sides
# from the neighbours). The level crossings rail_road01-06 (FLUFF 10:64-69), measured: the rail's and the road's
# axes as side masks.
RAIL_CROSSINGS={'rail_road01':(9,36),'rail_road02':(9,18),'rail_road03':(18,9),'rail_road04':(36,9),
                'rail_road05':(36,18),'rail_road06':(18,36)}


def rail(g, stem):
    """A rail sprite's route marker; a level crossing adds its panel decal and four signals."""
    sides,road=RAIL_CROSSINGS[stem] if stem in RAIL_CROSSINGS else (int(stem[4:]),None)
    g.component('scenery/rail/route',g.transform)
    g.components[-1]['connections']=sides
    if road is None:return
    axis={mask:angle for angle,mask in MAGLEV_SIDES.items()}
    rail_angle,road_angle=axis[sides],axis[road]
    # The decal's two 15 px strips run at its turn and 60 degrees anticlockwise from it.
    g.component('decal/rail/level-crossing',g.transform @ Matrix.Rotation(
        radians(rail_angle if (road_angle-rail_angle)%180==60 else road_angle),4,'Z'))
    along=Vector((-sin(radians(road_angle)),cos(radians(road_angle))))
    across=Matrix(((along.y,-along.x),(cos(radians(rail_angle)),sin(radians(rail_angle)))))
    for road_side in (-1,1):
        for rail_side in (-1,1):
            # Beside the road, 10 px from its centre line, and just outside the panel, 8.5 px from the track's; each
            # signal faces the road traffic that comes towards it.
            x,y=across.inverted() @ Vector((road_side*10,rail_side*8.5))
            g.place(crossing_signal,x=x,y=y,angle=road_angle+(0 if along.dot(Vector((x,y)))>0 else 180))


def geyser(g, magma=False):
    rng=random.Random(51)
    count=80
    angles=[i*2*pi/count for i in range(count)]
    uneven=[1+.10*sin(a*3+.4)+.075*sin(a*7-1)+.035*sin(a*19) for a in angles]
    # Shallow irregular deposits meet the terrain at zero height. Detailed albedo,
    # smooth mineral slopes and the terrain's own rock materials replace flat-colored facets.
    profile=([(20,0),(17,.45),(13,1.7),(8.5,4.2),(5.4,5.4),(3.7,1.7)] if magma else
             [(20,0),(17,.25),(14,.65),(11.5,1.1),(9.4,1.65),(7.8,.55)])
    rings=[[(r*f*cos(a),r*f*sin(a),z*(1+.21*sin(5*a+.8)+.13*sin(11*a)))
            for a,f in zip(angles,uneven)] for r,z in profile]
    g.texture('geyser-mineral','scenery/geyser-travertine.png')
    g.texture('geyser-rock','sculpt/volcano-basalt.png' if magma else 'sculpt/rock.png')
    g.texture('geyser-water','pool-water.png')
    g.texture('geyser-lava','magma/lava.png')
    for band,(outer,inner) in enumerate(zip(rings,rings[1:])):
        for i in range(count):
            j=(i+1)%count
            color=(.93,.93,.93) if magma else ((.76,.72,.63) if band==0 else (.94,.92,.85))
            points=[outer[i],outer[j],inner[j],inner[i]]
            g.face(points,color,'geyser-rock' if magma else 'geyser-mineral',
                   [(x/32+.5,y/32+.5) for x,y,z in points])
    liquid_z=1.85 if magma else .84
    water=[(p[0],p[1],liquid_z) for p in rings[-1]]
    for i in range(count):
        points=[(0,0,liquid_z),water[i],water[(i+1)%count]]
        g.face(points,(1,1,1) if magma else (.52,.76,.78),'geyser-lava' if magma else 'geyser-water',
               [(x/35+.5,y/35+.5) for x,y,z in points])
    if magma:
        # Narrow branching fissures follow the same sculpted surface, raised enough to clear the
        # 0.1 px coplanar margin. Runtime applies the shared animated lava material.
        for start in (4,29,57):
            for band in range(1,len(rings)-1):
                i=(start+band%2)%count;j=(i+1)%count
                k=(start+(band+1)%2)%count;l=(k+1)%count
                points=[rings[band][i],rings[band][j],rings[band+1][l],rings[band+1][k]]
                g.face([(x,y,z+.25) for x,y,z in points],(1,1,1),'geyser-lava')
    for i in range(12):
        a=i*2.39996+rng.uniform(-.25,.25);r=rng.uniform(11.5,18)
        size=(rng.uniform(1.1,3.2),rng.uniform(1,2.7),rng.uniform(.7,2.7))
        g.place(lambda mesh:mesh.ellipsoid((0,0,size[2]*.55),size,(.94,.94,.94),11,5,floor=0),
                x=r*cos(a),y=r*sin(a),angle=rng.uniform(0,360),role='geyser-rock')
    # Average coincident face normals within each stone/mineral part, preserving
    # the rim/liquid boundary. The dynamic jet is owned by GpuGeysers, never baked.
    for role in ('geyser-mineral','geyser-rock'):g.smooth(role)
    # Avoid unused textures/materials in the water and magma variants.
    g.parts={role:indices for role,indices in g.parts.items() if indices}
    g.materials={role:g.materials[role] for role in g.parts}


# Shared meshes and their ids under scenery/. None: the call names it (asset_name); every car is vehicles/car.
SHARED={bevel:'roofs/bevel', ledge:'roofs/ledge', roof_grille:'roofs/grille', chimney_stack:'roofs/chimney-stack',
        skylight:'roofs/skylight', garden_bed:'parks/garden-bed', pillar:'parks/pillar', picnic_table:'parks/picnic-table',
        hex_plaza:'parks/plaza', fountain:'parks/fountain', grandstand:'parks/grandstand',
        concrete_pipe:'construction/concrete-pipe', crane:'construction/crawler-crane', bulldozer:'construction/bulldozer',
        site_debris:None,
        car:None, parking_barrier:'vehicles/parking-barrier', shelter:'vehicles/parking-shelter',
        pool_basin:None, pool_deck:None, landing_light:'roofs/landing-light',
        crossing_signal:'rail/crossing-signal'}
# Palette objects, exported whether or not a legacy layout row names them (heli pads name the landing light, level
# crossings the signal).
PALETTE={'scenery/parks/bench':bench, 'scenery/pools/rectangular':pool,
         'scenery/roofs/landing-light':landing_light, 'scenery/rail/crossing-signal':crossing_signal}
# Legacy images whose artwork is one baked mesh, and that mesh's id under scenery/. No mesh is written
# at a legacy key: layouts.json decodes the key (scenery/<image path>) to its mesh with one row.
SEAPORT_AXES={1:'n-s',2:'ne-sw',3:'nw-se',4:'e-w'}
NAMES={
    'fluff/beacon1':'roofs/landing-beacon-hex','fluff/beacon2':'roofs/landing-beacon-round',
    'fluff/construction2':'construction/site-excavation',
    'fluff/square2':'parks/plaza-pillars','fluff/square3':'parks/plaza-hedge','fluff/square4':'parks/plaza-pond',
    'fluff/square5':'parks/plaza-flowers-pillars','fluff/square6':'parks/plaza-flowers',
    'saxarba/SMV_Fluff/FluffSystem-01-Building-07-GlassRoof-2-01':'roofs/glass-roof-wide',
    'saxarba/SMV_Fluff/FluffSystem-01-Building-07-GlassRoof-3-01':'roofs/glass-dome',
    'saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-01':'parks/formal-garden-hex',
    'saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-02':'parks/formal-garden-round',
    'saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-04':'parks/formal-garden-star',
    **{f'saxarba/misc/rubble_{kind}':f'rubble/{kind}' for kind in ('light','medium','heavy','hardened','wall')},
    **{f'saxarba/rubble_{kind}_path':f'rubble/{kind}-path' for kind in ('light','medium','heavy','hardened','wall')},
    'saxarba/misc/geyser_water_off':'geysers/water-dormant','saxarba/misc/geyser_water_on':'geysers/water-erupting',
    'saxarba/misc/geyser_magma':'geysers/magma','saxarba/misc/fortified':'military/fortification',
    'UlyssesSprites/orbitalguns/OrbitalGunE':'military/orbital-gun',
    # Seaport sets 1-4 are the container rows' axis; the numbers are the source's variants.
    **{f'saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-{s}-{n:02d}':f'seaport/containers-{axis}-{n:02d}'
       for s,axis in SEAPORT_AXES.items() for n in range(1,8)},
    **{f'saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-{s}-{n:02d}':
       f'seaport/gantry-crane-{axis}-{n:02d}' for s,axis in SEAPORT_AXES.items() for n in range(1,13)},
    # The straight (N) and diagonal (NE) tips; the other four directions are rows on them (CRANE_TIPS).
    **{f'saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-{n:02d}':f'seaport/crane-tip-{n:02d}'
       for n in range(1,3)},
}


# Crane tip direction -> the baked tip it turns: S is N turned 180 degrees; SE, SW and NW turn the NE tip.
CRANE_TIPS={3:2,4:1,5:2,6:2}


def mesh_id(name):
    """The id of the baked mesh that legacy image `name` decodes to."""
    return 'scenery/'+NAMES[Path(name).with_suffix('').as_posix()]


def build_mesh(name, layouts, shared=None):
    g=Mesh(shared); stem=Path(name).stem; layout=layouts.get(name,{})
    if name.startswith('fluff/skylight'):
        g.place(skylight,x=-1,y=1,angle=-(int(stem[-1])-1)*30)
    elif 'GlassRoof' in name:
        n=int(stem[-2:]); group=int(stem.split('-')[-2])
        if group==3:
            g.cylinder(0,0,0,30,2,STEEL)
            g.ellipsoid((0,0,1.6),(29,29,9),GLASS,16,6)
            for a in range(0,360,45):
                for k in range(6):
                    u,v=k*pi/12,(k+1)*pi/12
                    g.beam((29*cos(u)*cos(radians(a)),29*cos(u)*sin(radians(a)),1.6+9*sin(u)),
                           (29*cos(v)*cos(radians(a)),29*cos(v)*sin(radians(a)),1.6+9*sin(v)),.6,STEEL,4)
            # The dome's lower cap reaches below its ring; ground it where legacy SCENERY grounding put it.
            recentre(g,xy=False)
        else:
            # Variants 02-04 are rotations of variant 01 and decode as rows on its mesh. The narrow roof (group 1,
            # 29 px over its curbs) is the wide one (36 px) stretched across its width.
            angle=(0,90,-60,60)[(n-1)%4]
            if group==2 and n==1:skylight(g,width=34,length=58,rows=4)
            else:g.instance('scenery/roofs/glass-roof-wide',skylight,angle,stretch=(29/36 if group==1 else 1,1,1),
                            width=34,length=58,rows=4)
    elif name.startswith('fluff/ledge'):g.place(ledge,angle=-(int(stem[-1])-1)*60)
    elif name.startswith('fluff/stack'):g.place(roof_vent,angle=-(int(stem[-1])-1)*60)
    elif name.startswith('fluff/bevel'):g.place(bevel,angle=-(int(stem[-1])-1)*60)
    elif name.startswith('fluff/construction'):
        # The board already supplies the supporting terrain; export equipment/debris only.
        n=int(stem[-1])
        if n==2:
            excavation(g);site_debris(g,2)
        else:
            if n==1:g.place(crane,x=-5,y=-9,angle=-55)
            else:g.place(bulldozer,angle=-55)
            g.place(site_debris,n=n,asset_name=f'construction/debris-{n}')
    elif name.startswith('fluff/cars'):
        # Only roadside objects belong in the GLB. The board's shared road engine supplies the road.
        for x,y,angle,paint in layout['cars']:g.place(car,x=x,y=y,angle=angle,paint=paint,scale=.8)
        if stem in ('cars_7','cars_2b'):g.place(shelter,x=-7,y=-22,angle=-30)
        if stem in ('cars_8','cars_3b'):g.place(parking_barrier)
        # tools/build_board_decals.py adds the standard car-park decal rows and the cars' seats afterwards.
    elif name.startswith('fluff/square'):garden(g,int(stem[-1])-1)
    elif name.startswith('fluff/pillars'):
        for x,y in layout['pillars']:g.place(pillar,x=x,y=y)
    elif name.startswith('fluff/garden'):
        g.place(garden_bed,angle=-(int(stem[-1])-1)*60)
        a=radians(-(int(stem[-1])-1)*60)
        for i,(x,y) in enumerate(((-9,-6),(10,-10),(-7,-25),(11,-26),(-1,-18))):
            g.tree(x*cos(a)-y*sin(a),x*sin(a)+y*cos(a),9,i)
    elif name.startswith('fluff/pool'):
        g.place(pool_basin,outline=pool_shape(1),asset_name='pools/freeform')
        for i,(x,y) in enumerate(layout['trees']):g.tree(x,y,9,i)
    elif name.startswith('fluff/suburb'):
        n=int(stem[-1])
        if n==1:
            g.place(pool_basin,x=-10,y=4,scale=.75,deck=False,asset_name='pools/round-no-deck',
                    outline=[(18*cos(i*pi/16),18*sin(i*pi/16)) for i in range(32)])
            g.place(grandstand,x=22.7,y=6,angle=30)
            for i in range(3):g.place(car,x=-4+i*7,y=-22+i*2,scale=.75,angle=30,
                                   paint=('mustard','turquoise','red')[i])
        elif n==2:
            g.place(shelter,x=-11,y=18,angle=-30,floor=False,asset_name='vehicles/parking-shelter-no-floor')
            g.place(picnic_table,x=12,y=-3,angle=-30,scale=1.3)
            for i,(x,y) in enumerate(layout['trees']):g.tree(x,y,9,i)
            for i in range(3):g.place(car,x=-12+i*5,y=6-i*6,scale=.65,angle=30,paint='magenta')
        else:
            g.place(pool_basin,x=-8,y=0,angle=30,scale=.5,outline=round_rectangle(25,45,2),deck=False,
                    asset_name='pools/rectangular-no-deck')
            for i in range(3):g.place(concrete_pipe,x=10+i*4,y=-7+i*2)
            g.place(car,x=5,y=22,angle=30,scale=.65,paint='red')
    elif name.startswith('fluff/heli'):
        # Rows only: tools/build_board_decals.py adds the pad decal row and keeps these.
        (x,y),angles=HELI_LIGHTS[stem]
        for angle in angles:
            g.place(landing_light,x=x+HELI_LIGHT_RADIUS*cos(radians(angle)),y=y+HELI_LIGHT_RADIUS*sin(radians(angle)),
                    angle=angle)
    elif name.startswith('fluff/beacon'):
        g.cylinder(0,0,0,22,3,DARK,6 if stem[-1]=='1' else 24)
        g.ring(0,0,3,9,6,1.5,STEEL)
        g.ellipsoid((0,0,4),(6,6,3),LAMP,16,5)
    elif stem in MAGLEV:
        maglev(g,stem)
    elif name.startswith('hq_fluff/rail'):
        rail(g,stem)
    elif stem in HERDS_BY_STEM:
        for asset,x,y,angle,scale in HERDS_BY_STEM[stem]:
            asset,colours=COATS.get(asset,(asset,None))
            g.library_row('scenery/'+asset,Matrix.Translation((x,y,0)) @ Matrix.Rotation(radians(angle),4,'Z') @ Matrix.Scale(scale,4),
                          colours)
    elif '/SMV_Seaport/' in name:
        for x,y,angle,color in layout.get('containers',[]):
            g.place(container,x=x,y=y,angle=angle,color=color,role='containers')
        for index in layout['grabbers']:
            x,y,angle,_=layout['containers'][index]
            g.place(container_grabber,x=x,y=y,z=6.43,angle=angle,role='container-grabbers')
        if 'crane' in layout:
            c=layout['crane']
            if not c['tip']:g.place(gantry_support,angle=c['angle'],role='crane-support')
            if c['tip'] and c['direction'] in CRANE_TIPS:
                base=Path(name).with_stem(stem[:-2]+f"{CRANE_TIPS[c['direction']]:02d}").as_posix()
                g.instance(mesh_id(base),gantry_boom,c['angle'],base_angle=layouts[base]['crane']['angle'],
                           half_span=c['half_span'],tip=True,role='crane-boom')
            else:g.place(gantry_boom,angle=c['angle'],half_span=c['half_span'],tip=c['tip'],role='crane-boom')
    elif 'road_trees' in stem:
        for i,(x,y) in enumerate(layout.get('trees',[])):g.tree(x,y,12,i)
    elif '/SMV_Fluff/' in name:
        if 'SwimmingPool' in stem:
            n=int(stem[-2:])
            if n==1:
                g.place(pool_deck,shape=1,asset_name='pools/sport-1-deck')
                g.place(pool_basin,y=7,outline=round_rectangle(18,38,1.5),deck=False,asset_name='pools/sport-1-main')
                g.place(pool_basin,y=-25,outline=round_rectangle(18,12,1.5),deck=False,asset_name='pools/sport-1-wading')
            elif n==3:
                islands=[(x,y) for x,y in layout.get('trees',[]) if inside_outline(x,y,pool_shape(3))]
                g.place(pool_deck,shape=3,islands=islands,asset_name='pools/sport-3-deck')
                g.place(pool_basin,outline=pool_shape(3),deck=False,asset_name='pools/sport-3-main')
                g.place(pool_basin,y=-28,outline=[(4*cos(i*pi/20),4*sin(i*pi/20)) for i in range(40)],deck=False,
                        asset_name='pools/sport-3-wading')
            else:g.place(pool_basin,outline=round_rectangle(48,28,4) if n==5 else pool_shape(n),
                         asset_name=f'pools/sport-{n}')
        elif 'Lake' in stem:
            n=int(stem[-2:])
            shape=1 if n in (1,3,5) else n
            # A pond is the pool of the same outline in the pond colours.
            g.place(pool_basin,outline=pool_shape(shape),angle=(n-1)*30,scale=.85,colours=POND,
                    asset_name='pools/freeform' if shape==1 else f'pools/sport-{shape}')
        elif 'Landscape' in stem:
            n=int(stem[-2:])
            # Landscape 03 is the same mesh as 02.
            if n==3:g.instance(mesh_id(Path(name).with_stem(stem[:-2]+'02')),landscape,0,n=2)
            else:landscape(g,n)
        elif 'Garden' in stem:
            if 'Table' in stem:
                for x,y in layout['tables']:g.place(picnic_table,x=x,y=y,scale=.65)
        else:return None
        if 'Landscape' not in stem:
            # Tree rows stand at Z=0, also on the pool islands: a decoration offset cannot carry a model height.
            for i,(x,y) in enumerate(layout.get('trees',[])):g.tree(x,y,10,i)
    elif '/orbitalguns/' in name:
        angle={'E':0,'N':90,'S':-90,'W':180}[stem[-1]]
        # N, S and W are rotations of E and decode as rows on its mesh.
        if angle:g.instance(mesh_id(Path(name).with_stem(stem[:-1]+'E')),orbital_gun,angle)
        else:orbital_gun(g)
    elif 'rubble' in stem and 'cleared' not in stem:
        variant=next(i for i,kind in enumerate(('light','medium','heavy','hardened','wall')) if kind in stem)
        rubble(g,variant,path='path' in stem)
    elif stem=='fortified':fortified(g)
    elif stem.startswith('geyser'):
        geyser(g,magma='magma' in stem)
    else:return None
    return g if g.vertices or g.components else None


def blender_mesh(scene, name, mesh, location):
    values=mesh.vertices; points=[values[i:i+3] for i in range(0,len(values),12)]
    faces=[indices[i:i+3] for indices in mesh.parts.values() for i in range(0,len(indices),3)]
    data=bpy.data.meshes.new(name);data.from_pydata(points,[],faces);data.update()
    colors=data.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='POINT')
    colors.data.foreach_set('color',[v for i in range(0,len(values),12) for v in (*[linear(c) for c in values[i+6:i+9]],values[i+9])])
    uv=data.uv_layers.new(name='UVMap')
    for loop in data.loops:
        u,v=values[loop.vertex_index*12+10:loop.vertex_index*12+12]
        uv.data[loop.index].uv=(u,1-v) # glTF/runtime images use a top-left UV origin.
    data.normals_split_custom_set_from_vertices([values[i+3:i+6] for i in range(0,len(values),12)])
    offset=0
    for role,indices in mesh.parts.items():
        source=mesh.materials[role]
        material_name=('Scenery foliage / ' if 'alphaTest' in source else 'Scenery ')+role
        if source.get('textures'):material_name+=' / '+Path(source['textures'][0]['filename']).stem
        mat=bpy.data.materials.get(material_name)
        if mat is None:
            mat=bpy.data.materials.new(material_name);mat.use_nodes=True
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            vertex=mat.node_tree.nodes.new('ShaderNodeVertexColor');vertex.layer_name='Color'
            mat.node_tree.links.new(vertex.outputs['Color'],bsdf.inputs['Base Color'])
            bsdf.inputs['Roughness'].default_value=.68
            if source.get('textures'):
                texture=mat.node_tree.nodes.new('ShaderNodeTexImage')
                filename=source['textures'][0]['filename']
                if (BOARD/filename).exists():
                    texture.image=bpy.data.images.load(str(BOARD/filename),check_existing=True)
                    mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
                    mat.node_tree.links.new(vertex.outputs['Color'],mix.inputs[1]);mat.node_tree.links.new(texture.outputs['Color'],mix.inputs[2])
                    mat.node_tree.links.new(mix.outputs[0],bsdf.inputs['Base Color'])
                    if 'alphaTest' in source:
                        threshold=mat.node_tree.nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN'
                        threshold.inputs[1].default_value=source['alphaTest']
                        mat.node_tree.links.new(texture.outputs['Alpha'],threshold.inputs[0])
                        mat.node_tree.links.new(threshold.outputs[0],bsdf.inputs['Alpha'])
                    for mapping in source['textures'][1:]:
                        detail=mat.node_tree.nodes.new('ShaderNodeTexImage')
                        detail.image=bpy.data.images.load(str(BOARD/mapping['filename']),check_existing=True)
                        detail.image.colorspace_settings.name='Non-Color'
                        if mapping['type']=='NORMAL':
                            normal=mat.node_tree.nodes.new('ShaderNodeNormalMap')
                            mat.node_tree.links.new(detail.outputs['Color'],normal.inputs['Color'])
                            mat.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
                        elif mapping['type']=='AMBIENT':
                            channels=mat.node_tree.nodes.new('ShaderNodeSeparateColor')
                            mat.node_tree.links.new(detail.outputs['Color'],channels.inputs[0])
                            mat.node_tree.links.new(channels.outputs['Green'],bsdf.inputs['Roughness'])
        slot=len(data.materials);data.materials.append(mat)
        for polygon in data.polygons[offset:offset+len(indices)//3]:polygon.material_index=slot
        offset+=len(indices)//3
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=location
    return obj


def export_mesh(asset, mesh):
    target=BOARD/(asset+'.glb');target.parent.mkdir(parents=True,exist_ok=True)
    assert mesh.vertices,'Empty mesh: '+asset
    data=mesh.data(Path(asset).name)
    for mat in data['materials']:
        for texture in mat.get('textures',[]):
            if 'data' not in texture:
                texture['filename']=os.path.relpath(BOARD/texture['filename'],target.parent).replace('\\','/')
    if len(mesh.vertices)//12>65000:raise ValueError('Scenery exceeds rigid mesh budget: '+asset)
    write_glb(target,levels={0:data},extras={'mmColourSlots':mesh.colour_slots} if any(mesh.slots) else None)


def export_palette():
    """The palette objects alone, without rebuilding the catalogue (the `--palette` argument)."""
    for asset,function in PALETTE.items():
        mesh=Mesh();function(mesh);export_mesh(asset,mesh)
    return sorted(PALETTE)


def build(only=None):
    rows,_=declarations();layouts=json.loads((REVIEW/'layouts.json').read_text())
    scene=bpy.data.scenes.new('Board scenery / tileset catalog')
    if bpy.context.window:bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC'
    inventory_path=REVIEW/'model-inventory.json'
    stats=json.loads(inventory_path.read_text()) if only is not None and inventory_path.exists() else {}
    layout_path=BOARD/'scenery/layouts.json'
    compositions=json.loads(layout_path.read_text()) if only is not None and layout_path.exists() else {}
    shared={}
    built=0
    for name in sorted({r['image'] for r in rows if r['image']}):
        if only is not None and not any(key in name for key in only):continue
        mesh=build_mesh(name,layouts,shared)
        if mesh is None:continue
        asset=asset_id(name)
        if mesh.components:
            # A layout row never names its own key: baked geometry beside rows is a component of its own.
            assert not mesh.vertices,'Composition with baked geometry: '+name
            compositions[asset]=mesh.components
            preview=build_mesh(name,layouts)
        else:
            # Rows stand on their receiver. Only seaport crane tips are raised: they hang from the gantry boom.
            preview=mesh
            export_mesh(mesh_id(name),mesh)
            compositions[asset]=[{'asset':mesh_id(name),'position':[0.0,0.0,0.0],'rotation':0.0,'scale':1.0}]
        index=built
        built+=1
        # A plain rail key is only its route marker: the client generates the track, so there is nothing to preview.
        if preview.vertices:blender_mesh(scene,name,preview,((index%12)*100,-(index//12)*100,0))
        stats[name]={'asset':asset,'vertices':len(mesh.vertices)//12,'triangles':sum(len(v)//3 for v in mesh.parts.values()),
                     'height':round(max(preview.vertices[2::12])-min(preview.vertices[2::12]),3) if preview.vertices else 0,
                     'components':len(mesh.components),
                     'trees':sum(c['asset']=='tree-broad' for c in mesh.components)}
    for asset,mesh in shared.items():export_mesh(asset,mesh)
    export_palette()
    REVIEW.mkdir(parents=True,exist_ok=True)
    (REVIEW/'model-inventory.json').write_text(json.dumps(stats,indent=2)+'\n')
    layout_path.write_text(json.dumps(compositions,indent=2)+'\n')
    scene.world=bpy.data.worlds.new('Scenery studio world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.25,.30,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    scene.render.engine='CYCLES';scene.cycles.samples=24
    scene.view_settings.view_transform='AgX'
    source='board-scenery-compositions.blend'
    bpy.data.libraries.write(str(ROOT/'tools'/source),{scene},fake_user=True)
    return {'scene':scene.name,'models':built,'layouts':len(compositions),'shared_components':len(shared),
            'trees':sum(c['asset']=='tree-broad' for v in compositions.values() for c in v),
            'triangles':sum(v['triangles'] for v in stats.values()),
            'largest':max(stats.items(),key=lambda v:v[1]['vertices']) if stats else None}


if __name__=='__main__':
    # blender --background --factory-startup --python tools/build_scenery_assets.py -- [--palette | image name parts]
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    print(export_palette() if args==['--palette'] else build(args or None))
