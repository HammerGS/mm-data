"""Check exported scenery for overlapping roofs/rims, exposed garden fill and redundant ground slabs."""
import json
import math
from collections import Counter
from pathlib import Path

from glb_geometry import read_glb

ROOT = Path(__file__).resolve().parents[1]
SCENERY = ROOT/'data/models/board/scenery'
LAYOUTS = json.loads((SCENERY/'layouts.json').read_text())
# layouts.json maps each legacy key that was one mesh to that mesh with one row; invert it to find the source image.
# Only an unturned, unstretched row is the mesh's own image: crane tips 03-06 are turned rows on tips 01 and 02.
LEGACY = {rows[0]['asset']: key for key, rows in LAYOUTS.items()
          if len(rows) == 1 and rows[0]['rotation'] == 0 and 'stretch' not in rows[0]}
# Batch 10 pieces under scenery/: (lowest Z, size X, Y, Z) in model px (data/models/board/README.md, Rail pieces). Rail
# pieces have their origin at rail top, track along Y.
PIECES = {'roofs/landing-light': (0, (7, 7, 4)), 'rail/crossing-signal': (0, (2.83, 1.54, 10.91)),
          'rail/buffer-stop': (-.5, (6.6, 8.29, 7.1)), 'rail/locomotive': (0, (8.88, 56, 13.95)),
          'rail/coach': (0, (8.76, 62, 12.25)), 'rail/box-car': (0, (9.5, 46, 13.15)),
          'rail/tank-car': (0, (8.81, 42, 13.33)), 'rail/ore-hopper': (0, (9.3, 40, 12.97)),
          'rail/heavy-flatbed': (0, (8.8, 48, 13.1)), 'rail/express-power-car': (0, (8.5, 64, 13.23)),
          'rail/express-car': (0, (8.58, 62, 11.95)), 'rail/colony-locomotive': (0, (9.22, 56, 12.5)),
          'rail/container-wagon': (0, (8.8, 46, 12.72)), 'rail/heavy-hopper': (0, (9.49, 42, 14.11)),
          'rail/insulated-tanker': (0, (8.77, 42, 13.83)), 'rail/equipment-carrier': (0, (8.8, 48, 13.74))}


def image(file):
    """The tileset image (without extension) whose artwork a renamed scenery mesh bakes."""
    return LEGACY['scenery/'+file.relative_to(SCENERY).with_suffix('').as_posix()][len('scenery/'):]


def signed(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def intersection_area(first, second):
    polygon = first
    if signed(*second) < 0: second = list(reversed(second))
    for a, b in zip(second, second[1:]+second[:1]):
        clipped = []
        for p, q in zip(polygon, polygon[1:]+polygon[:1]):
            u, v = signed(a, b, p), signed(a, b, q)
            if u >= 0: clipped.append(p)
            if (u >= 0) != (v >= 0):
                t = u/(u-v)
                clipped.append([p[k]+t*(q[k]-p[k]) for k in (0, 1)])
        polygon = clipped
        if not polygon: return 0
    return abs(sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(polygon, polygon[1:]+polygon[:1])))/2


def hull(points):
    points=sorted(set(points))
    def half(ordered):
        result=[]
        for p in ordered:
            while len(result)>1 and signed(result[-2],result[-1],p)<=0:result.pop()
            result.append(p)
        return result
    return half(points)[:-1]+half(reversed(points))[:-1]


def mesh_triangles(data, role):
    for mesh in data['meshes']:
        values=mesh['vertices']
        for part in mesh['parts']:
            if part['id']!=role:continue
            for i in range(0,len(part['indices']),3):
                yield [values[j*12:j*12+3] for j in part['indices'][i:i+3]]


def below(points, ceiling):
    clipped=[]
    for a,b in zip(points,points[1:]+points[:1]):
        if a[2]<=ceiling:clipped.append(a[:2])
        if (a[2]<=ceiling)!=(b[2]<=ceiling):
            t=(ceiling-a[2])/(b[2]-a[2]);clipped.append([a[k]+t*(b[k]-a[k]) for k in (0,1)])
    return clipped


