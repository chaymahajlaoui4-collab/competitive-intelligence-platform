"""
Lit un fichier combiné contenant les colonnes 'instagram_url' ET 'facebook_url'
(ex: telecom_comptes_sociaux.csv), scrape les posts de chaque plateforme via
Apify, et sauvegarde chaque plateforme dans un format directement compatible
avec 'Analyze multi source.py' (qui détecte automatiquement le format).

- Instagram -> posts_instagram_bruts.csv  (colonnes account + posts en JSON imbriqué)
- Facebook  -> posts_facebook_bruts.csv   (colonnes content + page_name + url + likes + date_posted, 1 ligne = 1 post)

Installation : pip install apify-client

CONFIGURATION (clé jamais en dur dans le code) :
    set APIFY_TOKEN=ton_vrai_token_apify        (Windows cmd)

Usage :
    py scraper_posts_media.py telecom_comptes_sociaux.csv
    (le nom de fichier est un argument, adapte-le au secteur : le même
     script sert pour n'importe quel secteur tant que le CSV a les
     colonnes 'instagram_url' et/ou 'facebook_url')
"""

import csv
import json
import os
import re
import sys
from apify_client import ApifyClient

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()

if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print("Tape d'abord : set APIFY_TOKEN=ton_vrai_token_apify")
    sys.exit(1)

client = ApifyClient(APIFY_TOKEN)

REGEX_INSTAGRAM = re.compile(r"^(https:\/\/)?(www\.)?instagram\.com\/[A-Za-z0-9._-]+(\/.*)?$")
REGEX_FACEBOOK = re.compile(r"^(https:\/\/)?(www\.)?facebook\.com\/[A-Za-z0-9._\-\/]+\/?$")


def get_dataset_id(run):
    """Compatible avec les deux versions d'apify-client (dict ou objet)."""
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


# ========================================================================
# INSTAGRAM (inchangé, juste la clé qui bouge en variable d'environnement)
# ========================================================================

def lire_urls_instagram(chemin_csv: str) -> list[str]:
    with open(chemin_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    urls_brutes = [r["instagram_url"].strip().split("?")[0] for r in rows if r.get("instagram_url", "").strip()]

    urls_valides = [u for u in urls_brutes if REGEX_INSTAGRAM.match(u)]
    rejetees = len(urls_brutes) - len(urls_valides)

    urls_uniques = list(dict.fromkeys(urls_valides))
    doublons = len(urls_valides) - len(urls_uniques)

    print(f"[Instagram] {len(urls_brutes)} URLs lues -> {rejetees} rejetées (format invalide), "
          f"{doublons} doublons enlevés -> {len(urls_uniques)} comptes uniques à scraper.")
    return urls_uniques


def scraper_posts_instagram(urls: list[str], max_posts_par_compte: int = 15) -> list[dict]:
    run_input = {
        "directUrls": urls,
        "resultsType": "posts",
        "resultsLimit": max_posts_par_compte,
    }
    print(f"[Instagram] Lancement du scraping pour {len(urls)} comptes...")
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    items = list(client.dataset(get_dataset_id(run)).iterate_items())
    print(f"[Instagram] {len(items)} posts récupérés au total.")
    return items


def regrouper_instagram_par_compte(items: list[dict]) -> list[dict]:
    """Format attendu par normaliser_instagram() : account + posts en JSON imbriqué."""
    comptes = {}
    for item in items:
        compte = item.get("ownerUsername") or item.get("username") or "inconnu"
        post_normalise = {
            "caption": item.get("caption", "") or "",
            "likes": item.get("likesCount", 0),
            "datetime": item.get("timestamp", ""),
            "url": item.get("url", ""),
            "post_hashtags": item.get("hashtags", []),
        }
        comptes.setdefault(compte, []).append(post_normalise)

    return [{"account": compte, "posts": json.dumps(posts, ensure_ascii=False)}
            for compte, posts in comptes.items()]


def sauvegarder_instagram(lignes: list[dict], chemin_sortie: str = "posts_instagram_bruts.csv"):
    if not lignes:
        print("[Instagram] Aucune ligne à sauvegarder.")
        return
    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["account", "posts"])
        writer.writeheader()
        writer.writerows(lignes)
    print(f"[Instagram] Sauvegardé dans {chemin_sortie}")


