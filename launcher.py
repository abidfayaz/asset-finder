"""
Starts the Asset Finder and opens it in the browser.

Normally run by double-clicking "Start Asset Finder.bat" - nobody needs to type
this. It does not install anything; it only launches an app that is already
set up.

What it does, in order:
  1. If the app is already running, just opens the browser on it.
  2. Checks that the AI model runner (Unsloth Studio or Ollama) is reachable,
     and warns - without stopping - if it is not.
  3. Starts the app, with its technical messages written to app_log.txt
     instead of cluttering this window.
  4. Opens the browser as soon as the app is ready.
  5. Keeps running until the window is closed, which stops the app.
"""

import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PORT = 8501
APP_URL = f"http://localhost:{PORT}"
HEALTH_URL = f"{APP_URL}/_stcore/health"
LOG_FILE = PROJECT_ROOT / "app_log.txt"

# How long to wait for the app to start before giving up. The first start on a
# computer can be slow while Windows scans the libraries.
START_TIMEOUT_SECONDS = 180

LINE = "-" * 64


def app_is_running() -> bool:
    """True if an Asset Finder is already answering on this computer."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def model_runner_address() -> str:
    """
    The model runner's address from .env, or "" if the app is not set up to
    use one on this computer (for example it uses an online service instead).
    """
    try:
        from dotenv import dotenv_values
        settings = dotenv_values(PROJECT_ROOT / ".env")
    except Exception:
        return ""
    address = (settings.get("LLM_BASE_URL") or "").strip()
    host = urllib.parse.urlparse(address).hostname or ""
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        return address
    return ""


def model_runner_is_up(address: str) -> bool:
    """
    True if something answers at the runner's address. Any reply counts, even
    "not allowed" - that still means the runner is switched on.
    """
    try:
        with urllib.request.urlopen(address.rstrip("/") + "/models", timeout=3):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def open_browser(no_browser: bool) -> None:
    if not no_browser:
        webbrowser.open(APP_URL)


def main() -> int:
    # --no-browser is only for checking the launcher itself without a browser
    # tab popping up. Double-clicking never uses it.
    no_browser = "--no-browser" in sys.argv[1:]

    print(LINE)
    print("  Asset Finder")
    print(LINE)

    # 1. Already running? Do not start a second copy - just show it.
    if app_is_running():
        print(f"\n  The app is already running. Opening it in your browser:")
        print(f"  {APP_URL}")
        print("\n  (This extra window will close by itself.)")
        open_browser(no_browser)
        time.sleep(6)
        return 0

    # 2. The model runner. Search works without it, so this only warns.
    runner = model_runner_address()
    if runner and not model_runner_is_up(runner):
        print("\n  WARNING: the AI model runner is not running.")
        print(f"  (Looked for Unsloth Studio or Ollama at {runner})")
        print("  Search still works. Until you start it:")
        print("    - the 'why it matched' notes are simpler, and")
        print("    - pictures in new files cannot be read.")
        print("  Start Unsloth Studio (or Ollama) whenever you like -")
        print("  there is no need to restart the app afterwards.")

    # 3. Start the app. Its technical messages go to a log file.
    print("\n  Starting the app - this can take up to a minute...")
    log = open(LOG_FILE, "w", encoding="utf-8", errors="replace")
    app = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(PORT),
         # Watching the code for edits is only useful to a developer, and it
         # fills the log with harmless but alarming-looking messages.
         "--server.fileWatcherType", "none"],
        cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT,
    )

    # 4. Wait until it answers, then open the browser.
    waited = 0
    while not app_is_running():
        if app.poll() is not None:
            print("\n  The app could not start.")
            print(f"  The details are in: {LOG_FILE}")
            return 1
        if waited >= START_TIMEOUT_SECONDS:
            print("\n  The app is taking unusually long to start.")
            print(f"  The details are in: {LOG_FILE}")
            app.terminate()
            return 1
        time.sleep(1)
        waited += 1

    open_browser(no_browser)
    print(LINE)
    print("  The Asset Finder is open in your browser:")
    print(f"  {APP_URL}")
    print()
    print("  Keep this window open while you use the app.")
    print("  CLOSE THIS WINDOW TO STOP THE APP.")
    print(LINE)

    # 5. Stay here until the app stops or this window is closed. Closing the
    #    window ends the app too, because it runs inside this window.
    try:
        app.wait()
    except KeyboardInterrupt:
        app.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
