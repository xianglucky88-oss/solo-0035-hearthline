import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .codec import decode
from .errors import Problem
from .response import json_reply
from .routes import API, dispatch
from .static import web_reply


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def handle_request(self, method):
        try:
            uri = urlsplit(self.path)
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            host = self.headers.get('Host')
            if host not in allowed or uri.scheme or uri.netloc:
                raise Problem('请从本机工作台访问', 403)
            if method == 'POST' and self.headers.get('Origin', f'http://{host}') != f'http://{host}':
                raise Problem('请从本机工作台发起修改', 403)
            if method == 'GET' and not uri.path.startswith(API):
                reply = web_reply(uri.path)
            else:
                reply = dispatch(self.server.store, method, uri.path, uri.query, self.read_json)
        except Problem as exc:
            reply = json_reply({'error': str(exc)}, exc.status)
        except (ValueError, TimeoutError):
            reply = json_reply({'error': '请求格式错误或未完整接收'}, 400)
        except sqlite3.OperationalError as exc:
            self.log_error('%s', exc)
            reply = json_reply({'error': '存储暂不可用，请稍后重试'}, 503)
        try:
            self.send_response(reply.status)
            self.send_header('Content-Type', reply.content_type)
            self.send_header('Content-Length', str(len(reply.body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for key, value in reply.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(reply.body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def read_json(self):
        length = self.headers.get('Content-Length', '')
        if not length.isascii() or not length.isdigit() or len(length) > 7:
            raise Problem('请求需要有效的 Content-Length')
        size = int(length)
        if not 0 < size <= 4 * 1024 * 1024:
            raise Problem('输入包大小须在 1 字节至 4 MiB 之间', 413)
        if self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding'):
            raise Problem('请用 application/json 提交炉次资料', 415)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise Problem('请求正文未完整接收')
        return decode(raw)


def http_server(port, store):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.store = store
    return server
