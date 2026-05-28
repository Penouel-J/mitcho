"""
Generates MITCHÔ PDF reports.
Two visual layouts: "decideur" (professional) and "agriculteur" (simple, large text).
Uses fpdf2 — pure Python, no external binaries required.
"""
import io
import logging
import re
from datetime import datetime

from fpdf import FPDF

logger = logging.getLogger(__name__)

_UNICODE_REPLACEMENTS = str.maketrans({
    "\u2014": "--",
    "\u2013": "-",
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00ab": "<<",
    "\u00bb": ">>",
    "\u2022": "-",
    "\u00b0": " deg",
    "\u00a0": " ",
})

COLOR_PRIMARY    = (0, 100, 50)
COLOR_SECONDARY  = (16, 185, 129)
COLOR_DARK       = (10, 30, 20)
COLOR_LIGHT_BG   = (240, 248, 244)
COLOR_TEXT       = (30, 40, 35)
COLOR_MUTED      = (100, 120, 110)
COLOR_WHITE      = (255, 255, 255)
COLOR_BORDER     = (200, 225, 210)
COLOR_AGRI_GOLD  = (255, 193, 7)    # warm yellow for farmer accents
COLOR_AGRI_BG    = (255, 251, 235)  # soft warm background


def _clean(text: str) -> str:
    if not text:
        return ""
    text = text.translate(_UNICODE_REPLACEMENTS)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ─────────────────────────────────────────────
#  PROFESSIONAL REPORT  (decideur)
# ─────────────────────────────────────────────

class MitchoReportDecideur(FPDF):
    def __init__(self, data: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.data = data
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() == 1:
            return
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
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 60, 297, "F")

        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 9)
        self.set_xy(5, 260)
        self.cell(50, 6, "INTELLIGENCE PUBLIQUE", align="C")

        self.set_xy(70, 50)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(120, 6, "SYSTEME D'ANALYSE ALIMENTAIRE", align="L")

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
            "previsions et recommandations strategiques\npour le Benin.",
            align="L",
        )

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
        self.cell(50, 5, f"Genere : {self.data['generated_at']}")

        self.set_xy(70, 270)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_MUTED)
        self.cell(120, 4, "Document reserve aux decideurs publics - Benin", align="L")

    def prices_section(self, prices):
        if not prices:
            return
        self.add_page()
        self._section_title("Donnees de Prix Vivriers")
        self._subtitle(f"Source : WFP/HDX -- Periode : {self.data.get('price_updated_at', 'recent')}")

        col_w = [65, 35, 30, 25, 25]
        headers = ["Produit", "Marche", "Prix", "Unite", "Devise"]
        self.set_fill_color(*COLOR_PRIMARY)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 9)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 8, h, border=1, fill=True, align="C")
        self.ln()

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
        lines = _clean(analysis_text).split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                self.ln(3)
                continue
            if line.startswith("## "):
                self._section_title(line[3:].strip())
                continue
            if line.startswith("### "):
                self._subtitle(line[4:].strip())
                continue
            if line.startswith("- ") or line.startswith("* "):
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*COLOR_TEXT)
                self.set_x(25)
                self.multi_cell(165, 5, f"- {_clean(line[2:].strip())}", align="L")
                self.ln(1)
                continue
            if re.match(r"^\d+\.\s", line):
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*COLOR_TEXT)
                self.set_x(25)
                self.multi_cell(165, 5, _clean(line), align="L")
                self.ln(1)
                continue
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


# ─────────────────────────────────────────────
#  FARMER GUIDE  (agriculteur)
#  Large text, simple layout, warm colors
# ─────────────────────────────────────────────

