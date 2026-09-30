"""
dashboard_pipeline_section.py — Étape 6 du pipeline générique (PFA)

Bloc à intégrer dans dashboard.py pour piloter tout le pipeline dynamique
DEPUIS Streamlit (fini le terminal) :
  - découvre les secteurs déjà scrapés en scannant le dossier courant pour
    les paires <slug>_entreprises.csv / <slug>_posts_analyses.csv, EXACTEMENT
    ce que sauvegarde etape5_sauvegarde() dans secteur_dynamique.py (fichiers
    plats dans le dossier courant, pas de sous-dossier data/)
  - formulaire "Nouveau secteur" (secteur + région en texte libre)
  - lancement de secteur_dynamique.py en arrière-plan, non-bloquant
  - suivi de la progression en direct sans geler le dashboard pendant les
    8-9 minutes du pipeline (via st.fragment + auto-refresh)

Utilise sys.executable pour lancer le sous-processus : ça règle aussi le
piège py/python documenté dans le récap, puisque c'est l'interpréteur qui
fait déjà tourner Streamlit qui est réutilisé, sans ambiguïté de PATH.
"""

import re
import sys
import json
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent

ETAPES = ["découverte", "comptes sociaux", "scraping posts", "analyse NLP", "sauvegarde"]


def slug(texte: str) -> str:
    """Identique à slug() dans secteur_dynamique.py — dupliqué ici plutôt
    qu'importé pour éviter un import circulaire (secteur_dynamique.py
    importe déjà ecrire_statut depuis ce fichier). Les deux doivent rester
    en phase si l'un des deux change."""
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", texte.lower()).strip("_")


def _fichier_statut(secteur_slug: str) -> Path:
    return BASE_DIR / f"_status_{secteur_slug}.json"


# ---------------------------------------------------------------------------
# Côté secteur_dynamique.py
# ---------------------------------------------------------------------------

def ecrire_statut(secteur: str, etape: str, message: str = "", termine: bool = False, erreur: Optional[str] = None):
    statut = {
        "etape": etape,
        "etape_index": ETAPES.index(etape) + 1 if etape in ETAPES else 0,
        "total_etapes": len(ETAPES),
        "message": message,
        "termine": termine,
        "erreur": erreur,
        "maj": datetime.now().isoformat(),
    }
    with open(_fichier_statut(slug(secteur)), "w", encoding="utf-8") as f:
        json.dump(statut, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Côté dashboard.py
# ---------------------------------------------------------------------------

def lister_secteurs_disponibles() -> dict:
    """Scanne le dossier courant pour les paires <slug>_entreprises.csv /
    <slug>_posts_analyses.csv. Retourne {slug: nom_affichable}. Remplace le
    besoin d'éditer un sélecteur codé en dur : tout secteur passé par
    secteur_dynamique.py apparaît automatiquement.
    NB : le nom affichable est reconstruit depuis le slug (ex: "agence_immobiliere"
    -> "Agence Immobiliere") — les accents d'origine ne sont pas récupérables,
    c'est une limite cosmétique mineure, pas fonctionnelle."""
    secteurs = {}
    for fichier in BASE_DIR.glob("*_entreprises.csv"):
        slug_nom = fichier.name[: -len("_entreprises.csv")]
        if (BASE_DIR / f"{slug_nom}_posts_analyses.csv").exists():
            secteurs[slug_nom] = slug_nom.replace("_", " ").title()
    return secteurs


def lire_statut(secteur: str) -> Optional[dict]:
    fichier = _fichier_statut(slug(secteur))
    if not fichier.exists():
        return None
    try:
        with open(fichier, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def demarrer_pipeline_arriere_plan(secteur: str, region: str, max_entreprises: int = 15, max_posts: int = 15):
    """Lance secteur_dynamique.py en arrière-plan, sans bloquer Streamlit.
    (À ne pas confondre avec lancer_pipeline() DANS secteur_dynamique.py,
    qui est l'orchestrateur synchrone des 5 étapes — celui-ci le lance en
    sous-processus depuis l'UI.)"""
    log_path = BASE_DIR / f"_log_{slug(secteur)}.txt"
    log_file = open(log_path, "w", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, str(BASE_DIR / "secteur_dynamique.py"), secteur, region,
         "--max-entreprises", str(max_entreprises), "--max-posts", str(max_posts)],
        cwd=BASE_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    st.session_state["pipeline_en_cours"] = secteur
    ecrire_statut(secteur, "découverte", "Démarrage du pipeline...")


@st.fragment(run_every="3s")
def afficher_progression():
    """Fragment auto-rafraîchi : suit la progression sans recharger tout le
    dashboard. Nécessite un Streamlit récent (>=1.33) ; à défaut, remplacer
    par le package streamlit-autorefresh."""
    secteur = st.session_state.get("pipeline_en_cours")
    if not secteur:
        return

    statut = lire_statut(secteur)
    if statut is None:
        st.info(f"Initialisation du pipeline pour « {secteur} »...")
        return

    if statut.get("erreur"):
        st.error(f"Échec du pipeline sur « {secteur} » : {statut['erreur']}")
        del st.session_state["pipeline_en_cours"]
        return

    if statut.get("termine"):
        st.success(f"Pipeline terminé pour « {secteur} » ✅")
        del st.session_state["pipeline_en_cours"]
        st.cache_data.clear()  # pour que le nouveau secteur apparaisse dans le sélecteur
        st.rerun()
        return

    progression = statut["etape_index"] / statut["total_etapes"]
    st.progress(progression, text=f"Étape {statut['etape_index']}/{statut['total_etapes']} — {statut['etape']}")
    if statut.get("message"):
        st.caption(statut["message"])


def section_nouveau_secteur():
    """Bloc à placer dans la sidebar de dashboard.py : formulaire secteur +
    région, lancement du pipeline, et suivi de la progression."""
    with st.sidebar.expander("➕ Nouveau secteur", expanded=False):
        secteur = st.text_input("Secteur (texte libre)", placeholder="ex : immobilier, tourisme...")
        region = st.text_input("Région", placeholder="ex : Sfax, Tunis...")
        max_entreprises = st.slider(
            "Nombre max d'entreprises", 5, 50, 15,
            help="Fait varier le temps de scraping ET la taille du prompt SWOT ensuite dans le dashboard.",
        )
        max_posts = st.slider("Posts max par compte", 5, 30, 15)
        lancer = st.button("Lancer l'analyse", disabled=bool(st.session_state.get("pipeline_en_cours")))

        if lancer and secteur and region:
            demarrer_pipeline_arriere_plan(secteur.strip(), region.strip(), max_entreprises, max_posts)
            st.rerun()

    # Volontairement EN DEHORS de l'expander (qui se replie par défaut à
    # chaque rerun) : sinon la progression tourne bien en arrière-plan mais
    # reste invisible tant que le panneau n'est pas rouvert à la main.
    if st.session_state.get("pipeline_en_cours"):
        st.sidebar.divider()
        afficher_progression()