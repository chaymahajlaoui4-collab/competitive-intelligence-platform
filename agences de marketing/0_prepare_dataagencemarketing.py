"""
Nettoie le fichier brut issu du scraping Google Maps (Apify)
et produit un fichier simplifié prêt pour la recherche Instagram.

Input:
    dataagencemarketing11.csv   (export brut Apify Google Maps scraper)

Output:
    agences_marketing.csv       (colonnes: title, category, address, city, website)
"""

import csv

INPUT_FILE = "dataagencemarketing11.csv"
OUTPUT_FILE = "agences_marketing.csv"

# Mots-clés à garder dans la catégorie (insensible à la casse)
KEEP_KEYWORDS = [
    "marketing",
    "advertising",
    "digital",
    "communication",
    "branding",
    "social media",
]

# Catégories/mots à exclure explicitement même si "marketing" apparaît ailleurs
EXCLUDE_KEYWORDS = [
    "distance learning",
    "training center",
    "software company",
    "computer support",
    "website designer",
]




def is_relevant(category):
    category_lower = category.lower()

    for excl in EXCLUDE_KEYWORDS:
        if excl in category_lower:
            return False

    for keep in KEEP_KEYWORDS:
        if keep in category_lower:
            return True

    return False


def clean(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    # utf-8-sig pour gérer le BOM présent dans l'export Apify
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Lignes lues : {len(rows)}")

    cleaned_rows = []
    seen_titles = set()

    for row in rows:
        title = (row.get("title") or "").strip()
        category = (row.get("categoryName") or row.get("categories/0") or "").strip()
        address = (row.get("address") or "").strip()
        city = (row.get("city") or "").strip()
        website = (row.get("website") or "").strip()

        if not title:
            continue

        if not is_relevant(category):
            continue

        # évite les doublons (même agence trouvée plusieurs fois)
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        cleaned_rows.append({
            "title": title,
            "category": category,
            "address": address,
            "city": city,
            "website": website,
        })

    print(f"Lignes conservées après filtrage : {len(cleaned_rows)}")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["title", "category", "address", "city", "website"]
        )
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"Terminé -> {output_file}")


if __name__ == "__main__":
    clean()
