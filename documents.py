"""
Reading Word documents (.docx) and Excel workbooks (.xlsx).

Both are really zip folders of XML files, with any pasted pictures stored
inside as ordinary image files. This file pulls out two things from each:

  - the text, cut into small searchable pieces, and
  - the pictures, so the indexer can send them to the same vision model that
    reads slide pictures and standalone images.

It only ever READS the file. Nothing here talks to any service - the pictures
are handed back to the indexer, which decides what to send.

Why pieces and not pages: a Word file does not store pages. Word works out
where pages break when it shows the document, and the answer changes with the
font, the printer and the window size. Headings, on the other hand, are part
of the file - so a Word document is split by heading, and long sections are
cut into pieces of about 200 words. An Excel workbook is split by sheet.
"""

import datetime
import hashlib
import io
import posixpath
import zipfile

from lxml import etree

# Roughly how many words go into one searchable piece. The search model only
# reads the start of a long piece, so smaller pieces are found more reliably.
WORDS_PER_PIECE = 200

# A huge sheet of numbers would otherwise become thousands of pieces that
# search can do little with. Past this many pieces, the rest of the sheet is
# left out and the processing log says so.
MAX_PIECES_PER_SHEET = 200

# Picture formats the vision step can open. Word also stores drawings, SmartArt
# and some pasted charts as EMF/WMF - drawing instructions rather than a
# picture - which cannot be read, so those are skipped.
READABLE_PICTURE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif",
                          ".tiff", ".webp"}

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _xpath(element, expression: str) -> list:
    """Run an XPath search with the namespaces above, on any XML element."""
    return etree._Element.xpath(element, expression, namespaces=NS)


def _picture_check(blob: bytes, name: str, min_side: int) -> str:
    """
    Is this picture worth reading? Returns "ok", "small" (an icon or divider,
    skipped like tiny slide pictures) or "format" (a type that cannot be read).
    """
    extension = posixpath.splitext(name)[1].lower()
    if extension not in READABLE_PICTURE_TYPES:
        return "format"
    try:
        from PIL import Image
        with Image.open(io.BytesIO(blob)) as image:
            width, height = image.size
    except Exception:
        return "format"
    if width < min_side or height < min_side:
        return "small"
    return "ok"


class _PieceMaker:
    """
    Collects lines of text and cuts them into pieces of about WORDS_PER_PIECE
    words. Every piece starts with a heading line (a section title or a sheet
    name) so each piece still makes sense when found on its own.
    """

    def __init__(self):
        self.pieces = []        # finished pieces: (heading, text)
        self._lines = []
        self._words = 0
        self._heading = ""

    def next_number(self) -> int:
        """The number the piece being built will get when it is finished."""
        return len(self.pieces) + 1

    def new_heading(self, heading: str) -> None:
        self.finish()
        self._heading = heading

    def add(self, line: str) -> None:
        words = line.split()
        if not words:
            return
        # A single paragraph longer than a whole piece is cut up on its own.
        while len(words) > WORDS_PER_PIECE:
            self.finish()
            self._lines = [" ".join(words[:WORDS_PER_PIECE])]
            self._words = WORDS_PER_PIECE
            self.finish()
            words = words[WORDS_PER_PIECE:]
        if self._words + len(words) > WORDS_PER_PIECE:
            self.finish()
        self._lines.append(" ".join(words))
        self._words += len(words)

    def finish(self) -> None:
        if self._lines:
            body = "\n".join(self._lines)
            text = f"{self._heading}\n{body}" if self._heading else body
            self.pieces.append((self._heading, text))
        self._lines = []
        self._words = 0


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------

def _is_heading(paragraph) -> bool:
    try:
        name = (paragraph.style.name or "").lower()
    except Exception:
        return False
    return name.startswith("heading") or name == "title"


