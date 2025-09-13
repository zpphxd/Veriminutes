#!/usr/bin/env python3
"""
Start the VeriMinutes server and automatically open the browser.
"""

import subprocess
import time
import webbrowser
import sys
import os
from pathlib import Path

def is_server_running(port=8787):
    """Check if server is already running on the port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except:
        return False

def start_server():
    """Start the VeriMinutes server and open browser."""

    port = 8787
    url = f"http://localhost:{port}"

    # Check if server is already running
    if is_server_running(port):
        print(f"⚠️  Server already running on port {port}")
        print(f"Opening browser to {url}")
        webbrowser.open(url)
        return

    print("🚀 Starting VeriMinutes server...")
    print(f"📍 Server will run at: {url}")

    # Start the server in a subprocess
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.app.api:app",
         "--host", "localhost", "--port", str(port), "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait a moment for server to start
    print("⏳ Waiting for server to start...")
    max_attempts = 10
    for i in range(max_attempts):
        time.sleep(1)
        if is_server_running(port):
            print("✅ Server is ready!")
            break
        if i == max_attempts - 1:
            print("⚠️  Server took longer than expected to start")

    # Open the browser
    print(f"🌐 Opening browser to {url}")
    time.sleep(0.5)  # Small delay to ensure server is fully ready
    webbrowser.open(url)

    print("\n" + "="*50)
    print("🎉 VeriMinutes is running!")
    print(f"🔗 URL: {url}")
    print("📝 Press Ctrl+C to stop the server")
    print("="*50 + "\n")

    # Keep the process running
    try:
        for line in iter(server_process.stdout.readline, ''):
            if line:
                print(line.rstrip())
        server_process.wait()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server stopped")
        sys.exit(0)

if __name__ == "__main__":
    start_server()