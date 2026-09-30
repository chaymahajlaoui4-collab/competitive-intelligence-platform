"""
========================================================================
 ETAPE 2 : Scraper les posts Instagram des agences marketing
========================================================================

Ce script part de la liste des comptes Instagram trouvés à l'étape 1
et récupère leurs derniers posts (captions, likes, commentaires, etc.)

INPUT  : agences_avec_instagram.csv
         (doit contenir une colonne "instagram_url")

OUTPUT : instagram_posts.csv

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    set APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxx      (Windows cmd)
    $env:APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxx"   (PowerShell)

USAGE :
    python 2_scrape_instagram_posts.py
========================================================================
"""

import csv
import os
import sys
from apify_client import ApifyClient

INPUT_FILE = "agences_avec_instagram.csv"
OUTPUT_FILE = "instagram_posts.csv"
POSTS_PAR_COMPTE = 20
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print('Tape d\'abord : set APIFY_TOKEN=ton_token_apify')
    sys.exit(1)

client = ApifyClient(APIFY_TOKEN)


def get_dataset_id(run):
    """
    Récupère l'ID du dataset de sortie, que 'run' soit un dict
    (anciennes versions d'apify-client) ou un objet (versions récentes).
    """
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


def load_instagram_urls(file):
    urls = []
    with open(file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("instagram_url") or "").strip()
            if url:
                urls.append(url)
    return urls


def scrape_posts(urls, results_limit=POSTS_PAR_COMPTE):
    if not urls:
        print("Aucune URL Instagram trouvée dans le fichier d'entrée.")
        return []

    run_input = {
        "directUrls": urls,
        "resultsType": "posts",
        "resultsLimit": results_limit,
    }

    print(f"Scraping de {len(urls)} comptes Instagram ({results_limit} posts max par compte)...")

    run = client.actor("apify/instagram-scraper").call(run_input=run_input)

    posts = list(client.dataset(get_dataset_id(run)).iterate_items())

    return posts


def save(posts, output_file=OUTPUT_FILE):
    if not posts:
        print("Aucun post récupéré, rien à sauvegarder.")
        return

    # On collecte l'ensemble des clés présentes dans tous les posts
    # (les posts Instagram n'ont pas toujours exactement les mêmes champs)
    fieldnames = []
    seen = set()
    for post in posts:
        for key in post.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(posts)

    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    urls = load_instagram_urls(INPUT_FILE)
    print(f"{len(urls)} comptes Instagram à scraper.")

    posts = scrape_posts(urls)
    save(posts)

    print("----------------------------------------")
    print(len(posts), "posts au total récupérés")
