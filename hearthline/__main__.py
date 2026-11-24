import argparse
from pathlib import Path

from .server import http_server
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='炉迹 · 连续炉料盘热历核对台')
    parser.add_argument('--port', type=int, default=8735, help='本机 HTTP 端口')
    parser.add_argument('--db', type=Path, default=Path('var/hearthline.sqlite'), help='炉次证据库文件')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('端口须为 0 至 65535 的整数')
    with http_server(args.port, Store(args.db)) as server:
        print(f'炉迹工作台 http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
