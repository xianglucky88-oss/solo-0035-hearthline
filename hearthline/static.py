import mimetypes
from pathlib import Path

from .errors import Problem
from .response import Reply


WEB = Path(__file__).resolve().parents[1] / 'web'


def web_reply(path):
    asset = (WEB / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
    if not asset.is_relative_to(WEB) or asset.suffix not in ('.html', '.css', '.mjs') or not asset.is_file():
        raise Problem('没有找到该页面', 404)
    content_type = 'text/javascript' if asset.suffix == '.mjs' else mimetypes.guess_type(asset)[0]
    return Reply(asset.read_bytes(), f'{content_type}; charset=utf-8')