class MitchoGuideAgriculteur(FPDF):
    """
    Guide pratique PDF (commerçants et citoyens) :
    - Polices plus grandes (11pt au lieu de 9pt)
    - Accent jaune doré sur les en-têtes de section
    - Page de couverture adaptée au profil
    - Puces avec marqueurs colorés
    """
    # Textes de couverture selon le profil
    _COVER_TEXTS = {
        "commercant": {
            "tagline": "Votre bulletin mensuel pour bien acheter et bien vendre",
            "intro_title": "Ce bulletin est fait pour vous !",
            "intro_body": (
                "Dans ce bulletin, vous trouverez :\n"
                "- Les prix actuels sur les marches du Benin\n"
                "- Les meilleures opportunites d'achat-revente ce mois\n"
                "- Des conseils clairs : quand acheter, quand vendre\n"
                "- Les arbitrages entre marches avec marges estimees"
            ),
            "footer": "Sources des prix : WFP/PAM -- Programme Alimentaire Mondial",
        },
        "citoyen": {
            "tagline": "Vos infos prix pour bien gerer votre budget alimentation",
            "intro_title": "Ce guide est fait pour vous !",
            "intro_body": (
                "Dans ce guide, vous trouverez :\n"
                "- Les prix des aliments en FCFA ce mois\n"
                "- Ou acheter moins cher pres de chez vous\n"
                "- Les produits qui vont devenir plus chers\n"
                "- 5 conseils pour bien manger sans trop depenser"
            ),
            "footer": "Sources des prix : WFP/PAM -- Programme Alimentaire Mondial",
        },
    }
    _DEFAULT_COVER = _COVER_TEXTS["commercant"]

    def __init__(self, data: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.data = data
        self.profile = data.get("profile", "commercant")
        self.cover_txt = self._COVER_TEXTS.get(self.profile, self._DEFAULT_COVER)
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=28)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 5, "F")
        self.set_y(9)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*COLOR_MUTED)
        profile_label = "Commercant" if self.profile == "commercant" else "Citoyen"
        self.cell(0, 5, _clean(f"MITCHO -- Guide {profile_label} -- {self.data['month_label']}"), align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R")
        self.ln(7)
        self.set_text_color(*COLOR_TEXT)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 5, _clean("MITCHO - Votre conseiller agricole au Benin | gratuit"), align="C")
        self.ln(4)
        self.cell(0, 5, _clean(f"Genere le {self.data['generated_at']} | Prix : WFP/HDX"), align="C")
        self.set_text_color(*COLOR_TEXT)

    def cover_page(self):
        # Warm green header band
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 55, "F")

        self.set_xy(18, 12)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*COLOR_WHITE)
        self.cell(0, 12, "MITCHÔ", align="L")

        self.set_xy(18, 28)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(210, 240, 220)
        self.cell(0, 7, _clean(self.cover_txt["tagline"]), align="L")

        self.set_xy(18, 38)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*COLOR_AGRI_GOLD)
        self.cell(0, 7, _clean(f"Mois de {self.data['month_label']}"), align="L")

        # Intro box
        self.set_xy(18, 68)
        self.set_fill_color(*COLOR_AGRI_BG)
        self.set_draw_color(*COLOR_AGRI_GOLD)
        self.set_line_width(0.5)
        self.rect(18, 65, 174, 52, "FD")

        self.set_xy(22, 70)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 7, _clean(self.cover_txt["intro_title"]), align="L")

        self.set_xy(22, 80)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*COLOR_TEXT)
        self.multi_cell(166, 6, _clean(self.cover_txt["intro_body"]), align="L")

        # Price summary strip
        prices = self.data.get("prices", [])[:4]
        if prices:
            self.set_xy(18, 128)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*COLOR_MUTED)
            self.cell(0, 6, _clean(f"APERCU DES PRIX -- {self.data['month_label'].upper()}"), align="L")
            self.ln(7)

            for p in prices:
                self.set_x(18)
                self.set_fill_color(*COLOR_LIGHT_BG)
                self.set_draw_color(*COLOR_BORDER)
                self.rect(self.get_x(), self.get_y(), 174, 10, "FD")
                self.set_x(22)
                self.set_font("Helvetica", "B", 10)
                self.set_text_color(*COLOR_DARK)
                prod = str(p.get("product", ""))[:28]
                self.cell(100, 10, prod, align="L")
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(*COLOR_PRIMARY)
                price_str = f"{p.get('price', 0):,.0f} FCFA/{p.get('unit','kg')}"
                self.cell(72, 10, price_str, align="R")
                self.ln(11)

        self.set_xy(18, 270)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*COLOR_MUTED)
        self.cell(0, 5, _clean(self.cover_txt["footer"]), align="L")

    def prices_section(self, prices):
        if not prices:
            return
        self.add_page()
        self._section_title("Les Prix du Marche ce Mois")
        self._note("Tous les prix sont en FCFA. Source : Programme Alimentaire Mondial (WFP).")

        for idx, p in enumerate(prices):
            bg = COLOR_AGRI_BG if idx % 2 == 0 else COLOR_WHITE
            self.set_fill_color(*bg)
            self.set_draw_color(*COLOR_BORDER)
            self.rect(self.get_x(), self.get_y(), 174, 12, "FD")

            self.set_x(22)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*COLOR_DARK)
            prod = str(p.get("product", ""))[:30]
            market = str(p.get("market", ""))[:15]
            self.cell(80, 12, prod, align="L")

            self.set_font("Helvetica", "", 10)
            self.set_text_color(*COLOR_MUTED)
            self.cell(46, 12, f"Marche : {market}", align="L")

            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*COLOR_PRIMARY)
            price_str = f"{p.get('price', 0):,.0f} FCFA"
            self.cell(46, 12, price_str, align="R")
            self.ln(13)

        self.ln(4)

    def analysis_section(self, analysis_text: str):
        self.add_page()
        lines = _clean(analysis_text).split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                self.ln(4)
                continue

            if line.startswith("## "):
                self._section_title(line[3:].strip())
                continue

            if line.startswith("### "):
                self._subsection(line[4:].strip())
                continue

            # ATTENTION markers — render prominently
            if line.startswith("ATTENTION"):
                self.ln(2)
                self.set_fill_color(255, 240, 200)
                self.set_draw_color(*COLOR_AGRI_GOLD)
                self.set_line_width(0.8)
                clean = _clean(line)
                self.set_x(18)
                # Draw a yellow warning box
                box_h = max(10, len(clean) // 40 * 6 + 10)
                self.rect(18, self.get_y(), 174, box_h, "FD")
                self.set_x(22)
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(180, 80, 0)
                self.multi_cell(166, 6, clean, align="L")
                self.set_line_width(0.2)
                self.ln(3)
                continue

            if line.startswith("- ") or line.startswith("* "):
                body = _clean(line[2:].strip())
                self.set_x(22)
                # Bullet marker
                self.set_fill_color(*COLOR_PRIMARY)
                self.ellipse(18.5, self.get_y() + 3, 3, 3, "F")
                self.set_font("Helvetica", "", 11)
                self.set_text_color(*COLOR_TEXT)
                self.set_x(26)
                self.multi_cell(166, 6, body, align="L")
                self.ln(2)
                continue

            if re.match(r"^\d+\.\s", line):
                self.set_x(22)
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(*COLOR_PRIMARY)
                # Draw number badge
                num_match = re.match(r"^(\d+)\.\s*(.*)", line)
                if num_match:
                    num = num_match.group(1)
                    rest = _clean(num_match.group(2))
                    self.set_fill_color(*COLOR_PRIMARY)
                    self.set_text_color(*COLOR_WHITE)
                    self.cell(7, 7, num, fill=True, align="C")
                    self.set_font("Helvetica", "", 11)
                    self.set_text_color(*COLOR_TEXT)
                    self.set_x(32)
                    self.multi_cell(160, 6, rest, align="L")
                else:
                    self.set_font("Helvetica", "", 11)
                    self.set_text_color(*COLOR_TEXT)
                    self.multi_cell(166, 6, _clean(line), align="L")
                self.ln(2)
                continue

            # Bold text
            if "**" in line:
                clean = _clean(re.sub(r"\*\*(.+?)\*\*", r"\1", line))
                self.set_font("Helvetica", "B", 11)
            else:
                clean = _clean(line)
                self.set_font("Helvetica", "", 11)

            self.set_text_color(*COLOR_TEXT)
            self.set_x(18)
            self.multi_cell(174, 6, clean, align="L")
            self.ln(1)

    def _section_title(self, text: str):
        self.ln(5)
        # Yellow left accent bar + green background
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(18, self.get_y(), 174, 11, "F")
        self.set_fill_color(*COLOR_AGRI_GOLD)
        self.rect(18, self.get_y(), 4, 11, "F")
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*COLOR_WHITE)
        self.set_x(26)
        self.cell(166, 11, _clean(text.upper()), align="L")
        self.ln(5)
        self.set_text_color(*COLOR_TEXT)

    def _subsection(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*COLOR_PRIMARY)
        self.set_x(18)
        self.cell(0, 7, _clean(text), align="L")
        self.ln(4)
        self.set_text_color(*COLOR_TEXT)

    def _note(self, text: str):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*COLOR_MUTED)
        self.set_x(18)
        self.cell(0, 5, _clean(text), ln=True)
        self.ln(3)
        self.set_text_color(*COLOR_TEXT)


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def generate_pdf(report_data: dict) -> bytes:
    profile = report_data.get("profile", "decideur")

    if profile in ("commercant", "citoyen", "agriculteur"):
        pdf = MitchoGuideAgriculteur(data=report_data)
        profile_label = {"commercant": "Commercant", "citoyen": "Citoyen", "agriculteur": "Agriculteur"}.get(profile, profile.capitalize())
        pdf.set_author(f"MITCHO - Guide {profile_label}")
        pdf.set_title(_clean(f"Guide {profile_label} MITCHO - {report_data['month_label']}"))
    else:
        pdf = MitchoReportDecideur(data=report_data)
        pdf.set_author("MITCHO - Systeme d'Intelligence Publique")
        pdf.set_title(_clean(f"Rapport MITCHO - {report_data['month_label']}"))

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
