# Asset Finder — Setup Guide

A simple, step-by-step guide to running the Asset Finder on your own computer.

You do not need to be a programmer to follow this. Every step is spelled out, and
nothing needs to be typed into a command window except one line if you choose
Ollama. If a step feels unclear, that is a fault of the guide, not you.

Want to see the app before installing? The
[Walkthrough & FAQ (PDF)](Asset_Finder_Walkthrough_and_FAQ.pdf) shows every screen
and answers the common questions.

---

## 1. What this is, and what you will end up with

The Asset Finder lets you search your own content — slide decks, PDFs, Word and Excel files, images and
YouTube videos — by **meaning**, in plain words, instead of by file name.

For example, you can type *"the slide that explains star schema"* and it finds that
exact slide, even if the file is named something unhelpful. It reads inside your
files, including the words printed inside images, screenshots pasted into slides,
Word documents and Excel sheets, and the words spoken in videos.

Three promises:

- **It never changes your files.** It only reads them. It never moves, renames,
  deletes or uploads anything.
- **The AI runs on your own computer.** Your files and your searches are not sent
  to any outside company. The internet is only used to download the app's parts
  during setup, and to fetch YouTube captions if you list videos.
- **Only your computer can open it**, unless you choose to share it on your network
  (Section 10).

When you finish this guide, you will have:

- A search page you open in your web browser.
- All your content searchable by meaning.
- A settings panel where you choose how it behaves.

---

## Who this is for

If any of these sound familiar, Asset Finder is for you:

- You have years of files piled up — decks, PDFs, images, videos — and you *know* something exists, but you cannot find it.
- File names do not tell you what is inside, so you open file after file hoping to get lucky.
- You have given up searching and rebuilt something that already existed.
- Your content is private, and you do not want to upload it to a cloud service just to search it.
- You have a large, growing library and no time to tag or organise it.

Asset Finder reads what is *inside* your files and lets you find any of it by describing it in plain words — privately, on your own computer, without moving or renaming a thing. The more content you have, the more it helps.

---

## 2. What you need before you start

- **A Windows computer.** The double-click files are for Windows.
- **Python** — free, installed once (Section 5 explains).
- **Free disk space:** about 8 GB — roughly 2.5 GB for the app and its search
  model, plus 3–4 GB for an AI model (more for larger models).
- **Your content in one folder**, including sub-folders. It can be a synced
  OneDrive or Google Drive folder, as long as the files are downloaded to the
  computer. You do not reorganise anything. The app reads:
  - **PowerPoint decks (`.pptx`)** — the text on every slide, and the pictures and
    screenshots on them.
  - **PDFs (`.pdf`)** — the text on every page.
  - **Word documents (`.docx`)** — the text, including tables, and any screenshots
    or pictures pasted in. Results point to the heading a match sits under, as
    Word files have no fixed pages.
  - **Excel workbooks (`.xlsx`)** — sheet names and cell text, and any pictures
    placed on a sheet. **Works best for sheets that hold words** (lists, notes,
    trackers); a big table of numbers is found by its sheet name and column
    headings, not by the figures.
  - **Images (`.png`, `.jpg`)** — what the picture shows and any words in it.
  - **YouTube videos** listed in a spreadsheet (Step 7.4).

  **Older `.doc` and `.xls` files are not read** — open them in Word or Excel and
  save them as `.docx` / `.xlsx` first. Anything else (zip files, videos on disk and
  so on) is listed as *Skipped*.
- **About an hour, once**, for setup and the first reading of your files. A very
  large library takes longer the first time; after that, only new files are read.

You will set up two pieces of software:

- **A "model runner"** — the program that runs the AI on your computer. Choose
  **Unsloth** (Section 3) or **Ollama** (Section 4). You only need one.
- **The Asset Finder app itself** (Sections 5 and 6).

**Pick a model to match your computer's memory (RAM).** Bigger models read
pictures and write explanations better, but need more memory:

| Your computer's memory | Suggested model |
|---|---|
| **Basic** (around 16 GB, a normal laptop) | Qwen3-VL, **4B** size |
| **Medium** (around 32 GB) | Qwen3-VL, **8B** size |
| **Powerful** (64 GB or more) | Qwen3-VL, **30B** size |

- "4B", "8B", "30B" is the model's size. Bigger = more accurate, but needs more
  memory and is slower.
- To see your memory on Windows: **Settings → System → About → Installed RAM**.
- When in doubt, pick the smaller one. Something that runs smoothly beats
  something too big that runs slowly or not at all.
- This guide uses the 4B model in its examples. For another size, use that model's
  name exactly as your model runner shows it.

---

## 3. Path A — Setup with Unsloth

