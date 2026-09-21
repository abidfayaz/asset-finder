# Asset Finder

Search your slide decks, PDFs, Word and Excel files, images and YouTube videos
**by meaning** — in plain
words, not by file name — and see *why* each result matched.

Type *"how do I write a data analyst resume"* and it finds the right PDF page, even
if none of those words are in the file name. Type the words printed on a thumbnail
and it finds the thumbnail. Type a topic and it finds the minute of the video
where it is explained.

**It runs entirely on your own computer.** The AI model runs in a model runner you
install yourself (Unsloth or Ollama). Your files are only ever read — never
changed, moved, deleted or uploaded.

---

## What it does

- **Reads inside your files:** the text on every slide of a PowerPoint deck, every
  page of a PDF, every section of a Word document (`.docx`), the cells of every
  sheet in an Excel workbook (`.xlsx`), what an image shows and any words printed
  in it, pictures and screenshots inside slides, Word documents and Excel sheets,
  and the spoken words of YouTube videos.
- **Searches by meaning.** Results come back best first, and **only genuine matches
  are shown**. An AI check removes anything that does not really relate to your
  search.
- **Explains each result** in one plain sentence, highlights your search words, and
  shows a preview: the picture itself, a slide-shaped frame, or the quoted passage.
- **Gets you to the file:** an **Open file** (or **Download file**) button, the file
  location with a copy button, or, for a video, a **Watch on YouTube from 6:52**
  link that jumps to the moment.
- **Reads your library from a button** — no command line. It works in the
  background, in batches, with **Pause** and safe resume, and picks up new, changed,
  deleted and renamed files by itself each time you open the app.

---

## What you need

