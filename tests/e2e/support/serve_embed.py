"""Serve the real embed build at its root and versioned production URL in browser tests."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class EmbedHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urlsplit(path).path
        if path.startswith('/chat/v1/'):
            path = path[len('/chat/v1'):]
        return super().translate_path(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), partial(EmbedHandler, directory=args.directory)).serve_forever()
