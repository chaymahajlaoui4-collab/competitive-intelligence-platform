"""
Agent d'analyse comparative — secteur Télécommunications (3 opérateurs).

Compare Ooredoo, Orange Tunisie et Tunisie Telecom sur Instagram + Facebook
fusionnés, avec le même principe anti-hallucination que l'agent marketing :
les verdicts "au-dessus/en dessous de la moyenne" sont calculés en Python,
le LLM ne fait que rédiger le SWOT à partir de ces verdicts déjà corrects.

INPUTS (fusionnés automatiquement, un seul fichier suffit si l'autre manque) :
    posts_telecom_instagram_analyses.csv
    posts_telecom_facebook_analyses.csv
    (format attendu : celui produit par 'Analyze multi source.py' —
     colonnes source, auteur, post_url, date, likes, contenu_original,
     langue, type_contenu, theme, produit_service, promotion, sentiment)

Installation : pip install groq

CONFIGURATION :
    set GROQ_API_KEY=ta_clef_groq

Usage :
    py analyse_telecom.py
    py analyse_telecom.py --question "Quel opérateur communique le mieux sur la 5G ?"
"""

import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from groq import Groq
from normalize_agency_names import normaliser_colonne_agence

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    print("ERREUR : la variable d'environnement GROQ_API_KEY n'est pas définie.")
    print("Tape d'abord : set GROQ_API_KEY=ta_clef_groq")
    sys.exit(1)

client_groq = Groq(api_key=GROQ_API_KEY)
MODELE = " openai/gpt-oss-120b"

FICHIERS_SOURCE = [
    "posts_telecom_instagram_analyses.csv",
    "posts_telecom_facebook_analyses.csv",
]

POIDS = {"engagement": 0.45, "sentiment": 0.20, "frequence": 0.20, "diversite": 0.15}


# ============================================
# CHARGEMENT ET FUSION
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