| | |
|---|---|
| **Windows** | The double-click files are for Windows. Mac and Linux users: see *For developers*. |
| **Python 3.10 or newer** | Free from [python.org](https://www.python.org/downloads/). When installing, tick **"Add python.exe to PATH"**. |
| **About 8 GB of free disk space** | About 2.5 GB for the app and its search model, plus 3–4 GB for an AI model. |
| **A model runner** | **Unsloth Studio** or **Ollama** — installed separately, see below. |

### The model runner and model

The app needs one AI model that reads **pictures as well as text** (a "VL" or
vision model). Install **one** of these yourself — the Asset Finder's setup never
installs them.

| | Unsloth Studio | Ollama |
|---|---|---|
| Get it | [unsloth.ai](https://unsloth.ai/) | [ollama.com](https://ollama.com/) |
| Model | `Qwen/Qwen3-VL-4B-Instruct-GGUF` — download it **together with its vision file (mmproj)** | `qwen3-vl:4b` — download it with `ollama pull qwen3-vl:4b` (3.3 GB) |
| Address | `http://127.0.0.1:8888/v1` | `http://localhost:11434/v1` |
| Token | Create one in Studio: **Settings → API → Create** (starts `sk-unsloth-`) | Not checked — type `ollama` |

A larger model reads pictures and writes explanations better, if your computer
has the memory for it (for example the 8B versions of the same models).

---

## Installing — once

For a longer walkthrough of every step — choosing a model for your computer,
Unsloth or Ollama, and sharing with a team — see the
**[Setup Guide](Asset_Finder_Setup_Guide.md)**.

1. **Download this project** (the green **Code** button → **Download ZIP**) and
   unzip it somewhere easy to find, such as your Documents folder.
2. **Install your model runner and model** (table above). For Unsloth, also create
   the token, and under **Settings → API → Model auto-switch** turn ON both
   **"Switch model by request"** and **"Switch image and video model by
   request"** — without them, reading pictures fails with "No model loaded".
3. **Double-click `Setup Asset Finder.bat`.** A window walks through five steps in
   plain words:
   1. Checks Python and free disk space — and tells you where to get Python if it
      is missing.
   2. Creates the app's own Python space (the `.venv` folder).
   3. Installs the libraries (about 1.6 GB, a few minutes) and downloads the search
      model once.
   4. Creates your settings file, `.env`, from `.env.example`. An existing `.env`
      is never overwritten.
   5. Opens `.env` in Notepad.
4. **In Notepad, set the three lines under STEP 1**, then save and close:

   | Line | Unsloth | Ollama |
   |---|---|---|
   | `LLM_BASE_URL` | `http://127.0.0.1:8888/v1` *(filled in)* | `http://localhost:11434/v1` |
   | `LLM_MODEL` | `Qwen/Qwen3-VL-4B-Instruct-GGUF` *(filled in)* | `qwen3-vl:4b` |
   | `LLM_API_KEY` | your `sk-unsloth-` token | `ollama` |

   **Never leave `LLM_API_KEY` empty** — with no token the app does not use the
   model at all, and falls back to simple word-matching explanations.

If a setup step fails, the window says what went wrong and what to do; the
technical detail goes to `setup_log.txt`. Running setup again is always safe — it
carries on from where it stopped.

---

## Using it

### Starting and stopping

**Double-click `Start Asset Finder.bat`.** The app opens in your browser at
<http://localhost:8501> within about a minute.

- A black window stays open while you use the app. **Close it to stop the app.**
- The first time, it offers a desktop shortcut. It only asks once.
- If your model runner is not running, the window warns you. The app still opens,
  but explanations are simpler and pictures in new files cannot be read — open
  Unsloth or Ollama whenever you like; there is no need to restart the app.

Your model runner must be open while you use the app.

### Reading your library — the Processing log page

1. Open **Processing log** and paste the path of the folder that holds your files
   (in File Explorer, click the address bar and copy it). The app shows what it
   found, for example *"84 files, 2.3 GB found – 60 of them are decks, PDFs, Word
   or Excel files or images the app can read"*.
2. Press **Process the files**. A progress bar shows *"12 of 84 files done, 72
   remaining"* and which file is being read.

- **It runs in the background.** You can refresh the page, search, or close the
  browser tab. Files become searchable as each one finishes.
- **It works in batches of about five minutes**, carrying on by itself until
  everything is done.
- **Pause** stops after the file being read — never half-way through one.
  **Continue processing** carries on.
- **It is safe to close the app or shut down at any moment.** Each file is saved as
  soon as it is read. Next time, press **Process the files** and everything already
  done is skipped.
- **New files are picked up automatically.** Each time you open the app, it checks
  the folder in the background: new or changed files are read, and deleted or
  renamed ones are removed from search. **Check for new files** does the same on
  demand.
- **Choosing a different folder replaces your library.** The app warns you and asks
  you to confirm first. Your actual files are never touched.

Reading pictures is the slow part: each one goes to your model. A large library of
images can take hours the first time; after that only new files are read.

### Searching

Type what you are looking for in plain words and press **Search**. The first search
after starting takes about 25 seconds while the search model loads; after that it
is quick.

The **⚙️** button next to the title has two settings, kept until you close the tab:

| Setting | Choices | Default |
|---|---|---|
| **When nothing matches** | **Show nothing**, or **Show closest 3** — up to three genuinely near results, clearly labelled as the closest, and fewer (or none) when nothing is near | Show nothing |
| **When I click a result** | **Open the file directly**, or **Download the file** | Open directly |

### YouTube videos (optional)

Put a spreadsheet named **`public_links.xlsx`** anywhere in your content folder,
with these three column headings:

| Title / Description | url | source_type |
|---|---|---|
| Star schema explained | https://www.youtube.com/watch?v=… | youtube |

**A sample [`public_links.xlsx`](public_links.xlsx) is included** with the right
headings and one example row — replace the example with your own video links and
put it in your content folder.

Rows marked `youtube` are read when you press **Process the files**. The app
fetches each video's public captions (free, no account), so a search finds the
passage where your topic is spoken, and the link opens the video at that moment.

- **This is the one thing that uses the internet:** captions are fetched from
  YouTube. Opening the app never does.
- Captions are spoken words only — a slide shown on screen but not described aloud
  is not searchable.
- Only public videos with captions can be read; the others are listed in the
  Processing log with the reason.
- If YouTube temporarily refuses requests, processing stops at that video and the
  rest are picked up the next time you press **Process the files**.

---

## Privacy

- **Your files are only read.** Nothing is ever changed, moved, deleted or uploaded.
- **Everything runs on your computer:** reading files, reading pictures, the search,
  and the explanations. The internet is used only to download the libraries and
  search model during setup, and to fetch YouTube captions if you list videos.
- **Only this computer can open the app.** It is not reachable from other computers
  on your network unless you change that on purpose (see *Sharing with a team*).
- **Your token stays in `.env`**, which is excluded from git and never shared.

---

## Sharing with a team

One computer can do the work while everyone else searches from their browser:

1. On that computer, open `.streamlit/config.toml` and delete the line
   `address = "127.0.0.1"`, then restart the app.
2. Find that computer's address on your network (Windows: **Settings → Network &
   Internet → Properties → IPv4 address**, for example `192.168.1.25`).
3. Others open `http://192.168.1.25:8501` in their browser.

**Only do this on a network you trust:** there is no login, so anyone who can reach
the address can search the library and download files. People connecting this way
should choose **Download the file** in ⚙️ Settings — "Open the file directly" opens
files on the computer running the app, not on theirs.

---

## If something goes wrong

**"The AI model runner is not running"**, or the explanations are simple
word-matching ones. Open Unsloth Studio or Ollama, and check that `LLM_BASE_URL`
and `LLM_API_KEY` in `.env` are set (the token must not be empty).

**"The model '…' was not found."** `LLM_MODEL` must match the name exactly as your
model runner shows it. For Ollama, type `ollama list`.

**Pictures fail: "the picture model returned an error" or "No model loaded".** For
Unsloth, check that both auto-switch settings are ON (**Settings → API → Model
auto-switch**), and that the model was downloaded with its vision (mmproj) file.
Otherwise, the model runner may have stopped. Fix it, then press **Process the
files**: pictures already read are kept, and only the missing ones are tried again.

**The app says the index was built with a different model.** You changed
`EMBEDDING_MODEL`. Either change it back, or give `CHROMA_DIR` and `STATUS_FILE`
new folder names in `.env`, restart the app, and press **Process the files**.

**Changes to `.env` are not showing up.** Settings are read when the app starts:
close the black window and start the app again.

**Setup failed.** The window explains why. The full detail is in `setup_log.txt`.

---

## How it works

| Step | Done by | Where |
|---|---|---|
| Reading decks, PDFs, Word and Excel files | `python-pptx`, `pypdf`, `python-docx`, `openpyxl` | your computer |
| Reading images, and pictures inside slides, Word documents and Excel sheets | your vision model | your model runner, on your computer |
| Reading YouTube videos | their public captions (`youtube-transcript-api`) | fetched from YouTube |
| Turning text into searchable "meaning fingerprints" | `mixedbread-ai/mxbai-embed-large-v1` (`sentence-transformers`) | your computer |
| Storing and searching them | ChromaDB | your computer |
| "Why it matched" sentences, and the check that each result is related | your model | your model runner, on your computer |

A result counts as a match if its similarity score reaches `SIMILARITY_THRESHOLD`
(0.68), or if every word you typed appears in it. Under **Show closest 3**, a result
must still reach `CLOSEST_THRESHOLD` (0.60). These values were measured for the
mxbai search model: unrelated searches scored at most about 0.59, genuine near
misses from about 0.62. Every setting is explained in `.env.example`.

---

## Known limits

- **Deck previews show the slide's text**, not a picture of the slide — rendering
  real slides needs PowerPoint or LibreOffice.
- **Word results point at a heading, not a page.** Word files do not store pages,
  so a document is split by heading into pieces of about 200 words — results show
  e.g. *Section: Refund policy*, or *Part 3* in a document without headings.
- **Excel works best for sheets that hold words.** A big table of numbers is found
  by its sheet name and column headings, not by the figures. Formulas are read as
  their last saved value, and very large sheets are capped at 200 pieces each.
- **Some pictures in Word and Excel cannot be read:** drawings, SmartArt and some
  charts stored as drawing instructions (EMF/WMF), and pictures placed *inside* a
  cell with Excel's "Place in Cell". They are skipped, and the Processing log says so
  for drawings.
- **Older `.doc` and `.xls` files are not read** — only `.docx` and `.xlsx`.
  `public_links.xlsx` is always treated as the YouTube list, never as content.
- **Very long slides or pages are only partly represented** — the search model
  reads about the first 500 word-pieces of each.
- **Changes are detected by a file's modified time.** A program that rewrites a
  file without changing that time would go unnoticed.
- **YouTube links open at the start of the matching excerpt**, which can be up to
  a minute before the exact sentence.
- **No login, and one library at a time.** Choosing a new folder replaces the old
  library.
- **The search thresholds are tuned for the mxbai search model.** A different
  `EMBEDDING_MODEL` scores differently and would need new values.

---

## For developers

Set it up by hand (use `./.venv/bin/python` on Mac or Linux):

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, set the three STEP 1 lines, then run:

```bash
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This also reloads `app.py` automatically after edits (the launcher does not).

Command-line tools, all optional — the app's buttons do the same:

```bash
.\.venv\Scripts\python.exe indexer.py
.\.venv\Scripts\python.exe indexer.py --videos-only --limit 5
.\.venv\Scripts\python.exe indexer.py --pictures-only --limit 5
```

| File | What it is |
|---|---|
| `app.py` | The app: search page, Processing log, settings |
| `indexer.py` | Reads files and builds the index |
| `documents.py` | Reads Word and Excel files, and the pictures inside them |
| `processing.py` | Runs processing in the background, in batches |
| `search.py` | Searching, scoring and highlighting |
| `llm.py` | "Why it matched" sentences and the related check |
| `vision.py` | Reading images and pictures |
| `transcripts.py`, `links.py` | YouTube captions and the links spreadsheet |
| `config.py` | Reads the settings from `.env` |
| `launcher.py`, `Start Asset Finder.bat` | The double-click launcher |
| `setup_asset_finder.py`, `Setup Asset Finder.bat` | The one-time setup |

---

## Licence

MIT — free to use, change and share, including commercially. See [LICENSE](LICENSE).

The AI models you download (in Unsloth or Ollama) and the search model come with
their own licences, set by their authors.