# ========================================================================
# FACEBOOK (nouveau)
# ========================================================================

def lire_urls_facebook(chemin_csv: str) -> list[str]:
    with open(chemin_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    urls_brutes = [r["facebook_url"].strip().split("?")[0] for r in rows if r.get("facebook_url", "").strip()]

    urls_valides = [u for u in urls_brutes if REGEX_FACEBOOK.match(u)]
    rejetees = len(urls_brutes) - len(urls_valides)

    urls_uniques = list(dict.fromkeys(urls_valides))
    doublons = len(urls_valides) - len(urls_uniques)

    print(f"[Facebook] {len(urls_brutes)} URLs lues -> {rejetees} rejetées (format invalide), "
          f"{doublons} doublons enlevés -> {len(urls_uniques)} pages uniques à scraper.")
    return urls_uniques


def scraper_posts_facebook(urls: list[str], max_posts_par_page: int = 15) -> list[dict]:
    run_input = {
        "startUrls": [{"url": u} for u in urls],
        "resultsLimit": max_posts_par_page,
    }
    print(f"[Facebook] Lancement du scraping pour {len(urls)} pages...")
    run = client.actor("apify/facebook-posts-scraper").call(run_input=run_input)
    items = list(client.dataset(get_dataset_id(run)).iterate_items())
    print(f"[Facebook] {len(items)} posts récupérés au total.")
    return items


def normaliser_facebook_brut(items: list[dict]) -> list[dict]:
    """
    Format attendu par normaliser_facebook() dans analyze_multi_source.py :
    content, url, page_name, likes, date_posted — UNE LIGNE PAR POST
    (contrairement à Instagram, pas de regroupement par compte ici).
    """
    lignes = []
    for item in items:
        if (item.get("error") or "").strip():
            continue  # ligne en erreur côté Apify, on l'ignore
        lignes.append({
            "content": item.get("text", "") or "",
            "url": item.get("url", ""),
            "page_name": item.get("pageName") or item.get("facebookUrl", ""),
            "likes": item.get("likes", 0),
            "date_posted": item.get("time", "") or item.get("timestamp", ""),
        })
    return lignes


def sauvegarder_facebook(lignes: list[dict], chemin_sortie: str = "posts_facebook_bruts.csv"):
    if not lignes:
        print("[Facebook] Aucune ligne à sauvegarder.")
        return
    with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["content", "url", "page_name", "likes", "date_posted"])
        writer.writeheader()
        writer.writerows(lignes)
    print(f"[Facebook] Sauvegardé dans {chemin_sortie}")


# ========================================================================
# PROGRAMME PRINCIPAL
# ========================================================================

if __name__ == "__main__":
    chemin_comptes = sys.argv[1] if len(sys.argv) > 1 else "telecom_comptes_sociaux.csv"

    if not os.path.exists(chemin_comptes):
        print(f"ERREUR : fichier '{chemin_comptes}' introuvable.")
        sys.exit(1)

    # --- Instagram ---
    urls_ig = lire_urls_instagram(chemin_comptes)
    if urls_ig:
        items_ig = scraper_posts_instagram(urls_ig, max_posts_par_compte=15)
        lignes_ig = regrouper_instagram_par_compte(items_ig)
        sauvegarder_instagram(lignes_ig)
    else:
        print("[Instagram] Aucune URL Instagram valide trouvée, étape sautée.")

    print()

    # --- Facebook ---
    urls_fb = lire_urls_facebook(chemin_comptes)
    if urls_fb:
        items_fb = scraper_posts_facebook(urls_fb, max_posts_par_page=15)
        lignes_fb = normaliser_facebook_brut(items_fb)
        sauvegarder_facebook(lignes_fb)
    else:
        print("[Facebook] Aucune URL Facebook valide trouvée, étape sautée.")

    print("\nTerminé. Lance ensuite 'analyze_multi_source.py' séparément sur chaque fichier :")
    print("  py \"Analyze multi source.py\" posts_instagram_bruts.csv posts_instagram_analyses.csv")
    print("  py \"Analyze multi source.py\" posts_facebook_bruts.csv posts_facebook_analyses.csv")