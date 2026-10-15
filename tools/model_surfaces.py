"""Authored starting points for the generated kits, not measured material scans.

Painted armor is dielectric. The unit 'detail' role
mixes metal, rubber, skin and glass, so it cannot receive one metallic response.
Keep that role matte until those surfaces have an authored mask or separate art.
"""
import re


UNITS = ('bodies/atlas', 'bodies/warhammer')


def unit_surface(role, asset):
    if role not in ('paint', 'detail', 'bark'):
        raise ValueError('Unknown generated unit material: ' + role)
    # The paint role also includes camouflage-tinted clothing on other assets.
    # Scope this armor calibration explicitly and share it across a body's LODs.
    reviewed = re.sub(r'-lod[0-3]$', '', asset) in UNITS
    return {'roughness': .68 if reviewed and role == 'paint' else 1, 'metallic': 0}
