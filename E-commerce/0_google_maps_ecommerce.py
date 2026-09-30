"""
========================================================================
 ETAPE 0 : Découvrir les entreprises e-commerce tunisiennes (Google Maps)
========================================================================

Même principe que pour le secteur bancaire/marketing : utilise l'acteur
Apify Google Maps Scraper pour lister des entreprises e-commerce en
Tunisie, à partir de plusieurs requêtes de recherche.

Couverture voulue : TOUTE la Tunisie, sans découpage manuel par région/
ville. Le seul levier pour élargir la couverture ici est donc la liste
de CATEGORIES ci-dessous (Google Maps plafonne chaque requête
indépendamment de la taille de la zone recherchée, donc plus de
requêtes ciblées par catégorie = plus de résultats, sans avoir à
choisir de régions).

⚠️ PIEGE (déjà rencontré sur le bancaire) : sans locationQuery et
countryCode forcés sur "tn", l'acteur géolocalise n'importe où dans le
monde. Les deux sont donc explicitement fixés ici.

INPUT  : aucun (les catégories de recherche sont définies dans
         CATEGORIES ci-dessous — modifie cette liste selon ce que tu
         veux couvrir)

OUTPUT : ecommerce_entreprises.csv
         colonnes : title, category, address, city, website
         (même schéma que agences_marketing.csv, pour rester compatible
         avec 1_find_social_urls_ecommerce.py)

PREREQUIS :
    pip install apify-client

CONFIGURATION :
    set APIFY_TOKEN=ton_token_apify      (Windows cmd)

USAGE :
    py 0_google_maps_ecommerce.py
========================================================================
"""

import csv
import os
import sys
from apify_client import ApifyClient

OUTPUT_FILE = "ecommerce_entreprises.csv"

# Liste de catégories/mots-clés e-commerce à couvrir. Aucune ville n'est
# précisée ici volontairement : locationQuery="Tunisia" + countryCode="tn"
# suffisent à couvrir tout le pays. Pour élargir la couverture, ajoute
# des catégories plutôt que des villes.
CATEGORIES = [
    "boutique en ligne",
    "site e-commerce",
    "vente en ligne",
    "dropshipping",
    "marketplace",
    "livraison à domicile",
    "vente en ligne électroménager",
    "vente en ligne mode",
    "vente en ligne beauté cosmétique",
    "vente en ligne informatique",
    "vente en ligne alimentaire",
    "vente en ligne meubles décoration",
    "vente en ligne accessoires téléphone",
    "vente en ligne sport",
    "vente en ligne enfants jouets",
    "vente en ligne bijoux",
    "boutique en ligne chaussures",
    "achat en ligne Tunisie",
    "commerce électronique Tunisie",
    "e-shop Tunisie",
]

REQUETES = [f"{cat} Tunisie" for cat in CATEGORIES]

# Plafond par requête : Google Maps limite de toute façon le nombre de
# résultats pertinents renvoyés par une requête donnée, donc on met une
# valeur haute pour ne pas couper artificiellement avant cette limite.
MAX_RESULTATS_PAR_REQUETE = 300

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print('Tape d\'abord : set APIFY_TOKEN=ton_token_apify')
    sys.exit(1)

client = ApifyClient(APIFY_TOKEN)


def get_dataset_id(run):
    """Compatible avec les deux versions d'apify-client (dict ou objet)."""
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


def scraper_google_maps(requetes, max_par_requete):
    run_input = {
        "searchStringsArray": requetes,
        "locationQuery": "Tunisia",
        "countryCode": "tn",
        "maxCrawledPlacesPerSearch": max_par_requete,
        "language": "fr",
    }

    print(f"Lancement du Google Maps Scraper pour {len(requetes)} requêtes (couverture nationale)...")
    run = client.actor("compass/crawler-google-places").call(run_input=run_input)
    items = list(client.dataset(get_dataset_id(run)).iterate_items())
    print(f"{len(items)} résultats bruts récupérés.")
    return items


def nettoyer_et_dedupliquer(items):
    lignes = []
    vus = set()

    for item in items:
        nom = (item.get("title") or "").strip()
        adresse = (item.get("address") or "").strip()
        if not nom:
            continue

        # Dédoublonnage sur (nom + adresse) plutôt que nom seul, pour ne
        # pas fusionner par erreur deux enseignes homonymes dans des
        # villes différentes.
        cle = (nom.lower(), adresse.lower())
        if cle in vus:
            continue
        vus.add(cle)

        lignes.append({
            "title": nom,
            "category": item.get("categoryName", "") or "",
            "address": adresse,
            "city": item.get("city", "") or "",
            "website": item.get("website", "") or "",
        })

    return lignes


def sauvegarder(lignes, chemin_sortie):
    if not lignes:
        print("Aucune entreprise à sauvegarder.")
        return

    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "category", "address", "city", "website"])
        writer.writeheader()
        writer.writerows(lignes)

    print("----------------------------------------")
    print(f"{len(lignes)} entreprises e-commerce uniques -> {chemin_sortie}")


if __name__ == "__main__":
    items = scraper_google_maps(REQUETES, MAX_RESULTATS_PAR_REQUETE)
    lignes = nettoyer_et_dedupliquer(items)
    sauvegarder(lignes, OUTPUT_FILE)