def extract_docx(path, min_picture_side: int) -> tuple[list, list, list]:
    """
    Read a Word document.

    Returns (chunks, pictures, notes):
      chunks   - [{"number": 3, "text": "...", "label": "Refund policy"}, ...]
                 "number" counts the pieces from the top of the document;
                 "label" is the heading the piece sits under, if any.
      pictures - [{"number": 3, "blob": b"...", "sha1": "...", "label": ...,
                   "id_part": "3-picture1", "where": "..."}, ...]
                 each tied to the piece of text it sits beside.
      notes    - plain sentences for the processing log, e.g. pictures that
                 could not be read.

    Only the main body is read. Headers and footers are left out: they repeat
    on every page and usually hold a logo or a page number.
    """
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    maker = _PieceMaker()
    found = []          # (piece number, heading, relationship id)

    for element in document.element.body.iterchildren():
        tag = etree.QName(element).localname

        if tag == "p":
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()
            if text and _is_heading(paragraph):
                maker.new_heading(text)
            else:
                maker.add(text)
        elif tag == "tbl":
            # Tables row by row, cells separated by " | ". A merged cell is
            # reported once per row it spans, so repeats side by side are
            # dropped.
            for row in Table(element, document).rows:
                cells = []
                for cell in row.cells:
                    value = cell.text.strip()
                    if value and (not cells or cells[-1] != value):
                        cells.append(value)
                maker.add(" | ".join(cells))
        elif tag == "sectPr":
            continue
        else:
            # Content controls and other wrappers: just their words.
            maker.add(" ".join(t.strip() for t in _xpath(element, ".//w:t/text()")))

        # Pictures sitting in this paragraph or table, in order. Modern Word
        # uses a:blip; very old documents use v:imagedata.
        for rel_id in _xpath(element, ".//a:blip/@r:embed | .//v:imagedata/@r:id"):
            found.append((maker.next_number(), maker._heading, rel_id))

    maker.finish()

    chunks = [
        {"number": number, "text": text, "label": heading}
        for number, (heading, text) in enumerate(maker.pieces, start=1)
    ]

    pictures, notes = _collect_docx_pictures(document, found, min_picture_side)
    return chunks, pictures, notes


def _collect_docx_pictures(document, found, min_side) -> tuple[list, list]:
    pictures = []
    seen = set()
    unreadable = 0
    per_piece = {}

    for number, heading, rel_id in found:
        part = document.part.related_parts.get(rel_id)
        blob = getattr(part, "blob", None)
        if not blob:
            continue            # a linked picture, not stored in the file
        sha1 = hashlib.sha1(blob).hexdigest()
        if sha1 in seen:
            continue            # the same picture pasted twice
        seen.add(sha1)

        check = _picture_check(blob, str(part.partname), min_side)
        if check == "format":
            unreadable += 1
            continue
        if check == "small":
            continue

        per_piece[number] = per_piece.get(number, 0) + 1
        pictures.append({
            "number": number,
            "blob": blob,
            "sha1": sha1,
            "label": heading,
            "id_part": f"{number}-picture{per_piece[number]}",
            "where": f"under '{heading}'" if heading else f"in part {number}",
        })

    notes = []
    if unreadable:
        notes.append(f"{unreadable} drawing(s) or chart(s) are stored in a format "
                     f"the picture reader cannot open, so were skipped")
    return pictures, notes


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _cell_text(value) -> str:
    """A cell's value as short, readable text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(round(value, 4))
    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ", timespec="minutes")
    return str(value).strip()


def extract_xlsx(path, min_picture_side: int) -> tuple[list, list, list]:
    """
    Read an Excel workbook, one sheet at a time.

    Returns (chunks, pictures, notes) in the same shape as extract_docx. The
    "label" is the sheet name, and "number" is the sheet's position.

    Every piece starts with the sheet name and the sheet's first row (usually
    the column headings), so a piece from row 900 still says what its columns
    mean.

    Formulas are read as the value Excel last saved for them. This works best
    for sheets that hold words; a big table of numbers is found by its sheet
    name and headings, not by the figures in it.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    chunks = []
    notes = []
    try:
        for sheet_number, name in enumerate(workbook.sheetnames, start=1):
            sheet = workbook[name]
            if not hasattr(sheet, "iter_rows"):
                continue            # a chart sheet: no cells to read

            header = None
            maker = _PieceMaker()
            maker.new_heading(f"Sheet: {name}")
            cut_short = False

            for row in sheet.iter_rows(values_only=True):
                cells = [_cell_text(v) for v in row]
                line = " | ".join(c for c in cells if c)
                if not line:
                    continue
                if header is None:
                    header = line
                    maker.new_heading(f"Sheet: {name}\n{header}")
                    continue
                maker.add(line)
                if len(maker.pieces) >= MAX_PIECES_PER_SHEET:
                    cut_short = True
                    break

            maker.finish()
            if not maker.pieces and header:
                # Only one row of text - still worth finding.
                maker.pieces.append(("", f"Sheet: {name}\n{header}"))

            for piece, (_heading, text) in enumerate(maker.pieces, start=1):
                chunks.append({
                    "number": sheet_number,
                    "text": text,
                    "label": name,
                    "id_part": f"sheet{sheet_number}-{piece}",
                })
            if cut_short:
                notes.append(f"sheet '{name}' is very large - only its first "
                             f"{MAX_PIECES_PER_SHEET} pieces were made searchable")
    finally:
        workbook.close()

    pictures, picture_notes = _collect_xlsx_pictures(path, min_picture_side)
    return chunks, pictures, notes + picture_notes


