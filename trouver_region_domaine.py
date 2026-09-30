"""
Pour chaque agence de posts_analyzed.csv, cherche sa ville et sa catégorie/domaine
via Google Maps (Apify), et sauvegarde le résultat dans agences_region_domaine.csv.

Installation : pip install apify-client
Usage : py trouver_region_domaine.py posts_analyzed.csv
"""

import csv
import sys
from apify_client import ApifyClient
APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN","")
client = ApifyClient(APIFY_TOKEN)


def lire_noms_agences(chemin_csv: str) -> list[str]:
    with open(chemin_csv, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    noms = sorted(set(r["agence"].strip() for r in rows if r.get("agence", "").strip()))
    print(f"{len(noms)} agences uniques trouvées dans {chemin_csv}.")
    return noms


def chercher_region_domaine(noms_agences: list[str]) -> dict:
    """
    Lance une recherche Google Maps pour chaque agence (nom + Tunisie),
    et retourne {nom_agence: {"ville": ..., "domaine": ...}}
    """
    run_input = {
        "searchStringsArray": [f"{nom} Tunisie" for nom in noms_agences],
        "locationQuery": "Tunisia",
        "countryCode": "tn",
        "maxCrawledPlacesPerSearch": 1,  # on veut juste le meilleur résultat
        "language": "fr",
    }

    print(f"Lancement de la recherche Google Maps pour {len(noms_agences)} agences...")
    run = client.actor("compass/crawler-google-places").call(run_input=run_input)
    items = list(client.dataset(run.default_dataset_id).iterate_items())

    resultats = {}
    for item in items:
        titre_trouve = item.get("title", "")
        # Retrouve à quelle agence de départ ce résultat correspond
        # (on matche sur le nom contenu dans le titre trouvé, au cas où ce n'est pas exact)
        for nom in noms_agences:
            if nom.lower() in titre_trouve.lower() or titre_trouve.lower() in nom.lower():
                resultats[nom] = {
                    "ville": item.get("city", "") or item.get("address", "").split(",")[-1].strip(),
                    "domaine": item.get("categoryName", ""),
                    "adresse_complete": item.get("address", ""),
                }
                break

    return resultats


def sauvegarder(noms_agences: list[str], resultats: dict, chemin_sortie: str = "agences_region_domaine.csv"):
    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["agence", "ville", "domaine", "adresse_complete"])
        writer.writeheader()
        for nom in noms_agences:
            info = resultats.get(nom, {})
            writer.writerow({
                "agence": nom,
                "ville": info.get("ville", ""),
                "domaine": info.get("domaine", ""),
                "adresse_complete": info.get("adresse_complete", ""),
            })

    trouves = sum(1 for nom in noms_agences if nom in resultats)
    print(f"\n{trouves}/{len(noms_agences)} agences localisées avec succès.")
    print(f"Sauvegardé dans {chemin_sortie}")
    print("\n⚠️ Vérifie manuellement les lignes vides ou incorrectes avant de continuer,")
    print("   certaines agences peuvent ne pas être trouvables sur Google Maps.")


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "posts_analyzed.csv"
    noms = lire_noms_agences(chemin)
    resultats = chercher_region_domaine(noms)
    sauvegarder(noms, resultats)
