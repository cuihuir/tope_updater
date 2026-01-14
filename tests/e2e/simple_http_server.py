"""Simple HTTP server for serving test packages."""

import http.server
import socketserver
import threading
import os
from pathlib import Path
from functools import partial

class SimpleHTTPServer:
    """Simple HTTP server for E2E tests."""

    def __init__(self, directory: Path, port: int = 8080):
        self.directory = directory
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        """Start the HTTP server in a background thread."""
        # Create handler that serves from specific directory
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(self.directory))

        # Create server
        self.httpd = socketserver.TCPServer(("", self.port), handler)

        # Start in background thread
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

        print(f"HTTP server started on port {self.port}, serving {self.directory}")

    def stop(self):
        """Stop the HTTP server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print(f"HTTP server stopped on port {self.port}")


if __name__ == "__main__":
    # Test the server
    import time
    test_dir = Path(__file__).parent / "test_data" / "packages"
    test_dir.mkdir(parents=True, exist_ok=True)

    server = SimpleHTTPServer(test_dir, 8080)
    server.start()

    print("Server running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
