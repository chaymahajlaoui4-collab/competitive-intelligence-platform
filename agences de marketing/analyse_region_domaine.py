"""
Agent d'analyse par région + domaine — version 2.1 (verdicts pré-calculés).

Correctif vs v2 :
- BUG CORRIGÉ : le LLM inversait parfois "au-dessus/en dessous de la moyenne"
  même en citant le bon chiffre (ex: "21 posts, en dessous de la moyenne de 16.6"
  — ce qui est faux, 21 > 16.6). Cause : le LLM faisait lui-même la comparaison
  numérique et se trompait parfois de sens.
- CORRECTIF : chaque métrique a maintenant un "verdict" pré-calculé en Python
  (ex: "au-dessus de la moyenne (+26%)") injecté directement dans les données
  envoyées au LLM. Le prompt lui interdit explicitement de recalculer/juger
  lui-même si un chiffre est supérieur ou inférieur — il doit seulement citer
  le verdict déjà fourni. Le LLM garde son rôle : rédiger, pas comparer.

Usage :
    py analyse_region_domaine_v2.py "Sousse" "marketing"
    py analyse_region_domaine_v2.py "Sousse" "marketing" --question "Comment ACM peut dépasser Emmak Prod ?"
"""

import csv
import json
import os
import sys
from collections import Counter
from groq import Groq

# ============================================
# CLÉ API GROQ — lue depuis une variable d'environnement, jamais en dur
# dans le code (évite de re-exposer une clé par erreur dans un chat/repo).
#
# Avant de lancer ce script (ou dashboard.py qui l'importe), tape :
#   set GROQ_API_KEY=ta_vraie_clef_groq        (Windows cmd)
#   $env:GROQ_API_KEY="ta_vraie_clef_groq"     (PowerShell)
# ============================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    print("ERREUR : la variable d'environnement GROQ_API_KEY n'est pas définie.")
    print("Tape d'abord : set GROQ_API_KEY=ta_vraie_clef_groq")
    print("(si ce script est appelé depuis dashboard.py, lance 'set GROQ_API_KEY=...'")
    print(" AVANT de faire 'streamlit run dashboard.py', dans le même terminal)")
    sys.exit(1)

client_groq = Groq(api_key=GROQ_API_KEY)
MODELE = " openai/gpt-oss-120b"

FICHIER_REGIONS = "agences_region_domaine.csv"
FICHIER_POSTS = "posts_analyzed.csv"

# Poids du score (transparents, affichés à l'utilisateur)
POIDS = {"engagement": 0.45, "sentiment": 0.20, "frequence": 0.20, "diversite": 0.15}


# ============================================
# NORMALISATION
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


