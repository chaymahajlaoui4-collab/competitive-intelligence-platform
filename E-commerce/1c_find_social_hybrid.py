"""
========================================================================
 ETAPE 1c : Trouver les URLs Facebook/Instagram (méthode hybride)
========================================================================

Combine deux méthodes pour améliorer le taux de détection par rapport
à la recherche Google seule (152/749 Insta, 99/749 FB) :

  A) Pour les entreprises qui ont un site web propre (colonne
     "website") : on va directement scraper la page d'accueil de ce
     site et en extraire les liens facebook.com / instagram.com
     présents dans le header/footer. Beaucoup plus fiable qu'une
     recherche Google pour ces entreprises-là.

  B) Pour les entreprises restantes (sans site, ou dont le site n'a
     donné aucun lien) : on retombe sur la recherche Google via Apify
     (comme 1_find_instagram.py / 1b_find_facebook.py), avec
     resultsPerPage augmenté à 25 pour élargir la recherche.

INPUT  : ecommerce_clean.csv
         (ou directement ecommerce_avec_instagram.csv /
         ecommerce_avec_facebook.csv si tu veux repartir de ce qui a
         déjà été trouvé plutôt que de tout refaire - voir variable
         REPARTIR_DE_ZERO ci-dessous)

OUTPUT : ecommerce_urls_final.csv
         colonnes d'origine + facebook_url + instagram_url +
         source_facebook / source_instagram ("site_web" ou "google")

PREREQUIS :
    pip install apify-client requests beautifulsoup4

CONFIGURATION :
    set APIFY_TOKEN=ton_token_apify      (Windows cmd)

USAGE :
    py 1c_find_social_hybrid.py ecommerce_clean.csv
========================================================================
"""

import csv
import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from apify_client import ApifyClient

INPUT_DEFAULT = "ecommerce_clean.csv"
OUTPUT_FILE = "ecommerce_urls_final.csv"

# Si True, relance la recherche Google même pour les entreprises qui
# ont déjà une facebook_url/instagram_url dans le fichier d'entrée.
# Mets False pour ne compléter que ce qui manque (économise le quota
# Apify si tu repars de ecommerce_avec_instagram.csv / _facebook.csv).
REPARTIR_DE_ZERO = False

TIMEOUT_SITE = 8  # secondes max par site avant d'abandonner
RESULTS_PER_PAGE_GOOGLE = 25

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print('Tape d\'abord : set APIFY_TOKEN=ton_token_apify')
    sys.exit(1)

client = ApifyClient(APIFY_TOKEN)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ------------------------------------------------------------------
# A. Extraction depuis le site web propre de l'entreprise
# ------------------------------------------------------------------

def clean_facebook_url(url):
    if not url or "facebook.com" not in url:
        return None
    exclude = ["/posts/", "/photos/", "/videos/", "/photo.php", "/watch/",
               "/groups/", "/events/", "/story.php", "/reel/", "/reels/",
               "/permalink.php", "/sharer", "/plugins/"]
    if any(p in url for p in exclude):
        return None
    return url.split("?")[0].rstrip("/")


def clean_instagram_url(url):
    if not url or "instagram.com" not in url:
        return None
    exclude = ["/p/", "/reel/", "/reels/", "/explore/", "/accounts/"]
    if any(p in url for p in exclude):
        return None
    return url.split("?")[0].rstrip("/")


def extraire_liens_reseaux_sociaux(website_url):
    """Va chercher la page d'accueil du site et en extrait les liens
    Facebook/Instagram trouvés dans le HTML (typiquement footer/header)."""
    if not website_url:
        return None, None

    try:
        resp = requests.get(website_url, headers=HEADERS, timeout=TIMEOUT_SITE)
        resp.raise_for_status()
    except requests.RequestException:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    fb, insta = None, None

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not fb:
            fb = clean_facebook_url(href)
        if not insta:
            insta = clean_instagram_url(href)
        if fb and insta:
            break

    return fb, insta


# ------------------------------------------------------------------
# B. Fallback recherche Google via Apify (comme 1_find_instagram.py)
# ------------------------------------------------------------------

def get_dataset_id(run):
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