*(Using Ollama instead? Skip to Section 4. You only need one of the two.)*

Unsloth Studio is a free program that runs AI models on your own computer.

**Step 3.1 — Install Unsloth**
- Go to <https://unsloth.ai/>, download **Unsloth Studio** for your computer, and
  install it like any normal program.

**Step 3.2 — Download the model, with its vision file**
- Open Unsloth and go to the **Model hub**.
- Turn on the filter **"Only show models that can fit this device"**.
- Download **Qwen3-VL-4B-Instruct** (or the size you picked in Section 2).
- **Important:** download it **together with its vision file (called "mmproj")**.
  Without that file the model can read text but not pictures, and every image
  will fail with *"failed to process mtmd chunk"*.

**Step 3.3 — Check the model works**
- Open a new chat in Unsloth, choose the model at the **top-left**, and send a
  message such as *hello*. If it replies, it is working.

**Step 3.4 — Turn on automatic model loading (important for pictures)**
- In Unsloth, open **Settings → API**, and find the **"Model auto-switch"** area.
- Turn ON both of these:
  - **"Switch model by request"**
  - **"Switch image and video model by request"**
- These let the app load the right model automatically. **Without them, reading
  pictures fails with a "No model loaded" error.** This one step saves a lot of
  confusion later.

**Step 3.5 — Create a token and note the address**
- In Unsloth, still under **Settings → API**, **Create** a token (a kind of
  password). Give it any name, set it to never expire, and copy it — it starts with
  `sk-unsloth-`. Keep it safe; you will paste it in Section 5.
- The address the app uses is shown under **Settings → API → API monitor**, in the
  banner at the top (**Base URL**). It is usually `http://127.0.0.1:8888/v1`.
- The model's exact name is shown in Unsloth's model list — for the 4B model it
  is `Qwen/Qwen3-VL-4B-Instruct-GGUF`.

**Step 3.6 — Keep Unsloth open**
- Unsloth must be open whenever you use the Asset Finder. It is the engine.

Now go to Section 5.

---

## 4. Path B — Setup with Ollama

*(Use this section only if you chose Ollama. If you did Section 3, skip it.)*

Ollama is another free program that runs AI models on your own computer.

**Step 4.1 — Install Ollama**
- Go to <https://ollama.com/>, download Ollama for your computer, and install it.

**Step 4.2 — Download the model**
- Open a command window (press the Windows key, type `cmd`, press Enter), type the
  line below, and press Enter. This is the only command in the whole guide.
  ```
  ollama pull qwen3-vl:4b
  ```
- Wait for it to finish — about 3.3 GB, only once. (For another size, use
  `qwen3-vl:8b` or `qwen3-vl:30b`.)
- Qwen3-VL already reads pictures in Ollama; there is no separate vision file.
- To see the exact name of what you downloaded, type `ollama list`.

**Step 4.3 — Ollama runs in the background**
- Once installed, Ollama normally starts on its own and runs quietly. It must be
  running whenever you use the Asset Finder.

**Step 4.4 — Note the details**
- Address: `http://localhost:11434/v1`
- Model name: `qwen3-vl:4b`
- Token: Ollama does not check it, but the app needs one — use the word `ollama`.

Now go to Section 5.

---

## 5. Install the Asset Finder

**Step 5.1 — Install Python (if you do not have it)**
- Go to <https://www.python.org/downloads/> and download the latest Python.
- On the first screen of the installer, **tick "Add python.exe to PATH"**, then
  click **Install Now**.
- Not sure if you have it? Skip ahead: the setup in Step 5.3 checks, and tells you
  exactly what to do if Python is missing.

**Step 5.2 — Get the app**
- On the Asset Finder's GitHub page, click the green **Code** button →
  **Download ZIP**.
- Unzip it somewhere easy to find, such as your **Documents** folder. (Avoid
  putting the app itself inside a OneDrive folder — syncing can get in the way of
  the setup. Your *content* can live anywhere.)

**Step 5.3 — Double-click `Setup Asset Finder.bat`**

A window opens and walks through five steps, telling you what it is doing:

1. Checks Python and your free disk space.
2. Creates the app's own Python space (a folder called `.venv`).
3. Installs the app's libraries — about 1.6 GB, a few minutes — and downloads the
   **search model**. The search model runs inside the app; you do not download it
   in Unsloth or Ollama.
4. Creates your settings file, `.env`.
5. Opens `.env` in **Notepad**.

Leave the window open while it works. If a step fails, the window says what went
wrong and what to do. Running the setup again is always safe — it carries on from
where it stopped.

**Step 5.4 — Fill in three lines in Notepad**

Near the top of `.env`, under **STEP 1**, set these three lines, then **save
(Ctrl+S) and close Notepad**:

