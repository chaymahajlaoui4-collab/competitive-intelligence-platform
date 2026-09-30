"""
========================================================================
 ETAPE 1 : Trouver les comptes Instagram, Facebook et LinkedIn
           des entreprises e-commerce
========================================================================

Même principe que 1_find_instagram.py (secteur marketing), généralisé
à 3 plateformes au lieu d'une seule : pour chaque entreprise, une
recherche Google par plateforme (site:instagram.com / site:facebook.com
/ site:linkedin.com).

INPUT  : ecommerce_entreprises.csv
         colonnes attendues : title, category, address, city, website
         (sortie de 0_google_maps_ecommerce.py)

OUTPUT : ecommerce_avec_reseaux.csv
         = mêmes colonnes + instagram_url, facebook_url, linkedin_url
         (vide si rien trouvé pour une plateforme donnée)

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    set APIFY_TOKEN=ton_token_apify      (Windows cmd)

USAGE :
    py 1_find_social_urls_ecommerce.py
========================================================================
"""

import csv
import os
import re
import sys
from apify_client import ApifyClient

INPUT_FILE = "ecommerce_entreprises.csv"
OUTPUT_FILE = "ecommerce_avec_reseaux.csv"

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print('Tape d\'abord : set APIFY_TOKEN=ton_token_apify')
    sys.exit(1)

client = ApifyClient(APIFY_TOKEN)

# Une entrée par plateforme : domaine de recherche, nom de la colonne de
# sortie, et motifs d'URL à exclure (posts/reels individuels, pas la page)
PLATEFORMES = {
    "instagram": {
        "domaine": "instagram.com",
        "colonne": "instagram_url",
        "exclure": ["/p/", "/reel/", "/reels/"],
    },
    "facebook": {
        "domaine": "facebook.com",
        "colonne": "facebook_url",
        "exclure": ["/posts/", "/videos/", "/photos/", "/permalink.php"],
    },
    "linkedin": {
        "domaine": "linkedin.com",
        "colonne": "linkedin_url",
        "exclure": ["/posts/", "/pulse/"],
    },
}


def get_dataset_id(run):
    """Compatible avec les deux versions d'apify-client (dict ou objet)."""
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


def clean_url(url, domaine, motifs_exclus):
    if not url or domaine not in url:
        return None
    if any(motif in url for motif in motifs_exclus):
        return None
    return url.split("?")[0]


def search_platform(companies, plateforme_key):
    plateforme = PLATEFORMES[plateforme_key]
    domaine = plateforme["domaine"]

    queries = "\n".join(
        f'site:{domaine} "{company}" Tunisie e-commerce'
        for company in companies
    )

    run_input = {
        "queries": queries,
        "resultsPerPage": 10,
        "maxPagesPerQuery": 1,
        "countryCode": "tn",
        "languageCode": "fr",
    }

    print(f"[{plateforme_key}] Lancement de la recherche pour {len(companies)} entreprises...")
    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    data = list(client.dataset(get_dataset_id(run)).iterate_items())

    results = {}
    for item in data:
        query = item.get("searchQuery", {}).get("term", "")
        match = re.search(r'"([^"]+)"', query)
        company = match.group(1) if match else query

        trouve = None
        for result in item.get("organicResults", []):
            url = result.get("url", "")
            clean = clean_url(url, domaine, plateforme["exclure"])
            if clean:
                trouve = clean
                break

        results[company] = trouve
        print(f"  {'✓' if trouve else '✗'} {company} -> {trouve or 'aucun compte trouvé'}")

    return results


def process_csv(input_file, output_file):
    with open(input_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Le fichier d'entrée est vide.")
        return

    companies = [row["title"].strip() for row in rows if row["title"].strip()]

    resultats_par_plateforme = {}
    for plateforme_key in PLATEFORMES:
        resultats_par_plateforme[plateforme_key] = search_platform(companies, plateforme_key)
        print()

    for row in rows:
        name = row["title"].strip()
        for plateforme_key, plateforme in PLATEFORMES.items():
            colonne = plateforme["colonne"]
            row[colonne] = resultats_par_plateforme[plateforme_key].get(name, "") or ""

    fieldnames = list(rows[0].keys())
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("----------------------------------------")
    for plateforme_key, plateforme in PLATEFORMES.items():
        trouves = sum(1 for row in rows if row.get(plateforme["colonne"]))
        print(f"{plateforme_key} : {trouves}/{len(rows)} comptes trouvés")
    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    process_csv(INPUT_FILE, OUTPUT_FILE)
