"""
One-time setup for the Asset Finder on a new computer.

Run by double-clicking "Setup Asset Finder.bat" - nobody needs to type this.
After it has finished once, "Start Asset Finder.bat" is used every day.

What it does, in order:
  1. Checks the Python version and that there is enough free disk space.
  2. Creates the app's own private Python space (the ".venv" folder).
  3. Installs the libraries the app needs (about 1.6 GB), then downloads the
     search model once.
  4. Makes the settings file (.env) from the example - never overwriting one
     that already exists.
  5. Opens the settings file in Notepad for the three details.

Safe to run again: anything already done is kept and skipped, so running it a
second time simply carries on from wherever it stopped.

Written to work on older Pythons too, so it can explain "too old" in plain
words instead of crashing.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / "Scripts" / "python.exe"
LOG_FILE = ROOT / "setup_log.txt"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

MIN_PYTHON = (3, 10)
NEEDED_FREE_GB = 4
PYTHON_DOWNLOAD = "https://www.python.org/downloads/"
LINE = "-" * 64

# Every library the app loads - checked once installed, so a library that
# installed but cannot actually be used is caught here, not on first search.
LIBRARIES_TO_CHECK = ("streamlit", "dotenv", "pptx", "pypdf", "sentence_transformers",
                      "chromadb", "requests", "PIL", "openpyxl",
                      "youtube_transcript_api")


class SetupProblem(Exception):
    """A step could not be finished. The message is written for the user."""


# ---------------------------------------------------------------------------
# Output: plain words on screen, full technical detail in setup_log.txt
# ---------------------------------------------------------------------------

def say(text=""):
    print(text, flush=True)


def log(text):
    with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as handle:
        handle.write(text + "\n")


def heading(number, title):
    say()
    say("[{} of 5] {}".format(number, title))
    log("\n===== STEP {}: {} =====".format(number, title))


def run(command, show_lines=None):
    """
    Run a command, writing everything it prints to the log. `show_lines`, if
    given, is called with each line so a step can show plain progress.
    Returns (exit code, everything it printed).
    """
    log("> " + " ".join(str(part) for part in command))
    process = subprocess.Popen(
        [str(part) for part in command], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    printed = []
    for line in process.stdout:
        line = line.rstrip()
        printed.append(line)
        log(line)
        if show_lines:
            show_lines(line)
    process.wait()
    return process.returncode, "\n".join(printed)


class StillWorking:
    """Says "still working" now and then, so a long quiet step never looks stuck."""

    def __init__(self, every_seconds=45):
        self.every = every_seconds
        self.stopped = threading.Event()

    def __enter__(self):
        def keep_saying():
            while not self.stopped.wait(self.every):
                say("    ...still working, please wait")
        threading.Thread(target=keep_saying, daemon=True).start()
        return self

    def __exit__(self, *_):
        self.stopped.set()


# ---------------------------------------------------------------------------
# The five steps
# ---------------------------------------------------------------------------

def check_python_and_space():
    heading(1, "Checking Python and free disk space")
    version = "{}.{}.{}".format(*sys.version_info[:3])
    if sys.version_info[:2] < MIN_PYTHON:
        raise SetupProblem(
            "This computer has Python {}, which is too old. The Asset Finder "
            "needs Python 3.10 or newer.\n\n"
            "  1. Go to  {}\n"
            "  2. Download and install the latest Python. On its first screen, "
            "tick \"Add python.exe to PATH\".\n"
            "  3. Double-click \"Setup Asset Finder.bat\" again.".format(
                version, PYTHON_DOWNLOAD))
    say("    Found Python {} - good.".format(version))

    free_gb = shutil.disk_usage(str(ROOT)).free / (1024 ** 3)
    if free_gb < NEEDED_FREE_GB:
        raise SetupProblem(
            "There is not enough free disk space. Setup needs about {} GB, and "
            "this drive has {:.1f} GB free.\n\nFree up some space (for example, "
            "empty the Recycle Bin), then run setup again.".format(
                NEEDED_FREE_GB, free_gb))
    say("    {:.0f} GB free on this drive - enough.".format(free_gb))


def venv_works():
    if not VENV_PYTHON.exists():
        return False
    try:
        result = subprocess.run([str(VENV_PYTHON), "-c", "import sys"],
                                capture_output=True, timeout=60)
        return result.returncode == 0
    except Exception:
        return False


def create_private_python():
    heading(2, "Creating the app's own Python space")
    if venv_works():
        say("    Already there from an earlier setup - keeping it.")
        return

    if VENV.exists():
        say("    An earlier attempt left it incomplete - rebuilding it.")
        shutil.rmtree(str(VENV), ignore_errors=True)

    code, output = run([sys.executable, "-m", "venv", VENV])
    if code != 0 or not venv_works():
        raise SetupProblem(
            "Could not create the app's Python space in this folder.\n\n"
            "Common causes:\n"
            "  - The folder is inside OneDrive or another synced folder. Move "
            "the Asset Finder folder to, for example, your Documents folder.\n"
            "  - Security software blocked it. Try again, or ask your IT "
            "helper.\n\n"
            "The details are in setup_log.txt.")
    say("    Done.")


def explain_install_failure(output):
    """Turn a failed library install into something a person can act on."""
    text = output.lower()
    if any(sign in text for sign in (
            "failed to establish a new connection", "getaddrinfo failed",
            "temporary failure in name resolution", "connection timed out",
            "read timed out", "network is unreachable", "proxyerror",
            "connectionreseterror", "max retries exceeded")):
        return ("Could not download the libraries. Check this computer is "
                "connected to the internet, then run setup again - it carries "
                "on from where it stopped.")
    if "no space left" in text or "errno 28" in text or "not enough space" in text:
        return ("The drive ran out of space while installing. Free up about "
                "{} GB, then run setup again.".format(NEEDED_FREE_GB))
    if "no matching distribution" in text or "could not find a version" in text:
        return ("Some of the libraries are not available for this version of "
                "Python ({}.{}). Install Python 3.13 from {} (tick \"Add "
                "python.exe to PATH\"), delete the \".venv\" folder inside the "
                "Asset Finder folder, and run setup again.".format(
                    sys.version_info[0], sys.version_info[1], PYTHON_DOWNLOAD))
    if "access is denied" in text or "permission denied" in text or "winerror 5" in text:
        return ("Windows would not let the libraries be installed. If the Asset "
                "Finder is open, close its black window first. Then run setup "
                "again. If it still fails, security software may be blocking "
                "it - ask your IT helper.")
    return ("Something went wrong while installing the libraries. Run setup once "
            "more - a brief hiccup often clears. If it fails again, send "
            "setup_log.txt (in the Asset Finder folder) to whoever helps you.")


def embedding_model_name():
    """The search model named in .env (or the example), to download it now."""
    for source in (ENV_FILE, ENV_EXAMPLE):
        if not source.exists():
            continue
        for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("EMBEDDING_MODEL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    return "mixedbread-ai/mxbai-embed-large-v1"


def install_libraries():
    heading(3, "Installing the app's libraries")
    say("    This downloads about 1.6 GB and takes a few minutes (longer on a")
    say("    slow connection). The window keeps you posted - please leave it open.")

    # A current installer avoids a class of confusing failures. Not essential.
    run([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip",
         "--disable-pip-version-check", "--quiet"])

    announced = set()

    def show(line):
        if line.startswith("Collecting "):
            # "Collecting altair!=5.4.0,<6" -> "altair": keep just the name.
            name = re.split(r"[<>=!~;\[(, ]", line.split()[1])[0]
            if name.lower() not in announced:
                announced.add(name.lower())
                note = " (large - this one takes a while)" if name.lower() == "torch" else ""
                say("    getting {}{}".format(name, note))
        elif line.startswith("Installing collected packages"):
            say("    unpacking and installing everything - a few more minutes...")
        elif line.startswith("Successfully installed"):
            say("    installed.")

    with StillWorking():
        code, output = run([VENV_PYTHON, "-m", "pip", "install", "-r",
                            ROOT / "requirements.txt",
                            "--disable-pip-version-check", "--progress-bar", "off"],
                           show_lines=show)
    if code != 0:
        raise SetupProblem(explain_install_failure(output))

    say("    Checking the libraries can actually be used...")
    code, output = run([VENV_PYTHON, "-c",
                        "import " + ", ".join(LIBRARIES_TO_CHECK)])
    if code != 0:
        raise SetupProblem(
            "The libraries were installed, but Windows will not let one of them "
            "run. This is usually security software (such as Windows Application "
            "Control) blocking a file. Ask your IT helper to allow the Asset "
            "Finder folder, then run setup again.\n\n"
            "The details are in setup_log.txt.")
    say("    All libraries ready.")

    model = embedding_model_name()
    say()
    say("    Downloading the search model ({}).".format(model))
    say("    This is a few hundred MB, and only happens this once...")
    with StillWorking():
        code, output = run([VENV_PYTHON, "-c",
                            "from sentence_transformers import SentenceTransformer; "
                            "SentenceTransformer({!r})".format(model)])
    if code == 0:
        say("    Search model ready.")
    else:
        # Not a reason to stop: the app downloads it on first use instead.
        say("    Could not download it now - that is fine. The app will download")
        say("    it the first time you search (that first search will be slow).")


def make_settings_file():
    heading(4, "Creating your settings file")
    if ENV_FILE.exists():
        say("    You already have one (.env) - keeping it exactly as it is, so")
        say("    nothing you filled in before is lost.")
        return
    if not ENV_EXAMPLE.exists():
        raise SetupProblem(
            "The example settings file (.env.example) is missing from the Asset "
            "Finder folder, so the settings file cannot be made. Download the "
            "Asset Finder folder again, then run setup again.")
    shutil.copyfile(str(ENV_EXAMPLE), str(ENV_FILE))
    say("    Made .env from the example.")


def open_settings(open_notepad=True):
    heading(5, "Opening your settings in Notepad")
    say("    Check these THREE lines near the top, then save (Ctrl+S) and close.")
    say("    They are already filled in for Unsloth - just paste your token.")
    say("    Using Ollama? Change all three to the Ollama column:")
    say()
    say("                    UNSLOTH                           OLLAMA")
    say("      LLM_BASE_URL  http://127.0.0.1:8888/v1          http://localhost:11434/v1")
    say("      LLM_MODEL     Qwen/Qwen3-VL-4B-Instruct-GGUF    qwen3-vl:4b")
    say("      LLM_API_KEY   your token (sk-unsloth-...)       ollama")
    say()
    say("    Setup installs only the Asset Finder itself. Unsloth or Ollama is")
    say("    installed separately, and must be open when you use the app.")
    if open_notepad:
        subprocess.Popen(["notepad.exe", str(ENV_FILE)])


def main():
    open_notepad = "--no-notepad" not in sys.argv[1:]
    LOG_FILE.write_text("Asset Finder setup log - {}\nPython: {}\n".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), sys.executable), encoding="utf-8")

    say(LINE)
    say("  Asset Finder - one-time setup")
    say(LINE)

    try:
        check_python_and_space()
        create_private_python()
        install_libraries()
        make_settings_file()
        open_settings(open_notepad)
    except SetupProblem as problem:
        log("SETUP PROBLEM: " + str(problem))
        say()
        say(LINE)
        say("  SETUP DID NOT FINISH")
        say(LINE)
        say()
        say(str(problem))
        say()
        say("Nothing is broken. Fix the above, then double-click")
        say("\"Setup Asset Finder.bat\" again - it carries on from where it stopped.")
        return 1
    except KeyboardInterrupt:
        say()
        say("Setup was stopped. Double-click \"Setup Asset Finder.bat\" again to")
        say("carry on from where it stopped.")
        return 1
    except Exception:
        log(traceback.format_exc())
        say()
        say(LINE)
        say("  SETUP DID NOT FINISH")
        say(LINE)
        say()
        say("Something unexpected went wrong. Run setup once more. If it happens")
        say("again, send setup_log.txt (in the Asset Finder folder) to whoever")
        say("helps you.")
        return 1

    say()
    say(LINE)
    say("  SETUP FINISHED")
    say(LINE)
    say()
    say("What to do next:")
    say("  1. In Notepad, check the three lines above, then save and close it.")
    say("  2. Make sure your model runner (Unsloth or Ollama) is open.")
    say("  3. Double-click \"Start Asset Finder.bat\" - that is how you open the")
    say("     app from now on. You never need to run this setup again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
