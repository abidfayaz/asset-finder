"""
Runs "Process the files" in the background, in batches.

The reading happens on a separate thread inside the running app, not inside
the browser page. So refreshing the page, switching tabs or closing the browser
tab does not interrupt it - only stopping the app itself does.

Work goes in batches of about five minutes, with a short breather between them,
carrying on by itself until everything is done. That way the progress on screen
keeps moving and files become searchable while the rest is still being read.

Stopping is always BETWEEN files. Whatever is being read is finished and saved
first, so no file is ever left half-read - whether you press Pause, a batch
runs out of time, or you close the app.

The page asks status() every couple of seconds to draw the progress display.
"""

import threading
import time
import traceback
from pathlib import Path

import indexer

# How long one batch runs before pausing for breath. A file that is still
# being read when the time runs out is finished first, so a batch can overrun
# by however long that one file takes.
BATCH_SECONDS = 5 * 60

# A short gap between batches, so the screen visibly moves on to the next one.
REST_BETWEEN_BATCHES_SECONDS = 5

# Counts that add up across the batches of one run. The others - "already up
# to date", "skipped", the totals - describe the whole library each time a
# batch looks at it, so the last batch's number is the right one to keep.
_ADDING_UP = ("processed", "failed", "decorative_images", "removed_missing",
              "videos_indexed", "videos_skipped", "videos_failed", "partial")
_LISTS = ("failures", "skipped_files", "removed_files", "partial_files",
          "video_failures")

_lock = threading.Lock()
_state = {
    "running": False,
    "run_number": 0,        # goes up by one each time processing starts
    "phase": None,          # "clearing", "files", "videos" or "resting"
    "done": 0,
    "total": 0,
    "current": None,        # the file or video being read right now
    "batch": 0,
    "folder": None,
    "replaced": False,      # did this run replace the previous library?
    "paused": False,        # stopped by the Pause button
    "pause_requested": False,
    "automatic": False,     # started by the app opening, not by a button
    "videos": True,         # does this run look at the YouTube list too?
    "started_at": None,
    "finished_at": None,
    "summary": None,
    "error": None,
}


def status() -> dict:
    """A copy of where processing has got to. Safe to call at any time."""
    with _lock:
        return dict(_state)


def start(folder, replace: bool = False, include_videos: bool = True,
          automatic: bool = False, retry_unfinished: bool = True) -> bool:
    """
    Start processing `folder` in the background. `replace` empties the current
    library from search first.

    Also used to carry on after a pause, or after the app was closed part-way:
    files already done are skipped, so it picks up where it left off.

    `include_videos=False` reads only the files, leaving the YouTube list alone.
    `automatic=True` marks a run nobody asked for, so the screen can keep quiet
    about it when there is nothing new.

    Returns False, and does nothing, if processing is already running.
    """
    with _lock:
        if _state["running"]:
            return False
        _state.update({
            "automatic": automatic,
            "videos": include_videos,
            "running": True,
            "run_number": _state["run_number"] + 1,
            "phase": None,
            "done": 0,
            "total": 0,
            "current": None,
            "batch": 0,
            "folder": str(folder),
            "replaced": replace,
            "paused": False,
            "pause_requested": False,
            "started_at": time.time(),
            "finished_at": None,
            "summary": None,
            "error": None,
        })

    worker = threading.Thread(target=_run,
                              args=(Path(folder), replace, include_videos,
                                    retry_unfinished),
                              name="process-the-files", daemon=True)
    worker.start()
    return True


# Has the automatic check already run since the app started? It should happen
# once when the app opens, not on every page refresh.
_checked_on_open = False


def auto_check_on_open(folder) -> bool:
    """
    Look for new, changed, deleted and renamed files when the app opens.

    Runs once per app start, in the background, and only when a library has
    already been processed - there is nothing to compare against otherwise, and
    reading a whole library for the first time should be a deliberate choice.
    The YouTube list is left alone, so opening the app never reaches out to the
    internet.
    """
    global _checked_on_open
    with _lock:
        if _checked_on_open or _state["running"]:
            return False
        _checked_on_open = True

    folder = Path(folder)
    if not folder.is_dir():
        return False
    if not indexer.load_status().get("files"):
        return False

    return start(folder, replace=False, include_videos=False, automatic=True,
                 retry_unfinished=False)


def request_pause() -> bool:
    """
    Ask to stop after the file being read is finished.

    Returns False if nothing is running.
    """
    with _lock:
        if not _state["running"]:
            return False
        _state["pause_requested"] = True
        return True


def _progress(phase, done, total, current=None) -> None:
    with _lock:
        _state.update({"phase": phase, "done": done, "total": total,
                       "current": current})


def _should_stop() -> bool:
    """Asked between files: has Pause been pressed, or is this batch over?"""
    with _lock:
        if _state["pause_requested"]:
            return True
        deadline = _state.get("batch_deadline")
    return bool(deadline and time.monotonic() >= deadline)


def _merge(running_total: dict, batch: dict) -> dict:
    """One set of counts for the whole run, from each batch's counts."""
    if running_total is None:
        return dict(batch)
    merged = dict(batch)
    for name in _ADDING_UP:
        merged[name] = running_total.get(name, 0) + batch.get(name, 0)
    for name in _LISTS:
        merged[name] = list(running_total.get(name, [])) + list(batch.get(name, []))
    # A problem with the link spreadsheet is worth keeping: batches that stop
    # before reaching the videos never look at it and so never report it.
    merged["video_list_error"] = (batch.get("video_list_error")
                                  or running_total.get("video_list_error"))
    return merged


def _run(folder: Path, replace: bool, include_videos: bool = True,
         retry_unfinished: bool = True) -> None:
    try:
        if replace:
            _progress("clearing", 0, 0)
            collection = indexer.get_collection()
            record = indexer.load_status()
            indexer.clear_library(collection, record)
            record["library_folder"] = str(folder)
            indexer.save_status(record)

        # Files tried in this run already. Passed to the next batch so a file
        # that failed - or a deck whose pictures could not be read - is not
        # retried over and over within the same run.
        tried = set()
        totals = None

        while True:
            with _lock:
                _state["batch"] += 1
                _state["batch_deadline"] = time.monotonic() + BATCH_SECONDS

            batch = indexer.index_assets(folder, progress=_progress,
                                         should_stop=_should_stop,
                                         skip_files=tried,
                                         include_videos=include_videos,
                                         retry_unfinished=retry_unfinished)
            tried.update(batch.get("worked_on", []))
            totals = _merge(totals, batch)
            with _lock:
                _state["summary"] = totals
                paused = _state["pause_requested"]

            if paused:
                with _lock:
                    _state["paused"] = True
                    _state["pause_requested"] = False
                break

            if not batch.get("stopped_early"):
                break          # everything has been looked at

            # Out of time rather than out of work: breathe, then carry on.
            with _lock:
                _state["phase"] = "resting"
                _state["current"] = None
            time.sleep(REST_BETWEEN_BATCHES_SECONDS)

    except Exception as error:
        traceback.print_exc()
        with _lock:
            _state["error"] = str(error) or error.__class__.__name__
    finally:
        with _lock:
            _state.update({"running": False, "current": None,
                           "batch_deadline": None,
                           "finished_at": time.time()})
