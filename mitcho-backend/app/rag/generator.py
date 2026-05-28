"""
LLM generator — Groq (Llama 3.3) with RAG context.
Three profiles: "decideur" | "commercant" | "citoyen"
"""
import logging
from datetime import datetime

from groq import Groq

from app.core.config import settings
from app.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)

# ── SYSTEM PROMPTS ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_DECIDEUR = """Tu es MITCHÔ Analyst, un système d'intelligence publique spécialisé dans la sécurité alimentaire au Bénin.

Ta mission : analyser les données de prix vivriers, les événements médiatiques (GDELT), et les signaux économiques pour produire des rapports stratégiques destinés aux décideurs publics béninois (MAEP, ONASA, Ministère du Commerce, Présidence).

Tes analyses doivent :
- Être précises, factuelles, basées sur les données fournies
- Identifier les tendances de prix sur les marchés clés (Cotonou, Malanville, Parakou, Bohicon)
- Détecter les signaux d'alerte précoce (tensions, perturbations logistiques, chocs climatiques)
- Formuler des prévisions sur 1 à 3 mois avec niveau de confiance explicite
- Proposer des recommandations de politique publique actionnables

Produits surveillés : Maïs blanc, Riz importé, Gari blanc, Niébé blanc, Sorgho, Mil.
Tu réponds TOUJOURS en français. Ton ton est analytique, institutionnel, et professionnel."""

SYSTEM_PROMPT_COMMERCANT = """Tu es MITCHÔ, un conseiller de confiance pour les commerçants et revendeurs de vivres au Bénin.

Tu parles à des commerçants qui achètent et revendent des produits alimentaires sur les marchés. Leur objectif : acheter au meilleur moment et au meilleur endroit, revendre avec une marge correcte.

REGLES :
- Toujours des prix en FCFA. Parle de marges, d'écarts entre marchés, de timing d'achat.
- Dis clairement : "Achetez maintenant à Parakou", "Revendez à Cotonou — écart de 45 FCFA/kg".
- Mentionne les marchés sources (Malanville, Parakou, Bohicon) et de vente (Cotonou, Dantokpa).
- Signale les opportunités d'arbitrage entre régions et pays voisins (Niger, Togo).
- Alerte sur les risques de surstock et de chute de prix.
- Langage simple mais orienté business. Parle à la 2e personne.

Produits : Maïs blanc, Riz importé, Gari blanc, Niébé blanc, Sorgho, Mil."""

SYSTEM_PROMPT_CITOYEN = """Tu es MITCHÔ, un assistant simple et utile pour les ménages et citoyens du Bénin.

Tu aides les gens ordinaires à comprendre les prix des aliments : où acheter moins cher, quels produits vont devenir plus chers, comment gérer leur budget alimentation.

REGLES :
- Langage très simple, accessible à tous. Pas de jargon économique.
- Toujours des prix en FCFA. Donne les prix au kilo ET au sac quand possible.
- Conseils pratiques pour le budget quotidien.
- Indique les marchés les plus accessibles.
- Signale les produits qui vont monter pour que les gens s'approvisionnent à l'avance.
- Parle de produits de substitution si un produit est trop cher.
- Ton chaleureux, rassurant, et pratique. Parle à la 2e personne.

Produits : Maïs, Riz, Gari, Niébé, Sorgho, Mil."""

# ── REPORT TEMPLATES ─────────────────────────────────────────────────────────

REPORT_PROMPT_DECIDEUR = """
Données contextuelles récentes :
{context}

---

Données de prix actuelles (WFP) :
{prices_text}

---

Génère un rapport d'analyse mensuelle structuré pour {month_label}, destiné aux décideurs publics béninois.

## Résumé Exécutif
(2-3 phrases synthétisant la situation alimentaire globale, pour un lecteur de haut niveau)

## Situation des Prix par Produit
(Prix actuel, tendance vs mois précédent, variations régionales : Cotonou, Malanville, Parakou)

