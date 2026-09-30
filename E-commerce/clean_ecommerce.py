"""
========================================================================
 NETTOYAGE + FILTRAGE DU DATASET E-COMMERCE (Tunisie)
========================================================================

Objectif : partir du CSV brut issu du scraping Google Maps (colonnes
title, category, address, city, website) et produire un dataset propre
et ciblé sur le e-commerce, en écartant les catégories qui n'ont rien
à voir avec la vente en ligne (restaurants, salons de coiffure,
agences de services, grossistes B2B, fabricants...).

Deux fichiers de sortie :
  1. ecommerce_clean.csv          -> uniquement les entreprises jugées
                                      pertinentes pour le e-commerce
  2. ecommerce_exclus.csv         -> tout ce qui a été écarté, avec la
                                      raison, pour vérification manuelle

USAGE :
    python3 clean_ecommerce.py input.csv
    (génère ecommerce_clean.csv et ecommerce_exclus.csv à côté)
========================================================================
"""

import sys
import re
import pandas as pd

# ------------------------------------------------------------------
# 1. Catégories à exclure car hors périmètre e-commerce (services sur
#    place, restauration, B2B/grossiste, fabrication, agences...).
#    Complète cette liste si tu repères d'autres catégories parasites.
# ------------------------------------------------------------------
CATEGORIES_EXCLUES = {
    # Restauration / alimentation sur place
    "Restaurant", "Restaurant de hamburgers", "Restauration rapide",
    "Pizzeria", "Pizzas à emporter", "Livraison de pizzas",
    "Livraison de repas à domicile", "Sandwicherie", "Pâtisserie",
    "Traiteur", "Épicerie", "Épicerie fine",

    # Services rendus en personne (non e-commerce)
    "Salon de coiffure", "Salon de manucure", "Salon de piercing",
    "Institut de beauté",

    # Formation / social
    "École technique", "Centre de formation", "Service de santé mentale",

    # Ne sont pas des commerces
    "Immeuble en copropriété", "Siège social",

    # Artisans / services sur site
    "Menuisier", "Designer d'intérieur", "Décorateur d'intérieur",
    "Tapissier décorateur",

    # Conseil / IT B2B
    "Consultant.e économique", "Consultant informatique",
    "Assistance et services informatiques",

    # Logistique / télécom (infrastructure, pas vente en ligne)
    "Service de transport", "Service de transport et d'accompagnement",
    "Coursier", "Commutateur téléphonique",
    "Fournisseur d'accès Internet", "Entreprise de télécommunications",

    # Fabrication / production (B2B, pas vente directe en ligne)
    "Fabricant", "Fabricant de fromage", "Fabricant de meubles",
    "Producteur de nourriture", "Conserverie",
    "Équipement de transformation des aliments",
    "Équipement pour boulangerie",

    # Vente en gros / B2B (pas du e-commerce B2C)
    "Grossiste", "Grossiste alimentaire", "Grossiste de produits de beauté",
    "Grossiste en produits chirurgicaux", "Grossiste en produits pharmaceutiques",
    "Vendeur en gros", "Magasin de gros",
    "Fournisseur de produits alimentaires", "Fournisseur de meubles encastrables",
    "Fournisseur de produits de beauté", "Exportateur",

    # Agences de services (déjà couvertes par un autre secteur du projet)
    "Agence de marketing", "Agence de publicité", "Agence de design",
    "Agence artistique", "Agence commerciale", "Agence de voyages",
    "Service de marketing Internet", "Concepteur de sites Web",
    "Entreprise de logiciels",
}

# Valeurs de ville manifestement erronées (artefacts d'extraction Google Maps).
BAD_CITY_VALUES = {"2", "Décembre"}


def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in df.columns:
        df[col] = df[col].str.strip()
    return df


def drop_duplicates_and_empty(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["title", "address"], keep="first")
    df = df[df["title"].str.len() > 0]
    return df


def clean_city(row: pd.Series) -> tuple[str, bool]:
    city = row["city"]
    if city in BAD_CITY_VALUES:
        city = ""
    if city:
        return city, False

    addr = row["address"]
    if not addr:
        return "", True

    parts = [p.strip() for p in addr.split(",")]
    if len(parts) >= 2:
        candidate = parts[-2]
        candidate = re.sub(r"\s*\d{4,5}$", "", candidate).strip()
        looks_like_a_city = bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", candidate))
        if candidate and looks_like_a_city and candidate not in BAD_CITY_VALUES:
            return candidate, False
    return "", True


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def split_website_and_facebook(url: str) -> tuple[str, str]:
    if not url:
        return "", ""
    if "facebook.com" in url.lower():
        return "", url
    return url, ""


def build_search_query(title: str, city: str, site_filter: str) -> str:
    query = f"{title} {city} {site_filter}".strip()
    return re.sub(r"\s+", " ", query)


def is_excluded_category(category: str) -> bool:
    return category in CATEGORIES_EXCLUES


def clean_and_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = drop_duplicates_and_empty(df)

    city_results = df.apply(clean_city, axis=1)
    df["city"] = [r[0] for r in city_results]
    df["city_needs_review"] = [r[1] for r in city_results]

    df["website"] = df["website"].apply(normalize_url)
    website_fb = df["website"].apply(split_website_and_facebook)
    df["website"] = [w for w, _ in website_fb]
    df["facebook_url"] = [f for _, f in website_fb]
    df["instagram_url"] = ""

    df["has_website"] = df["website"].apply(bool)
    df["has_facebook"] = df["facebook_url"].apply(bool)
    df["needs_fb_search"] = ~df["has_facebook"]
    df["needs_insta_search"] = True

    df["fb_search_query"] = df.apply(
        lambda r: build_search_query(r["title"], r["city"], "site:facebook.com")
        if r["needs_fb_search"] else "",
        axis=1,
    )
    df["insta_search_query"] = df.apply(
        lambda r: build_search_query(r["title"], r["city"], "site:instagram.com")
        if r["needs_insta_search"] else "",
        axis=1,
    )

    # Séparation e-commerce pertinent vs exclu
    df["excluded"] = df["category"].apply(is_excluded_category)

    cols = [
        "title", "category", "city", "city_needs_review", "address",
        "website", "facebook_url", "instagram_url",
        "has_website", "has_facebook", "needs_fb_search", "needs_insta_search",
        "fb_search_query", "insta_search_query",
    ]

    df_clean = df[~df["excluded"]][cols].reset_index(drop=True)
    df_excluded = df[df["excluded"]][["title", "category", "city", "address", "website"]].reset_index(drop=True)

    return df_clean, df_excluded


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 clean_ecommerce.py input.csv")
        sys.exit(1)

    input_path = sys.argv[1]
    df_raw = load_dataset(input_path)
    df_clean, df_excluded = clean_and_filter(df_raw)

    df_clean.to_csv("ecommerce_clean.csv", index=False)
    df_excluded.to_csv("ecommerce_exclus.csv", index=False)

    print(f"Lignes brutes            : {len(df_raw)}")
    print(f"Retenues (e-commerce)    : {len(df_clean)}")
    print(f"Exclues (hors périmètre) : {len(df_excluded)}")
    print(f"  -> ecommerce_clean.csv")
    print(f"  -> ecommerce_exclus.csv (à vérifier si besoin)")
    print()
    print("Répartition des catégories exclues :")
    print(df_excluded["category"].value_counts().to_string())


if __name__ == "__main__":
    main()
