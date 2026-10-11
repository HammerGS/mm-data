"""Material parameters survive generation and offline GLB editing without gamma conversion."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from glb_geometry import read_glb, write_glb


class GlbMaterialsTest(unittest.TestCase):
    def test_authored_factors_and_packed_map_survive_round_trip(self):
        material = {'id': 'steel', 'diffuse': [.4, .5, .6], 'roughness': .37, 'metallic': .8,
                    'textures': [{'id': 'steel', 'type': 'METALLIC_ROUGHNESS', 'filename': 'surface.png'}]}
        model = {'nodes': [{'id': 'root'}], 'meshes': [], 'materials': [material]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'surface.glb'
            write_glb(path, model)
            loaded = read_glb(path)
            surface = loaded['materials'][0]
            self.assertEqual(.37, surface['roughness'])
            self.assertEqual(.8, surface['metallic'])
            self.assertEqual('METALLIC_ROUGHNESS', surface['textures'][0]['type'])
            write_glb(path, loaded)
            raw = path.read_bytes()
            length = struct.unpack_from('<I', raw, 12)[0]
            document = json.loads(raw[20:20 + length])
            pbr = document['materials'][0]['pbrMetallicRoughness']
            self.assertEqual(.37, pbr['roughnessFactor'])
            self.assertEqual(.8, pbr['metallicFactor'])
            self.assertEqual('surface.png', document['images'][document['textures'][
                pbr['metallicRoughnessTexture']['index']]['source']]['uri'])

    def test_existing_generators_stay_matte_and_invalid_factors_are_rejected(self):
        material = {'id': 'wall'}
        model = {'nodes': [{'id': 'root'}], 'meshes': [], 'materials': [material]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wall.glb'
            write_glb(path, model)
            surface = read_glb(path)['materials'][0]
            self.assertEqual(1, surface['roughness'])
            self.assertEqual(0, surface['metallic'])
            for key in ('roughness', 'metallic'):
                for value in (-.1, 1.1, float('nan')):
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        write_glb(path, {**model, 'materials': [{**material, key: value}]})


if __name__ == '__main__':
    unittest.main()
