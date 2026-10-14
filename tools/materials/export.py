"""Export every material with Material Maker's native CLI. Run: python export.py"""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
MATERIAL_MAKER = shutil.which('material_maker') or 'C:/material_maker/material_maker.exe'
BAKED = ROOT.parents[1] / 'data/models/board/textures'


def main():
    for project in sorted(ROOT.rglob('*.ptex')):
        if project == ROOT / 'example.ptex':
            continue
        destination = BAKED / project.parent.parent.relative_to(ROOT)
        destination.mkdir(parents=True, exist_ok=True)
        print(f'Exporting {project.relative_to(ROOT)}', flush=True)
        subprocess.run([MATERIAL_MAKER, '--export-material', str(project),
                        '--target', 'MegaMek/Maps', '--output-dir', str(destination)], check=True)


if __name__ == '__main__':
    main()
