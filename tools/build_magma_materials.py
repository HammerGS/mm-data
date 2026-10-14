#!/usr/bin/env python3
# Copyright (C) 2026 The MegaMek Team. SPDX-License-Identifier: GPL-3.0-or-later
"""Bake seamless volcanic materials from imagegen sources in tools/magma-reference.

The imagegen concept directs the geology and palette; source colour separates cold
basalt from incandescent cracks. Height is an artistic estimate, not a measured scan.
Reuse the terrain noise and relief baker. Each 1024px repeat spans 12 world metres.
NAME.png is unlit sRGB basalt albedo, NAME-normal.png is its tangent normal,
NAME-surface.png packs height/roughness/AO/relief-UV-divided-by-.1, and NAME-heat.png
packs linear emission intensity/signed flow X/signed flow Y/local crack-wall glow.
Zero metalness and opaque coverage are material constants. --check rebakes without writing.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from texture_helpers import Canvas, blur, display_rgb, linear_rgb, normal_map, periodic, pixels, smoothstep

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/models/board/textures/terrain/lava'
SOURCES = ROOT / 'tools/magma-reference'
SIZE = 1024
REPEAT = 12.0


def prepare(name, sources=SOURCES):
    molten = name == 'lava'
    canvas = Canvas(SIZE, REPEAT, 92817 if molten else 92816)
    broad = canvas.spectral(3, 1, 7)
    source = sources / f'{name}-source.png'
    with Image.open(source) as image:
        rgb = np.asarray(image.convert('RGB').resize((SIZE, SIZE), Image.Resampling.LANCZOS)) / 255.0
    # Colour, rather than brightness, identifies heat. A bright gray mineral stays cold,
    # and a red crack stays below its adjacent rock instead of becoming a raised orange ridge.
    hot_mask = smoothstep(.035, .28, rgb[..., 0] - rgb[..., 2]) * smoothstep(.13, .55, rgb[..., 0])
    # Keep the source's temperature streaks instead of saturating every orange pixel to
    # the same yellow. Green carries useful intensity detail even where red is at its ceiling.
    heat = hot_mask * rgb[..., 0] * (.18 + .82 * np.sqrt(rgb[..., 1]))
    heat = np.clip(periodic(heat), 0, 1)
    # A solid crust must not emit from warm reflections or the smooth seam correction.
    # Keep the fissures visible under their dark overhangs without lighting plate faces.
    if not molten:
        heat = np.sqrt(heat) * smoothstep(.035, .14, heat)
    plate = 1 - smoothstep(.08, .6, heat) if molten else 1 - smoothstep(.025, .16, heat)
    light = rgb @ np.array([.2126, .7152, .0722])
    cold = 1 - smoothstep(.025, .18, rgb[..., 0] - rgb[..., 2])
    # Reconstruct neutral reflectance in the molten channels by normalized convolution.
    # Their authored radiance goes only into emission; it must never be multiplied by daylight.
    stone = blur(light * cold, 14) / np.maximum(blur(cold, 14), .02)
    stone = np.clip(stone, .04, .5)
    basalt = light * cold + stone * (1 - cold)
    basalt *= np.power(np.mean(basalt) / np.maximum(blur(basalt, 20), .04), .35)
    basalt = np.clip(periodic(basalt), .035, .55)
    detail = blur(basalt, 1.1) - blur(basalt, 12)
    low, high = np.percentile(detail, [1, 99])
    detail = np.clip((detail - low) / max(high - low, .02), 0, 1) - .5
    # Curl follows broad heat contours around the basalt rafts, with a little background
    # convection inside broad pools. Opposite edges agree on both the pattern and its motion.
    stream = blur(heat, 24) + broad * .04
    flow_x = (np.roll(stream, -1, 0) - np.roll(stream, 1, 0)) * SIZE / 2
    flow_y = -(np.roll(stream, -1, 1) - np.roll(stream, 1, 1)) * SIZE / 2
    flow_range = max(np.percentile(np.hypot(flow_x, flow_y), 95), .01)
    flow_x = np.clip(flow_x / flow_range, -1, 1)
    flow_y = np.clip(flow_y / flow_range, -1, 1)
    if molten:
        height = .20 + plate * .48 + detail * (.22 * plate + .035)
    else:
        # Thick slabs carry the relief. Fine surface grain must not become deep,
        # almost vertical corrugations that make solid rock resemble a liquid skin.
        # Dark, cold fracture walls also descend into the fissure; using heat alone
        # would leave those walls level with the broad gray faces of the slabs.
        rock_face = smoothstep(.035, .23, blur(basalt, 16))
        height = .15 + plate * (.15 + .53 * rock_face) + detail * (.022 * plate + .006)
    height = pixels(np.clip(blur(height, 1.1), .04, .96)) / 255.0
    # The shader and baked normals decode exactly the same quantized relief range.
    # Active lava carries thin cooling skins. Giving those skins rock-slab depth
    # over-perturbs normals and folds their parallax UVs into artificial marbling.
    relief = round((.06 if molten else .95) / REPEAT / .1 * 255) / 255
    halo = np.clip(blur(heat, 7) * 1.9, 0, 1) if molten else np.clip(blur(heat, 2.5) * 1.2, 0, 1)
    # Pigment is deliberately dark and neutral; all incandescent orange comes from the
    # emission map in the renderer, independent of sun, shadows, weather and occlusion.
    basalt = basalt * (.70 + plate * .30)
    color = np.stack((basalt * 1.025, basalt, basalt * .96), -1)
    roughness = np.clip((.28 + plate * .57 if molten else .43 + plate * .46) - detail * .1, .24, .98)
    cavity = np.maximum(blur(height, 7) - height, 0)
    ao = np.exp(-cavity * 4.2)
    surface = np.stack((height, roughness, ao, np.full_like(height, relief)), -1)
    maps = {
        f'{name}.png': pixels(color),
        f'{name}-normal.png': normal_map(height, relief * .1),
        f'{name}-surface.png': pixels(surface),
        f'{name}-heat.png': pixels(np.stack((heat, .5 + flow_x * .5, .5 + flow_y * .5, halo), -1)),
    }
    if molten:
        finish_lava(maps)
    return maps


def finish_lava(maps):
    """Store the artist-directed matte skin in its intrinsic maps, using their actual quantized inputs."""
    surface = maps['lava-surface.png']
    albedo = linear_rgb(maps['lava.png'] / 255.0)
    exposed = smoothstep(.25, .65, maps['lava-heat.png'][..., 0] / 255.0)
    basalt = np.maximum(albedo, (.025 * (.7 + .6 * surface[..., 0] / 255.0))[..., None])
    maps['lava.png'] = pixels(display_rgb(basalt * (1 - exposed[..., None]) + albedo * exposed[..., None]))
    roughness = surface[..., 1] / 255.0
    surface[..., 1] = pixels(np.maximum(roughness, .96) * (1 - exposed)
                            + np.maximum(roughness, .92) * exposed)


def validate(name, maps):
    surface = maps[f'{name}-surface.png']
    expected = normal_map(surface[..., 0] / 255, float(surface[0, 0, 3]) / 255 * .1)
    assert np.array_equal(expected, maps[f'{name}-normal.png']), f'{name}: normal/height mismatch'
    assert surface[..., 2].min() < 240
    if name == 'lava':
        assert surface[..., 1].min() >= round(.92 * 255) and surface[..., 1].max() <= 250
    else:
        assert np.ptp(surface[..., 1]) > 40
    heat = maps[f'{name}-heat.png'][..., 0] / 255
    coverage = np.mean(heat > .2)
    if name == 'lava':
        # Active molten rivers may be mostly incandescent. Keep some cooled skin,
        # without imposing the solid crust's fissure-dominated coverage on liquid.
        assert .15 < coverage < .95, 'lava: preserve broad hot melt and some cooled rafts'
    else:
        assert .02 < coverage < .6, f'{name}: preserve both cold basalt and readable hot fissures'
    if name == 'crust':
        assert np.mean(heat == 0) > .7, 'crust: most of the solid basalt must remain cold'
        assert np.mean(heat > .05) < .22, 'crust: heat belongs in fissures, not across the plate faces'
    # A repeat boundary must behave like its interior, including normals and emission.
    for filename, data in maps.items():
        field = data.astype(float)
        edge_x = np.abs(field[:, 0] - field[:, -1]).mean()
        edge_y = np.abs(field[0] - field[-1]).mean()
        inner_x = np.abs(np.diff(field, axis=1)).mean()
        inner_y = np.abs(np.diff(field, axis=0)).mean()
        assert edge_x < inner_x * 3 + 1 and edge_y < inner_y * 3 + 1, f'{filename}: repeat seam'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source-dir', type=Path, default=SOURCES,
                        help='Input crust/lava sources; defaults to the checked-in references')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT,
                        help='Destination maps; allows reviewing a candidate without replacing runtime assets')
    args = parser.parse_args()
    manifest = {
        'generator': 'tools/build_magma_materials.py', 'size': SIZE, 'repeat_metres': REPEAT,
        'references': ['tools/magma-reference/crust-source.png', 'tools/magma-reference/lava-source.png'],
        'height_source': 'estimated basalt relief and recessed heat mask',
        'sources_sha256': {name: hashlib.sha256((args.source_dir / f'{name}-source.png').read_bytes()).hexdigest()
                           for name in ('crust', 'lava')},
        'maps': {'albedo': 'sRGB reflectance', 'normal': 'linear tangent normal: U right, V down',
                 'surface': 'R height, G roughness, B occlusion, A relief UV / .1',
                 'heat': 'R emission intensity, GB signed flow * .5 + .5, A crack-wall glow'},
        'metalness': 0, 'opacity': 1, 'materials': ['crust', 'lava'],
        'lava_skin': {
            'basis': 'artist-directed final intrinsic albedo and roughness; not measured thermal properties',
            'albedo': 'linear basalt floor .025 * mix(.7, 1.3, stored height), released by smoothstep(.25, .65, stored heat)',
            'roughness': 'mix(max(source, .96), max(source, .92), smoothstep(.25, .65, stored heat))',
            'filtering': 'completed albedo and roughness are filtered as material channels before lighting',
            'distant_roughness': .96,
            'distant_roughness_basis': 'declared coarse-LOD estimate when the surface map is omitted; crust remains .85',
        },
    }
    if not args.check:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in manifest['materials']:
        maps = prepare(name, args.source_dir)
        validate(name, maps)
        for filename, data in maps.items():
            path = args.output_dir / filename
            if args.check:
                with Image.open(path) as image:
                    assert np.array_equal(np.asarray(image), data), f'Stale material: {path}'
            else:
                Image.fromarray(data).save(path, optimize=True)
        coverage = np.mean(maps[f'{name}-heat.png'][..., 0] / 255 > .2)
        print(f'{name}: validated albedo, normal, height, roughness, AO, emission and flow '
              f'({SIZE}px, {coverage:.1%} hot coverage)')
    path = args.output_dir / 'manifest.json'
    if args.check:
        assert json.loads(path.read_text()) == manifest, 'Stale magma manifest'
    else:
        path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
