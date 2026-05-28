"""
Generates a professional PDF report from the assembled report data.
Uses fpdf2 — pure Python, no external binaries required.
"""
import io
import logging
import re
from datetime import datetime

from fpdf import FPDF, Align

logger = logging.getLogger(__name__)

# Characters outside Latin-1 must be replaced before calling fpdf2 built-in fonts
_UNICODE_REPLACEMENTS = str.maketrans({
    "\u2014": "--",   # em dash —
    "\u2013": "-",    # en dash –
    "\u2019": "'",    # right single quotation mark '
    "\u2018": "'",    # left single quotation mark '
    "\u201c": '"',    # left double quotation mark "
    "\u201d": '"',    # right double quotation mark "
    "\u2026": "...",  # ellipsis …
    "\u00ab": "<<",   # left guillemet «
    "\u00bb": ">>",   # right guillemet »
    "\u00e9": "e",    # é  (Latin-1 should be fine but just in case)
    "\u2022": "-",    # bullet •
    "\u00b0": " deg",# degree °
    "\u00a0": " ",    # non-breaking space
})


def _clean(text: str) -> str:
    """Strip characters outside Latin-1 range so fpdf2 built-in fonts don't crash."""
    if not text:
        return ""
    text = text.translate(_UNICODE_REPLACEMENTS)
    # Drop any remaining non-Latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


# MITCHÔ brand colors (RGB)
COLOR_PRIMARY = (0, 100, 50)        # dark green
COLOR_SECONDARY = (16, 185, 129)    # emerald
COLOR_DARK = (10, 30, 20)
COLOR_LIGHT_BG = (240, 248, 244)
COLOR_TEXT = (30, 40, 35)
COLOR_MUTED = (100, 120, 110)
COLOR_WHITE = (255, 255, 255)
COLOR_BORDER = (200, 225, 210)


