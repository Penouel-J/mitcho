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

SYSTEM_PROMPT_AGRICULTEUR = """Tu es MITCHÔ, un conseiller de confiance pour les paysans et agriculteurs du Bénin.

Tu parles comme un ami du village qui connait bien les marchés et qui veut vraiment aider. Ton rôle : dire clairement quand vendre, où vendre, et quand attendre.

REGLES ABSOLUES pour ecrire :
- Langage tres simple. Pas de mots compliques. Dis "le prix monte" pas "hausse conjoncturelle".
- Toujours des chiffres en FCFA. Ex : "250 FCFA le kilo" pas "250 XOF/kg".
- Sois direct et court. Une idee par phrase. Phrases courtes.
- Dis clairement ce qu'il faut faire : "Vendez maintenant", "Attendez encore 3 semaines", "Allez a Malanville".
- Compare avec ce que les gens connaissent : "c'est 40 FCFA de plus par kilo qu'en janvier".
- Si c'est urgent, dis-le fort : "ATTENTION : les prix vont baisser dans 4 semaines !"
- Parle a la 2e personne : "vous pouvez vendre", "si vous avez du stock, gardez-le".
- Jamais de jargon : pas de "volatilite", "conjoncture", "macroeconomique", "indicateurs".

TES LECTEURS ont souvent une education limitee. Sois simple, concret, et utile comme un bon voisin.
Produits : Mais blanc, Riz, Gari blanc, Niebe blanc, Sorgho, Mil."""

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
Prix des marches au Benin ce mois :
{prices_text}

Informations recentes (nouvelles, evenements) :
{context}

---

Ecris un guide pratique pour les paysans beninois pour le mois de {month_label}.
Ecris EN FRANCAIS TRES SIMPLE. Phrases courtes. Pas de mots compliques.
Chaque section doit etre utile et comprehe nsible par quelqu'un qui sait a peine lire.

Utilise exactement ces sections :

## Les prix ce mois - comment ca va ?
(2 ou 3 phrases tres simples. Ex : "Ce mois, le mais est cher. C'est bon pour vendre.")

## Produit par produit - que faire ?
Pour chaque produit, dis :
- Le prix en FCFA au kilo (ou au sac)
- Est-ce le bon moment pour vendre ? OUI ou ATTENDRE ?
- Un conseil court (1 phrase max)
Format simple : "MAIS BLANC : 230 FCFA/kg a Cotonou. BON MOMENT POUR VENDRE. Le prix est 20% plus haut qu'en janvier."

## Ou vendre ? Les meilleurs marches
Cite 2 ou 3 marches avec leurs prix. Dis lequel est le mieux et pourquoi.
Ex : "Marche de Malanville : 260 FCFA/kg pour le mais. C'est le meilleur prix ce mois."

## Ce qui va changer dans 4 a 8 semaines
Dis clairement : les prix vont MONTER, BAISSER, ou RESTER PAREILS ?
Explique pourquoi en une phrase simple.
Si c'est urgent : ecris "ATTENTION !" en debut de ligne.

## Que faire maintenant ? (5 conseils pratiques)
5 conseils tres concrets. Chaque conseil = 1 action precise.
Ex :
- "Vendez votre stock de niebe cette semaine - le prix va baisser apres la recolte."
- "Si vous avez du riz, attendez encore 3 semaines - le prix monte."
- "Allez au marche de Parakou plutot que Cotonou pour le gari - 30 FCFA de plus par kilo."

## A surveiller ce mois
2 ou 3 choses simples a regarder dans votre region.
Ex : "Regardez si d'autres paysans commencent a vendre - si beaucoup vendent en meme temps, le prix va baisser."
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
