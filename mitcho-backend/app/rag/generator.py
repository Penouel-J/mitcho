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

SYSTEM_PROMPT_DECIDEUR = """Tu es MITCHÔ Analyst, un système d'intelligence publique spécialisé dans la sécurité alimentaire au Bénin.

Ta mission est d'analyser les données de prix vivriers, les événements médiatiques (GDELT), et les signaux économiques pour produire des rapports d'analyse stratégiques destinés aux décideurs publics béninois (MAEP, ONASA, Ministère du Commerce, Présidence).

Tes analyses doivent :
- Être précises, factuelles, et basées sur les données fournies dans le contexte
- Identifier les tendances de prix sur les marchés clés (Cotonou, Malanville, Parakou, Bohicon)
- Détecter les signaux d'alerte précoce (tensions, perturbations logistiques, chocs climatiques)
- Formuler des prévisions sur 1 à 3 mois avec niveau de confiance explicite
- Proposer des recommandations de politique publique actionnables (stocks tampons, subventions, interventions)

Produits surveillés : Maïs blanc, Riz importé, Gari blanc, Niébé blanc, Sorgho, Mil.

Tu réponds TOUJOURS en français. Ton ton est analytique, institutionnel, et professionnel."""

SYSTEM_PROMPT_AGRICULTEUR = """Tu es MITCHÔ, un assistant d'aide à la décision pour les agriculteurs et producteurs du Bénin.

Ta mission est d'analyser les prix des marchés vivriers pour aider les agriculteurs à prendre de meilleures décisions : quand vendre, quand stocker, quels marchés cibler, comment anticiper les fluctuations.

Tes analyses doivent :
- Utiliser un langage simple, clair et accessible
- Indiquer concrètement les opportunités de vente ou de stockage selon les prix actuels
- Signaler les marchés où les prix sont les plus favorables (Cotonou, Malanville, Parakou)
- Donner des conseils pratiques et locaux basés sur les tendances observées
- Alerter sur les risques de baisse de prix ou de surplus

Produits surveillés : Maïs blanc, Riz, Gari, Niébé, Sorgho, Mil.

Tu réponds TOUJOURS en français simple et accessible. Évite le jargon technique. Parle directement à l'agriculteur (utilise "vous")."""

REPORT_PROMPT_DECIDEUR = """
Voici les données contextuelles récentes disponibles :

{context}

---

Données de prix actuelles (WFP) :
{prices_text}

---

Sur la base de ces informations, génère un rapport d'analyse mensuelle structuré pour {month_label}, destiné aux décideurs publics béninois.

Le rapport doit contenir exactement les sections suivantes :

## Résumé Exécutif
(2-3 phrases synthétisant la situation alimentaire globale du Bénin ce mois-ci, pour un lecteur de haut niveau)

## Situation des Prix par Produit
(Pour chaque produit clé : niveau actuel, tendance vs mois précédent, variations régionales notables entre Cotonou, Malanville et Parakou)

## Signaux d'Alerte Détectés
(Événements médiatiques, tensions logistiques, perturbations climatiques ou économiques. Si aucun signal critique, l'indiquer explicitement.)

## Prévisions — 30 à 90 jours
(Anticipations sur l'évolution des prix et de la disponibilité alimentaire, avec niveau de confiance : élevé / modéré / faible)

## Recommandations de Politique Publique
(3 à 5 recommandations concrètes pour les institutions : ONASA, MAEP, Ministère du Commerce, avec responsable suggéré pour chaque action)

## Indicateurs à Surveiller
(Liste des indicateurs prioritaires à suivre le mois prochain)
"""

REPORT_PROMPT_AGRICULTEUR = """
Voici les informations sur les prix des marchés du Bénin :

{prices_text}

Contexte additionnel :
{context}

---

Sur la base de ces informations, génère un guide pratique pour les agriculteurs béninois pour le mois de {month_label}.

Le guide doit contenir exactement les sections suivantes :

## Situation du marché ce mois
(En 2-3 phrases simples : comment se portent les prix des aliments ce mois-ci ?)

## Prix par produit — Ce que ça veut dire pour vous
(Pour chaque produit : le prix actuel, si c'est un bon ou mauvais moment pour vendre, et pourquoi — en langage simple)

## Marchés les plus favorables
(Quels marchés offrent les meilleurs prix ce mois ? Conseils concrets sur où vendre)

## Ce qui risque de changer dans les 1 à 2 prochains mois
(Prévisions simples : est-ce que les prix vont monter, baisser, ou rester stables ?)

## Conseils pratiques
(3 à 5 actions concrètes que vous pouvez prendre maintenant : vendre, stocker, négocier, attendre...)

## À surveiller
(2-3 signaux simples à observer dans votre région le mois prochain)
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


async def generate_analysis(prices, month_label=None, profile: str = "decideur") -> dict:
    """
    Full RAG pipeline: retrieve context → build prompt → call LLM → return result.

    profile: "agriculteur" | "decideur" — determines system prompt and template.
    Returns: { "analysis": str, "month": str, "tokens_used": int, "profile": str }
    """
    month_label = month_label or datetime.now().strftime("%B %Y")
    context = retrieve_context()
    prices_text = format_prices_text(prices)

    if profile == "agriculteur":
        system_prompt = SYSTEM_PROMPT_AGRICULTEUR
        user_prompt = REPORT_PROMPT_AGRICULTEUR.format(
            context=context,
            prices_text=prices_text,
            month_label=month_label,
        )
    else:
        system_prompt = SYSTEM_PROMPT_DECIDEUR
        user_prompt = REPORT_PROMPT_DECIDEUR.format(
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

    logger.info(f"[Generator] Analysis generated ({tokens_used} tokens, profile={profile})")
    return {
        "analysis": analysis_text,
        "month": month_label,
        "tokens_used": tokens_used,
        "profile": profile,
    }


async def generate_chat_reply(user_message: str, history=None, profile: str = "decideur") -> str:
    """
    Chatbot reply with RAG context injection.
    history: list of {"role": "user"|"assistant", "content": str}
    profile: "agriculteur" | "decideur"
    """
    context = retrieve_context(query=user_message, n_results=5)
    system_prompt = SYSTEM_PROMPT_AGRICULTEUR if profile == "agriculteur" else SYSTEM_PROMPT_DECIDEUR

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
