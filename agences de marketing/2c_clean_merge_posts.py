"""
========================================================================
 ETAPE 2c : Nettoyer et fusionner les posts Instagram + Facebook
========================================================================

Ce script prend les posts bruts scrapés sur Instagram et Facebook,
les nettoie, les uniformise dans un format commun, retrouve le nom
de l'agence correspondant à chaque compte/page, et fusionne le tout
dans un seul fichier prêt pour l'analyse Groq.

INPUTS :
    agences_avec_instagram.csv   (title -> instagram_url)
    agences_avec_facebook.csv    (title -> facebook_url)
    instagram_posts.csv          (posts bruts Instagram)
    facebook_posts.csv           (posts bruts Facebook)

OUTPUT :
    posts_media_bruts.csv
    colonnes : agence, source, texte, likes, commentaires, partages,
               date, url, hashtags

USAGE :
    python 2c_clean_merge_posts.py
========================================================================
"""

import csv
import re

# Adapte ces noms de fichiers si les tiens sont différents
AGENCES_INSTAGRAM_FILE = "agences_avec_instagram.csv"
AGENCES_FACEBOOK_FILE = "agences_avec_facebook.csv"
INSTAGRAM_POSTS_FILE = "instagram_posts_agencedemarketing.csv"
FACEBOOK_POSTS_FILE = "facebook_posts_agencedemarketing.csv"
OUTPUT_FILE = "posts_media_bruts.csv"


def normalize_url(url):
    """
    Normalise une URL pour pouvoir comparer facilement deux liens
    qui pointent vers le même compte/page malgré des variations
    (http/https, www, slash final, majuscules...).
    """
    if not url:
        return ""
    url = url.strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.rstrip("/")
    return url


def load_agency_lookup(file, url_column):
    """
    Construit un dictionnaire {url_normalisée: nom_agence} à partir
    d'un fichier agences_avec_xxx.csv
    """
    lookup = {}
    with open(file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get(url_column) or "").strip()
            title = (row.get("title") or "").strip()
            if url and title:
                lookup[normalize_url(url)] = title
    return lookup


def find_agency(identifier, lookup):
    """
    Cherche le nom d'agence correspondant à un identifiant
    (username Instagram ou URL Facebook), avec une correspondance
    exacte d'abord, puis une correspondance partielle en secours.
    """
    norm = normalize_url(identifier)
    if norm in lookup:
        return lookup[norm]

    # correspondance partielle (au cas où les URLs ne sont pas
    # identiques à 100% entre les deux fichiers)
    for key, title in lookup.items():
        if key and (key in norm or norm in key):
            return title

    return ""


def clean_instagram_posts(file, agency_lookup):
    cleaned = []

    with open(file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        text = (row.get("caption") or "").strip()
        if not text:
            continue  # on ignore les posts sans texte

        username = (row.get("ownerUsername") or "").strip()
        agency = find_agency(f"instagram.com/{username}", agency_lookup)

        cleaned.append({
            "agence": agency,
            "source": "instagram",
            "texte": text,
            "likes": row.get("likesCount", "") or "0",
            "commentaires": row.get("commentsCount", "") or "0",
            "partages": "",  # Instagram ne fournit pas ce chiffre
            "date": row.get("timestamp", ""),
            "url": row.get("url", ""),
            "hashtags": row.get("hashtags", ""),
        })

    return cleaned


def clean_facebook_posts(file, agency_lookup):
    cleaned = []

    with open(file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue  # on ignore les posts sans texte

        # ignorer les lignes en erreur (ex: "no_items")
        if (row.get("error") or "").strip():
            continue

        page_url = (row.get("facebookUrl") or "").strip()
        agency = find_agency(page_url, agency_lookup)

        cleaned.append({
            "agence": agency,
            "source": "facebook",
            "texte": text,
            "likes": row.get("likes", "") or "0",
            "commentaires": row.get("comments", "") or "0",
            "partages": row.get("shares", "") or "0",
            "date": row.get("time", "") or row.get("timestamp", ""),
            "url": row.get("url", ""),
            "hashtags": "",  # Facebook ne renvoie pas de hashtags séparés
        })

    return cleaned


def main():
    print("Chargement des correspondances agence <-> réseau social...")
    instagram_lookup = load_agency_lookup(AGENCES_INSTAGRAM_FILE, "instagram_url")
    facebook_lookup = load_agency_lookup(AGENCES_FACEBOOK_FILE, "facebook_url")

    print("Nettoyage des posts Instagram...")
    instagram_posts = clean_instagram_posts(INSTAGRAM_POSTS_FILE, instagram_lookup)
    print(f"  {len(instagram_posts)} posts Instagram conservés")

    print("Nettoyage des posts Facebook...")
    facebook_posts = clean_facebook_posts(FACEBOOK_POSTS_FILE, facebook_lookup)
    print(f"  {len(facebook_posts)} posts Facebook conservés")

    all_posts = instagram_posts + facebook_posts

    non_identifies = sum(1 for p in all_posts if not p["agence"])
    if non_identifies:
        print(f"  ⚠ {non_identifies} posts sans agence identifiée (agence laissée vide)")

    fieldnames = ["agence", "source", "texte", "likes", "commentaires",
                  "partages", "date", "url", "hashtags"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_posts)

    print("----------------------------------------")
    print(f"{len(all_posts)} posts au total ({len(instagram_posts)} IG + {len(facebook_posts)} FB)")
    print(f"Terminé -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