| Line | If you use Unsloth | If you use Ollama |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:8888/v1` *(already filled in)* | `http://localhost:11434/v1` |
| `LLM_MODEL` | `Qwen/Qwen3-VL-4B-Instruct-GGUF` *(already filled in)* | `qwen3-vl:4b` |
| `LLM_API_KEY` | your token, starting `sk-unsloth-` | `ollama` |

- Write each value straight after the `=`, with no spaces and no quotes.
- **Never leave `LLM_API_KEY` empty.** With no token, the app does not use the AI
  at all and gives only simple word-matching explanations.
- Using a different model size? Put its exact name in `LLM_MODEL`.
- Leave everything else in the file as it is.

`.env` holds your token. It stays on your computer and is never shared.

---

## 6. Start the app

- Make sure your model runner (Unsloth or Ollama) is running.
- **Double-click `Start Asset Finder.bat`.**
- A black window opens, and the app opens in your web browser at
  `http://localhost:8501` within about a minute.
- **Keep the black window open while you use the app. Close it to stop the app.**
- The first time, it offers to put a shortcut on your desktop. Press **Y** or **N**;
  it only asks once.
- If the black window says the model runner is not running, the app still opens,
  but explanations are simpler and pictures cannot be read. Open Unsloth or Ollama
  — there is no need to restart the app.

---

## 7. First run — letting the app read your content

Before you can search, the app reads your files once. This is called
"processing". Afterwards, only new or changed files are read.

**Step 7.1 — Point it at your folder**
- In the app, open the **Processing log** page.
- Paste the path of your content folder into the box. To copy the path: open the
  folder in File Explorer, click the address bar at the top, and copy. Press Enter.
- The app shows what it found, for example *"84 files, 2.3 GB found – 60 of them
  are decks, PDFs, Word or Excel files or images the app can read."*

**Step 7.2 — Press "Process the files"**
- A progress bar shows *"12 of 84 files done, 72 remaining"* and which file is
  being read.
- It runs **in the background**: you can refresh the page, search, or close the
  browser tab. Files become searchable as each one finishes.
- It works in **batches of about five minutes** and carries on by itself.
- **Pause** stops after the current file — never half-way through one.
  **Continue processing** picks up again.
- **It is safe to close the app or shut down the computer at any time.** Next
  time, press **Process the files** and everything already done is skipped.

**Step 7.3 — What to expect**
- Reading pictures is the slow part: every image, and every picture inside a
  slide, Word document or Excel sheet, is read by your AI model. A large library can take several hours the
  first time. That is normal, and only happens once.
- The Processing log lists every file with what happened to it. **Skipped** means a
  file type the app does not handle (such as a zip file) — nothing is wrong.
  **Failed** gives the reason in plain words.
- Choosing a **different folder later replaces your library**. The app warns you and
  asks you to confirm. Your actual files are never touched.

**Step 7.4 — YouTube videos (optional)**
- **A sample `public_links.xlsx` is included — download it, replace the example
  with your own video links, and put it in your content folder.** It is in the app
  folder you downloaded, or on the GitHub page: click `public_links.xlsx`, then the
  download button. It already has the right headings and one example row (YouTube's
  first-ever video, which has captions — search *elephants* to try it).
- Put a spreadsheet named exactly **`public_links.xlsx`** anywhere in your content
  folder (capital letters do not matter; it must be an `.xlsx` file).
- Its **first sheet** needs a heading row with three columns, in any order:

  | Title / Description | url | source_type |
  |---|---|---|
  | Star schema explained | https://www.youtube.com/watch?v=… | youtube |

  The headings can also be written as `Title` or `Description`; `link`; and
  `source` or `type`. Extra columns are ignored.
- Rows whose `source_type` is `youtube` are read when you press **Process the
  files**. The app fetches each video's public captions — free, no account.
- Video results link straight to the moment the passage is spoken.
- If the headings are wrong, the Processing log says so, and the rest of your files
  are still processed normally.
- Only public videos with captions can be read. Captions are the spoken words —
  a slide shown on screen but not described aloud is not searchable.

---

## 8. Using it day to day

**Searching**
- Type what you are looking for in plain words — a topic, an idea, or what you
  half-remember — and press **Search**. The first search after starting takes about
  25 seconds while the search model loads; after that it is quick.
- Results come back best first, and **only genuine matches are shown**. Each result
  shows what it is, where it came from (which slide or page), a short note on why
  it matched, and your search words highlighted.
- Images and slides show a preview. Videos have a link that opens at the right
  moment.

