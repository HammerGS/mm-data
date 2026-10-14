"""Run with Blender's Python: opposing decimation faces must retain oriented normals."""
import copy
import math
import unittest

from build_volcano_foliage import smooth_bark


def model(triangles):
    vertices = []
    for points, normal in triangles:
        for point in points:
            vertices.extend([*point, *normal, .2, .4, .6, 1, len(vertices) / 12, .25])
    return {'meshes': [{'vertices': vertices,
                        'parts': [{'id': 'bark-volcano', 'indices': list(range(len(vertices) // 12))}]}]}


class VolcanoNormalsTest(unittest.TestCase):
    def test_opposed_faces_keep_each_corners_own_orientation(self):
        source = model([(((0, 0, 0), (1, 0, 0), (0, 1, 0)), (0, 0, 1)),
                        (((0, 1, 0), (1, 0, 0), (0, 0, 0)), (0, 0, -1))])
        before = copy.deepcopy(source)
        smooth_bark(source)
        self.assertEqual(before, source)

    def test_regular_uv_seams_still_share_area_weighted_smooth_normal(self):
        source = model([(((0, 0, 0), (1, 0, 0), (0, 1, 0)), (0, 0, 1)),
                        (((0, 0, 0), (0, 0, 1), (1, 0, 0)), (0, 1, 0))])
        before = copy.deepcopy(source)
        smooth_bark(source)
        vertices = source['meshes'][0]['vertices']
        for index in (0, 1, 3, 5):
            normal = vertices[index * 12 + 3:index * 12 + 6]
            self.assertAlmostEqual(0, normal[0])
            self.assertAlmostEqual(math.sqrt(.5), normal[1], places=6)
            self.assertAlmostEqual(math.sqrt(.5), normal[2], places=6)
        for index in range(6):
            for channel in (0, 1, 2, 6, 7, 8, 9, 10, 11):
                self.assertEqual(before['meshes'][0]['vertices'][index * 12 + channel],
                                 vertices[index * 12 + channel])
        self.assertEqual(before['meshes'][0]['parts'], source['meshes'][0]['parts'])


if __name__ == '__main__':
    unittest.main(argv=[__file__])
