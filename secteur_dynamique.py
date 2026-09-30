"""
========================================================================
 PIPELINE DYNAMIQUE — Un secteur en entrée, analyse complète en sortie
========================================================================

Comme Apollo/Spyglass : tu ne lances plus chaque script à la main.
Une seule commande enchaîne TOUT automatiquement :

    Découverte (Google Maps) -> Comptes sociaux (Google Search)
    -> Scraping posts (Instagram + Facebook) -> Analyse NLP (Groq)
    -> Fichiers prêts pour le dashboard

PREREQUIS :
    pip install apify-client groq

CONFIGURATION (variables d'environnement, jamais en dur dans le code) :
    set APIFY_TOKEN=ton_token_apify
    set GROQ_API_KEY=ta_cle_groq

USAGE :
    py secteur_dynamique.py "assurance" "Tunisie"
    py secteur_dynamique.py "agence immobilière" "Sousse"

    Options :
    --max-entreprises 30       (défaut: 30, limite le volume découvert)
    --max-posts 15              (défaut: 15, posts par compte)
========================================================================
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata

from apify_client import ApifyClient
from groq import Groq

try:
    # Suivi de progression pour le dashboard (voir dashboard_pipeline_section.py).
    # Si le fichier n'est pas à côté (execution en terminal seul), on ignore
    # silencieusement au lieu de planter.
    from dashboard_pipeline_section import ecrire_statut
except ImportError:
    def ecrire_statut(*args, **kwargs):
        pass

# ============================================
# CONFIGURATION
# ============================================

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not APIFY_TOKEN:
    print("ERREUR : la variable d'environnement APIFY_TOKEN n'est pas définie.")
    print("Tape d'abord : set APIFY_TOKEN=ton_token_apify")
    sys.exit(1)

if not GROQ_API_KEY:
    print("ERREUR : la variable d'environnement GROQ_API_KEY n'est pas définie.")
    print("Tape d'abord : set GROQ_API_KEY=ta_cle_groq")
    sys.exit(1)

client_apify = ApifyClient(APIFY_TOKEN)
client_groq = Groq(api_key=GROQ_API_KEY)
MODELE_GROQ = "openai/gpt-oss-120b"  

REGEX_INSTAGRAM = re.compile(r"^(https:\/\/)?(www\.)?instagram\.com\/[A-Za-z0-9._-]+(\/.*)?$")
REGEX_FACEBOOK = re.compile(r"^(https:\/\/)?(www\.)?facebook\.com\/[A-Za-z0-9._-]+(\/.*)?$")

# Motifs qui indiquent un lien vers un post/une page individuelle plutot
# qu'un compte -- a exclure, comme dans 1_find_instagram.py et
# 1_find_social_urls_ecommerce.py
EXCLUS_INSTAGRAM = ("/p/", "/reel/", "/reels/")
EXCLUS_FACEBOOK = ("/posts/", "/videos/", "/photos/", "/permalink.php")


def nettoyer_url_instagram(url):
    if not url or "instagram.com" not in url or not REGEX_INSTAGRAM.match(url):
        return None
    if any(motif in url for motif in EXCLUS_INSTAGRAM):
        return None
    return url.split("?")[0]


def nettoyer_url_facebook(url):
    if not url or "facebook.com" not in url or not REGEX_FACEBOOK.match(url):
        return None
    if any(motif in url for motif in EXCLUS_FACEBOOK):
        return None
    return url.split("?")[0]


def get_dataset_id(run):
    """Compatible avec les deux versions d'apify-client (dict ou objet)."""
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return run.default_dataset_id


