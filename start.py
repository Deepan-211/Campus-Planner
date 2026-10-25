"""
Single-command launcher for CampusRide Planner.
Starts both the FastAPI REST backend (port 8000) and the Next.js frontend (port 3000).
"""
import subprocess
import sys
import time
import os
import signal

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_services():
    print("=" * 65)
    print("[*] Starting CampusRide Planner Digital Twin")
    print("=" * 65)

    backend_cmd = [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    frontend_cmd = ["npm", "run", "dev"]

    print("[1/2] Launching FastAPI REST Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(backend_cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    # Wait for backend to initialize
    time.sleep(2)

    print("[2/2] Launching Next.js Digital Twin Dashboard on http://localhost:3000 ...")
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    # Use shell=True on Windows for npm
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=frontend_dir, shell=(sys.platform == "win32"))

    print("\n" + "=" * 65)
    print(" CampusRide Planner is live:")
    print("   * Frontend Dashboard: http://localhost:3000")
    print("   * Backend API Docs:   http://localhost:8000/docs")
    print("   * Healthcheck:        http://localhost:8000/health")
    print("=" * 65 + "\n")
    print("Press Ctrl+C to stop both services.")

    def signal_handler(sig, frame):
        print("\n[*] Shutting down CampusRide Planner...")
        backend_proc.terminate()
        frontend_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    run_services()
