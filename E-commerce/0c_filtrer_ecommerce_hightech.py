"""
========================================================================
 ETAPE 0c : Réduire le dataset e-commerce au périmètre exploitable
             Sous-secteur retenu : High-tech / Électronique
========================================================================

Filtre ecommerce_urls_final.csv sur 3 critères combinés :
  1. Catégorie dans le périmètre High-tech (informatique, électronique,
     téléphonie mobile, électroménager) — cohérent avec Mytek/Tunisianet/
     Batam déjà vérifiés manuellement
  2. Ville dans les grandes villes tunisiennes (évite les 116 villes
     dispersées, garde un périmètre comparable aux autres secteurs)
  3. Au moins une URL sociale trouvée (facebook_url OU instagram_url) —
     sinon rien à scraper/analyser de toute façon

INPUT  : ecommerce_urls_final.csv
OUTPUT : ecommerce_hightech_final.csv

USAGE :
    py 0c_filtrer_ecommerce_hightech.py
========================================================================
"""

import csv

INPUT_FILE = "ecommerce_urls_final.csv"
OUTPUT_FILE = "ecommerce_hightech_final.csv"

CATEGORIES_GARDEES = [
    "magasin d'informatique",
    "magasin d'électronique",
    "magasin de téléphonie mobile",
    "magasin d'électroménager",
]

VILLES_GARDEES = [
    "tunis", "sousse", "sfax", "ariana", "monastir", "nabeul",
    "bizerte", "houmt souk", "ksar hellal", "téboulba", "teboulba",
    "mahdia", "moknine", "ksour essef", "ras jebel", "marsa",
    "le kef", "kef", "sayada", "bekalta", "khniss", "djerba midun",
    "zarzis", "siliana", "ksibet el médiouni", "ksibet el mediouni",
    "dahmani", "kairouan", "menzel bourguiba", "bennane",
    "ben arous", "hammam sousse", "menzel jemil",
]

# Comptes déjà vérifiés manuellement — toujours gardés même si la ville/catégorie
# ne matche pas exactement (au cas où Google Maps les aurait mal classés)
NOMS_TOUJOURS_GARDES = ["mytek", "tunisianet", "batam"]


def categorie_ok(categorie: str) -> bool:
    cat = (categorie or "").strip().lower()
    return any(c in cat for c in CATEGORIES_GARDEES)


def ville_ok(ville: str) -> bool:
    v = (ville or "").strip().lower()
    return any(vg in v for vg in VILLES_GARDEES)


def nom_prioritaire(nom: str) -> bool:
    n = (nom or "").strip().lower()
    return any(np in n for np in NOMS_TOUJOURS_GARDES)


def a_un_reseau_social(row: dict) -> bool:
    return bool(row.get("facebook_url", "").strip()) or bool(row.get("instagram_url", "").strip())


def filtrer(chemin_entree: str, chemin_sortie: str):
    with open(chemin_entree, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))

    print(f"{len(rows)} entreprises avant filtrage.")

    gardees = []
    vus = set()

    for r in rows:
        titre = r.get("title", "").strip()
        titre_norm = titre.lower()
        if not titre or titre_norm in vus:
            continue

        prioritaire = nom_prioritaire(titre)

        if not prioritaire:
            if not categorie_ok(r.get("category", "")):
                continue
            if not ville_ok(r.get("city", "")):
                continue
            if not a_un_reseau_social(r):
                continue

        vus.add(titre_norm)
        gardees.append(r)

    print(f"{len(gardees)} entreprises conservées après filtrage combiné.")

    if not gardees:
        print("Aucune entreprise conservée — vérifie tes critères (catégories/villes trop strictes ?).")
        return

    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(gardees)

    print(f"\nSauvegardé dans {chemin_sortie}")

    # Petit résumé pour vérification rapide
    print("\nAperçu des entreprises retenues :")
    for r in gardees[:15]:
        fb = "FB" if r.get("facebook_url", "").strip() else "  "
        ig = "IG" if r.get("instagram_url", "").strip() else "  "
        print(f"  [{fb}|{ig}] {r['title']} — {r.get('category','')} — {r.get('city','')}")
    if len(gardees) > 15:
        print(f"  ... et {len(gardees) - 15} de plus")


if __name__ == "__main__":
    filtrer(INPUT_FILE, OUTPUT_FILE)