class MitchoReport(FPDF):
    def __init__(self, data: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.data = data
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() == 1:
            return
        # Thin green top bar
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 4, "F")
        self.set_y(8)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 5, _clean(f"MITCHO -- Rapport {self.data['month_label']}"), align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R")
        self.ln(6)
        self.set_text_color(*COLOR_TEXT)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 5, _clean("MITCHO - Intelligence Publique pour la Securite Alimentaire au Benin"), align="C")
        self.ln(4)
        self.cell(0, 5, _clean(f"Genere le {self.data['generated_at']} | Sources : WFP/HDX, GDELT 2.0"), align="C")
        self.set_text_color(*COLOR_TEXT)

    def cover_page(self):
        # Full-height green sidebar
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 60, 297, "F")

        # Sidebar text (rotated feel via top-down labels)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 9)
        self.set_xy(5, 260)
        self.cell(50, 6, "INTELLIGENCE PUBLIQUE", align="C")

        # Right side content
        self.set_xy(70, 50)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(120, 6, "SYSTÈME D'ANALYSE ALIMENTAIRE", align="L")

        self.set_xy(70, 65)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*COLOR_DARK)
        self.multi_cell(120, 12, "MITCHÔ", align="L")

        self.set_xy(70, 95)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*COLOR_PRIMARY)
        self.multi_cell(120, 8, _clean(f"Rapport d'Analyse\n{self.data['month_label']}"), align="L")

        self.set_xy(70, 130)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*COLOR_MUTED)
        self.multi_cell(
            120, 6,
            "Analyse des prix vivriers, signaux GDELT,\n"
            "prévisions et recommandations stratégiques\npour le Bénin.",
            align="L",
        )

        # Stats box
        self.set_xy(70, 175)
        self.set_fill_color(*COLOR_LIGHT_BG)
        self.set_draw_color(*COLOR_BORDER)
        self.rect(70, 175, 120, 45, "FD")

        self.set_xy(75, 181)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(50, 5, "SOURCES")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*COLOR_TEXT)
        self.set_xy(75, 188)
        self.cell(50, 5, f"Prix WFP : {len(self.data.get('prices', []))} produits")
        self.set_xy(75, 195)
        self.cell(50, 5, f"Articles GDELT : {self.data.get('gdelt_articles_count', 0)}")
        self.set_xy(75, 202)
        self.cell(50, 5, f"Généré : {self.data['generated_at']}")

        # Footer note on cover
        self.set_xy(70, 270)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_MUTED)
        self.cell(120, 4, "Document reserve aux decideurs publics - Benin", align="L")

    def prices_section(self, prices):
        if not prices:
            return
        self.add_page()
        self._section_title("Données de Prix Vivriers")
        self._subtitle(f"Source : WFP/HDX — Période : {self.data.get('price_updated_at', 'récent')}")

        col_w = [65, 35, 30, 25, 25]
        headers = ["Produit", "Marché", "Prix", "Unité", "Devise"]

        # Table header
        self.set_fill_color(*COLOR_PRIMARY)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 9)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 8, h, border=1, fill=True, align="C")
        self.ln()

        # Table rows
        self.set_font("Helvetica", "", 9)
        for idx, p in enumerate(prices):
            bg = COLOR_LIGHT_BG if idx % 2 == 0 else COLOR_WHITE
            self.set_fill_color(*bg)
            self.set_text_color(*COLOR_TEXT)
            self.cell(col_w[0], 7, str(p.get("product", "")), border=1, fill=True)
            self.cell(col_w[1], 7, str(p.get("market", ""))[:18], border=1, fill=True, align="C")
            self.cell(col_w[2], 7, f"{p.get('price', 0):,.0f}", border=1, fill=True, align="R")
            self.cell(col_w[3], 7, str(p.get("unit", "kg")), border=1, fill=True, align="C")
            self.cell(col_w[4], 7, str(p.get("currency", "XOF")), border=1, fill=True, align="C")
            self.ln()

        self.ln(6)

    def analysis_section(self, analysis_text: str):
        self.add_page()
        # Sanitise the entire analysis first to remove non-Latin-1 characters
        lines = _clean(analysis_text).split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                self.ln(3)
                continue

            # Markdown H2 → section title
            if line.startswith("## "):
                self._section_title(line[3:].strip())
                continue

            # Markdown H3 → subtitle
            if line.startswith("### "):
                self._subtitle(line[4:].strip())
                continue

            # Bullet points (use plain hyphen — no Unicode bullet)
            if line.startswith("- ") or line.startswith("* "):
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*COLOR_TEXT)
                self.set_x(25)
                bullet_text = _clean(line[2:].strip())
                self.multi_cell(165, 5, f"- {bullet_text}", align="L")
                self.ln(1)
                continue

            # Numbered list
            if re.match(r"^\d+\.\s", line):
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*COLOR_TEXT)
                self.set_x(25)
                self.multi_cell(165, 5, _clean(line), align="L")
                self.ln(1)
                continue

            # Bold text (simple **...**)
            if "**" in line:
                clean = _clean(re.sub(r"\*\*(.+?)\*\*", r"\1", line))
                self.set_font("Helvetica", "B", 9)
            else:
                clean = _clean(line)
                self.set_font("Helvetica", "", 9)

            self.set_text_color(*COLOR_TEXT)
            self.set_x(20)
            self.multi_cell(170, 5, clean, align="L")
            self.ln(1)

    def _section_title(self, text: str):
        self.ln(4)
        self.set_fill_color(*COLOR_PRIMARY)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, f"  {_clean(text)}", fill=True, ln=True)
        self.ln(4)
        self.set_text_color(*COLOR_TEXT)

    def _subtitle(self, text: str):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 5, _clean(text), ln=True)
        self.ln(2)
        self.set_text_color(*COLOR_TEXT)


def generate_pdf(report_data: dict) -> bytes:
    """
    Main entry point: takes assembled report data, returns PDF as bytes.
    """
    pdf = MitchoReport(data=report_data)
    pdf.set_author("MITCHO - Systeme d'Intelligence Publique")
    pdf.set_title(f"Rapport MITCHO - {report_data['month_label']}")

    # Cover
    pdf.add_page()
    pdf.cover_page()

    # Prices table
    if report_data.get("prices"):
        pdf.prices_section(report_data["prices"])

    # Analysis (RAG-generated text)
    if report_data.get("analysis_text"):
        pdf.analysis_section(report_data["analysis_text"])

    output = pdf.output(dest="S")
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)
