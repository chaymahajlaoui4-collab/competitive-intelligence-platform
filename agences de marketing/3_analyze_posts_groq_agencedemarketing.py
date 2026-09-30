"""
========================================================================
 ETAPE 3 : Analyser les posts (Instagram + Facebook) avec Groq
========================================================================

Ce script part du fichier fusionné et nettoyé (posts_media_bruts.csv)
et fait analyser chaque post par un LLM (via Groq) pour en extraire :
langue, type de contenu, thème, service mis en avant, objectif,
hashtags clés, sentiment.

IMPORTANT : ce script sauvegarde son résultat AU FUR ET A MESURE
(après chaque post) et REPREND automatiquement là où il s'était
arrêté si tu le relances après une coupure de connexion. Tu peux
donc relancer la même commande sans rien perdre ni repayer ce qui
a déjà été analysé.

INPUT  : posts_media_bruts.csv
         colonnes attendues : agence, source, texte, likes,
         commentaires, partages, date, url, hashtags

OUTPUT : posts_analyzed.csv
         = mêmes colonnes + langue, type_contenu, theme, service,
           objectif, hashtags_analyse, sentiment

PREREQUIS :
    pip install groq

CONFIGURATION :
    set GROQ_API_KEY=ta_clef_groq                       (Windows cmd)
    $env:GROQ_API_KEY="ta_clef_groq"                     (PowerShell)

USAGE :
    python 3_analyze_posts_groq.py
    ou
    python 3_analyze_posts_groq.py mon_fichier.csv
========================================================================
"""

import csv
import json
import os
import sys
import time

from groq import Groq

INPUT_FILE_DEFAULT = "posts_media_bruts.csv"
OUTPUT_FILE = "posts_analyzed.csv"
MODEL = "openai/gpt-oss-20b"  # quota séparé de gpt-oss-120b, pour continuer sans attendre

# Colonne utilisée comme identifiant unique d'un post pour la reprise.
# On combine agence+source+texte tronqué pour éviter les collisions.
ID_COLUMNS = ["agence", "source", "url"]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    print("ERREUR : la variable d'environnement GROQ_API_KEY n'est pas définie.")
    print('Tape d\'abord : set GROQ_API_KEY=ta_clef_groq')
    sys.exit(1)

client = Groq(api_key=GROQ_API_KEY)

PROMPT_TEMPLATE = """
Tu es un analyste marketing spécialisé dans les agences digitales tunisiennes.

Analyse ce post {source}.

Retourne uniquement un JSON, sans aucun texte autour, avec ce format exact :

{{
"langue":"",
"type_contenu":"",
"theme":"",
"service":"",
"objectif":"",
"hashtags":[],
"sentiment":""
}}

Post:
{post_content}
"""

DEFAULT_ANALYSIS = {
    "langue": "",
    "type_contenu": "",
    "theme": "",
    "service": "",
    "objectif": "",
    "hashtags": [],
    "sentiment": "",
}

OUTPUT_FIELDNAMES = [
    "agence", "source", "texte", "likes", "commentaires", "partages",
    "date", "url", "hashtags", "langue", "type_contenu", "theme",
    "service", "objectif", "hashtags_analyse", "sentiment",
]


def post_id(row):
    """Identifiant unique et stable d'un post, pour savoir s'il a déjà été traité."""
    return "|".join(str(row.get(col, "")) for col in ID_COLUMNS)


