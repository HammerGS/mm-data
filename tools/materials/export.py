"""Export all materials, or one relative PTEX path: python export.py [material.ptex]"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MATERIAL_MAKER = shutil.which('material_maker') or 'C:/material_maker/material_maker.exe'
BAKED = ROOT.parents[1] / 'data/models/board/textures'


def main():
    if len(sys.argv) > 2:
        raise SystemExit('Usage: python export.py [relative/path/to/material.ptex]')
    projects = sorted(project for project in ROOT.rglob('*.ptex') if project != ROOT / 'example.ptex')
    if len(sys.argv) == 2:
        relative = Path(sys.argv[1])
        project = (ROOT / relative).resolve()
        if relative.is_absolute() or project not in projects:
            raise SystemExit('Expected an existing production .ptex path relative to tools/materials')
        projects = [project]
    for project in projects:
        destination = BAKED / project.parent.parent.relative_to(ROOT)
        destination.mkdir(parents=True, exist_ok=True)
        print(f'Exporting {project.relative_to(ROOT)}', flush=True)
        subprocess.run([MATERIAL_MAKER, '--export-material', str(project),
                        '--target', 'MegaMek/Maps', '--output-dir', str(destination)], check=True)
        # The native export may disable an optional map; do not leave its old bake behind.
        metadata = destination / (project.stem + '.json')
        if metadata.is_file() and 'roughness_map' not in json.loads(metadata.read_text(encoding='utf-8')):
            (destination / (project.stem + '-roughness.png')).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
