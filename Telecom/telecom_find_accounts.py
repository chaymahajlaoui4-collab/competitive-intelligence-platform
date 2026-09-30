"""
Secteur Télécommunications Tunisie — pas de découverte Google Maps nécessaire
(seulement 3 opérateurs connus), on va directement chercher leurs comptes sociaux.

Installation : pip install apify-client
Usage : py telecom_find_accounts.py
"""

import csv
from apify_client import ApifyClient

APIFY_TOKEN = os.environ.get("APIFY_TOKEN","")
client = ApifyClient(APIFY_TOKEN)

# Les 3 opérateurs télécom tunisiens (liste fixe, pas de découverte nécessaire)
OPERATEURS = [
    "Ooredoo Tunisie",
    "Orange Tunisie",
    "Tunisie Telecom",
]


def chercher_comptes_sociaux(noms_operateurs: list[str]) -> dict:
    """
    Cherche les comptes Instagram ET Facebook de chaque opérateur en une fois.
    Retourne {nom: {"instagram_url": ..., "facebook_url": ...}}
    """
    # Une requête par opérateur ET par réseau (6 requêtes au total pour 3 opérateurs)
    queries = []
    for nom in noms_operateurs:
        queries.append(f"{nom} instagram officiel")
        queries.append(f"{nom} facebook officiel")

    run_input = {
        "queries": "\n".join(queries),
        "resultsPerPage": 10,
        "maxPagesPerQuery": 1,
        "countryCode": "tn",
        "languageCode": "fr",
    }

    print(f"Recherche des comptes sociaux pour {len(noms_operateurs)} opérateurs...")
    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    pages = list(client.dataset(run.default_dataset_id).iterate_items())

    resultats = {nom: {"instagram_url": "", "facebook_url": ""} for nom in noms_operateurs}

    for page in pages:
        query_originale = page.get("searchQuery", {}).get("term", "")

        for nom in noms_operateurs:
            if nom.lower() not in query_originale.lower():
                continue

            for result in page.get("organicResults", []):
                url = result.get("url", "")
                if "instagram" in query_originale.lower() and "instagram.com" in url and not resultats[nom]["instagram_url"]:
                    resultats[nom]["instagram_url"] = url
                elif "facebook" in query_originale.lower() and "facebook.com" in url and not resultats[nom]["facebook_url"]:
                    resultats[nom]["facebook_url"] = url

    return resultats


def sauvegarder(resultats: dict, chemin_sortie: str = "telecom_comptes_sociaux.csv"):
    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["operateur", "instagram_url", "facebook_url"])
        writer.writeheader()
        for nom, comptes in resultats.items():
            writer.writerow({
                "operateur": nom,
                "instagram_url": comptes["instagram_url"],
                "facebook_url": comptes["facebook_url"],
            })

    print(f"\nSauvegardé dans {chemin_sortie}")
    for nom, comptes in resultats.items():
        print(f"  {nom} : Instagram={'OK' if comptes['instagram_url'] else 'MANQUANT'}, "
              f"Facebook={'OK' if comptes['facebook_url'] else 'MANQUANT'}")
    print("\n⚠️ Vérifie manuellement les URLs trouvées avant de scraper —")
    print("   avec seulement 3 opérateurs, une vérification rapide (2 min) garantit des données fiables.")


if __name__ == "__main__":
    resultats = chercher_comptes_sociaux(OPERATEURS)
    sauvegarder(resultats)