def slug(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", texte.lower()).strip("_")


# ========================================================================
# ÉTAPE 1 — DÉCOUVERTE (Google Maps)
# ========================================================================

# Bruit récurrent identifié sur plusieurs secteurs : agences web/marketing
# qui remontent sur des requêtes trop génériques, hors-sujet pour tout
# secteur qui n'est pas "marketing".
CATEGORIES_EXCLUES = [
    "agence web", "agence de communication", "agence marketing",
    "web designer", "graphic designer",
]


def generer_requetes_google_maps(secteur, ville, n_variantes=3):
    """secteur en texte libre + ville -> 2-4 requêtes Google Maps précises.
    Remplace la requête brute unique par une génération dynamique via Groq,
    pour que n'importe quel secteur tapé par l'utilisateur soit couvert
    sans avoir besoin d'un mapping statique par secteur."""
    prompt = f"""Tu es un expert en veille concurrentielle en Tunisie.

Secteur demandé : "{secteur}"
Ville/région : "{ville}"

Donne {n_variantes} formulations de recherche Google Maps DIFFÉRENTES et
PRÉCISES pour trouver les entreprises de ce secteur précis (évite les
termes trop génériques comme "agence" seul, qui ramènent des agences
web/marketing hors-sujet).

Réponds UNIQUEMENT avec un objet JSON de cette forme, rien d'autre :
{{"queries": ["requête 1", "requête 2", "requête 3"]}}
"""
    try:
        response = client_groq.chat.completions.create(
            model=MODELE_GROQ,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content)
        queries = [q.strip() for q in data.get("queries", []) if q.strip()]
        if queries:
            return [f"{q} {ville}" for q in queries]
    except Exception as e:
        print(f"  (génération de requêtes via Groq échouée, fallback requête brute : {e})")

    return [f"{secteur} {ville}"]


def etape1_decouverte(secteur, ville, max_entreprises):
    print(f"\n[ÉTAPE 1/5] Découverte des entreprises « {secteur} » à « {ville} »...")

    requetes = generer_requetes_google_maps(secteur, ville)
    print(f"  -> {len(requetes)} requête(s) générée(s) : {requetes}")

    entreprises = []
    noms_vus = set()
    for requete in requetes:
        run_input = {
            "searchStringsArray": [requete],
            "locationQuery": "Tunisia",
            "countryCode": "tn",
            "maxCrawledPlacesPerSearch": max_entreprises,
            "language": "fr",
        }
        run = client_apify.actor("compass/crawler-google-places").call(run_input=run_input)
        items = list(client_apify.dataset(get_dataset_id(run)).iterate_items())

        for item in items:
            nom = (item.get("title") or "").strip()
            categorie = (item.get("categoryName") or "").lower()
            if not nom or nom.lower() in noms_vus:
                continue
            if any(exclu in categorie for exclu in CATEGORIES_EXCLUES):
                continue
            noms_vus.add(nom.lower())
            entreprises.append({
                "title": nom,
                "category": item.get("categoryName", "") or "",
                "city": item.get("city", "") or "",
                "address": item.get("address", "") or "",
                "website": item.get("website", "") or "",
            })

    if len(entreprises) > max_entreprises:
        print(f"  -> {len(entreprises)} trouvées au total, tronqué à {max_entreprises} (--max-entreprises).")
        entreprises = entreprises[:max_entreprises]

    print(f"  -> {len(entreprises)} entreprises uniques trouvées.")
    return entreprises


# ========================================================================
# ÉTAPE 2 — RÉSOLUTION DES COMPTES SOCIAUX (Google Search)
# ========================================================================

def etape2_comptes_sociaux(entreprises):
    print(f"\n[ÉTAPE 2/5] Recherche des comptes Instagram/Facebook pour {len(entreprises)} entreprises...")

    queries = []
    for e in entreprises:
        queries.append(f"{e['title']} Tunisie instagram")
        queries.append(f"{e['title']} Tunisie facebook")

    run_input = {
        "queries": "\n".join(queries),
        "resultsPerPage": 10,
        "maxPagesPerQuery": 1,
        "countryCode": "tn",
        "languageCode": "fr",
    }

    run = client_apify.actor("apify/google-search-scraper").call(run_input=run_input)
    pages = list(client_apify.dataset(get_dataset_id(run)).iterate_items())

    resultats_par_nom = {e["title"]: {"instagram_url": "", "facebook_url": ""} for e in entreprises}

    for page in pages:
        query_originale = page.get("searchQuery", {}).get("term", "")
        for e in entreprises:
            nom = e["title"]
            if nom.lower() not in query_originale.lower():
                continue
            for result in page.get("organicResults", []):
                url = result.get("url", "")
                if "instagram" in query_originale.lower() and not resultats_par_nom[nom]["instagram_url"]:
                    clean = nettoyer_url_instagram(url)
                    if clean:
                        resultats_par_nom[nom]["instagram_url"] = clean
                elif "facebook" in query_originale.lower() and not resultats_par_nom[nom]["facebook_url"]:
                    clean = nettoyer_url_facebook(url)
                    if clean:
                        resultats_par_nom[nom]["facebook_url"] = clean

    for e in entreprises:
        e["instagram_url"] = resultats_par_nom[e["title"]]["instagram_url"]
        e["facebook_url"] = resultats_par_nom[e["title"]]["facebook_url"]

    trouves = sum(1 for e in entreprises if e["instagram_url"] or e["facebook_url"])
    print(f"  -> {trouves}/{len(entreprises)} entreprises avec au moins un compte social trouvé.")

    return [e for e in entreprises if e["instagram_url"] or e["facebook_url"]]


# ========================================================================
# ÉTAPE 3 — SCRAPING DES POSTS (Instagram + Facebook)
# ========================================================================

def etape3_scraping_posts(entreprises, max_posts):
    print(f"\n[ÉTAPE 3/5] Scraping des posts pour {len(entreprises)} entreprises...")

    urls_instagram = list(dict.fromkeys(e["instagram_url"] for e in entreprises if e["instagram_url"]))
    urls_facebook = list(dict.fromkeys(e["facebook_url"] for e in entreprises if e["facebook_url"]))

    tous_les_posts = []

    if urls_instagram:
        print(f"  -> Instagram : {len(urls_instagram)} comptes...")
        run_input = {"directUrls": urls_instagram, "resultsType": "posts", "resultsLimit": max_posts}
        run = client_apify.actor("apify/instagram-scraper").call(run_input=run_input)
        items = list(client_apify.dataset(get_dataset_id(run)).iterate_items())
        for item in items:
            contenu = (item.get("caption") or "").strip()
            if not contenu:
                continue
            tous_les_posts.append({
                "source": "instagram",
                "auteur": item.get("ownerUsername", ""),
                "post_url": item.get("url", ""),
                "date": item.get("timestamp", ""),
                "likes": item.get("likesCount", 0),
                "contenu_original": contenu,
            })
        print(f"     {len(items)} posts Instagram récupérés.")

    if urls_facebook:
        print(f"  -> Facebook : {len(urls_facebook)} pages...")
        run_input = {"startUrls": [{"url": u} for u in urls_facebook], "resultsLimit": max_posts}
        # apify/facebook-posts-scraper : meme acteur que scraper_posts_media.py
        # (deja valide sur le telecom) -- apify/facebook-pages-scraper est un
        # acteur different, au format de sortie non confirme ici
        run = client_apify.actor("apify/facebook-posts-scraper").call(run_input=run_input)
        items = list(client_apify.dataset(get_dataset_id(run)).iterate_items())
        for item in items:
            if (item.get("error") or "").strip():
                continue  # ligne en erreur cote Apify, on l'ignore (comme scraper_posts_media.py)
            contenu = (item.get("text") or item.get("content") or "").strip()
            if not contenu:
                continue
            tous_les_posts.append({
                "source": "facebook",
                "auteur": item.get("pageName", "") or item.get("page_name", ""),
                "post_url": item.get("url", ""),
                "date": item.get("time", "") or item.get("date", ""),
                "likes": item.get("likes", 0),
                "contenu_original": contenu,
            })
        print(f"     {len(items)} posts Facebook récupérés.")

    print(f"  -> {len(tous_les_posts)} posts au total (avant nettoyage).")
    return tous_les_posts


# ========================================================================
# ÉTAPE 4 — ANALYSE NLP (Groq)
# ========================================================================

PROMPT_ANALYSE_POST = """Analyse ce post de réseau social d'une entreprise tunisienne et extrais
les informations suivantes au format JSON STRICT (rien d'autre) :

{{
  "langue": "français|arabe|mixte|anglais",
  "type_contenu": "promotion produit|information pratique|relations publiques|actualité|autre",
  "theme": "résumé en 3-5 mots",
  "produit_service": "nom du produit/service mentionné, ou null",
  "promotion": "description de l'offre si présente, ou null",
  "sentiment": "positif|neutre|négatif"
}}

Post :
\"\"\"{contenu}\"\"\"
"""


def etape4_analyse_nlp(posts):
    print(f"\n[ÉTAPE 4/5] Analyse NLP de {len(posts)} posts via Groq...")

    posts_analyses = []
    for i, post in enumerate(posts):
        try:
            response = client_groq.chat.completions.create(
                model=MODELE_GROQ,
                messages=[{"role": "user", "content": PROMPT_ANALYSE_POST.format(contenu=post["contenu_original"])}],
                temperature=0.2,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            texte = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            analyse = json.loads(texte)
        except Exception as e:
            analyse = {"erreur": str(e)}

        posts_analyses.append({**post, **analyse})

        if (i + 1) % 10 == 0 or (i + 1) == len(posts):
            print(f"  -> {i + 1}/{len(posts)} posts analysés...")

        time.sleep(0.5)

    return posts_analyses


# ========================================================================
# ÉTAPE 5 — SAUVEGARDE
# ========================================================================

def etape5_sauvegarde(secteur, entreprises, posts_analyses):
    print(f"\n[ÉTAPE 5/5] Sauvegarde des résultats...")

    prefixe = slug(secteur)

    fichier_entreprises = f"{prefixe}_entreprises.csv"
    with open(fichier_entreprises, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(entreprises[0].keys()))
        writer.writeheader()
        writer.writerows(entreprises)
    print(f"  -> {fichier_entreprises}")

    fichier_posts = None
    if posts_analyses:
        fichier_posts = f"{prefixe}_posts_analyses.csv"
        toutes_colonnes = set()
        for p in posts_analyses:
            toutes_colonnes.update(p.keys())
        with open(fichier_posts, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(toutes_colonnes))
            writer.writeheader()
            writer.writerows(posts_analyses)
        print(f"  -> {fichier_posts}")

    return fichier_entreprises, fichier_posts


# ========================================================================
# PROGRAMME PRINCIPAL
# ========================================================================

def lancer_pipeline(secteur, ville, max_entreprises=30, max_posts=15):
    debut = time.time()
    print("=" * 70)
    print(f"PIPELINE DYNAMIQUE — Secteur : {secteur} — Ville : {ville}")
    print("=" * 70)

    etape_courante = "découverte"
    try:
        ecrire_statut(secteur, etape_courante, f"Recherche des entreprises « {secteur} » à « {ville} »...")
        entreprises = etape1_decouverte(secteur, ville, max_entreprises)
        if not entreprises:
            ecrire_statut(secteur, etape_courante, erreur="Aucune entreprise trouvée.")
            print("\nAucune entreprise trouvée. Arrêt du pipeline.")
            return

        etape_courante = "comptes sociaux"
        ecrire_statut(secteur, etape_courante, f"{len(entreprises)} entreprises trouvées, résolution des comptes...")
        entreprises = etape2_comptes_sociaux(entreprises)
        if not entreprises:
            ecrire_statut(secteur, etape_courante, erreur="Aucun compte social trouvé.")
            print("\nAucun compte social trouvé. Arrêt du pipeline.")
            return

        etape_courante = "scraping posts"
        ecrire_statut(secteur, etape_courante, f"Scraping des posts pour {len(entreprises)} entreprises...")
        posts = etape3_scraping_posts(entreprises, max_posts)
        if not posts:
            etape_courante = "sauvegarde"
            ecrire_statut(secteur, etape_courante, "Aucun post récupéré, sauvegarde des entreprises seules.")
            print("\nAucun post récupéré. Arrêt du pipeline (le fichier entreprises est quand même sauvegardé).")
            etape5_sauvegarde(secteur, entreprises, [])
            ecrire_statut(secteur, etape_courante, "Terminé (sans posts).", termine=True)
            return

        etape_courante = "analyse NLP"
        ecrire_statut(secteur, etape_courante, f"Analyse de {len(posts)} posts...")
        posts_analyses = etape4_analyse_nlp(posts)

        etape_courante = "sauvegarde"
        ecrire_statut(secteur, etape_courante, "Écriture des fichiers CSV...")
        etape5_sauvegarde(secteur, entreprises, posts_analyses)
        ecrire_statut(secteur, etape_courante, "Terminé.", termine=True)

    except Exception as e:
        ecrire_statut(secteur, etape_courante, erreur=str(e))
        raise

    duree = round((time.time() - debut) / 60, 1)
    print("\n" + "=" * 70)
    print(f"PIPELINE TERMINÉ en {duree} minutes.")
    print(f"  {len(entreprises)} entreprises, {len(posts_analyses)} posts analysés.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline dynamique : secteur -> analyse complète")
    parser.add_argument("secteur", help="Ex: 'assurance', 'agence immobilière'")
    parser.add_argument("ville", help="Ex: 'Tunisie', 'Sousse'")
    parser.add_argument("--max-entreprises", type=int, default=30)
    parser.add_argument("--max-posts", type=int, default=15)
    args = parser.parse_args()

    lancer_pipeline(args.secteur, args.ville, args.max_entreprises, args.max_posts)