"""
GDELT CSV loader — lit le fichier gdelt_data.csv (déjà extrait via BigQuery).

Le fichier contient 336 403 événements (2020-2026) pour le Bénin (BN),
le Niger (NI), le Nigeria (NG) et le Togo (TO), filtrés sur les acteurs
et codes d'événements liés à la sécurité alimentaire et à la stabilité sociale.

Deux types de chunks RAG sont produits :
  1. Résumés mensuels : agrégation par mois × catégorie d'événement
  2. Événements notables : événements à forte couverture ou fort impact
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Chemin par défaut vers le fichier CSV ─────────────────────────────────────
_DEFAULT_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "raw" / "gdelt_data.csv"
_DEFAULT_XLS_PATH = Path(__file__).resolve().parents[3] / "data" / "raw" / "base_donnees_prix_vivriers.xlsx"

# ── Labels CAMEO root codes (codes événements) ────────────────────────────────
CAMEO_LABELS: dict[int, str] = {
    1:  "Déclarations publiques",
    2:  "Appels / demandes",
    3:  "Coopération exprimée",
    4:  "Consultation",
    5:  "Engagement diplomatique",
    6:  "Demandes matérielles",
    7:  "Menaces",
    8:  "Protestations",
    9:  "Violence verbale",
    10: "Demandes non satisfaites",
    11: "Cessions / coopération",
    12: "Aide matérielle",
    13: "Sanctions / menaces",
    14: "Manifestations / grèves",
    15: "Coercition",
    16: "Violence non conventionnelle",
    17: "Engagement militaire",
    18: "Frappes militaires",
    19: "Violence de masse",
    20: "Armes non conventionnelles",
}

PAYS_LABELS: dict[str, str] = {
    "BN": "Bénin",
    "NI": "Niger",
    "NG": "Nigeria",
    "TO": "Togo",
}


def _goldstein_label(gs: float) -> str:
    if gs >= 7:  return "très stabilisant"
    if gs >= 3:  return "stabilisant"
    if gs >= 0:  return "neutre"
    if gs >= -3: return "déstabilisant"
    if gs >= -7: return "très déstabilisant"
    return "extrêmement déstabilisant"


def _tone_label(tone: float) -> str:
    if tone > 5:   return "positif"
    if tone > 1:   return "légèrement positif"
    if tone < -5:  return "très négatif"
    if tone < -1:  return "négatif"
    return "neutre"


def _doc_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


# ── Chargement du DataFrame ────────────────────────────────────────────────────

def _load_df(csv_path: Path) -> Optional[pd.DataFrame]:
    if not csv_path.exists():
        logger.warning(f"[GDELT CSV] Fichier introuvable : {csv_path}")
        return None
    try:
        df = pd.read_csv(
            csv_path,
            dtype={
                "SQLDATE": str,
                "EventCode": str,
                "EventBaseCode": str,
                "EventRootCode": str,
                "ActionGeo_CountryCode": str,
                "ActionGeo_ADM1Code": str,
            },
        )
        # Colonnes numériques
        for col in ["GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # Date lisible
        df["date_parsed"] = pd.to_datetime(df["SQLDATE"], format="%Y%m%d", errors="coerce")
        df["month_key"]   = df["date_parsed"].dt.strftime("%Y-%m")
        df["EventRootCode"] = pd.to_numeric(df["EventRootCode"], errors="coerce").astype("Int64")
        logger.info(f"[GDELT CSV] {len(df):,} lignes chargées depuis {csv_path.name}")
        return df
    except Exception as exc:
        logger.error(f"[GDELT CSV] Erreur de chargement : {exc}")
        return None


# ── Chunk 1 : résumés mensuels ─────────────────────────────────────────────────

def _build_monthly_summaries(df: pd.DataFrame) -> list[dict]:
    """
    Crée un chunk par (mois × pays × catégorie d'événement) avec :
    - nombre d'événements
    - tonalité moyenne
    - impact moyen (GoldsteinScale)
    - couverture médiatique totale (NumArticles)
    """
    chunks = []

    # Priorité Bénin + contexte régional
    df_benin    = df[df["ActionGeo_CountryCode"] == "BN"]
    df_regional = df[df["ActionGeo_CountryCode"].isin(["NI", "NG", "TO"])]

    for label, subset in [("Bénin", df_benin), ("Région", df_regional)]:
        grouped = (
            subset
            .groupby(["month_key", "EventRootCode"], dropna=True)
            .agg(
                n_events=("SQLDATE", "count"),
                avg_tone=("AvgTone", "mean"),
                avg_goldstein=("GoldsteinScale", "mean"),
                total_articles=("NumArticles", "sum"),
            )
            .reset_index()
        )

        for _, row in grouped.iterrows():
            month     = row["month_key"]
            root_code = int(row["EventRootCode"]) if pd.notna(row["EventRootCode"]) else 0
            category  = CAMEO_LABELS.get(root_code, f"Code {root_code}")
            n         = int(row["n_events"])
            tone      = float(row["avg_tone"]) if pd.notna(row["avg_tone"]) else 0.0
            gs        = float(row["avg_goldstein"]) if pd.notna(row["avg_goldstein"]) else 0.0
            articles  = int(row["total_articles"]) if pd.notna(row["total_articles"]) else 0

            content = (
                f"[GDELT — {label} — {month}] Catégorie : {category}\n"
                f"Nombre d'événements : {n} | Couverture médiatique : {articles} articles\n"
                f"Tonalité médiatique : {_tone_label(tone)} ({tone:.1f}) | "
                f"Impact stabilité : {_goldstein_label(gs)} ({gs:.1f}/10)"
            )

            doc_id = _doc_id(f"monthly_{label}_{month}_{root_code}")
            chunks.append({
                "doc_id":   doc_id,
                "content":  content,
                "source":   "gdelt_csv_monthly",
                "title":    f"[{label}] {month} — {category}",
                "metadata": {
                    "source":    "gdelt_csv",
                    "type":      "monthly_summary",
                    "month":     month,
                    "country":   label,
                    "category":  category,
                    "n_events":  str(n),
                    "avg_tone":  f"{tone:.1f}",
                },
            })

    logger.info(f"[GDELT CSV] {len(chunks)} résumés mensuels créés")
    return chunks


# ── Chunk 2 : événements notables ──────────────────────────────────────────────

def _build_notable_events(df: pd.DataFrame, min_articles: int = 5) -> list[dict]:
    """
    Crée un chunk par événement à forte couverture ou fort impact.
    Filtre : NumArticles >= min_articles OU |GoldsteinScale| >= 5
    Priorité : Bénin + acteurs liés à l'alimentation/commerce.
    """
    notable = df[
        (df["NumArticles"] >= min_articles) |
        (df["GoldsteinScale"].abs() >= 5)
    ].copy()

    # Prioriser le Bénin
    benin   = notable[notable["ActionGeo_CountryCode"] == "BN"]
    other   = notable[notable["ActionGeo_CountryCode"] != "BN"].head(500)
    notable = pd.concat([benin, other]).drop_duplicates()

    chunks = []
    seen: set[str] = set()

    for _, row in notable.iterrows():
        url    = str(row.get("SOURCEURL", "")) if pd.notna(row.get("SOURCEURL")) else ""
        doc_id = _doc_id(url or f"{row['SQLDATE']}_{row['EventCode']}_{row.get('ActionGeo_FullName','')}")
        if doc_id in seen:
            continue
        seen.add(doc_id)

        date_str  = row["date_parsed"].strftime("%d/%m/%Y") if pd.notna(row["date_parsed"]) else "date inconnue"
        pays      = PAYS_LABELS.get(str(row.get("ActionGeo_CountryCode", "")), "Région")
        lieu      = str(row.get("ActionGeo_FullName", pays)) if pd.notna(row.get("ActionGeo_FullName")) else pays
        actor1    = str(row["Actor1Name"]) if pd.notna(row.get("Actor1Name")) else "Acteur inconnu"
        actor2    = str(row["Actor2Name"]) if pd.notna(row.get("Actor2Name")) else ""
        root_code = int(row["EventRootCode"]) if pd.notna(row.get("EventRootCode")) else 0
        category  = CAMEO_LABELS.get(root_code, f"Événement {root_code}")
        gs        = float(row["GoldsteinScale"]) if pd.notna(row.get("GoldsteinScale")) else 0.0
        tone      = float(row["AvgTone"]) if pd.notna(row.get("AvgTone")) else 0.0
        articles  = int(row["NumArticles"]) if pd.notna(row.get("NumArticles")) else 0

        actors_str = f"{actor1} / {actor2}" if actor2 else actor1

        content = (
            f"[GDELT — {date_str} — {lieu}]\n"
            f"Événement : {category} impliquant {actors_str}\n"
            f"Impact stabilité : {_goldstein_label(gs)} ({gs:+.1f}) | "
            f"Tonalité : {_tone_label(tone)} | Couverture : {articles} articles"
        )
        if url:
            content += f"\nSource : {url}"

        chunks.append({
            "doc_id":   doc_id,
            "content":  content,
            "source":   "gdelt_csv_event",
            "title":    f"[{pays}] {date_str} — {category}",
            "url":      url,
            "metadata": {
                "source":   "gdelt_csv",
                "type":     "notable_event",
                "country":  pays,
                "date":     date_str,
                "category": category,
                "goldstein": f"{gs:+.1f}",
            },
        })

    logger.info(f"[GDELT CSV] {len(chunks)} événements notables créés")
    return chunks


# ── Chunk 3 : données prix (Excel) ────────────────────────────────────────────

def load_prix_chunks(xls_path: Optional[Path] = None) -> list[dict]:
    """Charge le fichier Excel de prix et crée un chunk RAG synthétique."""
    path = xls_path or _DEFAULT_XLS_PATH
    if not path.exists():
        logger.warning(f"[PRIX] Fichier introuvable : {path}")
        return []
    try:
        df = pd.read_excel(path)
        lines = []
        for _, row in df.iterrows():
            pays    = str(row.get("Pays", ""))
            produit = str(row.get("Produit", ""))
            moy     = row.get("Prix Moyen", "?")
            pmin    = row.get("Prix Min", "?")
            pmax    = row.get("Prix Max", "?")
            lines.append(
                f"  - {produit} ({pays}) : {moy:.0f} FCFA/kg en moyenne "
                f"[min {pmin:.0f} — max {pmax:.0f}]"
            )
        content = (
            "Données de prix des produits vivriers au Bénin :\n"
            + "\n".join(lines)
            + "\n(Source : base_donnees_prix_vivriers.xlsx)"
        )
        chunk = [{
            "doc_id":   "prix-vivriers-benin",
            "content":  content,
            "source":   "prix_locaux",
            "title":    "Prix des produits vivriers — Bénin",
            "metadata": {
                "source": "prix_locaux",
                "type":   "price_data",
                "date":   "2024-2025",
            },
        }]
        logger.info(f"[PRIX] {len(df)} produits chargés depuis {path.name}")
        return chunk
    except Exception as exc:
        logger.error(f"[PRIX] Erreur : {exc}")
        return []


# ── Fonction principale ────────────────────────────────────────────────────────

def load_gdelt_csv_chunks(
    csv_path: Optional[Path] = None,
    min_articles: int = 5,
) -> list[dict]:
    """
    Charge le CSV GDELT et retourne tous les chunks RAG (résumés + événements notables).

    Args:
        csv_path: chemin vers gdelt_data.csv (default: ../data/raw/)
        min_articles: seuil pour les événements notables

    Returns: liste de chunks prêts pour upsert_chunks()
    """
    path = csv_path or _DEFAULT_CSV_PATH
    df   = _load_df(path)
    if df is None:
        return []

    monthly  = _build_monthly_summaries(df)
    notable  = _build_notable_events(df, min_articles=min_articles)
    prix     = load_prix_chunks()

    all_chunks = monthly + notable + prix
    logger.info(f"[GDELT CSV] Total chunks produits : {len(all_chunks)}")
    return all_chunks
