"""Bake preserved plant sources: cutouts, estimated relief normals and packed leaf surface maps."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from texture_helpers import blur, display_rgb, linear_rgb, normal_map, periodic, resize_linear_rgb

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'tools/foliage-sources'
OUT = ROOT / 'data/models/board/textures/vegetation'


def resize_cutout_rgb(image, size):
    """Filter linear premultiplied color; transparent source RGB cannot bleed into the leaf."""
    rgba = np.asarray(image.convert('RGBA')) / 255.0
    alpha = rgba[..., 3:]
    premultiplied = np.concatenate((linear_rgb(rgba[..., :3]) * alpha, alpha), axis=-1)
    filtered = np.stack([np.asarray(Image.fromarray(premultiplied[..., channel].astype(np.float32))
                         .resize(size, Image.Resampling.LANCZOS)) for channel in range(4)], axis=-1)
    rgb = np.divide(filtered[..., :3], filtered[..., 3:], out=np.zeros_like(filtered[..., :3]),
                    where=filtered[..., 3:] > 1e-8)
    return np.clip(rgb, 0, 1)


def bleed_rgb(rgb, valid):
    """Fill the existing eight-pixel rim in the supplied color domain; never change alpha."""
    rgb, valid = rgb.copy(), valid.copy()
    for _ in range(8):
        total = np.zeros(rgb.shape, dtype=np.float32)
        count = np.zeros(valid.shape, dtype=np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            mask = np.roll(valid, (dy, dx), (0, 1))
            total += np.roll(rgb, (dy, dx), (0, 1)) * mask[:, :, None]
            count += mask
        fill = ~valid & (count > 0)
        values = total[fill] / count[fill, None]
        # The legacy byte recipe remains exact for the independently authored numeric maps.
        rgb[fill] = np.rint(values) if rgb.dtype == np.uint8 else values
        valid |= fill
    return rgb


def bake(source, *, linear_color=True):
    with Image.open(source) as image:
        pixels = np.array(image.convert('RGBA').resize((512, 512), Image.Resampling.LANCZOS))
        rgb = resize_cutout_rgb(image, (512, 512)) if linear_color else pixels[..., :3]
    # Keep the established silhouette/coverage bytes, including alpha-test boundaries.
    alpha = pixels[:, :, 3].copy()
    valid = alpha > 127
    assert .15 < valid.mean() < .85, f'{source.name}: expected a branch cutout'
    rgb = bleed_rgb(rgb, valid)
    pixels[..., :3] = np.rint(display_rgb(rgb) * 255).clip(0, 255).astype(np.uint8) if linear_color else rgb
    pixels[:, :, 3] = alpha
    return pixels


def cactus_maps():
    with Image.open(SOURCES / 'cactus-skin.png') as image:
        color = np.asarray(image.convert('RGB').resize((512, 512), Image.Resampling.LANCZOS)) / 255.0
        pigment = np.clip(periodic(resize_linear_rgb(image, (512, 512))), 0, 1)
    # Preserve the established encoded source estimate for the independent numeric normal map.
    color = np.clip(periodic(color), 0, 1)
    # Source-aligned estimated shallow rib/areole relief, never extra stem geometry.
    height = blur(color @ np.array([.2126, .7152, .0722]), 1.3)
    return {'cactus-skin': np.rint(display_rgb(pigment) * 255).clip(0, 255).astype(np.uint8),
            'cactus-skin-normal': normal_map(height, .035)}


def leaf_maps(name, pixels):
    """Source-aligned shallow relief and AO/roughness/transmission; no displacement or baked sunlight.

    These are artistic estimates from the preserved source, not measured scan data.
    Broad source lighting is removed before estimating relief, and bark-colored veins
    transmit less than green leaf tissue. Alpha remains in the original color map.
    """
    color = pixels[:, :, :3] / 255.0
    alpha = pixels[:, :, 3] / 255.0
    light = color @ np.array([.2126, .7152, .0722])
    detail = blur(light, 1.2) - blur(light, 6)
    height = detail * .35 + blur(alpha, 1.4) * .12
    cavity = np.clip(np.exp(-np.maximum(blur(light, 4) - light, 0) * 1.8), .65, 1)
    green = np.clip((color[:, :, 1] - color[:, :, 0] * .6 - color[:, :, 2] * .4)
                    / np.maximum(color[:, :, 1], .05) * 3, 0, 1)
    snow = name == 'snow' or '-snow-' in name
    roughness = np.full_like(light, .85) if snow else np.clip(.62 - .15 * green + .1 * (1 - light), .4, .85)
    transmission = np.zeros_like(light) if snow else green * .65
    surface = np.stack((cavity, roughness, transmission), axis=-1)
    return {name + '-normal': normal_map(height, .012 if snow else .018),
            name + '-surface': np.rint(surface * 255).astype(np.uint8)}


def shrub_maps():
    """The retained biome atlases supply matching shallow bark, leaf and cactus-pad surface detail."""
    result = {}
    for source in sorted((OUT / 'shrubs').glob('*.png')):
        if source.stem.endswith(('-normal', '-surface')):
            continue
        with Image.open(source) as image:
            pixels = np.array(image.convert('RGBA'))
        result.update({'shrubs/' + name: values for name, values in leaf_maps(source.stem, pixels).items()})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    maps = {}
    for source in sorted(SOURCES.glob('*-cutout.png')):
        maps[source.stem] = bake(source)
        # Geometry/material estimates retain their original encoded authoring input.
        maps.update(leaf_maps(source.stem, bake(source, linear_color=False)))
    maps.update(cactus_maps())
    maps.update(shrub_maps())
    for name, pixels in maps.items():
        destination = OUT / (name + '.png')
        if args.check:
            with Image.open(destination) as expected:
                assert np.array_equal(pixels, np.array(expected)), f'Stale foliage texture: {destination}'
        else:
            Image.fromarray(pixels).save(destination)
        print(name, 'checked' if args.check else 'baked')