def filtrer_agences(region: str, domaine: str) -> list[str]:
    with open(FICHIER_REGIONS, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    region_lower, domaine_lower = region.lower().strip(), domaine.lower().strip()
    return [r["agence"] for r in rows
            if region_lower in (r.get("ville") or "").lower()
            and domaine_lower in (r.get("domaine") or "").lower()]


def charger_posts(chemin_csv: str = FICHIER_POSTS) -> list[dict]:
    with open(chemin_csv, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["sentiment"] = normaliser_sentiment(r.get("sentiment", ""))
        r["likes"] = int(r["likes"]) if r.get("likes", "").strip().isdigit() else 0
    return rows


# ============================================
# PROFILS BRUTS (avant normalisation du score)
# ============================================

def profil_brut(rows: list[dict], nom: str) -> dict:
    posts = [r for r in rows if r["agence"] == nom]
    if not posts:
        return {}

    total_likes = sum(p["likes"] for p in posts)
    sentiments = Counter(p["sentiment"] for p in posts)
    themes = Counter(p["theme"] for p in posts if p.get("theme"))
    objectifs = Counter(p["objectif"] for p in posts if p.get("objectif"))

    return {
        "nom": nom,
        "nb_posts": len(posts),
        "engagement_moyen": round(total_likes / len(posts), 1),
        "sentiment_positif_pct": round(sentiments.get("positif", 0) / len(posts) * 100),
        "nb_themes_uniques": len(themes),
        "diversite_ratio": round(len(themes) / len(posts), 2),  # thèmes uniques / posts
        "top_themes": [t for t, _ in themes.most_common(4)],
        "top_objectifs": [o for o, _ in objectifs.most_common(3)],
    }


# ============================================
# SCORE TRANSPARENT (normalisé 0-100 par composante, pondéré)
# ============================================

def normaliser_0_100(valeur, mini, maxi):
    if maxi == mini:
        return 50.0
    return round((valeur - mini) / (maxi - mini) * 100, 1)


def verdict_vs_moyenne(valeur, moyenne, unite=""):
    """
    Calcule le verdict au-dessus/en dessous/égal EN PYTHON (jamais par le LLM),
    pour éliminer tout risque d'inversion logique par le modèle.
    Retourne un texte prêt à être cité tel quel dans le SWOT.
    """
    if moyenne == 0:
        return "moyenne du secteur non calculable"

    ecart_pct = round((valeur - moyenne) / moyenne * 100)

    if abs(ecart_pct) < 3:  # écart négligeable -> on ne force pas une conclusion trompeuse
        return f"proche de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, écart {ecart_pct:+d}%)"
    elif ecart_pct > 0:
        return f"AU-DESSUS de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"
    else:
        return f"EN DESSOUS de la moyenne du secteur ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"


def calculer_scores(profils: list[dict]) -> list[dict]:
    engagements = [p["engagement_moyen"] for p in profils]
    sentiments = [p["sentiment_positif_pct"] for p in profils]
    frequences = [p["nb_posts"] for p in profils]
    diversites = [p["diversite_ratio"] for p in profils]

    moy_engagement = round(sum(engagements) / len(engagements), 1)
    moy_sentiment = round(sum(sentiments) / len(sentiments), 1)
    moy_frequence = round(sum(frequences) / len(frequences), 1)
    moy_diversite = round(sum(diversites) / len(diversites), 2)

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

        # Preuves chiffrées vs moyenne du secteur (pour le benchmark ASCII)
        p["vs_moyenne_engagement_pct"] = (
            round((p["engagement_moyen"] - moy_engagement) / moy_engagement * 100) if moy_engagement else 0
        )
        p["vs_moyenne_frequence_pct"] = (
            round((p["nb_posts"] - moy_frequence) / moy_frequence * 100) if moy_frequence else 0
        )

        # --- CORRECTIF DU BUG : verdicts déjà tranchés, le LLM ne fait que les citer ---
        p["verdict_engagement"] = verdict_vs_moyenne(p["engagement_moyen"], moy_engagement)
        p["verdict_frequence"] = verdict_vs_moyenne(p["nb_posts"], moy_frequence, " posts")
        p["verdict_sentiment"] = verdict_vs_moyenne(p["sentiment_positif_pct"], moy_sentiment, "%")
        p["verdict_diversite"] = verdict_vs_moyenne(p["diversite_ratio"], moy_diversite)

    profils.sort(key=lambda p: p["score_final"], reverse=True)
    for i, p in enumerate(profils):
        p["priorite"] = i + 1

    moyennes = {
        "moy_engagement": moy_engagement,
        "moy_frequence": moy_frequence,
        "moy_sentiment": moy_sentiment,
        "moy_diversite": moy_diversite,
    }
    return profils, moyennes


# ============================================
# BENCHMARK VISUEL (ASCII, console)
# ============================================

def afficher_benchmark(profils: list[dict]):
    print("\n=== BENCHMARK ENGAGEMENT (barres proportionnelles) ===")
    max_engagement = max(p["engagement_moyen"] for p in profils) or 1
    for p in profils[:10]:
        largeur = int(p["engagement_moyen"] / max_engagement * 30)
        barre = "█" * largeur
        signe = "+" if p["vs_moyenne_engagement_pct"] >= 0 else ""
        print(f"  [{p['priorite']}] {p['nom']:<45} {barre} {p['engagement_moyen']:>6} "
              f"({signe}{p['vs_moyenne_engagement_pct']}% vs moyenne)")


def afficher_score_detaille(profils: list[dict]):
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
# ANALYSE IA — avec preuves obligatoires + SWOT + question métier
# ============================================

PROMPT_TEMPLATE = """Tu es un consultant en intelligence concurrentielle rigoureux.

RÈGLE ABSOLUE N°1 : tu ne dois JAMAIS inventer un fait, un chiffre ou une affirmation qui n'est pas
présent dans les données ci-dessous. Chaque force, faiblesse ou recommandation doit s'appuyer
sur une donnée chiffrée fournie.

RÈGLE ABSOLUE N°2 (IMPORTANT) : chaque profil ci-dessous contient déjà des champs
"verdict_engagement", "verdict_frequence", "verdict_sentiment" et "verdict_diversite" qui
indiquent EXPLICITEMENT si l'agence est "AU-DESSUS" ou "EN DESSOUS" de la moyenne du secteur
pour chaque métrique. Ces verdicts sont DÉJÀ CALCULÉS et CORRECTS.
INTERDICTION FORMELLE de recalculer ou de rejuger toi-même si un chiffre est supérieur ou
inférieur à la moyenne — utilise UNIQUEMENT le verdict déjà fourni, tel quel. Ne dis jamais
"en dessous" si le verdict fourni dit "AU-DESSUS" (et inversement). Ton seul travail est de
citer ces verdicts et de les reformuler en phrases naturelles, pas de les recalculer.

Données du secteur "{domaine}" à "{region}" (moyennes du groupe : engagement {moy_engagement},
fréquence {moy_frequence} posts, sentiment positif {moy_sentiment}%, diversité {moy_diversite}) :
{profils_json}

{question_section}

Pour CHAQUE agence, génère un SWOT basé UNIQUEMENT sur les chiffres et verdicts fournis :
- Forces : maximum 2, chacune doit s'appuyer sur un verdict "AU-DESSUS de la moyenne"
- Faiblesses : maximum 2, chacune doit s'appuyer sur un verdict "EN DESSOUS de la moyenne"
  (si aucun verdict n'est "EN DESSOUS", dis "Aucune faiblesse notable dans les données disponibles")
- Opportunités : basées sur ce que font mieux les autres agences (thèmes non exploités, etc.)
- Menaces : basées sur l'écart avec le leader

Réponds au format JSON STRICT :
{{
  "swot_par_agence": [
    {{
      "priorite": 1,
      "nom": "...",
      "forces": ["... (chiffre: ...)"],
      "faiblesses": ["... (chiffre: ...)"],
      "opportunites": ["..."],
      "menaces": ["..."]
    }}
  ],
  "reponse_question": "réponse détaillée à la question métier posée, basée uniquement sur les chiffres",
  "synthese_secteur": "3-4 phrases de synthèse globale, chiffrée"
}}
"""


def generer_analyse(profils, moyennes, region, domaine, question=None, retries=4):
    if question:
        question_section = f'QUESTION MÉTIER À TRAITER EN PRIORITÉ : "{question}"\nRéponds à cette question de façon détaillée et chiffrée dans le champ "reponse_question".'
    else:
        question_section = ('QUESTION MÉTIER PAR DÉFAUT : "Pourquoi l\'agence en priorité 1 est-elle devant les autres, '
                             'et comment les agences classées 2 et 3 pourraient-elles la rattraper ?"\n'
                             'Réponds à cette question dans le champ "reponse_question".')

    prompt = PROMPT_TEMPLATE.format(
        domaine=domaine, region=region,
        moy_engagement=moyennes["moy_engagement"], moy_frequence=moyennes["moy_frequence"],
        moy_sentiment=moyennes["moy_sentiment"], moy_diversite=moyennes["moy_diversite"],
        profils_json=json.dumps(profils, ensure_ascii=False, indent=2),
        question_section=question_section,
    )

    import time

    for tentative in range(1, retries + 1):
        try:
            response = client_groq.chat.completions.create(
                model=MODELE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},  # force une sortie JSON valide
            )

            choix = response.choices[0]
            texte = (choix.message.content or "").strip()
            texte = texte.replace("```json", "").replace("```", "").strip()

            if not texte:
                print(f"  ⚠ Tentative {tentative}/{retries} : réponse vide "
                      f"(finish_reason={choix.finish_reason}). Nouvelle tentative...")
                time.sleep(2)
                continue

            return json.loads(texte)

        except json.JSONDecodeError as e:
            print(f"  ⚠ Tentative {tentative}/{retries} : JSON invalide ({e}).")
            print(f"  Début de la réponse reçue : {texte[:300]!r}")
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ Tentative {tentative}/{retries} : erreur Groq : {e}")
            time.sleep(min(2 ** tentative, 20))

    raise RuntimeError(
        "Impossible d'obtenir une réponse JSON valide de Groq après "
        f"{retries} tentatives. Vérifie ta clé API, ton quota, et que le "
        "modèle utilisé supporte bien response_format=json_object."
    )


# ============================================
# VALIDATION POST-GÉNÉRATION (garde-fou supplémentaire)
# ============================================

def valider_coherence_swot(resultat: dict, profils: list[dict]) -> list[str]:
    """
    Double-vérification automatique : signale si un texte du SWOT contient
    "en dessous" ou "au-dessus" qui contredirait les verdicts calculés.
    Ne bloque pas l'affichage, mais alerte pour vérification manuelle.
    """
    alertes = []
    profils_par_nom = {p["nom"]: p for p in profils}

    for s in resultat.get("swot_par_agence", []):
        profil = profils_par_nom.get(s["nom"])
        if not profil:
            continue

        texte_complet = " ".join(s.get("forces", []) + s.get("faiblesses", [])).lower()

        if "en dessous" in texte_complet and "AU-DESSUS" in profil["verdict_engagement"] + profil["verdict_frequence"]:
            # heuristique simple : si le texte dit "en dessous" alors que TOUT est au-dessus, c'est suspect
            if "AU-DESSUS" in profil["verdict_engagement"] and "AU-DESSUS" in profil["verdict_frequence"]:
                alertes.append(f"⚠ Vérifie manuellement le SWOT de '{s['nom']}' : le texte mentionne "
                                f"'en dessous' alors que engagement ET fréquence sont au-dessus de la moyenne.")

    return alertes


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main(region: str, domaine: str, question: str = None):
    print(f"Recherche des agences dans la région '{region}', domaine '{domaine}'...")
    noms_agences = filtrer_agences(region, domaine)
    if not noms_agences:
        print("Aucune agence trouvée avec ces critères.")
        return
    print(f"{len(noms_agences)} agences trouvées.\n")

    rows_posts = charger_posts()
    profils_bruts = [profil_brut(rows_posts, nom) for nom in noms_agences]
    profils_bruts = [p for p in profils_bruts if p]

    profils, moyennes = calculer_scores(profils_bruts)

    afficher_benchmark(profils)
    afficher_score_detaille(profils)

    print(f"\nMoyennes du secteur — Engagement: {moyennes['moy_engagement']} | "
          f"Fréquence: {moyennes['moy_frequence']} posts | "
          f"Sentiment positif: {moyennes['moy_sentiment']}% | "
          f"Diversité: {moyennes['moy_diversite']}")

    print("\nGénération de l'analyse SWOT + réponse métier via l'agent...\n")
    resultat = generer_analyse(profils, moyennes, region, domaine, question)

    # Garde-fou : vérifie la cohérence du texte généré vs les verdicts calculés
    alertes = valider_coherence_swot(resultat, profils)
    if alertes:
        print("=" * 70)
        print("⚠️  ALERTES DE COHÉRENCE (à vérifier avant d'utiliser ce résultat)")
        print("=" * 70)
        for a in alertes:
            print(a)
        print()

    print("=" * 70)
    print(f"ANALYSE SECTORIELLE — {domaine.upper()} À {region.upper()}")
    print("=" * 70)

    for s in resultat["swot_par_agence"]:
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
        args = args[:idx]

    region = args[0] if len(args) > 0 else "Sousse"
    domaine = args[1] if len(args) > 1 else "marketing"
    main(region, domaine, question)