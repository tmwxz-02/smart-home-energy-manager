"""Start the website: backend (Python API) + frontend (HTML/CSS/JS).

Run:  python app.py              (opens http://127.0.0.1:8000 in the browser)
      python app.py --port 8080
      python app.py --network    (other devices in the same Wi-Fi can open it)
      python app.py --no-browser
      python app.py --data-dir D:\backup\data   (use another data folder)
      Or double-click start.bat on Windows.
"""

import argparse

from backend.server import make_server


def local_ip():
    """Best guess of this computer's address in the Wi-Fi / LAN network."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))  # no packet is sent
            return sock.getsockname()[0]
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Serve the Smart Home Energy Manager.")
    import os
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)),
                        help="port (default 8000, or the PORT environment variable)")
    parser.add_argument("--host", help="address to listen on (default 127.0.0.1; 0.0.0.0 on a server)")
    parser.add_argument("--network", action="store_true",
                        help="also allow other devices in the same Wi-Fi to open the page")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the browser automatically")
    parser.add_argument("--data-dir", help="folder for the SQLite files (default: ./data)")
    args = parser.parse_args()
    if args.data_dir:
        import os
        os.environ["SHEM_DATA_DIR"] = args.data_dir
    host = args.host or ("0.0.0.0" if args.network else "127.0.0.1")
    try:
        server = make_server(host, args.port)
    except OSError:
        print(f"Port {args.port} is already in use. Another copy of the server may still be running.")
        print("Close it with Ctrl+C in its terminal, or start on another port: "
              f"python app.py --port {args.port + 1}")
        return
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print("Smart Home Energy Manager")
    print(f"Open {url} in your browser.")
    if args.network:
        ip = local_ip()
        if ip:
            print(f"Other devices in the same Wi-Fi: open http://{ip}:{port}/")
    print("Keep this window open while you use the site. Press Ctrl+C to stop.")
    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
