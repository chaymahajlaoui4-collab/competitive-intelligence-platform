"""
========================================================================
 ETAPE 1 : Trouver les comptes Instagram des agences marketing
========================================================================

Ce script part de la liste d'agences marketing tunisiennes (nettoyée à
l'étape 0) et cherche, pour chacune, son compte Instagram via une
recherche Google (site:instagram.com "Nom Agence").

INPUT  : agences_marketing.csv
         colonnes attendues : title, category, address, city, website

OUTPUT : agences_avec_instagram.csv
         = mêmes colonnes + une colonne "instagram_url"
         (vide si aucun compte n'a été trouvé)

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    Il faut un token API Apify (https://console.apify.com -> Settings ->
    Integrations -> Personal API token).
    Définis-le AVANT de lancer le script, dans le terminal :

        set APIFY_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxx      (Windows cmd)
        $env:APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxx"   (PowerShell)

USAGE :
    python 1_find_instagram.py
========================================================================
"""

import csv
import os
import re
import sys
from apify_client import ApifyClient

INPUT_FILE = "agences_marketing.csv"
OUTPUT_FILE = "agences_avec_instagram.csv"

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


def clean_instagram_url(url):
    """
    Garde uniquement les profils Instagram.
    Supprime les liens vers des posts (/p/) et des reels (/reel/).
    """
    if not url:
        return None

    if "instagram.com" not in url:
        return None

    if "/p/" in url:
        return None

    if "/reel/" in url or "/reels/" in url:
        return None

    return url.split("?")[0]


def search_instagram(companies):
    """
    Utilise l'acteur Apify 'google-search-scraper' pour trouver
    un lien Instagram probable pour chaque agence.
    """
    queries = "\n".join(
        f'site:instagram.com "{company}" Tunisie agence marketing'
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
        # 'site:instagram.com "MUSE Agency" Tunisie agence marketing' -> "MUSE Agency"
        match = re.search(r'"([^"]+)"', query)
        company = match.group(1) if match else query

        insta = None
        for result in item.get("organicResults", []):
            url = result.get("url", "")
            clean = clean_instagram_url(url)
            if clean:
                insta = clean
                break

        results[company] = insta

        if insta:
            print(f"  ✓ {company} -> {insta}")
        else:
            print(f"  ✗ {company} -> aucun compte trouvé")

    return results


def process_csv(input_file, output_file):
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Le fichier d'entrée est vide.")
        return

    companies = [row["title"].strip() for row in rows if row["title"].strip()]

    instagram_results = search_instagram(companies)

    for row in rows:
        name = row["title"].strip()
        row["instagram_url"] = instagram_results.get(name, "") or ""

    fieldnames = list(rows[0].keys())
    if "instagram_url" not in fieldnames:
        fieldnames.append("instagram_url")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    trouves = sum(1 for row in rows if row.get("instagram_url"))
    print("----------------------------------------")
    print(f"{trouves}/{len(rows)} comptes Instagram trouvés")
    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    process_csv(INPUT_FILE, OUTPUT_FILE)