def recherche_google_fallback(companies, plateforme):
    """plateforme = 'instagram' ou 'facebook'. Retourne {company: url|None}."""
    domaine = f"{plateforme}.com"
    queries = "\n".join(
        f'site:{domaine} "{company}" Tunisie e-commerce'
        for company in companies
    )

    run_input = {
        "queries": queries,
        "resultsPerPage": RESULTS_PER_PAGE_GOOGLE,
        "maxPagesPerQuery": 1,
        "countryCode": "tn",
        "languageCode": "fr",
    }

    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    data = list(client.dataset(get_dataset_id(run)).iterate_items())

    nettoyeur = clean_facebook_url if plateforme == "facebook" else clean_instagram_url
    results = {}

    for item in data:
        query = item.get("searchQuery", {}).get("term", "")
        match = re.search(r'"([^"]+)"', query)
        company = match.group(1) if match else query

        trouve = None
        for result in item.get("organicResults", []):
            clean = nettoyeur(result.get("url", ""))
            if clean:
                trouve = clean
                break
        results[company] = trouve

    return results


# ------------------------------------------------------------------
# Programme principal
# ------------------------------------------------------------------

def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else INPUT_DEFAULT

    with open(input_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Le fichier d'entrée est vide.")
        return

    for row in rows:
        row.setdefault("facebook_url", "")
        row.setdefault("instagram_url", "")
        row["source_facebook"] = ""
        row["source_instagram"] = ""

    if REPARTIR_DE_ZERO:
        for row in rows:
            row["facebook_url"] = ""
            row["instagram_url"] = ""

    # --- ETAPE A : scraping des sites web propres ---
    a_scraper = [r for r in rows if r.get("website") and (not r["facebook_url"] or not r["instagram_url"])]
    print(f"Etape A : scraping de {len(a_scraper)} sites web...")

    for i, row in enumerate(a_scraper, 1):
        fb, insta = extraire_liens_reseaux_sociaux(row["website"])
        if fb and not row["facebook_url"]:
            row["facebook_url"] = fb
            row["source_facebook"] = "site_web"
        if insta and not row["instagram_url"]:
            row["instagram_url"] = insta
            row["source_instagram"] = "site_web"

        if i % 25 == 0:
            print(f"  ... {i}/{len(a_scraper)} sites traités")

    trouve_a_fb = sum(1 for r in rows if r["source_facebook"] == "site_web")
    trouve_a_insta = sum(1 for r in rows if r["source_instagram"] == "site_web")
    print(f"  -> {trouve_a_fb} Facebook et {trouve_a_insta} Instagram trouvés via les sites web.\n")

    # --- ETAPE B : fallback Google pour ce qui manque encore ---
    manque_fb = [r["title"].strip() for r in rows if not r["facebook_url"] and r["title"].strip()]
    manque_insta = [r["title"].strip() for r in rows if not r["instagram_url"] and r["title"].strip()]

    print(f"Etape B : recherche Google fallback -> {len(manque_fb)} Facebook, {len(manque_insta)} Instagram restants...")

    fb_results = recherche_google_fallback(manque_fb, "facebook") if manque_fb else {}
    time.sleep(1)
    insta_results = recherche_google_fallback(manque_insta, "instagram") if manque_insta else {}

    for row in rows:
        name = row["title"].strip()
        if not row["facebook_url"] and fb_results.get(name):
            row["facebook_url"] = fb_results[name]
            row["source_facebook"] = "google"
        if not row["instagram_url"] and insta_results.get(name):
            row["instagram_url"] = insta_results[name]
            row["source_instagram"] = "google"

    # --- Sauvegarde ---
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total_fb = sum(1 for r in rows if r["facebook_url"])
    total_insta = sum(1 for r in rows if r["instagram_url"])
    print("\n----------------------------------------")
    print(f"Total entreprises      : {len(rows)}")
    print(f"Facebook trouvés       : {total_fb}  (site web: {trouve_a_fb}, google: {total_fb - trouve_a_fb})")
    print(f"Instagram trouvés      : {total_insta}  (site web: {trouve_a_insta}, google: {total_insta - trouve_a_insta})")
    print(f"Terminé -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
