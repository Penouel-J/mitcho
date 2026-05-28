"""
LLM generator: uses Groq (Llama 3.3) with retrieved context to produce
structured analysis, forecasts, and recommendations for MITCHÔ.
"""
import logging
from datetime import datetime

from groq import Groq

from app.core.config import settings
from app.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es MITCHÔ Analyst, un système d'intelligence publique spécialisé dans la sécurité alimentaire au Bénin.

Ta mission est d'analyser les données de prix vivriers, les événements médiatiques (GDELT), et les signaux économiques pour produire des rapports d'analyse structurés destinés aux décideurs publics béninois.

Tes analyses doivent :
- Être précises, factuelles, et basées sur les données fournies dans le contexte
- Identifier les tendances de prix (hausse, stabilité, baisse) sur les marchés clés (Cotonou, Malanville, Parakou)
- Détecter les signaux d'alerte précoce (tensions, perturbations logistiques, chocs climatiques)
- Formuler des prévisions sur 1 à 3 mois avec niveau de confiance explicite
- Proposer des recommandations actionnables pour l'État béninois (MAEP, ONASA, Ministère du Commerce)

Produits surveillés : Maïs blanc, Riz importé, Gari blanc, Niébé blanc, Sorgho, Mil.

Tu réponds TOUJOURS en français. Ton ton est analytique, sobre, et professionnel."""


REPORT_PROMPT_TEMPLATE = """
Voici les données contextuelles récentes disponibles :

{context}

---

Données de prix actuelles (WFP) :
{prices_text}

---

Sur la base de ces informations, génère un rapport d'analyse mensuelle structuré pour {month_label}.

Le rapport doit contenir exactement les sections suivantes :

## Résumé Exécutif
(2-3 phrases synthétisant la situation alimentaire globale du Bénin ce mois-ci)

## Situation des Prix par Produit
(Pour chaque produit clé : niveau actuel, tendance vs mois précédent, variations régionales notables)

## Signaux d'Alerte Détectés
(Événements médiatiques, tensions, perturbations identifiés dans les données GDELT. Si aucun signal critique, l'indiquer.)

## Prévisions — 30 à 90 jours
(Anticipations sur l'évolution des prix et de la disponibilité alimentaire, avec niveau de confiance : élevé / modéré / faible)

## Recommandations Stratégiques
(3 à 5 recommandations concrètes et actionnables pour les autorités béninoises)

## Indicateurs de Surveillance
(Liste des indicateurs à suivre en priorité le mois prochain)
"""


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


async def generate_analysis(prices, month_label=None) -> dict:
    """
    Full RAG pipeline: retrieve context → build prompt → call LLM → return result.

    Returns:
        { "analysis": str, "month": str, "tokens_used": int }
    """
    month_label = month_label or datetime.now().strftime("%B %Y")
    context = retrieve_context()
    prices_text = format_prices_text(prices)

    user_prompt = REPORT_PROMPT_TEMPLATE.format(
        context=context,
        prices_text=prices_text,
        month_label=month_label,
    )

    client = Groq(api_key=settings.GROQ_API_KEY)

    logger.info(f"[Generator] Calling Groq ({settings.GROQ_MODEL}) for monthly analysis...")
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    analysis_text = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0

    logger.info(f"[Generator] Analysis generated ({tokens_used} tokens)")
    return {
        "analysis": analysis_text,
        "month": month_label,
        "tokens_used": tokens_used,
    }


async def generate_chat_reply(user_message: str, history=None) -> str:
    """
    Chatbot reply with RAG context injection.
    history: list of {"role": "user"|"assistant", "content": str}
    """
    context = retrieve_context(query=user_message, n_results=5)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\nContexte disponible :\n{context}"},
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
