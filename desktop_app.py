"""
Market Chart — Desktop Launcher
"""
import sys
import os
import threading
import webbrowser
import time

PORT = 5000


def open_browser():
    time.sleep(1.5)
    webbrowser.open(f'http://127.0.0.1:{PORT}')


def main():
    print(f"Starting Market Chart at http://127.0.0.1:{PORT}")
    print(f"Frozen: {getattr(sys, 'frozen', False)}")
    print(f"MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    print(f"cwd: {os.getcwd()}")

    threading.Thread(target=open_browser, daemon=True).start()

    from app.app import start_server
    start_server(port=PORT, debug=False)


if __name__ == '__main__':
    main()
