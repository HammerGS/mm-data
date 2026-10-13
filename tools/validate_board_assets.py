"""Validate the shipped 3D board catalog, roof fidelity and isolated dependencies."""
from glb_geometry import read_glb
from io import BytesIO
from pathlib import Path
import json
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'data/models/board'
buildings = json.loads((BOARD / 'building-manifest.json').read_text())
features = json.loads((BOARD / 'manifest.json').read_text())
catalog = dict(features, **buildings)

for asset, entry in features.items():
    if asset.startswith(('foliage-', 'orchard-')):
        assert len(entry['lods']) == 3, asset
        for level, lod in enumerate(entry['lods']):
            assert lod['node'] == f'{asset}-lod{level}', asset
            assert 0 < lod['triangles'] <= (480, 240, 96)[level], lod
            catalog[lod['node']] = lod
    if 'source' in entry:
        assert len(entry['lods']) == 3, asset
        for level, lod in enumerate(entry['lods']):
            assert lod['node'] == f'{asset}-lod{level}', asset
            assert 0 < lod['triangles'] <= entry['triangles'] // (1 if level == 0 else 2 if level == 1 else 5), lod
            catalog[lod['node']] = lod
maximum = 0
assert not list(BOARD.rglob('*.g3dj')), 'All deployed board meshes must use GLB'
assert not any(name.startswith('rock-') for name in features), 'Retired rocks in manifest'
assert not {'tank', 'industrial'}.intersection(features), 'Generic structure models must not return'
for asset in catalog:
    if asset in features and 'source' in features[asset]:
        # The source's full count remains in the manifest for authoring; deployed LOD0 is checked below.
        continue
    if '-lod' in asset:
        name, level = asset.rsplit('-lod', 1)
        path = BOARD / (name + '.glb')
        model = read_glb(path, int(level))
    else:
        path = BOARD / (asset + '.glb')
        model = read_glb(path)
    heights = [z for mesh in model['meshes'] for z in mesh['vertices'][2::12]]
    if asset in buildings:
        assert min(heights) == 0 and max(heights) == 18, f'One-level building: {path}'
    elif asset.startswith('foliage-'):
        assert abs(min(heights)) < 1e-5, f'Floating understory root: {path}'
        assert 17 < max(heights) < 18.1, f'Understory LOD silhouette: {path}'
    elif asset.startswith('orchard-'):
        assert abs(min(heights)) < 1e-5, f'Floating orchard root: {path}'
        assert 29 < max(heights) < 31, f'Orchard LOD silhouette: {path}'
    triangles = 0
    for mesh in model['meshes']:
        assert mesh['attributes'] == ['POSITION', 'NORMAL', 'COLOR', 'TEXCOORD0'], path
        vertices = mesh['vertices']
        assert len(vertices) % 12 == 0, path
        for part in mesh['parts']:
            indices = part['indices']
            assert len(indices) % 3 == 0, path
            assert all(0 <= index < len(vertices) // 12 for index in indices), path
            triangles += len(indices) // 3
            if part['id'] == 'roof' and asset in buildings:
                for offset in range(0, len(indices), 3):
                    a, b, c = [vertices[index * 12:index * 12 + 3] for index in indices[offset:offset + 3]]
                    normal_z = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                    assert normal_z > 0, f'Roof winding: {path}'
    assert 0 < triangles <= 500, (path, triangles)
    assert triangles == catalog[asset]['triangles'], path
    maximum = max(maximum, triangles)
    for material in model['materials']:
        for texture in material.get('textures', []):
            if 'data' in texture:
                assert Image.open(BytesIO(texture['data'])).format in ('PNG', 'JPEG'), path
                continue
            dependency = (path.parent / texture['filename']).resolve()
            assert dependency.is_relative_to(BOARD.resolve()), dependency
            assert dependency.is_file(), dependency
    if asset in buildings:
        facade = buildings[asset]['wall_texture']
        wall = next(material for material in model['materials'] if material['id'] != 'roof')
        assert (path.parent / wall['textures'][0]['filename']).resolve() == (BOARD / facade).resolve(), path
        assert '/full-resolution/' not in facade, path
        assert Image.open(BOARD / facade).size == (128, 128), path
        assert (wall['id'] == 'shell') == buildings[asset]['full_height_facade'], path
        source = Image.open(BOARD / 'tileset' / buildings[asset]['source']).convert('RGBA')
        roof_material = next(material for material in model['materials'] if material['id'] == 'roof')
        roof_data = roof_material['textures'][0]['data']
        sibling = path.with_suffix('.png')
        assert sibling.read_bytes() == (BOARD / 'tileset' / buildings[asset]['source']).read_bytes(), \
            f'Original building artwork differs: {sibling}'
        assert not path.with_name(path.stem + '-roof.png').exists(), f'Processed roof sibling: {path}'
        roof = Image.open(BytesIO(roof_data)).convert('RGB')
        difference = ImageChops.difference(source.convert('RGB'), roof)
        mask = source.getchannel('A').point(lambda alpha: 255 if alpha >= 245 else 0)
        assert ImageChops.multiply(difference.convert('L'), mask).getbbox() is None, path
    elif asset.startswith('foliage-'):
        family = asset.removeprefix('foliage-').rsplit('-lod', 1)[0]
        roles = {material['id'] for material in model['materials']}
        expected = {'cactus'} if family == 'desert' else {'leaves', 'bark'}
        assert roles == expected | ({'snow'} if family == 'snow' else set()), (asset, roles)
        assert {part['id'] for mesh in model['meshes'] for part in mesh['parts']} == roles, asset
        for material in model['materials']:
            texture = material['textures'][0]
            assert texture['filename'] == f'textures/foliage/shrubs/{family}.png', path
            assert texture['wrapS'] == texture['wrapT'] == 33071, path
    elif asset != 'field':
        family = asset.rsplit('-lod', 1)[0]
        roles = {material['id'] for material in model['materials']}
        leaf = ('needles-pine' if asset.startswith('pine') else
                'leaves-willow' if asset.startswith('willow') else
                'fronds-palm' if asset.startswith('palm') else 'leaves-broad')
        bark = 'bark-birch' if asset.startswith('birch') else 'bark-palm' if asset.startswith('palm') else 'bark'
        # Cacti are a ribbed stem with optional flowers; dead trees are bare wood.
        expected = ({'cactus', 'leaves-broad'} if asset.startswith('cactus-flowers') else {'cactus'}
                    if asset.startswith('cactus') else {bark} if asset.startswith('tree-dead') else {leaf, bark})
        assert roles == expected | ({'snow'} if family.endswith('-snow') else set()), (asset, roles)
        assert {part['id'] for mesh in model['meshes'] for part in mesh['parts']} == roles, asset
        for material in model['materials']:
            assert material['textures'][0]['filename'] == f"textures/foliage/{material['id']}.png", path
        for mesh in model['meshes']:
            vertices = mesh['vertices']
            for part in mesh['parts']:
                assert part['indices'], (asset, part['id'])
                for offset in range(0, len(part['indices']), 3):
                    a, b, c = [vertices[index * 12 + 10:index * 12 + 12]
                               for index in part['indices'][offset:offset + 3]]
                    area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
                    assert abs(area) > 1e-10, f'Collapsed foliage UV: {asset}: {part["id"]}'
                if part['id'] == 'snow':
                    assert all(min(vertices[index * 12 + 6:index * 12 + 9]) > .75
                               for index in part['indices']), f'Snow must not inherit foliage tint: {asset}'

for family in ('buildings', 'terrain'):
    folder = BOARD / 'textures' / family
    for original in (folder / 'full-resolution').glob('*.png'):
        assert min(Image.open(original).size) > 128, original
        assert Image.open(folder / original.name).size == (128, 128), original

for path in (BOARD / 'textures/foliage').glob('*.png'):
    with Image.open(path) as image:
        assert image.size == (64, 64), path
        assert image.convert('RGBA').getchannel('A').getextrema() == (255, 255), path

for path in (BOARD / 'textures/foliage/shrubs').glob('*.png'):
    with Image.open(path) as image:
        assert image.width == image.height and image.width >= 1024, path
        assert image.convert('RGBA').getchannel('A').getextrema() == (255, 255), path

sources = json.loads((BOARD / 'tileset/sources.json').read_text())['files']
for name in sources:
    copy = BOARD / 'tileset' / name
    assert copy.is_file(), copy
    assert copy.resolve().is_relative_to((BOARD / 'tileset').resolve()), copy
    assert not copy.samefile(ROOT / 'data/images/hexes' / name), copy
print(json.dumps({'buildings': len(buildings), 'features': len(features), 'tree_lods': len(catalog) - len(buildings) - len(features),
                  'max_triangles': maximum, 'independent_tileset_files': len(sources)}))