**The settings panel (the ⚙️ button next to the title)**
- **When nothing matches:** "Show nothing" (the default), or "Show closest 3" —
  up to three results that are genuinely near your search, clearly labelled as the
  closest. It shows fewer, or none, when nothing is near.
- **When I click a result:** "Open the file directly" (the default — opens the
  actual file), or "Download the file" (a copy — useful when others use the app
  over your network).

**Adding new content**
- Just add files to your content folder. **The app picks up new, changed, deleted
  and renamed files by itself each time you open it.** Or press **Check for new
  files** on the Processing log page at any time.

---

## 9. Changing models later

- **Switching between Unsloth and Ollama, or to another size of Qwen3-VL:** change
  the three lines in `.env` (Section 5.4), then close the black window and start
  the app again. Nothing needs re-reading.
- **Changing the search model** (`EMBEDDING_MODEL` in `.env`) is different: the old
  and new "meaning fingerprints" are not compatible, so the library must be read
  again. The app tells you this if it happens. Most people never need to.

---

## 10. For a team — one computer as the "brain"

If several people need to search the same library, one computer can do all the
work while everyone else searches from their web browser.

- **The "brain" computer** runs the model runner and the app, reads the library
  once, and answers everyone's searches.
- **Everyone else** just opens a web page. Their own computer does no heavy work.
- **Privacy stays inside your network.** Nothing goes to an outside company.

**How to set it up:**
1. On the brain computer, open the app folder, then the `.streamlit` folder, and
   open `config.toml` in Notepad. Delete the line `address = "127.0.0.1"`, save,
   and restart the app. (By default only the computer itself can open the app —
   this line is what keeps it private.)
2. Find the brain computer's network address: **Settings → Network & Internet →
   your connection → Properties**, and look for the **IPv4 address** — it looks
   like `192.168.1.25`.
3. On any other computer on the **same network**, open a browser and go to that
   address followed by `:8501` — for example `http://192.168.1.25:8501`. Windows
   may ask the brain computer to allow the app through its firewall; allow it on
   private networks only.

**Before you do this:**
- **There is no login.** Anyone who can reach that address can search the library
  and download files. Only do this on a network you trust, never on public Wi-Fi.
- People connecting this way should choose **"Download the file"** in ⚙️ Settings —
  "Open the file directly" opens files on the brain computer, not on theirs.
- The brain computer must be switched on, with the model runner and the app
  running, whenever people want to search. A dedicated computer works best.

**Alternative:** each person can install their own copy by following this guide,
choosing a model that suits their own computer. Each copy reads its own folder.

---

## 11. How accurate is it?

The search was tested with 16 real searches on a sample library of decks, PDFs,
images and YouTube videos, running fully on one computer:

- **12 searches with a known right answer:** the correct item was in the top 3
  every time — 12 out of 12.
- **4 searches for things not in the library:** it correctly found nothing every
  time — 4 out of 4.

This was a focused test of the search itself, not a large scientific benchmark.
On your own library, try a handful of searches where you know the right answer.

---

## 12. If something goes wrong

**The black window says the model runner is not running, or the explanations look
very basic.** Open Unsloth or Ollama. Check that `LLM_BASE_URL` in `.env` matches
it, and that `LLM_API_KEY` is not empty.

**"The model '…' was not found."** `LLM_MODEL` must match the name exactly as your
model runner shows it. For Ollama, type `ollama list` in a command window.

**Pictures fail with "the picture model returned an error" or "No model loaded".**
For Unsloth, check two things: (1) both auto-switch settings are ON (Section 3.4),
and (2) the model was downloaded *with* its vision (mmproj) file (Section 3.2).
Otherwise, the model runner may have stopped. Then press **Process the files**
again: only the missing pictures are tried.

**"Python is not installed on this computer."** Install it from python.org with
**"Add python.exe to PATH"** ticked (Section 5.1), then run the setup again.

**The setup stopped with a message.** Do what it says, then double-click
`Setup Asset Finder.bat` again. The full details are in `setup_log.txt` in the app
folder — send that file to whoever helps you.

**A change to `.env` is not taking effect.** Settings are read when the app starts:
close the black window and start the app again.

**My videos are missing.** Check the Processing log for a message about
`public_links.xlsx`, and check its name and headings (Section 7.4).

**It feels slow.** Reading pictures is the slow part, and happens once per file.
Everyday searching is quick. A computer with more memory can use a faster, larger
model.

---

## In short

- Install a model runner (Unsloth or Ollama) and a Qwen3-VL model.
- Double-click **Setup Asset Finder.bat** once, and fill in three lines.
- Double-click **Start Asset Finder.bat**, paste your folder, press **Process the
  files**.
- Search by meaning. New files are picked up by themselves.
- Everything runs on your computer, and your files are only ever read.
