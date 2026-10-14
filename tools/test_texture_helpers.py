"""Shared texture helpers: wrap seams, physical normal direction and linear-light resizing."""
import unittest

import numpy as np
from PIL import Image

from texture_helpers import normal_map, periodic, resize_linear_rgb


class TextureHelpersTest(unittest.TestCase):
    def test_periodic_correction_removes_a_photo_edge_step_without_mirroring(self):
        x = np.arange(128) / 128
        field = np.tile(.3 * np.sin(x * 4 * np.pi) + x * .5, (128, 1))
        wrapped = periodic(field)
        seam = np.abs(wrapped[:, 0] - wrapped[:, -1]).mean()
        interior = np.abs(np.diff(wrapped, axis=1)).mean()
        self.assertLess(seam, interior * 2)
        self.assertAlmostEqual(wrapped.mean(), field.mean())
        self.assertGreater(np.std(wrapped), .1, 'Tiling must preserve broad geological structure')

    def test_normals_follow_positive_height_in_image_u_and_v(self):
        x = np.arange(128) / 128 * 2 * np.pi
        height = .5 + .2 * np.sin(x)[None, :] + .1 * np.sin(x)[:, None]
        normal = (normal_map(height, .04).astype(float) - 128) / 127
        self.assertLess(normal[0, 0, 0], 0, 'A rising U slope points the normal against U')
        self.assertLess(normal[0, 0, 1], 0, 'A rising V/down slope points against V/down')
        self.assertGreater(normal[64, 64, 0], 0)
        self.assertGreater(normal[64, 64, 1], 0)
        self.assertTrue(np.allclose(np.linalg.norm(normal, axis=-1), 1, atol=.007))
        self.assertTrue(np.array_equal(normal_map(np.full((16, 16), .5), .04)[0, 0], [128, 128, 255]))

    def test_source_color_resizes_after_decoding_without_touching_input(self):
        for width, height in [(2, 1), (1, 2)]:
            pixels = np.zeros((height, width, 3), dtype=np.uint8)
            pixels[-1, -1] = 255
            image = Image.fromarray(pixels)
            result = resize_linear_rgb(image, (1, 1))
            np.testing.assert_allclose(result, .5, atol=1e-6,
                                       err_msg='A black/white footprint averages .5 linear, not encoded .5')
            np.testing.assert_array_equal(np.asarray(image), pixels)


if __name__ == '__main__':
    unittest.main()
