"""
========================================================================
 ETAPE 1bis : Trouver les pages Facebook des agences marketing
========================================================================

Même principe que la recherche Instagram, mais pour Facebook.

INPUT  : agences_marketing.csv
         colonnes attendues : title, category, address, city, website

OUTPUT : agences_avec_facebook.csv
         = mêmes colonnes + une colonne "facebook_url"
         (vide si aucune page n'a été trouvée)

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    set APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxx      (Windows cmd)
    $env:APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxx"   (PowerShell)

USAGE :
    python 1b_find_facebook.py
========================================================================
"""

import csv
import os
import re
import sys
from apify_client import ApifyClient

INPUT_FILE = "agences_marketing.csv"
OUTPUT_FILE = "agences_avec_facebook.csv"

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


def clean_facebook_url(url):
    """
    Garde uniquement les pages Facebook (profils/pages).
    Supprime les liens vers des posts, photos, vidéos, groupes, events...
    """
    if not url:
        return None

    if "facebook.com" not in url:
        return None

    exclude_patterns = [
        "/posts/",
        "/photos/",
        "/videos/",
        "/photo.php",
        "/watch/",
        "/groups/",
        "/events/",
        "/story.php",
        "/reel/",
        "/reels/",
        "/permalink.php",
    ]
    for pattern in exclude_patterns:
        if pattern in url:
            return None

    return url.split("?")[0]


def search_facebook(companies):
    """
    Utilise l'acteur Apify 'google-search-scraper' pour trouver
    une page Facebook probable pour chaque agence.
    """
    queries = "\n".join(
        f'site:facebook.com "{company}" Tunisie agence marketing'
        for company in companies
    )

    run_input = {
        "queries": queries,
        "resultsPerPage": 10,
        "maxPagesPerQuery": 1,
        "countryCode": "tn",
        "languageCode": "fr",
    }

    print(f"Lancement de la recherche pour {len(companies)} agences...")

    run = client.actor("apify/google-search-scraper").call(run_input=run_input)

    data = list(client.dataset(get_dataset_id(run)).iterate_items())

    results = {}

    for item in data:
        query = item.get("searchQuery", {}).get("term", "")

        # Extrait le texte entre guillemets, ex:
        # 'site:facebook.com "MUSE Agency" Tunisie agence marketing' -> "MUSE Agency"
        match = re.search(r'"([^"]+)"', query)
        company = match.group(1) if match else query

        fb = None
        for result in item.get("organicResults", []):
            url = result.get("url", "")
            clean = clean_facebook_url(url)
            if clean:
                fb = clean
                break

        results[company] = fb

        if fb:
            print(f"  ✓ {company} -> {fb}")
        else:
            print(f"  ✗ {company} -> aucune page trouvée")

    return results


def process_csv(input_file, output_file):
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Le fichier d'entrée est vide.")
        return

    companies = [row["title"].strip() for row in rows if row["title"].strip()]

    facebook_results = search_facebook(companies)

    for row in rows:
        name = row["title"].strip()
        row["facebook_url"] = facebook_results.get(name, "") or ""

    fieldnames = list(rows[0].keys())
    if "facebook_url" not in fieldnames:
        fieldnames.append("facebook_url")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    trouves = sum(1 for row in rows if row.get("facebook_url"))
    print("----------------------------------------")
    print(f"{trouves}/{len(rows)} pages Facebook trouvées")
    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    process_csv(INPUT_FILE, OUTPUT_FILE)