def _relationships(archive: zipfile.ZipFile, part: str) -> list[tuple[str, str]]:
    """
    The (type, full path) links from one part of an Office file to others -
    e.g. from a sheet to its drawing, or from a drawing to its pictures.
    """
    folder, file_name = posixpath.split(part)
    rels_path = posixpath.join(folder, "_rels", file_name + ".rels")
    try:
        root = etree.fromstring(archive.read(rels_path))
    except KeyError:
        return []
    links = []
    for rel in _xpath(root, "rel:Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        target = rel.get("Target", "")
        if target.startswith("/"):
            full = target.lstrip("/")
        else:
            full = posixpath.normpath(posixpath.join(folder, target))
        links.append((rel.get("Type", ""), full))
    return links


def _collect_xlsx_pictures(path, min_side) -> tuple[list, list]:
    """
    Pictures placed on each sheet. They are stored in the file's drawings,
    which are linked from each sheet - so each picture can be tied to the
    sheet it sits on.

    TODO: pictures placed INSIDE a cell with Excel's newer "Place in Cell"
    option are stored differently and are not picked up yet.
    """
    pictures = []
    seen = set()
    unreadable = 0

    try:
        with zipfile.ZipFile(str(path)) as archive:
            workbook = etree.fromstring(archive.read("xl/workbook.xml"))
            rel_paths = {
                rel.get("Id"): full
                for rel, full in _workbook_rel_ids(archive)
            }

            sheets = _xpath(workbook, "x:sheets/x:sheet")
            for sheet_number, sheet in enumerate(sheets, start=1):
                name = sheet.get("name", "")
                sheet_part = rel_paths.get(sheet.get(f"{{{NS['r']}}}id"))
                if not sheet_part:
                    continue
                count = 0
                for rel_type, drawing in _relationships(archive, sheet_part):
                    if not rel_type.endswith("/drawing"):
                        continue
                    for image_type, image in _relationships(archive, drawing):
                        if not image_type.endswith("/image"):
                            continue
                        try:
                            blob = archive.read(image)
                        except KeyError:
                            continue
                        sha1 = hashlib.sha1(blob).hexdigest()
                        if sha1 in seen:
                            continue
                        seen.add(sha1)
                        check = _picture_check(blob, image, min_side)
                        if check == "format":
                            unreadable += 1
                            continue
                        if check == "small":
                            continue
                        count += 1
                        pictures.append({
                            "number": sheet_number,
                            "blob": blob,
                            "sha1": sha1,
                            "label": name,
                            "id_part": f"sheet{sheet_number}-picture{count}",
                            "where": f"on sheet '{name}'",
                        })
    except (KeyError, zipfile.BadZipFile, etree.XMLSyntaxError):
        # The text was read fine; an odd internal layout only costs the
        # pictures, so do not fail the whole workbook over it.
        return [], ["the pictures in this workbook could not be located"]

    notes = []
    if unreadable:
        notes.append(f"{unreadable} picture(s) are in a format the picture "
                     f"reader cannot open, so were skipped")
    return pictures, notes


def _workbook_rel_ids(archive: zipfile.ZipFile):
    """Each relationship element of the workbook, with its full target path."""
    rels_path = "xl/_rels/workbook.xml.rels"
    try:
        root = etree.fromstring(archive.read(rels_path))
    except KeyError:
        return []
    found = []
    for rel in _xpath(root, "rel:Relationship"):
        target = rel.get("Target", "")
        full = (target.lstrip("/") if target.startswith("/")
                else posixpath.normpath(posixpath.join("xl", target)))
        found.append((rel, full))
    return found
