"""
Asset Finder - the app: search your decks, PDFs, images and YouTube videos by
meaning, and process your content folder, all in the browser.

Normally started by double-clicking "Start Asset Finder.bat".
Developers can run it with:  streamlit run app.py
"""

import html
from pathlib import Path

import streamlit as st

import config
import indexer
import llm
import processing
import search as search_module

# Use the content folder chosen on the Processing log page, remembered in the
# index's record. Not while files are being processed - that run has set it.
if not processing.status()["running"]:
    indexer.use_saved_library_folder()

# New, changed, deleted and renamed files are picked up on their own when the
# app opens - nobody has to press anything. It happens once per app start, in
# the background, and only for a library that has been processed before.
processing.auto_check_on_open(config.ASSETS_FOLDER)

# Browser tab title and page width. Must be the first Streamlit call.
st.set_page_config(page_title="Asset Finder", page_icon="🔎", layout="wide")

# The one accent colour, used for buttons, highlights and the best-match
# banner. Change it here and the whole app follows.
ACCENT = "#4F46E5"
ACCENT_SOFT = "#EEF0FE"
ACCENT_EDGE = "#D9DDFB"
MUTED = "#6B7280"

# A small amount of styling on top of Streamlit's defaults: a comfortable page
# width, consistent spacing between cards, and readable type sizes.
st.markdown(
    f"""
    <style>
      /* Keep the page from stretching too wide to read on a big monitor. */
      .block-container {{ max-width: 1180px; padding-top: 2.2rem;
                          padding-bottom: 3rem; }}

      /* The settings gear: nudged down a few pixels so its top edge is not
         hidden under Streamlit's top bar. It stays level with the title. */
      .st-key-settings_gear {{ position: relative; top: 6px; }}

      /* Even spacing between result cards. */
      div[data-testid="stVerticalBlockBorderWrapper"] {{
          margin-bottom: 0.85rem; }}

      /* Headings: a clear step down in size, not shouty. */
      h1 {{ font-size: 1.9rem !important; font-weight: 700 !important;
            letter-spacing: -0.01em; }}
      h2 {{ font-size: 1.35rem !important; font-weight: 650 !important;
            margin-top: 1.6rem !important; }}
      h3 {{ font-size: 1.05rem !important; font-weight: 650 !important;
            margin-top: 1.4rem !important; margin-bottom: 0.2rem !important; }}

      /* Body text a touch larger than the default for comfortable reading. */
      .stMarkdown p {{ font-size: 0.94rem; line-height: 1.6; }}

      /* Tabs: roomier, with the accent colour marking the active one. */
      button[data-baseweb="tab"] {{ font-size: 1rem; padding: 0.4rem 0.1rem; }}
      div[data-baseweb="tab-highlight"] {{ background-color: {ACCENT}; }}

      /* Recent-search chips: pill shaped and quiet, so they do not compete
         with the search button. */
      div[data-testid="column"] button[kind="secondary"] {{
          border-radius: 999px; font-size: 0.82rem; padding: 0.2rem 0.9rem;
          color: {MUTED}; border-color: #E2E4EE; font-weight: 500; }}
      div[data-testid="column"] button[kind="secondary"]:hover {{
          border-color: {ACCENT}; color: {ACCENT}; }}

      /* The summary numbers on the processing screen. */
      div[data-testid="stMetricValue"] {{ font-size: 1.7rem; }}
      div[data-testid="stMetricLabel"] {{ font-size: 0.82rem; color: {MUTED}; }}

      /* File paths are one long unbroken string - let them wrap rather than
         forcing a sideways scrollbar. */
      div[data-testid="stCode"] code {{
          white-space: pre-wrap !important; overflow-wrap: anywhere !important;
          font-size: 0.78rem !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Loading the model and the database
#
# Both take a few seconds to open, so we do it once and Streamlit keeps them
# in memory. Without this they would reload on every single click.
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading the search model (first time only)...")
def load_model():
    return indexer.get_embedding_model()


@st.cache_resource(show_spinner="Opening the search database...")
def load_collection():
    return indexer.get_collection()


# How many past searches to keep as clickable chips. These live only for as
# long as the browser tab is open - nothing is written to disk.
RECENT_LIMIT = 5


def remember_search(query: str) -> None:
    """
    Add a search to the recent list, newest first, with no duplicates.
    Searching something again moves it back to the front.
    """
    recents = st.session_state.setdefault("recent_searches", [])
    if query in recents:
        recents.remove(query)
    recents.insert(0, query)
    # Keep only the most recent few.
    del recents[RECENT_LIMIT:]


def render_recent_chips() -> None:
    """
    Show past searches as buttons. Clicking one runs that search again.
    """
    recents = st.session_state.get("recent_searches", [])
    if not recents:
        return

    st.caption("Recent searches")
    columns = st.columns(len(recents))
    for column, past_query in zip(columns, recents):
        with column:
            if st.button(past_query, key=f"chip_{past_query}",
                         use_container_width=True):
                # Note which chip was clicked and start the page again. The
                # search box is actually filled in at the top of the next run,
                # because Streamlit will not let us change a box that has
                # already been drawn on this run.
                st.session_state["pending_chip"] = past_query
                st.rerun()


def get_reasons(query: str, results: list[dict],
                weak: bool = False) -> tuple[list[tuple], str | None]:
    """
    Work out a "why it matched" sentence for EVERY result.

    Only the top few are worth paying an AI call for (see WHY_TOP_N). The rest
    get the free word-overlap explanation, so no card is ever left blank.

    Returns a list of (sentence, source) pairs in result order - where source
    is "ai" or "words" - plus any problem message from the AI service.

    Both are kept in session memory against the exact search text, so clicking
    around the page does not fire the same AI request over and over.
    """
    cache = st.session_state.setdefault("reason_cache", {})
    cache_key = (query, weak)
    if cache_key in cache:
        return cache[cache_key]

    paid_for = results[: config.WHY_TOP_N]
    the_rest = results[config.WHY_TOP_N:]

    sentences = llm.why_it_matched(query, paid_for, weak=weak)
    error = llm.last_error
    verdicts = llm.last_related

    # If there is no key, or the call failed, those top sentences are word
    # overlap too - so label them honestly rather than claiming they are AI.
    top_source = "ai" if (llm.is_configured() and not error) else "words"

    # Each entry: (sentence, where it came from, the AI's related verdict).
    entries = [(sentence, top_source,
                verdicts[index] if index < len(verdicts) else None)
               for index, sentence in enumerate(sentences)]
    # The rest cost nothing: no API call, no waiting - and no verdict.
    entries += [(llm.simple_reason(query, r["text"], weak), "words", None)
                for r in the_rest]

    # Store the error together with the reasons, so a cached result keeps
    # showing the message that actually belongs to it.
    cache[cache_key] = (entries, error)
    return cache[cache_key]


def judged_unrelated(result: dict) -> bool:
    """
    Did the AI decide this result is not really a match? Either it said so
    outright, or its own sentence says there is no relation to the search.
    """
    if result.get("related") is False:
        return True
    return (result.get("reason_source") == "ai"
            and llm.says_unrelated(result.get("reason") or ""))


def show_nothing_matched(query: str, closest_chosen: bool = False) -> None:
    """The plain message for a search with no genuine match."""
    if closest_chosen:
        # "Show closest" is on, and still nothing is near enough to show.
        st.info(f"**Nothing matched, and nothing in your library is close.** "
                f"Nothing is a match for \"{query}\", and nothing is near enough "
                f"to be worth showing either.")
        return
    st.info(f"**Nothing matched exactly.** Nothing in your library is a "
            f"confident match for \"{query}\".  \n"
            f"To see the nearest results anyway, open ⚙️ Settings and choose "
            f"\"{SHOW_CLOSEST}\".")


def render_table(rows: list[dict]) -> None:
    """
    Draw a plain HTML table.

    Streamlit's own table needs pandas, and pandas will not load on every
    machine - Windows Application Control blocks one of its files on some
    setups. Writing the table by hand keeps this screen working everywhere.
    """
    if not rows:
        return

    headers = list(rows[0].keys())

    head = "".join(
        f"<th style='text-align:left; padding:8px 10px; position:sticky; "
        f"top:0; background:#f2f3f6; border-bottom:2px solid #dcdde3; "
        f"white-space:nowrap;'>{html.escape(h)}</th>"
        for h in headers
    )

    body = []
    for number, row in enumerate(rows):
        stripe = "#ffffff" if number % 2 == 0 else "#fafafc"
        cells = "".join(
            f"<td style='padding:7px 10px; border-bottom:1px solid #ecedf1; "
            f"vertical-align:top;'>{html.escape(str(row[h]))}</td>"
            for h in headers
        )
        body.append(f"<tr style='background:{stripe};'>{cells}</tr>")

    st.markdown(
        f"<div style='max-height:430px; overflow:auto; border:1px solid "
        f"#e3e4e9; border-radius:6px;'>"
        f"<table style='width:100%; border-collapse:collapse; "
        f"font-size:0.86rem;'>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )


def render_preview(result: dict, query: str) -> None:
    """
    Show what the result actually looks like.

    Images: the picture itself, with the description underneath.
    Deck slides: a slide-shaped frame holding the slide's text.
    PDFs: just the matching text.

    The deck preview is a stand-in: rendering the real slide to a picture would
    look better, but needs PowerPoint or LibreOffice installed.
    """
    highlighted = search_module.highlight(result["snippet"], query)

    if result["type"] == "image":
        picture, caption = st.columns([1, 2])
        with picture:
            # Found via the assets folder, so this works whether the app is
            # running on the machine that built the index or on a server.
            picture_file = search_module.local_file(result)
            try:
                if picture_file:
                    st.image(str(picture_file), use_container_width=True)
                else:
                    st.caption("(picture not available here)")
            except Exception:
                # A missing or unreadable file must not break the whole page.
                st.caption("(preview unavailable)")
        with caption:
            st.caption("What the image shows")
            st.markdown(highlighted, unsafe_allow_html=True)
        return

    if result["type"] == "youtube":
        # The words spoken in this stretch of the video. Labelled clearly,
        # because it is a quote from the soundtrack - not text on screen.
        st.markdown(
            f"<div style='border:1px solid #d8dae2; border-radius:6px; "
            f"background:#fbfbfd; padding:16px 20px; margin:6px 0 10px 0; "
            f"box-shadow:0 1px 3px rgba(0,0,0,0.06); overflow-wrap:anywhere;'>"
            f"<div style='font-size:0.68rem; letter-spacing:0.08em; "
            f"color:#9aa0a6; margin-bottom:6px;'>"
            f"SPOKEN IN THIS VIDEO</div>"
            f"<div style='font-size:0.95rem; line-height:1.55;'>"
            f"“{highlighted}”</div></div>",
            unsafe_allow_html=True,
        )
        return

    if result["type"] == "deck":
        # A slide-shaped box: pale background, slide number above the text.
        # If the match came from a picture on the slide rather than typed
        # text, say so - otherwise the wording looks like it was written there.
        label = result["location_label"].upper()
        if result.get("source") == "picture":
            label += " · FROM A PICTURE ON THIS SLIDE"
        st.markdown(
            f"<div style='border:1px solid #d8dae2; border-radius:6px; "
            f"background:#fbfbfd; padding:18px 22px; margin:6px 0 10px 0; "
            f"min-height:120px; box-shadow:0 1px 3px rgba(0,0,0,0.06); "
            f"overflow-wrap:anywhere;'>"
            f"<div style='font-size:0.68rem; letter-spacing:0.08em; "
            f"color:#9aa0a6; margin-bottom:6px;'>"
            f"{html.escape(label)}</div>"
            f"<div style='font-size:0.95rem; line-height:1.5;'>"
            f"{highlighted}</div></div>",
            unsafe_allow_html=True,
        )
        return

    # PDFs and anything else: the text on its own.
    st.markdown(
        f"<div style='font-size:0.94rem; line-height:1.55; "
        f"overflow-wrap:anywhere;'>{highlighted}</div>",
        unsafe_allow_html=True,
    )


def confidence_pill(confidence: str, align: str = "right") -> str:
    """The little rounded label saying how good the match is."""
    strong = confidence.startswith("Strong")
    text_colour = ACCENT if strong else MUTED
    background = ACCENT_SOFT if strong else "#F1F2F5"
    return (
        f"<div style='text-align:{align};'>"
        f"<span style='background:{background}; color:{text_colour}; "
        f"font-size:0.72rem; font-weight:600; padding:3px 10px; "
        f"border-radius:999px; white-space:nowrap;'>{confidence}</span></div>"
    )


def render_result_card(result: dict, query: str, weak: bool = False) -> None:
    """
    Draw one search result.

    The rank number and the "why it matched" sentence are carried on the
    result itself, so the card has everything it needs.
    """
    rank = result.get("rank")
    reason = result.get("reason")

    with st.container(border=True):
        # Line 1: file name on the left, how confident we are on the right.
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"**{rank}. {result['file_name']}**")
        with right:
            st.markdown(confidence_pill(result["confidence"]),
                        unsafe_allow_html=True)

        # Line 2: what kind of file, and which slide/page inside it.
        bits = [search_module.type_label(result["type"])]
        if result["location_label"]:
            bits.append(result["location_label"])
        st.caption(" · ".join(bits))

        # Line 3: why this came back, in one plain sentence.
        # Blue with an "AI" tag = written by the AI service (top results).
        # Grey with a "word check" tag = the free explanation (all the rest).
        if reason:
            if result.get("reason_source") == "ai":
                tint, edge, tag = ACCENT_SOFT, ACCENT, "AI"
            else:
                tint, edge, tag = "#F4F5F7", "#9AA0A6", "word check"

            st.markdown(
                f"<div style='background-color:{tint}; "
                f"border-left:3px solid {edge}; padding:8px 12px; "
                f"border-radius:4px; margin-bottom:10px; "
                f"font-size:0.9rem; line-height:1.5; "
                f"overflow-wrap:anywhere;'>"
                f"<span style='display:inline-block; background-color:{edge}; "
                f"color:white; font-size:0.66rem; font-weight:700; "
                f"padding:1px 6px; border-radius:8px; margin-right:8px; "
                f"vertical-align:middle;'>{tag}</span>"
                # In the "closest few" state, nothing matched - so calling this
                # "why it matched" would contradict the banner above it.
                f"<b>{'What this covers' if weak else 'Why it matched'}:</b> "
                f"{html.escape(reason)}</div>",
                unsafe_allow_html=True,
            )

        # Line 4: a look at the thing itself, so you can recognise it without
        # opening the file.
        render_preview(result, query)

        # Line 5: how to get to the thing itself.
        if result["type"] == "youtube":
            # A video is not a file, so showing a "file location" would be a
            # lie. Give a link that actually opens it instead.
            link = search_module.web_link(result)
            if link:
                # Say where the link lands, when the excerpt's start is known.
                start = result.get("start_seconds")
                watch_label = "▶ Watch on YouTube"
                if start is not None:
                    import transcripts
                    watch_label += f" from {transcripts.format_time(start)}"
                # Escaping the link turned "&" into "&amp;" in the visible
                # text. web_link has already checked it is a plain http(s)
                # address, so only the characters that could break out of the
                # HTML are removed, and "&t=74s" reads as written.
                shown_link = link.translate({ord(c): None for c in "<>\"'"})
                st.markdown(
                    f"<a href='{shown_link}' target='_blank' "
                    f"rel='noopener noreferrer' "
                    f"style='display:inline-block; background:{ACCENT}; "
                    f"color:#ffffff; text-decoration:none; font-weight:600; "
                    f"font-size:0.85rem; padding:7px 16px; border-radius:6px; "
                    f"margin-top:2px;'>{watch_label}</a>"
                    f"<div style='font-size:0.72rem; color:{MUTED}; "
                    f"margin-top:6px; overflow-wrap:anywhere;'>"
                    f"{shown_link}</div>",
                    unsafe_allow_html=True,
                )
            else:
                # Better to show nothing than a button that goes nowhere.
                st.caption("Video address unavailable for this result.")
        else:
            # For real files: where it is, with a copy button for free.
            #
            # This is a location, not a web link - the app points you at the
            # file in your own library rather than serving a copy of it. The
            # wording says which kind of location it is, so nobody tries to
            # paste a folder path into a browser.
            # Open or download the file, depending on the choice in Settings.
            render_file_action(result)

            st.caption("File location — paste into File Explorer to open")
            st.code(search_module.display_location(result), language=None)


# ---------------------------------------------------------------------------
# Processing the files - the folder box, the button and the progress display
#
# The reading itself runs in the background (processing.py), so refreshing the
# page, switching tabs or closing the browser tab does not stop it.
# ---------------------------------------------------------------------------

def _readable_size(size: int) -> str:
    for unit, step in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if size >= step:
            return f"{size / step:.1f} {unit}"
    return f"{size} bytes"


def _clean_folder_text(text: str) -> str:
    """File Explorer's "Copy as path" puts quotes round the path - drop them."""
    return (text or "").strip().strip('"').strip("'").strip()


@st.cache_data(ttl=60, show_spinner="Looking through the folder...")
def folder_summary(folder: str) -> dict:
    return indexer.scan_folder(folder)


def render_finished_message(job: dict) -> None:
    """What the last "Process the files" run did."""
    if job.get("error"):
        st.error(f"Processing stopped: {job['error']}")
        return
    summary = job.get("summary") or {}

    # The check that runs when the app opens should not announce itself when
    # there was nothing to do - which is most of the time.
    nothing_changed = not any(summary.get(count) for count in
                              ("processed", "failed", "removed_missing"))
    if job.get("automatic") and nothing_changed:
        st.caption(
            f"Checked for new files when the app opened - nothing new. "
            f"{summary.get('skipped_unchanged', 0)} files already up to date."
        )
        return

    message = (
        f"Finished. {summary.get('processed', 0)} files newly processed, "
        f"{summary.get('skipped_unchanged', 0)} already up to date, "
        f"{summary.get('failed', 0)} failed, "
        f"{summary.get('skipped_unsupported', 0)} skipped."
    )
    if summary.get("videos_indexed"):
        message += f" {summary['videos_indexed']} video(s) added."
    if summary.get("removed_missing"):
        message += (f" Removed {summary['removed_missing']} file(s) that are no "
                    f"longer in the folder.")
    if job.get("replaced"):
        message = "Your library was replaced. " + message
    st.success(message)


@st.fragment(run_every=2)
def render_progress() -> None:
    """The live progress display, redrawn every two seconds."""
    job = processing.status()
    if not job["running"]:
        # Finished or paused - redraw the whole page so the counts catch up.
        st.rerun()

    done, total = job["done"], job["total"]
    # Work goes in batches of about five minutes. The batch number only means
    # anything once there has been more than one.
    batch = f"Batch {job['batch']} · " if job.get("batch", 0) > 1 else ""

    if job["phase"] == "clearing":
        st.info("Removing the previous library from search...")
    elif job["phase"] == "resting":
        st.progress(done / total if total else 0.0,
                    text=f"{batch}{done} of {total} files done - short break "
                         f"before the next batch")
    elif job["phase"] == "videos" and total:
        st.progress(done / total,
                    text=f"All files done. Video captions: {done} of {total} "
                         f"videos done, {total - done} remaining")
    elif total:
        looking = "Checking for new files - " if job.get("automatic") else ""
        st.progress(done / total,
                    text=f"{looking}{batch}{done} of {total} files done, "
                         f"{total - done} remaining")
    else:
        st.info("Getting ready - looking through the folder...")

    if job["current"] and job["phase"] != "resting":
        st.caption(f"Now reading: {job['current']}")

    if job["pause_requested"]:
        st.caption("Pausing - finishing the file being read first...")
    elif st.button("Pause", key="pause_processing"):
        processing.request_pause()
        st.rerun()

    st.caption(
        "This carries on in the background. You can refresh this page, search, "
        "or close the browser tab. Closing the app stops it - and nothing is "
        "lost, because finished files are saved as they go."
    )


def render_process_files_panel(files: dict, last_run) -> None:
    """The folder box, its summary, the replace warning and the button."""
    st.subheader("Your content folder")
    job = processing.status()

    if job["running"]:
        st.markdown(f"Processing `{job['folder']}`")
        render_progress()
        return

    if job["finished_at"]:
        if st.session_state.get("seen_processing_run") != job["run_number"]:
            # Let searches see everything that was just added or removed.
            load_collection.clear()
            st.session_state["seen_processing_run"] = job["run_number"]
        if job.get("paused"):
            st.info(
                f"**Paused.** {job['done']} of {job['total']} files done. The "
                f"file being read was finished and saved first, so nothing was "
                f"left half-read. Everything done so far is searchable."
            )
            if st.button("Continue processing", type="primary"):
                processing.start(Path(job["folder"]), replace=False)
                st.rerun()
        else:
            render_finished_message(job)

    current = config.ASSETS_FOLDER
    typed = st.text_input(
        "Paste the path of the folder that holds your decks, PDFs and images",
        value=str(current),
        help="In File Explorer, open the folder, click the address bar at the "
             "top, copy the path and paste it here.",
    )
    folder_text = _clean_folder_text(typed)
    if not folder_text:
        return
    folder = Path(folder_text)
    if not folder.is_dir():
        if not files and indexer.same_folder(folder, current):
            # First visit on a new computer: the box still holds the starting
            # value, which may not exist here. Ask for the folder rather than
            # greet someone with an error they did not cause.
            st.info(
                "**Start here:** paste the path of the folder that holds your "
                "decks, PDFs and images into the box above, then press Enter."
            )
        else:
            st.error(
                "That folder could not be found. Check the path - it should "
                "look like C:\\Users\\you\\OneDrive\\Content - and paste it again."
            )
        return
    folder = folder.resolve()

    found = folder_summary(str(folder))
    st.markdown(
        f"**{found['files']:,} files, {_readable_size(found['bytes'])} found** "
        f"- {found['readable']:,} of them are decks, PDFs or images the app "
        f"can read."
    )
    if not found["readable"]:
        st.warning("There are no decks, PDFs or images in this folder, so there "
                   "is nothing to process.")
        return

    replacing = bool(files) and not indexer.same_folder(folder, current)
    if replacing:
        videos = sum(1 for r in files.values() if r.get("type") == "youtube")
        documents = len(files) - videos
        what = f"{documents} files" + (f" and {videos} videos" if videos else "")
        st.warning(
            f"**This replaces your current library.** Everything searchable "
            f"now - {what} from `{current}` - will be removed from search, and "
            f"the new folder will be read from scratch. Your actual files are "
            f"not changed or deleted."
        )

    # Replacing asks once more before anything happens: the button opens a
    # confirmation, and only "Yes, replace my library" starts the work. The
    # confirmation belongs to this exact folder - paste a different one and
    # it disappears.
    asking = st.session_state.get("confirm_replace_folder") == str(folder)

    left, middle, right = st.columns([1, 1, 2], vertical_alignment="center")
    with left:
        clicked = st.button("Process the files", type="primary",
                            disabled=asking)
    with middle:
        # A manual version of what already happens when the app opens. Files
        # only - it never goes to YouTube, so it is quick and works offline.
        check_now = st.button("Check for new files",
                              disabled=asking or replacing)
    with right:
        if last_run and not replacing:
            st.caption(f"Last processed: {last_run.replace('T', ' at ')}")

    st.caption(
        "**Process the files** reads anything new or changed, removes anything "
        "deleted, and also fetches your YouTube captions. **Check for new files** "
        "does the same for the folder only, leaving YouTube alone. New files are "
        "picked up on their own each time you open the app."
    )

    if check_now:
        processing.start(folder, replace=False, include_videos=False)
        st.rerun()

    if clicked:
        if replacing:
            st.session_state["confirm_replace_folder"] = str(folder)
        else:
            processing.start(folder, replace=False)
        st.rerun()

    if replacing and asking:
        with st.container(border=True):
            st.markdown(
                f"**Replace your current library with `{folder}`?**  \n"
                f"Everything searchable now will be removed from search. Your "
                f"actual files are not changed or deleted."
            )
            yes, no, _ = st.columns([2, 1, 3])
            with yes:
                confirmed = st.button("Yes, replace my library", type="primary")
            with no:
                cancelled = st.button("Cancel")
        if confirmed or cancelled:
            st.session_state.pop("confirm_replace_folder", None)
            if confirmed:
                processing.start(folder, replace=True)
            st.rerun()


def render_background_note() -> None:
    """A line on the Search tab while files are being processed."""
    job = processing.status()
    if not job["running"]:
        return
    if job["phase"] == "files" and job["total"]:
        st.info(f"Files are being processed in the background: {job['done']} of "
                f"{job['total']} done. Search already includes the finished ones.")
    else:
        st.info("Files are being processed in the background. Search already "
                "includes the finished ones.")


# ---------------------------------------------------------------------------
# Settings - the gear panel next to the title
#
# Two choices, kept for as long as the browser tab stays open. Nothing here
# calls any online service: opening a file happens on this computer, and a
# download is sent straight from the file already on disk.
# ---------------------------------------------------------------------------

SETTING_NOTHING_MATCHES = "setting_nothing_matches"
SHOW_NOTHING = "Show nothing"
SHOW_CLOSEST = f"Show closest {config.CLOSEST_FEW}"

SETTING_CLICK = "setting_click_action"
OPEN_DIRECTLY = "Open the file directly (works when running on my own machine)"
DOWNLOAD = "Download the file (works when hosted online)"


def _default_click_choice() -> str:
    """The app runs on your own computer, so opening files directly works."""
    return OPEN_DIRECTLY


def render_settings_panel() -> None:
    """The gear button, and the small panel it opens."""
    with st.popover("⚙️", help="Settings"):
        st.markdown("**Settings**")
        st.radio("When nothing matches", [SHOW_NOTHING, SHOW_CLOSEST],
                 index=0, key=SETTING_NOTHING_MATCHES)
        click_options = [OPEN_DIRECTLY, DOWNLOAD]
        st.radio("When I click a result", click_options,
                 index=click_options.index(_default_click_choice()),
                 key=SETTING_CLICK)
        st.caption("Kept until you close or refresh this browser tab.")


def _safe_file_to_hand_out(path) -> bool:
    """
    Only ever open or download files that are genuinely part of the library:
    inside the assets folder, and one of the content types the app indexes.
    The paths come from the index, and this makes sure a result can never
    point the app at anything else on the computer.
    """
    try:
        path.resolve().relative_to(config.ASSETS_FOLDER.resolve())
    except ValueError:
        return False
    return path.suffix.lower() in config.SUPPORTED_EXTENSIONS


def _open_on_this_computer(path) -> tuple[bool, str]:
    """Open a file in its usual app - PowerPoint, a PDF reader, an image viewer."""
    import os
    import subprocess
    import sys

    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True, f"Opened {path.name}"
    except Exception as error:
        return False, f"Could not open {path.name}: {error}"


def render_file_action(result: dict) -> None:
    """The Open or Download button on a file result, as chosen in Settings."""
    import mimetypes

    path = search_module.local_file(result)
    if path is None or not _safe_file_to_hand_out(path):
        st.caption("This file is not available here, so it cannot be opened "
                   "or downloaded.")
        return

    key = f"file_action_{result.get('rank')}_{result['path']}"
    choice = st.session_state.get(SETTING_CLICK, _default_click_choice())

    if choice == DOWNLOAD:
        st.download_button(
            "Download file",
            # A function rather than the file's contents: the file is only read
            # when the button is actually clicked. Reading every result's file
            # up front would be slow - one sample deck is over 150 MB.
            data=lambda p=path: p.read_bytes(),
            file_name=path.name,
            mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            key=key,
            on_click="ignore",
            icon=":material/download:",
        )
    else:
        if st.button("Open file", key=key, icon=":material/open_in_new:"):
            opened, message = _open_on_this_computer(path)
            if opened:
                st.toast(message)
            else:
                st.warning(message)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

title_area, settings_area = st.columns([14, 1], vertical_alignment="center")
with title_area:
    st.title("🔎 Asset Finder")
with settings_area:
    with st.container(key="settings_gear"):
        render_settings_panel()
st.caption("Search your decks, PDFs and images by meaning - not by filename.")

tab_search, tab_log = st.tabs(["Search", "Processing log"])

with tab_search:
    render_background_note()
    st.header("Search")

    # What the search box should contain, and a counter used to force a fresh
    # box when a chip is clicked (see below).
    st.session_state.setdefault("box_value", "")
    st.session_state.setdefault("box_version", 0)

    # If a recent-search chip was clicked on the previous run, apply it now -
    # before the search box is drawn.
    clicked_chip = st.session_state.pop("pending_chip", None)
    if clicked_chip:
        st.session_state["box_value"] = clicked_chip
        st.session_state["last_query"] = clicked_chip
        # Streamlit keeps whatever you typed in a form box, even when the
        # value behind it changes. Bumping the version gives the box a new
        # key, so it is rebuilt from scratch showing the chip's text.
        st.session_state["box_version"] += 1

    # Reserve the spot above the search box for the recent-search chips. They
    # are drawn later, once we know what the current search is, but they
    # appear here on the page.
    chip_area = st.container()

    # A form means pressing Enter in the box runs the search, not just the
    # button.
    with st.form("search_form"):
        query = st.text_input(
            "What are you looking for?",
            value=st.session_state["box_value"],
            key=f"search_box_{st.session_state['box_version']}",
            placeholder="e.g. star schema, or how to build a resume",
        )
        submitted = st.form_submit_button("Search", type="primary")

    if submitted:
        # Remember the query so results survive Streamlit's reruns.
        st.session_state["last_query"] = query
        st.session_state["box_value"] = query

    current_query = st.session_state.get("last_query", "")

    if current_query:
        remember_search(current_query)

    # Now draw the chips into the space reserved above the box.
    with chip_area:
        render_recent_chips()

    if current_query:
        collection = load_collection()

        if collection.count() == 0:
            # Most often a brand-new setup where nothing has been read yet. Say
            # what to click - never a command to type.
            if processing.status()["running"]:
                st.info(
                    "Your files are being processed right now. Search works as "
                    "soon as the first ones are finished - try again in a minute."
                )
            else:
                st.warning(
                    "Nothing has been processed yet, so there is nothing to "
                    "search. Open the **Processing log** page, paste the path of "
                    "the folder that holds your files, and press **Process the "
                    "files**."
                )
        else:
            # Checked before loading the model, because a large embedding model
            # takes a while to load and there is no point if it cannot be used.
            try:
                indexer.check_index_matches_model()
            except indexer.IndexModelMismatch as problem:
                st.error(str(problem))
                st.stop()

            model = load_model()
            with st.spinner("Searching..."):
                results = search_module.search(
                    current_query, collection=collection, model=model
                )

            # Did anything clear the quality bar? What happens when nothing does
            # is a choice in Settings: say so and stop, or show the closest few.
            weak_search = bool(results) and not search_module.has_strong_match(results)
            show_closest = (st.session_state.get(SETTING_NOTHING_MATCHES, SHOW_NOTHING)
                            == SHOW_CLOSEST)
            if weak_search and show_closest:
                # The closest few, as chosen in Settings - but only ones that
                # are genuinely near the search. Anything far below any
                # reasonable relevance is left out, so this can show fewer than
                # asked for, or nothing at all.
                results = [r for r in results
                           if r["similarity"] >= config.CLOSEST_THRESHOLD]
                results = results[: config.CLOSEST_FEW]
            elif not weak_search:
                # Only genuine matches are shown. A result below the bar is not
                # a match, so it never appears alongside one that is - even if
                # that leaves a single result.
                results = [r for r in results
                           if r["confidence"].startswith("Strong")]

            if weak_search and not show_closest:
                # Nothing to show - and so no AI call to explain results that
                # nobody is going to see.
                show_nothing_matched(current_query)
            elif not results:
                # Nothing close enough to show, even as "closest".
                show_nothing_matched(current_query, closest_chosen=show_closest)
            else:
                with st.spinner("Working out why these matched..."):
                    reasons, reason_error = get_reasons(
                        current_query, results, weak=weak_search)

                # Attach the reason, where it came from and the AI's verdict to
                # each result, so the cards carry everything they need.
                for position, result in enumerate(results, start=1):
                    entry = (tuple(reasons[position - 1]) if position <= len(reasons)
                             else ())
                    entry = (entry + (None, None, None))[:3]
                    result["reason"], result["reason_source"], result["related"] = entry

                # A second check, for matches and "closest" alike. The AI has
                # read each result against the search: one it judges unrelated -
                # or whose own sentence says so - is never shown, whatever its
                # score.
                results = [r for r in results if not judged_unrelated(r)]

                for position, result in enumerate(results, start=1):
                    result["rank"] = position

                if not results:
                    show_nothing_matched(current_query, closest_chosen=show_closest)
                else:
                    if weak_search:
                        # Nothing was a confident match. Say so plainly, then
                        # show the closest anyway, as chosen in Settings.
                        st.warning(
                            f"**Nothing matched exactly — "
                            + ("here is the closest.**  \n" if len(results) == 1
                               else f"here are the {len(results)} closest.**  \n")
                            + f"These are the nearest things in your library to "
                            f"\"{current_query}\". They may not be what you want."
                        )
                    else:
                        count = len(results)
                        st.caption(
                            f"{count} {'match' if count == 1 else 'matches'} "
                            f"for \"{current_query}\", closest first"
                        )

                    if not llm.is_configured():
                        st.caption(
                            "No AI key set up, so the reasons below are simple "
                            "word-overlap explanations. Add LLM_API_KEY to your "
                            ".env for AI-written ones."
                        )
                    elif reason_error:
                        # The AI call failed - say so rather than pretending.
                        st.warning(f"Showing simple reasons: {reason_error}.")

                    # One ranked list, best first, whatever was typed. However
                    # many words the search has, every one of them is
                    # highlighted in the results below.
                    for result in results:
                        render_result_card(result, current_query, weak=weak_search)

with tab_log:
    st.header("Processing log")
    st.caption(
        "What the app has read, what it skipped, and anything that went wrong. "
        "Use this to check whether a file you just added has been picked up."
    )

    status = indexer.load_status()
    files = status.get("files", {})

    # ----- Choosing the content folder and processing it ----------------
    render_process_files_panel(files, status.get("last_run"))

    if not files and processing.status()["running"]:
        st.caption("Files appear here as they are processed.")
    elif not files:
        st.info(
            "Nothing has been processed yet. Paste the path of your content "
            "folder above and press **Process the files**."
        )
    else:
        # ----- Summary counts -------------------------------------------
        counts = {"processed": 0, "in_progress": 0, "failed": 0, "skipped": 0}
        for record in files.values():
            if record["status"] in counts:
                counts[record["status"]] += 1

        total_chunks = sum(r.get("chunks", 0) for r in files.values())

        st.subheader("Summary")
        boxes = st.columns(5)
        boxes[0].metric("Files seen", len(files))
        boxes[1].metric("Processed", counts["processed"])
        boxes[2].metric("In progress", counts["in_progress"])
        boxes[3].metric("Failed", counts["failed"])
        boxes[4].metric("Skipped", counts["skipped"])
        st.caption(
            f"{total_chunks} searchable pieces indexed in total.  ·  "
            f"**Failed** means something is wrong with the file. "
            f"**Skipped** means a file type this app does not handle - "
            f"nothing is broken."
        )

        # ----- The full table -------------------------------------------
        st.subheader("All content")
        st.caption("Most recently processed first.")

        # Friendly words instead of the internal status names.
        status_words = {
            "processed": "✅ Processed",
            "in_progress": "⏳ In progress",
            "failed": "❌ Failed",
            "skipped": "⚪ Skipped",
        }
        unit_words = {"deck": "slides", "pdf": "pages", "image": "description"}

        # Newest first: the file you added a minute ago should be at the top,
        # which is what this screen is mostly used to check. Anything never
        # actually read (skipped types) has no time, so it sits at the bottom
        # in name order rather than jumping to the top.
        def newest_first(record):
            return (record.get("indexed_time") or "", record["file_name"].lower())

        ordered = sorted(files.values(), key=newest_first, reverse=True)

        rows = []
        for record in ordered:
            rows.append({
                "File": record["file_name"],
                "Type": search_module.type_label(record["type"]),
                "Status": status_words.get(record["status"], record["status"]),
                "Indexed": (
                    f"{record.get('chunks', 0)} "
                    f"{unit_words.get(record['type'], 'pieces')}"
                    if record.get("chunks") else "-"
                ),
                "Processed at": (record.get("indexed_time") or "-").replace("T", " "),
                "Note / reason": record.get("reason") or "",
            })

        render_table(rows)

        # ----- Failures: things that are actually wrong ------------------
        failed = [r for r in files.values() if r["status"] == "failed"]
        st.subheader(f"Failed files ({len(failed)})")
        if not failed:
            st.success("No failures. Every supported file was read successfully.")
        else:
            st.caption("Something went wrong reading these. They are worth a look.")
            for record in failed:
                st.error(f"**{record['file_name']}** — {record['reason']}")

        # ----- Skipped: deliberate, not a problem ------------------------
        skipped = [r for r in files.values() if r["status"] == "skipped"]
        st.subheader(f"Skipped files ({len(skipped)})")
        if not skipped:
            st.caption("Nothing skipped.")
        else:
            st.caption(
                "Not indexed as searchable documents, on purpose - nothing is "
                "wrong with them. Either the app does not handle that file "
                "type, or the file is used for something else (the link "
                "spreadsheet is read separately, to find your YouTube videos)."
            )
            for record in skipped:
                st.info(f"**{record['file_name']}** — {record['reason']}")

        # ----- Per-day feed ---------------------------------------------
        st.subheader("Processing history")
        st.caption("Newest first. Open a day to see exactly which files were read.")

        by_day = {}
        for record in files.values():
            stamp = record.get("indexed_time")
            if not stamp:
                continue  # never actually read (skipped files have no time)
            day = stamp.split("T")[0]
            by_day.setdefault(day, []).append(record)

        if not by_day:
            st.caption("Nothing has been read yet.")
        else:
            for day in sorted(by_day, key=lambda d: d, reverse=True):
                day_files = sorted(by_day[day], key=lambda r: r["indexed_time"],
                                   reverse=True)
                good = sum(1 for r in day_files if r["status"] == "processed")
                bad = sum(1 for r in day_files if r["status"] == "failed")
                headline = f"{good} files processed on {day}"
                if bad:
                    headline += f"  ({bad} failed)"

                with st.expander(headline):
                    for record in day_files:
                        mark = status_words.get(record["status"], "")
                        when = record["indexed_time"].split("T")[1]
                        line = f"{mark} `{when}`  {record['file_name']}"
                        if record.get("reason"):
                            line += f" — {record['reason']}"
                        st.markdown(line)

# A small footer so you can confirm the config file is being read correctly.
st.divider()
st.caption(f"Content folder: {config.ASSETS_FOLDER}")
if not config.ASSETS_FOLDER.exists():
    st.warning(
        "That folder cannot be found. On the Processing log page, paste the "
        "path of the folder that holds your files."
    )
