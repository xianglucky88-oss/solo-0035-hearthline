import ast
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = sorted(ROOT.glob('hearthline/*.py')) + sorted(ROOT.glob('tools/*.py'))
    for path in paths:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    modules = sorted((ROOT / 'web').glob('*.mjs'))
    for path in modules:
        subprocess.run(['node', '--check', path], check=True, timeout=5)
    for path in sorted((ROOT / 'examples').glob('*.json')):
        json.loads(path.read_text(encoding='utf-8'))
    print(f'Python 语法 {len(paths)} 个文件、浏览器模块 {len(modules)} 个、示例 JSON 均通过')


if __name__ == '__main__':
    main()