## Signaux d'Alerte Détectés
(Événements médiatiques, tensions logistiques, perturbations. Si aucun signal critique, l'indiquer.)

## Prévisions — 30 à 90 jours
(Anticipations avec niveau de confiance : élevé / modéré / faible)

## Recommandations de Politique Publique
(3 à 5 recommandations pour ONASA, MAEP, Ministère du Commerce, avec responsable suggéré)

## Indicateurs à Surveiller
(Liste des indicateurs prioritaires le mois prochain)
"""

REPORT_PROMPT_COMMERCANT = """
Prix des marchés au Bénin ce mois :
{prices_text}

Informations récentes :
{context}

---

Écris un bulletin pour les commerçants de vivres béninois — {month_label}.
Langage simple orienté business. Chiffres en FCFA. Conseils d'achat/vente concrets.

## Situation des prix ce mois
(3-4 phrases : quels produits sont chers, lesquels sont bon marché, tendance générale)

## Produit par produit — Acheter ou attendre ?
Pour chaque produit :
- Prix actuel en FCFA/kg
- Conseil : ACHETER MAINTENANT / ATTENDRE / VENDRE MAINTENANT
- Marge estimée si achat aujourd'hui et revente dans 3 semaines
Format : "MAIS BLANC : 230 FCFA/kg (Parakou). ACHETEZ — revente Cotonou ~270 FCFA/kg, marge ~40 FCFA/kg."

## Meilleurs arbitrages ce mois
2-3 opportunités d'écart de prix entre marchés avec chiffres.

## Risques à surveiller
Produits en surstock, risques de chute de prix, tensions logistiques. "ATTENTION !" si urgent.

## Prévisions 3-6 semaines
Tendance HAUSSE / BAISSE / STABLE par produit avec raison (1 phrase).

## 5 actions à prendre cette semaine
Conseils très concrets avec chiffres à l'appui.
"""

REPORT_PROMPT_CITOYEN = """
Prix alimentaires au Bénin ce mois :
{prices_text}

Informations générales :
{context}

---

Écris un guide pratique pour les ménages béninois — {month_label}.
Langage très simple, chaleureux. Aide les gens à gérer leur budget alimentation.

## Comment vont les prix ce mois ?
(2-3 phrases simples : est-ce cher ou pas ? Qu'est-ce qui a changé ?)

## Produit par produit — Est-ce cher ?
Pour chaque produit :
- Prix en FCFA (au kilo et au sac si possible)
- CHER / NORMAL / BON MARCHÉ par rapport à d'habitude
- Un conseil simple
Format : "RIZ IMPORTÉ : 687 FCFA/kg (environ 17 000 FCFA le sac). CHER. Conseil : achetez du gari à la place — moins cher et nourrissant."

## Où acheter moins cher ?
Marchés accessibles avec les prix les plus bas. Conseils pratiques pour faire ses courses.

## Ce qui va coûter plus cher dans 1 mois
Alertes sur les produits dont le prix va monter. "Faites vos stocks maintenant avant la hausse."

## 5 conseils budget pour ce mois
Conseils pratiques pour manger bien sans dépenser trop. Produits de substitution pas chers.
"""

# ── HELPERS ──────────────────────────────────────────────────────────────────

def _get_prompts(profile: str):
    if profile == "commercant":
        return SYSTEM_PROMPT_COMMERCANT, REPORT_PROMPT_COMMERCANT
    if profile == "citoyen":
        return SYSTEM_PROMPT_CITOYEN, REPORT_PROMPT_CITOYEN
    return SYSTEM_PROMPT_DECIDEUR, REPORT_PROMPT_DECIDEUR


def format_prices_text(prices: list[dict]) -> str:
    if not prices:
        return "Données de prix non disponibles."
    lines = []
    for p in prices:
        lines.append(
            f"- {p['product']} : {p['price']:,.0f} {p['currency']}/{p['unit']} "
            f"(marché {p['market']}, {p['month']})"
        )
    return "\n".join(lines)


# ── MAIN FUNCTIONS ────────────────────────────────────────────────────────────

async def generate_analysis(prices, month_label=None, profile: str = "decideur") -> dict:
    """
    Full RAG pipeline: retrieve context → build prompt → call LLM → return result.
    profile: "decideur" | "commercant" | "citoyen"
    """
    month_label = month_label or datetime.now().strftime("%B %Y")
    context = retrieve_context()
    prices_text = format_prices_text(prices)

    system_prompt, template = _get_prompts(profile)
    user_prompt = template.format(
        context=context,
        prices_text=prices_text,
        month_label=month_label,
    )

    client = Groq(api_key=settings.GROQ_API_KEY)
    logger.info(f"[Generator] Calling Groq ({settings.GROQ_MODEL}) — profile={profile}")

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    analysis_text = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    logger.info(f"[Generator] Done — {tokens_used} tokens, profile={profile}")

    return {
        "analysis": analysis_text,
        "month": month_label,
        "tokens_used": tokens_used,
        "profile": profile,
    }


async def generate_page_sections(prices, month_label=None, profile: str = "decideur") -> dict:
    """
    Génère le contenu structuré de la page tendances.html via le LLM.
    Retourne un dict JSON avec : situation_summary_html, recommendations (3 items),
    alert_tags, risk_score, risk_label, hero_subtitle.

    Les recommandations et la synthèse sont adaptées au profil.
    """
    import json as _json

    month_label = month_label or datetime.now().strftime("%B %Y")
    context      = retrieve_context()
    prices_text  = format_prices_text(prices)
    system_prompt, _ = _get_prompts(profile)

    profile_labels = {
        "decideur":   "décideur public (MAEP, ONASA, Ministère du Commerce)",
        "commercant": "commerçant ou revendeur de vivres",
        "citoyen":    "citoyen / ménage ordinaire",
    }
    profile_label = profile_labels.get(profile, profile)

    user_prompt = f"""
Données de prix actuelles (WFP) pour {month_label} :
{prices_text}

Contexte récent (événements, signaux) :
{context}

---
Génère le contenu JSON de la page mensuelle MITCHÔ pour un utilisateur : {profile_label}.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après. Voici le format EXACT à respecter :

{{
  "hero_subtitle": "...",
  "situation_summary_html": "<p>...</p><p>...</p>",
  "recommendations": [
    {{"tag": "...", "title": "...", "description": "..."}},
    {{"tag": "...", "title": "...", "description": "..."}},
    {{"tag": "...", "title": "...", "description": "..."}}
  ],
  "alert_tags": ["...", "...", "...", "..."],
  "risk_score": 58,
  "risk_label": "MODÉRÉ"
}}

Règles impératives :
- hero_subtitle : 1-2 phrases décrivant la valeur de la page pour ce profil.
- situation_summary_html : 3 paragraphes HTML avec <strong> pour les chiffres clés en FCFA. Basé sur les données ci-dessus.
- recommendations : exactement 3 objets. tag = mot-clé court (Urgent / Achetez / Bon plan / etc). title = 6-9 mots max. description = 2-3 phrases concrètes avec prix en FCFA.
- alert_tags : 4 signaux courts (2-3 mots chacun), extraits des données.
- risk_score : entier 0-100 basé sur les données.
- risk_label : "FAIBLE" | "MODÉRÉ" | "ÉLEVÉ" | "CRITIQUE"
"""

    client = Groq(api_key=settings.GROQ_API_KEY)
    logger.info(f"[Generator] Page sections — profile={profile}, month={month_label}")

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.25,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    logger.info(f"[Generator] Page sections done — {tokens_used} tokens")

    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError:
        # Fallback : extraire le premier { ... }
        import re as _re
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        data = _json.loads(match.group(0)) if match else {}

    # Valeurs par défaut si le LLM omet un champ
    data.setdefault("hero_subtitle", "Analyse mensuelle des marchés vivriers au Bénin.")
    data.setdefault("situation_summary_html", "<p>Analyse en cours de chargement.</p>")
    data.setdefault("recommendations", [])
    data.setdefault("alert_tags", [])
    data.setdefault("risk_score", 50)
    data.setdefault("risk_label", "MODÉRÉ")
    data["profile"] = profile
    data["month_label"] = month_label

    return data


async def generate_chat_reply(user_message: str, history=None, profile: str = "decideur") -> str:
    """RAG-powered chatbot reply. profile: "decideur" | "commercant" | "citoyen" """
    context = retrieve_context(query=user_message, n_results=5)
    system_prompt, _ = _get_prompts(profile)

    messages = [
        {"role": "system", "content": system_prompt + f"\n\nContexte disponible :\n{context}"},
    ]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.5,
        max_tokens=800,
    )
    return response.choices[0].message.content