def main():
    files = list((SCENERY/'seaport').glob('*.glb'))
    checked, overlaps = 0, []
    for file in files:
        data = read_glb(file, 0)
        roofs = []
        for mesh in data['meshes']:
            values = mesh['vertices']
            for part in mesh['parts']:
                indices = part['indices']
                for i in range(0, len(indices), 3):
                    points = [values[index*12:index*12+3] for index in indices[i:i+3]]
                    if all(abs(p[2]-6.4) < .0001 for p in points): roofs.append([p[:2] for p in points])
        checked += len(roofs)
        for i, first in enumerate(roofs):
            for second in roofs[i+1:]:
                area = intersection_area(first, second)
                if area > .001: overlaps.append({'file': file.name, 'area': round(area, 5)})
    pools, bad_edges, coping_overlaps = 0, [], []
    for file in SCENERY.rglob('*.glb'):
        if file.parent.name != 'pools' and not file.stem.startswith(('plaza-', 'fountain')): continue
        data = read_glb(file, 0)
        edges, tops = Counter(), []
        for mesh in data['meshes']:
            values = mesh['vertices']
            for part in mesh['parts']:
                if part['id'] not in ('pool-coping', 'pool-deck', 'pool-wall'): continue
                indices = part['indices']
                for i in range(0, len(indices), 3):
                    points = [tuple(round(v, 5) for v in values[index*12:index*12+3]) for index in indices[i:i+3]]
                    for a, b in zip(points, points[1:]+points[:1]): edges[tuple(sorted((a, b)))] += 1
                    if part['id'] == 'pool-coping' and max(p[2] for p in points)-min(p[2] for p in points) < .0001:
                        tops.append(points)
        if not edges: continue
        pools += 1
        if any(count != 2 for count in edges.values()): bad_edges.append(file.name)
        for i, first in enumerate(tops):
            for second in tops[i+1:]:
                if abs(first[0][2]-second[0][2]) > .0001: continue
                if any(max(p[k] for p in first) <= min(p[k] for p in second)
                       or max(p[k] for p in second) <= min(p[k] for p in first) for k in (0, 1)): continue
                if intersection_area([p[:2] for p in first], [p[:2] for p in second]) > .001:
                    coping_overlaps.append(file.name)
    squares, outside = 0, []
    for file in (SCENERY/'parks').glob('plaza-*.glb'):
        values=read_glb(file,0)['meshes'][0]['vertices']
        green,border=[],[]
        for i in range(0,len(values),12):
            p=values[i:i+3];color=values[i+6:i+9]
            if max(abs(a-b) for a,b in zip(color,(.22,.34,.12)))<.001:green.append(tuple(p[:2]))
            if abs(p[2]-1.4)<.001 and max(abs(a-b) for a,b in zip(color,(.59,.58,.53)))<.001:
                border.append(tuple(p[:2]))
        boundary=hull(border)
        escaped=sum(any(signed(a,b,p)<-.001 for a,b in zip(boundary,boundary[1:]+boundary[:1])) for p in set(green))
        if not green or len(boundary)<3 or escaped:outside.append({'file':file.name,'outside_vertices':escaped})
        squares+=1
    construction_area,platforms,construction_overlaps,construction_min_z={},[],[],{}
    for file in (SCENERY/'construction').glob('*.glb'):
        data=read_glb(file,0)
        construction_min_z[file.name]=round(min(z for m in data['meshes'] for z in m['vertices'][2::12]),5)
        area,tops=0,[]
        for mesh in data['meshes']:
            values=mesh['vertices']
            for part in mesh['parts']:
                for i in range(0,len(part['indices']),3):
                    points=[values[j*12:j*12+3] for j in part['indices'][i:i+3]]
                    if max(p[2] for p in points)-min(p[2] for p in points)<.0001 and signed(*points)>0:
                        tops.append(points)
                        if 0<=points[0][2]<=.5:area+=signed(*points)/2
        construction_area[file.name]=round(area,3)
        # A supporting tile-sized slab must come from terrain, not a scenery mesh.
        if area>1800:platforms.append(file.name)
        for i,first in enumerate(tops):
            for second in tops[i+1:]:
                if abs(first[0][2]-second[0][2])<.0001 and intersection_area(
                        [p[:2] for p in first],[p[:2] for p in second])>.001:
                    construction_overlaps.append(file.name)
    animals,animal_errors={},[]
    # One mesh per animal (tools/extract_herd_animals.py), standing on Z=0 within the livestock budget.
    for file in sorted((SCENERY/'farm').glob('*.glb')):
        data=read_glb(file,0)
        triangles=sum(len(p['indices'])//3 for m in data['meshes'] for p in m['parts'])
        low=min(z for m in data['meshes'] for z in m['vertices'][2::12])
        animals[file.stem]={'triangles':triangles,'min_z':round(low,6)}
        # The procedural poultry was never within the 600-triangle livestock budget.
        budget=1100 if file.stem in ('hen','rooster') else 600
        if triangles>budget or abs(low)>.0001:animal_errors.append(file.stem)
    layouts=json.loads((ROOT/'tools/board-models/scenery/layouts.json').read_text())
    crane_errors,grabber_errors=[],[]
    for file in files:
        name=image(file)+'.png';layout=layouts[name];data=read_glb(file,0)
        roofs=[p for p in mesh_triangles(data,'containers') if all(abs(v[2]-6.4)<.0001 for v in p)]
        grabs=list(mesh_triangles(data,'container-grabbers'))
        if len(layout['grabbers'])!=bool(grabs) or any(p[2]<6.42 for tri in grabs for p in tri):
            grabber_errors.append(file.name)
        c=layout.get('crane')
        if c is None or c['tip']:continue
        for tri in mesh_triangles(data,'crane-support'):
            footprint=below(tri,6.4)
            if len(footprint)<3:continue
            if any(intersection_area(footprint,[p[:2] for p in roof])>.0001 for roof in roofs):
                crane_errors.append({'file':file.name,'error':'support intersects container'});break
        # The neighbour's tip as its legacy key draws it: its row turns the straight or the diagonal tip.
        row,=LAYOUTS['scenery/'+name.replace('ShipToShoreGantryCrane-01-20Footer','ShipToShoreGantryCrane-03-CraneTip')
                     .rsplit('-',2)[0]+f"-1-{c['direction']:02d}"]
        tip=read_glb(ROOT/f"data/models/board/{row['asset']}.glb",0)
        dx,dy=c['neighbor'];span=math.hypot(dx,dy);ax,ay=dx/span,dy/span
        def joint(model,translation,angle=0):
            result=[]
            cos,sin=math.cos(math.radians(angle)),math.sin(math.radians(angle))
            for tri in mesh_triangles(model,'crane-boom'):
                for x,y,z in tri:
                    x,y=x*cos-y*sin+translation[0],x*sin+y*cos+translation[1]
                    if abs(x*ax+y*ay-c['half_span'])<.001 and 27.5<z<31.5:result.append((x,y,z))
            return result
        first,second=joint(data,(0,0)),joint(tip,(dx,dy),row['rotation'])
        # Every joint vertex of the crane meets one of the tip's within 0.001 px, and the other way round.
        meets=lambda a,b:all(any(math.dist(p,q)<.001 for q in b) for p in a)
        if len(first)<16 or not (meets(first,second) and meets(second,first)):
            crane_errors.append({'file':file.name,'error':'boom joint mismatch'})
    geysers,geyser_errors={},[]
    for file in (SCENERY/'geysers').glob('*.glb'):
        data=read_glb(file,0);low=min(z for m in data['meshes'] for z in m['vertices'][2::12])
        roles={p['id'] for m in data['meshes'] for p in m['parts']}
        geysers[file.name]={'min_z':round(low,5),'triangles':sum(len(p['indices'])//3 for m in data['meshes'] for p in m['parts'])}
        if low<-.0001 or 'geyser-spray' in roles:geyser_errors.append(file.name)
    debris,debris_errors={},[]
    for file in list((SCENERY/'rubble').glob('*.glb'))+[SCENERY/'military/fortification.glb']:
        data=read_glb(file,0)
        points=[m['vertices'][i:i+3] for m in data['meshes'] for i in range(0,len(m['vertices']),12)]
        roles={p['id'] for m in data['meshes'] for p in m['parts']}
        low=min(p[2] for p in points)
        count=sum(len(p['indices'])//3 for m in data['meshes'] for p in m['parts'])
        debris[file.name]={'triangles':count,'min_z':round(low,5),'materials':sorted(roles)}
        if low<-.0001 or len(roles)<2 or any(not mat.get('textures') for mat in data['materials']):
            debris_errors.append({'file':file.name,'error':'untextured or ungrounded debris'})
        if file.stem.endswith('-path'):
            # Checking all three triangle vertices also catches fragments spanning the cleared lane.
            for role in roles:
                for tri in mesh_triangles(data,role):
                    if min(p[0] for p in tri)<9 and max(p[0] for p in tri)>-9:
                        debris_errors.append({'file':file.name,'error':'cleared lane obstructed'});break
        if file.stem=='fortification' and any(math.hypot(p[0],p[1])<21 for p in points):
            debris_errors.append({'file':file.name,'error':'sandbags cover open center'})
    # Batch 10 pieces: the lowest point (the buffer stop's posts reach the sleeper tops below its rail-top origin) and
    # the designed size; a vehicle's length is over its couplers, so coupled vehicles stand half their lengths apart.
    pieces,piece_errors={},[]
    for name,(floor,size) in PIECES.items():
        data=read_glb(SCENERY/(name+'.glb'),0)
        points=[m['vertices'][i:i+3] for m in data['meshes'] for i in range(0,len(m['vertices']),12)]
        low,high=[min(p[k] for p in points) for k in range(3)],[max(p[k] for p in points) for k in range(3)]
        pieces[name]={'min_z':round(low[2],5),'size':[round(b-a,3) for a,b in zip(low,high)]}
        if abs(low[2]-floor)>.0001 or any(abs(b-a-s)>.01 for a,b,s in zip(low,high,size)):piece_errors.append(name)
    result = {'seaport_assets': len(files), 'container_roof_triangles': checked, 'coplanar_overlaps': overlaps,
              'pool_assets': pools, 'pool_nonmanifold_shells': bad_edges, 'pool_coping_overlaps': coping_overlaps,
              'square_assets':squares,'square_fill_outside_border':outside,
              'construction_low_ground_area':construction_area,'construction_platforms':platforms,
              'construction_min_z':construction_min_z,
              'construction_surface_overlaps':sorted(set(construction_overlaps)),
              'animals':animals,'animal_budget_or_ground_errors':animal_errors,
              'crane_join_or_container_collisions':crane_errors,'container_grabber_errors':grabber_errors,
              'geysers':geysers,'geyser_geometry_errors':geyser_errors,
              'demolition':debris,'demolition_geometry_errors':debris_errors,
              'pieces':pieces,'piece_floor_or_size_errors':piece_errors}
    print(json.dumps(result))
    (ROOT/'tools/board-models/scenery/geometry-check.json').write_text(json.dumps(result, indent=2)+'\n')
    if (overlaps or bad_edges or coping_overlaps or outside or platforms or construction_overlaps
            or any(z<-.0001 for z in construction_min_z.values()) or animal_errors or crane_errors or grabber_errors
            or geyser_errors or debris_errors or piece_errors):
        raise AssertionError('Invalid exported scenery geometry')


if __name__ == '__main__': main()
