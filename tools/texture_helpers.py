# Copyright (C) 2026 The MegaMek Team. SPDX-License-Identifier: GPL-3.0-or-later
"""Shared texture helpers for the board material tools (NumPy + Pillow).

Canvas.spectral() makes periodic noise; linear_rgb() and display_rgb() convert sRGB;
resize_linear_rgb() filters in linear light; periodic() makes a field tile seamlessly; blur() is a
wrapped Gaussian; normal_map() derives RGB tangent normals (U right, V down) from a height field;
pixels() encodes [0, 1] values as 8-bit.
"""
import math

import numpy as np
from PIL import Image


class Canvas:
    """One material's square, periodic sample grid: N pixels span `tile` metres."""

    def __init__(self, n, tile, seed):
        self.n = n
        self.tile = tile
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self._salt = 0
        self.v, self.u = np.mgrid[0:n, 0:n].astype(np.float32) / n  # u: columns (right), v: rows (down), in tiles

    def child(self):
        self._salt += 1
        return np.random.default_rng((self.seed, self._salt))

    def spectral(self, beta=2.0, lo=1.0, hi=None, stretch=(1.0, 1.0), angle=0.0):
        """Zero-mean, unit-deviation noise with power ~ f^-beta between lo and hi cycles per tile.

        stretch > 1 along an axis elongates features along that axis (u, v), after rotating by angle."""
        n = self.n
        white = self.child().standard_normal((n, n)).astype(np.float32)
        f = np.fft.fftfreq(n) * n
        fu, fv = np.meshgrid(f, f)
        c, s = math.cos(angle), math.sin(angle)
        a = (fu * c + fv * s) * stretch[0]
        b = (-fu * s + fv * c) * stretch[1]
        radius = np.sqrt(a * a + b * b)
        radius[0, 0] = 1
        amplitude = radius ** (-beta / 2)
        amplitude *= smoothstep(lo * .7, lo, radius)
        if hi is not None:
            amplitude *= 1 - smoothstep(hi, hi * 1.4, radius)
        amplitude[0, 0] = 0
        field = np.real(np.fft.ifft2(np.fft.fft2(white) * amplitude)).astype(np.float32)
        return (field - field.mean()) / (field.std() + 1e-9)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def linear_rgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def display_rgb(rgb):
    return np.where(rgb <= .0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - .055)


def resize_linear_rgb(image, size):
    """Decode once before filtering source artwork; retain floating-point linear RGB for subsequent color work."""
    rgb = linear_rgb(np.asarray(image.convert('RGB')) / 255.0)
    return np.clip(np.stack([np.asarray(Image.fromarray(rgb[..., channel].astype(np.float32)).resize(
        size, Image.Resampling.LANCZOS)) for channel in range(3)], axis=-1), 0, 1)


def periodic(image):
    """Remove the smooth boundary mismatch using a periodic Poisson solve.

    Unlike mirror tiling, this retains one unreflected geological pattern. The
    same periodic signal supplies color, height, normals and all mip levels.
    """
    height, width = image.shape[:2]
    boundary = np.zeros_like(image, dtype=np.float64)
    boundary[0] = image[-1] - image[0]
    boundary[-1] = -boundary[0]
    boundary[:, 0] += image[:, -1] - image[:, 0]
    boundary[:, -1] -= image[:, -1] - image[:, 0]
    denominator = (2 * np.cos(2 * np.pi * np.arange(height) / height)[:, None]
                   + 2 * np.cos(2 * np.pi * np.arange(width) / width)[None, :] - 4)
    denominator[0, 0] = 1
    if image.ndim == 3:
        denominator = denominator[..., None]
    frequency = np.fft.fft2(boundary, axes=(0, 1)) / denominator
    frequency[0, 0] = 0
    return image - np.fft.ifft2(frequency, axes=(0, 1)).real


def blur(field, radius):
    """Gaussian convolution with wrap boundaries, including sub-pixel radii."""
    fy = np.fft.fftfreq(field.shape[0])[:, None]
    fx = np.fft.fftfreq(field.shape[1])[None, :]
    kernel = np.exp(-2 * np.pi ** 2 * radius ** 2 * (fx * fx + fy * fy))
    return np.fft.ifft2(np.fft.fft2(field) * kernel).real


def normal_map(height, depth):
    """Differentiate the actual height field at its UV/world scale, not color edges."""
    du = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * height.shape[1] / 2
    dv = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * height.shape[0] / 2
    normal = np.stack((-du * depth, -dv * depth, np.ones_like(height)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    return np.rint(normal * 127 + 128).clip(0, 255).astype(np.uint8)


def pixels(values):
    return np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
