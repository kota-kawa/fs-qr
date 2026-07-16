"""ノート本文の PDF エクスポート処理。"""

from __future__ import annotations

import os
from pathlib import Path

from fpdf import FPDF


class NotePdfFontUnavailableError(RuntimeError):
    """PDF 用の日本語フォントが見つからない場合の例外。"""


def _font_candidates() -> tuple[Path, ...]:
    """Return portable Noto CJK font locations. / Noto CJK の候補を返す。"""
    configured = os.getenv("NOTE_PDF_FONT_PATH", "").strip()
    project_font = Path(__file__).resolve().parents[1] / "static" / "fonts"
    home_font = Path.home() / ".fonts"
    candidates = [
        project_font / "NotoSansCJK-Regular.ttc",
        project_font / "NotoSansJP-Regular.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/local/share/fonts/NotoSansCJK-Regular.ttc"),
        home_font / "NotoSansCJK-Regular.ttc",
    ]
    if configured:
        candidates.insert(0, Path(configured).expanduser())
    return tuple(candidates)


def find_note_pdf_font() -> Path:
    """利用可能な日本語フォントを探す。"""
    for candidate in _font_candidates():
        if candidate.is_file():
            return candidate.resolve()
    raise NotePdfFontUnavailableError(
        "Noto Sans CJK font is unavailable. Install fonts-noto-cjk or set "
        "NOTE_PDF_FONT_PATH."
    )


def build_note_pdf(
    content: str,
    room_id: str,
    *,
    font_path: Path | None = None,
) -> bytes:
    """ノート本文を検索・コピー可能な PDF に変換する。"""
    selected_font = (font_path or find_note_pdf_font()).resolve()
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(f"FS!QR Note {room_id}")
    pdf.set_author("FS!QR")
    pdf.add_page()
    # TTC files contain multiple regional faces; index 0 is the Japanese face.
    # TTC は複数地域の書体を含み、index 0 が日本語書体です。
    pdf.add_font(
        "NotoSansCJK",
        fname=selected_font,
        collection_font_number=0,
    )
    pdf.set_font("NotoSansCJK", size=10.5)
    # HarfBuzz handles complex scripts and bidirectional text when present.
    # 複雑な文字体系や右横書きが含まれる場合も HarfBuzz で字形処理します。
    pdf.set_text_shaping(True)
    pdf.multi_cell(
        w=0,
        h=6.5,
        text=content.replace("\t", "    ") or " ",
        wrapmode="CHAR",
    )
    return bytes(pdf.output())
