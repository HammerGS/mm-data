#!/usr/bin/env python3
# Copyright (C) 2026 The MegaMek Team. SPDX-License-Identifier: GPL-3.0-or-later
"""Bake aligned road maps from imagegen material sources, reusing the terrain baker.

Height is an artistic estimate, not a measured scan. All maps share the same periodic
field. Surface RGBA stores height, perceptual roughness, cavity AO and relief UV / .1.
No road shapes, markings or wheel spacing are encoded in these repeating materials.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from texture_helpers import blur, display_rgb, normal_map, periodic, pixels, resize_linear_rgb

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/models/board/textures/roads'
# One repeat in the renderer's detail metres, relief metres, dry roughness.
PROFILES = {'asphalt': (1.0, .0035, .83), 'dirt': (1.0, .009, .94), 'gravel': (1.0, .014, .88)}


def prepare(name):
    source = ROOT / 'tools/road-sources' / f'{name}.png'
    with Image.open(source) as image:
        rgb = resize_linear_rgb(image, (1024, 1024))
        # Retain the authored numeric relief recipe independently of the color filtering correction.
        geometry = np.asarray(image.convert('RGB').resize((1024, 1024), Image.Resampling.LANCZOS)) / 255.0
    rgb = np.clip(periodic(rgb), 0, 1)
    geometry = np.clip(periodic(geometry), .015, .985)
    light = geometry @ np.array([.2126, .7152, .0722])
    # Avoid turning the broad albedo mottling into a bumpy road. Resolve embedded grain
    # with millimetre relief, rather than interpreting every bright mineral as a tall rock.
    field = .65 * blur(light, 1.2) + .35 * blur(light, 3.5) - blur(light, 24)
    low, high = np.percentile(field, [1, 99])
    height = pixels(np.clip((field - low) / max(high - low, .01), 0, 1)) / 255.0
    repeat, relief, roughness = PROFILES[name]
    encoded = round(relief / repeat / .1 * 255)
    depth = encoded / 255 * .1
    cavity = np.maximum(blur(height, 4) - height, 0)
    surface = np.stack((height, np.clip(roughness + (.5 - height) * .12, .4, .98),
                        np.exp(-cavity * 1.7), np.full_like(height, encoded / 255)), axis=-1)
    maps = {f'{name}.png': pixels(display_rgb(rgb)), f'{name}-normal.png': normal_map(height, depth),
            f'{name}-surface.png': pixels(surface)}
    entry = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'size': 1024,
             'repeat_detail_metres': repeat, 'height_source': 'estimated local material relief',
             'relief_uv': depth, 'roughness': roughness, 'color_filtering': 'linear RGB', 'color_range': [0, 1]}
    return maps, entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = {'generator': 'tools/prepare_road_materials.py', 'materials': {}}
    if not args.check:
        OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in PROFILES:
        maps, entry = prepare(name)
        manifest['materials'][name] = entry
        for filename, data in maps.items():
            target = OUTPUT / filename
            if args.check:
                with Image.open(target) as image:
                    if not np.array_equal(np.asarray(image), data):
                        raise SystemExit(f'Stale road material: {target}')
            else:
                Image.fromarray(data).save(target, optimize=True)
        # Integration check: packed height/range and tangent normals agree, including wrapped edges.
        surface = maps[f'{name}-surface.png']
        derived = normal_map(surface[..., 0] / 255.0, float(surface[0, 0, 3]) / 255 * .1)
        if not np.array_equal(derived, maps[f'{name}-normal.png']):
            raise SystemExit(f'Road normal/height mismatch: {name}')
        print(f'{name}: aligned 1024px albedo, normal, height/roughness/AO')
    target = OUTPUT / 'manifest.json'
    if args.check:
        if json.loads(target.read_text()) != manifest:
            raise SystemExit('Stale road material manifest')
    else:
        target.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
