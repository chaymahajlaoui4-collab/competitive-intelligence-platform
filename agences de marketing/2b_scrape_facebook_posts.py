"""
========================================================================
 ETAPE 2bis : Scraper les posts Facebook des agences marketing
========================================================================

Ce script part de la liste des pages Facebook trouvées à l'étape 1bis
et récupère leurs derniers posts (texte, likes, commentaires, partages...)

INPUT  : agences_avec_facebook.csv
         (doit contenir une colonne "facebook_url")

OUTPUT : facebook_posts.csv

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    set APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxx      (Windows cmd)
    $env:APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxx"   (PowerShell)

USAGE :
    python 2b_scrape_facebook_posts.py
========================================================================
"""

import csv
import os
import sys
from apify_client import ApifyClient

INPUT_FILE = "agences_avec_facebook.csv"
OUTPUT_FILE = "facebook_posts.csv"
POSTS_PAR_PAGE = 20

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


def load_facebook_urls(file):
    urls = []
    with open(file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("facebook_url") or "").strip()
            if url:
                urls.append(url)
    return urls


def scrape_posts(urls, results_limit=POSTS_PAR_PAGE):
    if not urls:
        print("Aucune URL Facebook trouvée dans le fichier d'entrée.")
        return []

    # L'acteur facebook-posts-scraper attend une liste d'objets {"url": ...}
    start_urls = [{"url": url} for url in urls]

    run_input = {
        "startUrls": start_urls,
        "resultsLimit": results_limit,
    }

    print(f"Scraping de {len(urls)} pages Facebook ({results_limit} posts max par page)...")

    run = client.actor("apify/facebook-posts-scraper").call(run_input=run_input)

    posts = list(client.dataset(get_dataset_id(run)).iterate_items())

    return posts


def save(posts, output_file=OUTPUT_FILE):
    if not posts:
        print("Aucun post récupéré, rien à sauvegarder.")
        return

    # On collecte l'ensemble des clés présentes dans tous les posts
    # (les posts Facebook n'ont pas toujours exactement les mêmes champs)
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
    urls = load_facebook_urls(INPUT_FILE)
    print(f"{len(urls)} pages Facebook à scraper.")

    posts = scrape_posts(urls)
    save(posts)

    print("----------------------------------------")
    print(len(posts), "posts au total récupérés")
