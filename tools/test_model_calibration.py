"""Calibration must preserve geometry, embedded artwork, LODs and authored overrides."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from calibrate_model_materials import calibrated_glb
from glb_geometry import read_glb, write_glb
from model_surfaces import unit_surface
from unit_model_geometry import Geometry


def chunks(raw):
    length = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + length]), raw[20 + length:]


class ModelCalibrationTest(unittest.TestCase):
    def test_only_surface_factors_change_in_a_packaged_textured_asset(self):
        model = {'materials': [{'id': 'paint', 'textures': [
            {'id': 'paint', 'type': 'DIFFUSE', 'filename': 'paint.png'}]}],
            'nodes': [{'id': 'root', 'parts': [{'meshpartid': 'panel', 'materialid': 'paint'}]}],
            'meshes': [{'attributes': ['POSITION', 'NORMAL', 'TEXCOORD0'],
                        'vertices': [0, 0, 0, 0, 0, 1, 0, 0,
                                     1, 0, 0, 0, 0, 1, 1, 0,
                                     0, 1, 0, 0, 0, 1, 0, 1],
                        'parts': [{'id': 'panel', 'type': 'TRIANGLES', 'indices': [0, 1, 2]}]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'asset.glb'
            write_glb(path, levels={0: model, 1: copy.deepcopy(model)},
                      embedded_images={'paint.png': b'\x89PNG\r\n\x1a\nartwork'})
            original = path.read_bytes()
            updated = calibrated_glb(original, {'paint': unit_surface('paint', 'bodies/atlas')})
            before, binary_before = chunks(original)
            after, binary_after = chunks(updated)
            self.assertEqual(binary_before, binary_after)
            before['materials'][0]['pbrMetallicRoughness']['roughnessFactor'] = .68
            self.assertEqual(before, after)
            self.assertEqual(len(updated), struct.unpack_from('<I', updated, 8)[0])
            self.assertEqual(updated, calibrated_glb(updated, {'paint': unit_surface('paint', 'bodies/atlas')}))

    def test_independent_materials_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'asset.glb'
            for material in ({'id': 'paint', 'roughness': .4}, {'id': 'paint', 'metallic': 1},
                             {'id': 'paint', 'textures': [{'id': 'surface', 'type': 'METALLIC_ROUGHNESS',
                                                          'filename': 'surface.png'}]}, {'id': 'glass'}):
                write_glb(path, {'nodes': [{'id': 'root'}], 'meshes': [], 'materials': [material]})
                with self.subTest(material=material), self.assertRaises(ValueError):
                    calibrated_glb(path.read_bytes(), {'paint': unit_surface('paint', 'bodies/atlas')})

    def test_unit_export_keeps_mixed_details_separate_from_painted_armor(self):
        geometry = Geometry(modular=True)
        geometry.box((0, 0, 0), (2, 2, 2), 'root', 'paint')
        geometry.box((3, 0, 0), (2, 2, 2), 'root', 'metal')
        geometry.box((6, 0, 0), (2, 2, 2), 'root', 'glass')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'body.glb'
            geometry.export(path, 'bodies/atlas', z_scale=1, paint_uv=True)
            loaded = read_glb(path)
            materials = {material['id']: material for material in loaded['materials']}
            self.assertEqual({'paint', 'detail'}, materials.keys())
            self.assertEqual(.68, materials['paint']['roughness'])
            self.assertEqual(1, materials['detail']['roughness'])
            self.assertTrue(all(material['metallic'] == 0 for material in materials.values()))
            self.assertEqual(2, len(loaded['meshes'][0]['parts']))

    def test_rebuild_scopes_calibration_to_reviewed_assets_including_their_lods(self):
        geometry = Geometry(modular=True)
        geometry.box((0, 0, 0), (2, 2, 2), 'root', 'paint')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'asset.glb'
            for key in ('bodies/atlas', 'bodies/warhammer'):
                for suffix in ('', '-lod0', '-lod1', '-lod2'):
                    geometry.export(path, key + suffix, z_scale=1, paint_uv=True)
                    self.assertEqual(.68, read_glb(path)['materials'][0]['roughness'])
            for key in ('troops/rifle-standing', 'equipment/ppc', 'bodies/family-hover', 'bodies/atlas-custom'):
                geometry.export(path, key, z_scale=1, paint_uv=True)
                self.assertTrue(all(m['roughness'] == 1 and m['metallic'] == 0 for m in read_glb(path)['materials']))


if __name__ == '__main__':
    unittest.main()
