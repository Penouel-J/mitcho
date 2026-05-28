"""
MITCHÔ PDF — mise en forme simple, épurée, noir et blanc.
Titres en gras, texte corps, tableau de prix propre. C'est tout.
"""
import io
import logging
import re
from datetime import datetime

from fpdf import FPDF

logger = logging.getLogger(__name__)

_UNICODE_REPLACEMENTS = str.maketrans({
    "\u2014": "--", "\u2013": "-",  "\u2019": "'",  "\u2018": "'",
    "\u201c": '"',  "\u201d": '"',  "\u2026": "...", "\u00ab": "<<",
    "\u00bb": ">>", "\u2022": "-",  "\u00b0": " deg","\u00a0": " ",
})


def _clean(text: str) -> str:
    if not text:
        return ""
    text = text.translate(_UNICODE_REPLACEMENTS)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── Constantes typographiques ──────────────────────────────────────────────────
MARGIN   = 22        # mm gauche/droite
COL_W    = 210 - MARGIN * 2   # largeur utile
BODY_SZ  = 10
TITLE_SZ = 13
H1_SZ    = 16
SMALL_SZ = 8


class MitchoReport(FPDF):
    """
    PDF unifié pour tous les profils — design noir et blanc.
    Le contenu (analysis_text) est déjà adapté au profil par le LLM.
    """

    PROFILE_TITLES = {
        "decideur":   "Rapport d'Analyse",
        "commercant": "Bulletin Marché",
        "citoyen":    "Guide Pratique",
        "agriculteur":"Guide Pratique",
    }

    def __init__(self, data: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.data    = data
        self.profile = data.get("profile", "decideur")
        self.set_margins(MARGIN, 18, MARGIN)
        self.set_auto_page_break(auto=True, margin=22)

    # ── En-tête / pied ────────────────────────────────────────────────────────
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", SMALL_SZ)
        self.set_text_color(130, 130, 130)
        title = self.PROFILE_TITLES.get(self.profile, "Rapport")
        self.cell(0, 5, _clean(f"MITCHÔ  |  {title}  |  {self.data['month_label']}"), align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        self.line(MARGIN, self.get_y(), 210 - MARGIN, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        self.line(MARGIN, self.get_y(), 210 - MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "", SMALL_SZ - 1)
        self.set_text_color(150, 150, 150)
        self.cell(0, 4, _clean(
            f"MITCHÔ — Intelligence pour la Securite Alimentaire au Benin  |  "
            f"Genere le {self.data['generated_at']}  |  Sources : WFP/HDX, GDELT 2.0"
        ), align="C")
        self.set_text_color(0, 0, 0)

    # ── Page de couverture ────────────────────────────────────────────────────
    def cover_page(self):
        title_label = self.PROFILE_TITLES.get(self.profile, "Rapport")

        # Ligne décorative fine en haut
        self.set_draw_color(0, 0, 0)
        self.set_line_width(1.0)
        self.line(MARGIN, 28, 210 - MARGIN, 28)
        self.set_line_width(0.2)

        # Nom de la plateforme
        self.set_xy(MARGIN, 35)
        self.set_font("Helvetica", "B", 32)
        self.set_text_color(0, 0, 0)
        self.cell(0, 14, "MITCHO", align="L")

        # Sous-titre
        self.set_xy(MARGIN, 52)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(80, 80, 80)
        self.cell(0, 7, _clean("Intelligence Publique pour la Securite Alimentaire au Benin"), align="L")

        # Ligne séparatrice
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.4)
        self.line(MARGIN, 64, 210 - MARGIN, 64)
        self.set_line_width(0.2)

        # Titre du rapport
        self.set_xy(MARGIN, 72)
        self.set_font("Helvetica", "B", H1_SZ + 2)
        self.set_text_color(0, 0, 0)
        self.cell(0, 9, _clean(title_label), align="L")

        self.set_xy(MARGIN, 83)
        self.set_font("Helvetica", "", TITLE_SZ)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, _clean(self.data["month_label"]), align="L")

        # Métadonnées sources
        self.set_xy(MARGIN, 105)
        self.set_font("Helvetica", "", BODY_SZ)
        self.set_text_color(100, 100, 100)
        meta = [
            f"Prix WFP : {len(self.data.get('prices', []))} produits",
            f"Evenements GDELT : {self.data.get('gdelt_articles_count', 0)} signaux indexes",
            f"Genere le {self.data['generated_at']}",
        ]
        for m in meta:
            self.cell(0, 6, _clean(m), align="L")
            self.ln(6)

        # Ligne de bas de couverture
        self.set_draw_color(0, 0, 0)
        self.set_line_width(1.0)
        self.line(MARGIN, 260, 210 - MARGIN, 260)
        self.set_line_width(0.2)

        self.set_xy(MARGIN, 263)
        self.set_font("Helvetica", "", SMALL_SZ)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, _clean("mitchobenin.org"), align="L")
        self.set_text_color(0, 0, 0)

    # ── Tableau des prix ──────────────────────────────────────────────────────
    def prices_section(self, prices):
        if not prices:
            return
        self.add_page()
        self._h1("Prix des produits vivriers")
        self.set_font("Helvetica", "", SMALL_SZ)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, _clean(f"Source : WFP/HDX  —  Periode : {self.data.get('price_updated_at', 'recente')}"), ln=True)
        self.ln(4)

        # En-têtes de tableau
        cols = [75, 45, 35, 25]
        hdrs = ["Produit", "Marche", "Prix (FCFA)", "Unite"]
        self.set_font("Helvetica", "B", BODY_SZ)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.3)
        for i, h in enumerate(hdrs):
            self.cell(cols[i], 7, h, border="B", align="L")
        self.ln()

        # Lignes de données
        self.set_font("Helvetica", "", BODY_SZ)
        self.set_line_width(0.1)
        for p in prices:
            self.cell(cols[0], 6, _clean(str(p.get("product", "")))[:35], border="B", align="L")
            self.cell(cols[1], 6, _clean(str(p.get("market",  "")))[:22], border="B", align="L")
            self.cell(cols[2], 6, f"{p.get('price', 0):,.0f}",            border="B", align="R")
            self.cell(cols[3], 6, str(p.get("unit", "kg")),               border="B", align="C")
            self.ln()
        self.ln(6)

    # ── Section analyse LLM ───────────────────────────────────────────────────
    def analysis_section(self, analysis_text: str):
        self.add_page()
        for line in _clean(analysis_text).split("\n"):
            line = line.strip()
            if not line:
                self.ln(3)
                continue

            # ## Titre de section
            if line.startswith("## "):
                self.ln(4)
                self.set_font("Helvetica", "B", TITLE_SZ)
                self.set_text_color(0, 0, 0)
                self.set_x(MARGIN)
                self.multi_cell(COL_W, 7, _clean(line[3:].strip()), align="L")
                # Soulignement léger
                self.set_draw_color(0, 0, 0)
                self.set_line_width(0.3)
                self.line(MARGIN, self.get_y(), MARGIN + COL_W, self.get_y())
                self.ln(4)
                self.set_text_color(0, 0, 0)
                continue

            # ### Sous-titre
            if line.startswith("### "):
                self.ln(2)
                self.set_font("Helvetica", "B", BODY_SZ + 1)
                self.set_text_color(0, 0, 0)
                self.set_x(MARGIN)
                self.multi_cell(COL_W, 6, _clean(line[4:].strip()), align="L")
                self.ln(1)
                continue

            # Puce —
            if line.startswith("- ") or line.startswith("* "):
                body = _clean(line[2:].strip())
                # Retrait gras si **...**
                bold_parts = re.split(r'\*\*(.+?)\*\*', body)
                self.set_x(MARGIN + 4)
                self.set_font("Helvetica", "", BODY_SZ)
                self.cell(4, 5.5, "-", align="L")
                self.set_x(MARGIN + 8)
                # Simplifié : affiche le texte nettoyé sans gras inline
                clean_body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
                self.multi_cell(COL_W - 8, 5.5, clean_body, align="L")
                self.ln(0.5)
                continue

            # Liste numérotée
            if re.match(r"^\d+\.\s", line):
                self.set_font("Helvetica", "", BODY_SZ)
                self.set_x(MARGIN + 2)
                self.multi_cell(COL_W - 2, 5.5, _clean(line), align="L")
                self.ln(0.5)
                continue

            # Texte en gras **...**
            if "**" in line:
                clean = _clean(re.sub(r'\*\*(.+?)\*\*', r'\1', line))
                self.set_font("Helvetica", "B", BODY_SZ)
            else:
                clean = _clean(line)
                self.set_font("Helvetica", "", BODY_SZ)

            self.set_text_color(0, 0, 0)
            self.set_x(MARGIN)
            self.multi_cell(COL_W, 5.5, clean, align="L")
            self.ln(0.5)

    # ── Titre H1 ──────────────────────────────────────────────────────────────
    def _h1(self, text: str):
        self.set_font("Helvetica", "B", H1_SZ)
        self.set_text_color(0, 0, 0)
        self.set_x(MARGIN)
        self.cell(0, 9, _clean(text), ln=True)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.5)
        self.line(MARGIN, self.get_y(), MARGIN + COL_W, self.get_y())
        self.ln(5)
        self.set_line_width(0.2)


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def generate_pdf(report_data: dict) -> bytes:
    profile = report_data.get("profile", "decideur")

    pdf = MitchoReport(data=report_data)
    pdf.set_author("MITCHÔ")
    title_map = {"decideur": "Rapport", "commercant": "Bulletin Marche", "citoyen": "Guide Pratique"}
    pdf.set_title(_clean(f"MITCHÔ {title_map.get(profile, 'Rapport')} {report_data['month_label']}"))

    pdf.add_page()
    pdf.cover_page()

    if report_data.get("prices"):
        pdf.prices_section(report_data["prices"])

    if report_data.get("analysis_text"):
        pdf.analysis_section(report_data["analysis_text"])

    output = pdf.output(dest="S")
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)
