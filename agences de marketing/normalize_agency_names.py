"""
Normalisation des noms d'entreprises/comptes, pour fusionner les doublons
qui apparaissent quand le même opérateur a des noms différents sur
Instagram vs Facebook (ex: "orange.tn" et "orange_tunisie" = Orange Tunisie).

À importer dans TOUT script qui charge des données multi-sources
(analyse_telecom.py, dashboard.py, analyse_region_domaine_v2.py...).

Usage :
    from normalize_agency_names import normaliser_nom

    nom_propre = normaliser_nom("orange.tn")  # -> "Orange Tunisie"
"""

# ============================================
# TABLE DE CORRESPONDANCE — à compléter au fur et à mesure
# que tu ajoutes des secteurs/comptes
# ============================================
CORRESPONDANCES = {
    # --- Télécommunications ---
    "tunisietelecom": "Tunisie Telecom",
    "TunisieTelecom": "Tunisie Telecom",
    "tunisie telecom": "Tunisie Telecom",
    "orange.tn": "Orange Tunisie",
    "orange_tunisie": "Orange Tunisie",
    "orangetunisie": "Orange Tunisie",
    "ooredootn": "Ooredoo",
    "ooredoo tunisie": "Ooredoo",
    "ooredoo_tunisie": "Ooredoo",

    # --- Bancaire (au cas où le même souci apparaisse) ---
    "stbbank": "STB",
    "stb bank": "STB",
    "banquezitouna": "Banque Zitouna",
    "attijaribanktunisie": "Attijari Bank",
    "attijari bank tunisie": "Attijari Bank",
    "bhbank": "BH Bank",
    "bh bank": "BH Bank",

    # Ajoute ici tes futures correspondances au format :
    # "nom_brut_en_minuscule": "Nom Officiel Propre",
}


def normaliser_nom(nom_brut: str) -> str:
    """
    Retourne le nom "officiel" propre pour un compte donné.
    Si aucune correspondance n'est trouvée, retourne le nom d'origine tel quel.
    """
    if not nom_brut:
        return nom_brut

    cle = nom_brut.strip().lower()
    return CORRESPONDANCES.get(cle, nom_brut.strip())


def normaliser_colonne_agence(rows: list[dict], colonne: str = "agence") -> list[dict]:
    """
    Applique normaliser_nom() sur toute une liste de dicts (ex: posts chargés d'un CSV),
    en modifiant directement la colonne donnée.
    """
    for r in rows:
        if colonne in r:
            r[colonne] = normaliser_nom(r[colonne])
    return rows


if __name__ == "__main__":
    # Petit test rapide
    tests = ["orange.tn", "orange_tunisie", "TunisieTelecom", "tunisietelecom", "ooredootn", "Nom Inconnu XYZ"]
    for t in tests:
        print(f"{t!r:25} -> {normaliser_nom(t)!r}")
