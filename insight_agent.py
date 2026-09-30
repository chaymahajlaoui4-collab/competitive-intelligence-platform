"""
Insight Agent - version "light" (1 agent, pas de framework LangGraph complexe)

Rôle : prendre les données déjà analysées (posts_analyzed.csv), désigner UNE
entreprise comme "client", traiter toutes les autres comme "concurrents",
et générer des recommandations stratégiques priorisées via Groq.

Usage :
    py insight_agent.py posts_analyzed.csv "Nom De L'Agence Client"
"""

import csv
import json
import sys
from collections import Counter
from groq import Groq

# ============================================
# METS TA CLÉ API GROQ ICI
# ============================================
import os
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODELE = "openai/gpt-oss-120b"


# ============================================
# NORMALISATION (corrige les labels incohérents FR/EN)
# ============================================

def normaliser_sentiment(s):
    s = (s or "").lower().strip()
    if s in ("positif", "positive"):
        return "positif"
    if s in ("neutre", "neutral"):
        return "neutre"
    if s in ("negatif", "négatif", "negative"):
        return "négatif"
    return "neutre"


def charger_et_normaliser(chemin_csv):
    with open(chemin_csv, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for r in rows:
        r["sentiment"] = normaliser_sentiment(r.get("sentiment", ""))
        r["likes"] = int(r["likes"]) if r.get("likes", "").strip().isdigit() else 0
    return [r for r in rows if r.get("agence", "").strip()]


# ============================================
# AGRÉGATION : résume une entreprise en quelques indicateurs clés
# (on n'envoie pas 400 posts bruts au LLM, juste un résumé structuré)
# ============================================

def resumer_entreprise(rows, nom):
    posts = [r for r in rows if r["agence"] == nom]
    if not posts:
        return {}

    total_likes = sum(p["likes"] for p in posts)
    sentiments = Counter(p["sentiment"] for p in posts)
    themes = Counter(p["theme"] for p in posts if p.get("theme"))
    objectifs = Counter(p["objectif"] for p in posts if p.get("objectif"))
    sources = Counter(p["source"] for p in posts)

    return {
        "nom": nom,
        "nb_posts": len(posts),
        "engagement_moyen": round(total_likes / len(posts), 1),
        "sentiment_positif_pct": round(sentiments.get("positif", 0) / len(posts) * 100),
        "top_themes": [t for t, _ in themes.most_common(5)],
        "top_objectifs": [o for o, _ in objectifs.most_common(3)],
        "sources": dict(sources),
    }


def resumer_concurrents(rows, nom_client):
    concurrents = sorted(set(r["agence"] for r in rows if r["agence"] != nom_client))
    return [resumer_entreprise(rows, c) for c in concurrents if resumer_entreprise(rows, c)]


# ============================================
# INSIGHT AGENT : génère les recommandations via Groq
# ============================================

PROMPT_TEMPLATE = """Tu es un consultant en stratégie marketing spécialisé en intelligence concurrentielle.

Voici le profil du CLIENT que tu dois conseiller :
{client_json}

Voici le profil de SES CONCURRENTS (même secteur) :
{concurrents_json}

À partir de ces données, génère entre 3 et 5 recommandations stratégiques concrètes et priorisées pour le CLIENT.
Chaque recommandation doit :
- Comparer explicitement le client à un ou plusieurs concurrents (avec chiffres si possible)
- Identifier une opportunité ou un écart concret
- Proposer une action précise et actionnable

Réponds au format JSON STRICT (liste d'objets, rien d'autre) :
[
  {{
    "priorite": 1,
    "constat": "description du constat comparatif",
    "recommandation": "action concrète à mener"
  }}
]
"""


def generer_recommandations(profil_client, profils_concurrents):
    prompt = PROMPT_TEMPLATE.format(
        client_json=json.dumps(profil_client, ensure_ascii=False, indent=2),
        concurrents_json=json.dumps(profils_concurrents, ensure_ascii=False, indent=2),
    )

    response = client_groq.chat.completions.create(
        model=MODELE,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
    )

    texte = response.choices[0].message.content.strip()
    texte = texte.replace("```json", "").replace("```", "").strip()
    return json.loads(texte)


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main(chemin_csv, nom_client):
    rows = charger_et_normaliser(chemin_csv)

    profil_client = resumer_entreprise(rows, nom_client)
    if not profil_client:
        print(f"Aucune donnée trouvée pour '{nom_client}'.")
        return

    profils_concurrents = resumer_concurrents(rows, nom_client)

    print(f"=== Profil client : {nom_client} ===")
    print(json.dumps(profil_client, ensure_ascii=False, indent=2))
    print(f"\n{len(profils_concurrents)} concurrents chargés pour comparaison.\n")

    print("Génération des recommandations via l'Insight Agent...\n")
    recommandations = generer_recommandations(profil_client, profils_concurrents)

    print("=" * 60)
    print(f"RECOMMANDATIONS STRATÉGIQUES POUR : {nom_client}")
    print("=" * 60)
    for r in recommandations:
        print(f"\n[Priorité {r['priorite']}]")
        print(f"Constat : {r['constat']}")
        print(f"Recommandation : {r['recommandation']}")


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "posts_analyzed.csv"
    nom_client = sys.argv[2] if len(sys.argv) > 2 else "24-7 Digital Design"
    main(chemin, nom_client)