def charger_et_fusionner(fichiers):
    tous_les_posts = []
    for fichier in fichiers:
        if not os.path.exists(fichier):
            print(f"  (fichier '{fichier}' introuvable, ignoré)")
            continue
        with open(fichier, encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            r["likes"] = int(r["likes"]) if str(r.get("likes", "")).strip().isdigit() else 0
            r["sentiment"] = normaliser_sentiment(r.get("sentiment", ""))
            tous_les_posts.append(r)
        print(f"  {len(rows)} posts chargés depuis '{fichier}'")

    if not tous_les_posts:
        print("ERREUR : aucun fichier source trouvé. Vérifie les noms de fichiers.")
        sys.exit(1)

    tous_les_posts = normaliser_colonne_agence(tous_les_posts, colonne="auteur")

    return tous_les_posts


# ============================================
# PROFILS PAR OPÉRATEUR (colonne 'auteur' = nom de l'opérateur)
# ============================================

def profil_brut(rows, operateur):
    posts = [r for r in rows if r.get("auteur") == operateur]
    if not posts:
        return {}

    total_likes = sum(p["likes"] for p in posts)
    sentiments = Counter(p["sentiment"] for p in posts)
    themes = Counter(p["theme"] for p in posts if p.get("theme"))
    produits = Counter(p["produit_service"] for p in posts if p.get("produit_service") and p.get("produit_service") != "null")

    return {
        "nom": operateur,
        "nb_posts": len(posts),
        "engagement_moyen": round(total_likes / len(posts), 1),
        "sentiment_positif_pct": round(sentiments.get("positif", 0) / len(posts) * 100),
        "nb_themes_uniques": len(themes),
        "diversite_ratio": round(len(themes) / len(posts), 2),
        "top_themes": [t for t, _ in themes.most_common(4)],
        "top_produits_services": [p for p, _ in produits.most_common(3)],
    }


# ============================================
# SCORE + VERDICTS PRÉ-CALCULÉS (jamais laissés au LLM)
# ============================================

def normaliser_0_100(valeur, mini, maxi):
    if maxi == mini:
        return 50.0
    return round((valeur - mini) / (maxi - mini) * 100, 1)


def verdict_vs_moyenne(valeur, moyenne, unite=""):
    if moyenne == 0:
        return "moyenne du secteur non calculable"
    ecart_pct = round((valeur - moyenne) / moyenne * 100)
    if abs(ecart_pct) < 3:
        return f"proche de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"
    elif ecart_pct > 0:
        return f"AU-DESSUS de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"
    else:
        return f"EN DESSOUS de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"


def calculer_scores(profils):
    engagements = [p["engagement_moyen"] for p in profils]
    sentiments = [p["sentiment_positif_pct"] for p in profils]
    frequences = [p["nb_posts"] for p in profils]
    diversites = [p["diversite_ratio"] for p in profils]

    moyennes = {
        "moy_engagement": round(sum(engagements) / len(engagements), 1),
        "moy_sentiment": round(sum(sentiments) / len(sentiments), 1),
        "moy_frequence": round(sum(frequences) / len(frequences), 1),
        "moy_diversite": round(sum(diversites) / len(diversites), 2),
    }

    for p in profils:
        score_engagement = normaliser_0_100(p["engagement_moyen"], min(engagements), max(engagements))
        score_sentiment = normaliser_0_100(p["sentiment_positif_pct"], min(sentiments), max(sentiments))
        score_frequence = normaliser_0_100(p["nb_posts"], min(frequences), max(frequences))
        score_diversite = normaliser_0_100(p["diversite_ratio"], min(diversites), max(diversites))

        p["detail_score"] = {
            "engagement": round(score_engagement * POIDS["engagement"], 1),
            "sentiment": round(score_sentiment * POIDS["sentiment"], 1),
            "frequence": round(score_frequence * POIDS["frequence"], 1),
            "diversite": round(score_diversite * POIDS["diversite"], 1),
        }
        p["score_final"] = round(sum(p["detail_score"].values()), 1)

        p["vs_moyenne_engagement_pct"] = (
            round((p["engagement_moyen"] - moyennes["moy_engagement"]) / moyennes["moy_engagement"] * 100)
            if moyennes["moy_engagement"] else 0
        )

        p["verdict_engagement"] = verdict_vs_moyenne(p["engagement_moyen"], moyennes["moy_engagement"])
        p["verdict_frequence"] = verdict_vs_moyenne(p["nb_posts"], moyennes["moy_frequence"], " posts")
        p["verdict_sentiment"] = verdict_vs_moyenne(p["sentiment_positif_pct"], moyennes["moy_sentiment"], "%")
        p["verdict_diversite"] = verdict_vs_moyenne(p["diversite_ratio"], moyennes["moy_diversite"])

    profils.sort(key=lambda p: p["score_final"], reverse=True)
    for i, p in enumerate(profils):
        p["priorite"] = i + 1

    return profils, moyennes


# ============================================
# AFFICHAGE BENCHMARK
# ============================================

def afficher_benchmark(profils):
    print("\n=== BENCHMARK ENGAGEMENT (barres proportionnelles) ===")
    max_engagement = max(p["engagement_moyen"] for p in profils) or 1
    for p in profils:
        largeur = int(p["engagement_moyen"] / max_engagement * 30)
        barre = "█" * largeur
        signe = "+" if p["vs_moyenne_engagement_pct"] >= 0 else ""
        print(f"  [{p['priorite']}] {p['nom']:<20} {barre} {p['engagement_moyen']:>7} "
              f"({signe}{p['vs_moyenne_engagement_pct']}% vs moyenne)")


def afficher_score_detaille(profils):
    print("\n=== DÉTAIL DU SCORE (transparent) ===")
    print(f"  Pondération : Engagement {int(POIDS['engagement']*100)}% | "
          f"Sentiment {int(POIDS['sentiment']*100)}% | "
          f"Fréquence {int(POIDS['frequence']*100)}% | "
          f"Diversité {int(POIDS['diversite']*100)}%\n")
    for p in profils:
        d = p["detail_score"]
        print(f"  [{p['priorite']}] {p['nom']}")
        print(f"      Engagement: {d['engagement']} | Sentiment: {d['sentiment']} | "
              f"Fréquence: {d['frequence']} | Diversité: {d['diversite']}  "
              f"=> SCORE FINAL: {p['score_final']}")


# ============================================
# ANALYSE IA — SWOT avec verdicts déjà tranchés
# ============================================

PROMPT_TEMPLATE = """Tu es un consultant en intelligence concurrentielle rigoureux, spécialisé
dans le secteur des télécommunications en Tunisie.

RÈGLE ABSOLUE N°1 : tu ne dois JAMAIS inventer un fait ou un chiffre absent des données ci-dessous.

RÈGLE ABSOLUE N°2 : chaque profil contient déjà des champs "verdict_engagement",
"verdict_frequence", "verdict_sentiment" et "verdict_diversite", DÉJÀ CALCULÉS et CORRECTS.
INTERDICTION de les recalculer toi-même — utilise-les tels quels.

Données des 3 opérateurs télécom tunisiens (moyennes du groupe : engagement {moy_engagement},
fréquence {moy_frequence} posts, sentiment positif {moy_sentiment}%, diversité {moy_diversite}) :
{profils_json}

{question_section}

Pour CHAQUE opérateur, génère un SWOT basé UNIQUEMENT sur les chiffres et verdicts fournis :
- Forces : max 2, appuyées sur un verdict "AU-DESSUS de la moyenne"
- Faiblesses : max 2, appuyées sur un verdict "EN DESSOUS de la moyenne"
  (si aucune, dis "Aucune faiblesse notable dans les données disponibles")
- Opportunités : basées sur ce que font mieux les autres opérateurs
- Menaces : basées sur l'écart avec le leader

Réponds au format JSON STRICT :
{{
  "swot_par_operateur": [
    {{"priorite": 1, "nom": "...", "forces": ["..."], "faiblesses": ["..."], "opportunites": ["..."], "menaces": ["..."]}}
  ],
  "reponse_question": "réponse détaillée à la question métier, chiffrée",
  "synthese_secteur": "3-4 phrases de synthèse globale du secteur télécom, chiffrée"
}}
"""


def generer_analyse(profils, moyennes, question=None, retries=4):
    if question:
        question_section = f'QUESTION MÉTIER : "{question}"\nRéponds dans le champ "reponse_question".'
    else:
        question_section = ('QUESTION MÉTIER PAR DÉFAUT : "Pourquoi l\'opérateur en priorité 1 est-il devant '
                             'les autres, et comment les 2 autres pourraient-ils le rattraper ?"\n'
                             'Réponds dans le champ "reponse_question".')

    prompt = PROMPT_TEMPLATE.format(
        moy_engagement=moyennes["moy_engagement"], moy_frequence=moyennes["moy_frequence"],
        moy_sentiment=moyennes["moy_sentiment"], moy_diversite=moyennes["moy_diversite"],
        profils_json=json.dumps(profils, ensure_ascii=False, indent=2),
        question_section=question_section,
    )

    for tentative in range(1, retries + 1):
        try:
            response = client_groq.chat.completions.create(
                model=MODELE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"},
            )
            choix = response.choices[0]
            texte = (choix.message.content or "").strip().replace("```json", "").replace("```", "").strip()

            if not texte:
                print(f"  ⚠ Tentative {tentative}/{retries} : réponse vide. Nouvelle tentative...")
                time.sleep(2)
                continue

            return json.loads(texte)

        except json.JSONDecodeError as e:
            print(f"  ⚠ Tentative {tentative}/{retries} : JSON invalide ({e}).")
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ Tentative {tentative}/{retries} : erreur Groq : {e}")
            time.sleep(min(2 ** tentative, 20))

    raise RuntimeError(f"Impossible d'obtenir une réponse JSON valide après {retries} tentatives.")


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main(question=None):
    print("Chargement et fusion des données Instagram + Facebook télécom...")
    rows = charger_et_fusionner(FICHIERS_SOURCE)

    operateurs = sorted(set(r.get("auteur", "") for r in rows if r.get("auteur")))
    print(f"\n{len(operateurs)} opérateurs détectés : {', '.join(operateurs)}\n")

    profils_bruts = [profil_brut(rows, op) for op in operateurs]
    profils_bruts = [p for p in profils_bruts if p]

    if len(profils_bruts) < 2:
        print("Pas assez d'opérateurs avec des données pour une comparaison.")
        return

    profils, moyennes = calculer_scores(profils_bruts)

    afficher_benchmark(profils)
    afficher_score_detaille(profils)
    print(f"\nMoyennes du secteur — Engagement: {moyennes['moy_engagement']} | "
          f"Fréquence: {moyennes['moy_frequence']} posts | "
          f"Sentiment positif: {moyennes['moy_sentiment']}% | "
          f"Diversité: {moyennes['moy_diversite']}")

    print("\nGénération du SWOT + réponse métier via l'agent...\n")
    resultat = generer_analyse(profils, moyennes, question)

    print("=" * 70)
    print("ANALYSE SECTORIELLE — TÉLÉCOMMUNICATIONS TUNISIE")
    print("=" * 70)

    for s in resultat["swot_par_operateur"]:
        print(f"\n[Priorité {s['priorite']}] {s['nom']}")
        print(f"  Forces        : {' | '.join(s['forces'])}")
        print(f"  Faiblesses    : {' | '.join(s['faiblesses'])}")
        print(f"  Opportunités  : {' | '.join(s['opportunites'])}")
        print(f"  Menaces       : {' | '.join(s['menaces'])}")

    print("\n" + "-" * 70)
    print("RÉPONSE À LA QUESTION MÉTIER")
    print("-" * 70)
    print(resultat["reponse_question"])

    print("\n" + "-" * 70)
    print("SYNTHÈSE DU SECTEUR")
    print("-" * 70)
    print(resultat["synthese_secteur"])


if __name__ == "__main__":
    args = sys.argv[1:]
    question = None
    if "--question" in args:
        idx = args.index("--question")
        question = args[idx + 1]
    main(question)
