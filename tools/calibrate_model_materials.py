"""Apply the first reviewed surface calibration without re-exporting any geometry.

No arguments previews the two unit assets; --apply updates them and the
unit manifest hashes. Complete kit exports use the same model_surfaces selection
and values. Other assets keep their existing generator defaults.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from model_surfaces import UNITS, unit_surface


def calibrated_glb(raw, surfaces):
    """Change only two JSON factors. Preserve every following chunk byte for byte."""
    if len(raw) < 20 or struct.unpack_from('<III', raw) != (0x46546c67, 2, len(raw)):
        raise ValueError('Invalid GLB header')
    length, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4e4f534a or length % 4 or 20 + length > len(raw):
        raise ValueError('Invalid GLB JSON chunk')
    document = json.loads(raw[20:20 + length])
    materials = document.get('materials', [])
    if {material.get('name') for material in materials} != surfaces.keys():
        raise ValueError('Material roles differ from the reviewed asset')
    changed = False
    for material in materials:
        pbr = material['pbrMetallicRoughness']
        surface = surfaces[material['name']]
        current = (pbr.get('roughnessFactor', 1), pbr.get('metallicFactor', 1))
        target = (surface['roughness'], surface['metallic'])
        if 'metallicRoughnessTexture' in pbr or current not in ((1, 0), target):
            raise ValueError('Refusing to replace an independently authored surface')
        if current != target:
            pbr.update(roughnessFactor=target[0], metallicFactor=target[1])
            changed = True
    if not changed:
        return raw
    encoded = json.dumps(document, separators=(',', ':'), allow_nan=False).encode('utf-8')
    encoded += b' ' * (-len(encoded) % 4)
    tail = raw[20 + length:]
    return (struct.pack('<IIIII', 0x46546c67, 2, 20 + len(encoded) + len(tail), len(encoded), 0x4e4f534a)
            + encoded + tail)


def calibrate(root, apply=False):
    models = Path(root) / 'data/models'
    manifest_path = models / 'units/modular/manifest.json'
    manifest_text = manifest_path.read_text(encoding='utf-8')
    manifest = json.loads(manifest_text)
    changes = []
    for key in UNITS:
        path = models / 'units/modular' / (key + '.glb')
        raw = path.read_bytes()
        updated = calibrated_glb(raw, {role: unit_surface(role, key) for role in ('paint', 'detail')})
        stats = manifest['assets'][key]
        old_hash = hashlib.sha256(raw).hexdigest()
        if stats['sha256'] != old_hash:
            raise ValueError('Unit manifest already differs from its asset: ' + key)
        new_hash = hashlib.sha256(updated).hexdigest()
        # Preserve the existing manifest formatting and all unrelated entries.
        hash_field = '"sha256": "' + old_hash + '"'
        if manifest_text.count(hash_field) != 1:
            raise ValueError('Expected one manifest entry for ' + key)
        manifest_text = manifest_text.replace(hash_field, '"sha256": "' + new_hash + '"')
        changes.append((path, raw, updated))
    # Validate the entire selection before writing any asset.
    for path, raw, updated in changes:
        print(('update ' if raw != updated else 'current ') + str(path.relative_to(root)))
        if apply and raw != updated:
            path.write_bytes(updated)
    if apply and manifest_text != manifest_path.read_text(encoding='utf-8'):
        with manifest_path.open('w', encoding='utf-8', newline='') as stream:
            stream.write(manifest_text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    calibrate(Path(__file__).resolve().parents[1], args.apply)