def load_already_done(output_file):
    """
    Si le fichier de sortie existe déjà (run précédent interrompu),
    on récupère les identifiants des posts déjà analysés pour les
    sauter cette fois-ci.
    """
    done = set()
    if not os.path.exists(output_file):
        return done

    with open(output_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add(post_id(row))

    return done


def build_post_content(row):
    texte = row.get("texte", "") or ""
    hashtags = row.get("hashtags", "") or ""
    likes = row.get("likes", "") or ""
    commentaires = row.get("commentaires", "") or ""
    partages = row.get("partages", "") or ""

    parts = [f"Texte: {texte}"]
    if hashtags:
        parts.append(f"Hashtags: {hashtags}")
    if likes:
        parts.append(f"Likes: {likes}")
    if commentaires:
        parts.append(f"Commentaires: {commentaires}")
    if partages:
        parts.append(f"Partages: {partages}")

    return "\n".join(parts)


def analyze_post(post_content, source, retries=5):
    prompt = PROMPT_TEMPLATE.format(source=source, post_content=post_content)

    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                # Une légère température évite de reproduire indéfiniment
                # la même sortie invalide en cas d'échec de validation JSON.
                temperature=0 if attempt == 1 else 0.3,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content), True

        except json.JSONDecodeError:
            print("  Réponse JSON invalide (côté client), nouvelle tentative...")
            time.sleep(1)

        except Exception as e:
            error_text = str(e)

            if "json_validate_failed" in error_text:
                # Erreur de contenu (le modèle a mal généré) : pas la peine
                # d'attendre longtemps, un court délai + un peu de température suffit.
                print(f"  Erreur de validation JSON (tentative {attempt}/{retries}), nouvelle tentative rapide...")
                time.sleep(1)
            else:
                # Erreur réseau / rate limit / serveur : backoff exponentiel classique.
                wait = min(2 ** attempt, 30)
                print(f"  Erreur Groq (tentative {attempt}/{retries}) : {e}")
                print(f"  Attente de {wait}s avant de réessayer...")
                time.sleep(wait)

    # Toutes les tentatives ont échoué : on renvoie une valeur vide
    # ET on signale l'échec pour que ce post soit retraité au prochain lancement.
    return dict(DEFAULT_ANALYSIS), False


def process_csv(input_file, output_file=OUTPUT_FILE):
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Le fichier d'entrée est vide.")
        return

    already_done = load_already_done(output_file)
    if already_done:
        print(f"Reprise détectée : {len(already_done)} posts déjà analysés, ils seront sautés.")

    # Ouvre le fichier de sortie en mode "ajout" (append), et écrit
    # l'en-tête seulement s'il n'existe pas encore.
    file_exists = os.path.exists(output_file)
    out_f = open(output_file, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=OUTPUT_FIELDNAMES, extrasaction="ignore")
    if not file_exists:
        writer.writeheader()

    total = len(rows)
    a_traiter = [row for row in rows if post_id(row) not in already_done]
    print(f"{len(a_traiter)}/{total} posts restants à analyser.")

    echecs = 0

    try:
        for i, row in enumerate(a_traiter, start=1):
            agence = row.get("agence", "") or "?"
            source = row.get("source", "") or "post"

            print(f"[{i}/{len(a_traiter)}] {agence} ({source})...")

            post_content = build_post_content(row)
            analysis, success = analyze_post(post_content, source)

            if not success:
                echecs += 1

            merged = dict(row)
            merged["langue"] = analysis.get("langue", "")
            merged["type_contenu"] = analysis.get("type_contenu", "")
            merged["theme"] = analysis.get("theme", "")
            merged["service"] = analysis.get("service", "")
            merged["objectif"] = analysis.get("objectif", "")
            merged["hashtags_analyse"] = ", ".join(analysis.get("hashtags", []) or [])
            merged["sentiment"] = analysis.get("sentiment", "")

            # On n'écrit dans le fichier QUE si l'analyse a réussi.
            # Comme ça, un post en échec n'est jamais marqué "déjà fait"
            # et sera automatiquement retenté au prochain lancement.
            if success:
                writer.writerow(merged)
                out_f.flush()  # écrit immédiatement sur le disque

            time.sleep(0.5)  # respecter les limites de débit de l'API

    finally:
        out_f.close()

    print("----------------------------------------")
    if echecs:
        print(f"⚠ {echecs} posts ont échoué après plusieurs tentatives.")
        print("  Relance simplement la même commande pour les retraiter :")
        print(f"  python {os.path.basename(sys.argv[0])} {input_file}")
    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE_DEFAULT
    process_csv(input_file)