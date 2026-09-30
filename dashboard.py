"""
========================================================================
 DASHBOARD — Competitive Pulse
 Intelligence concurrentielle multi-secteurs (marketing + télécom)
========================================================================

Design : palette officielle Brima Digital, version claire — fond quasi-
blanc, Oxford Blue #211F44 comme encre de texte, cyan #01FFFF et fuchsia
#841171 réservés aux accents (boutons, graphiques, logo). Fraunces
(titres/scores) + IBM Plex Sans (texte/data). Signature : classement
pondéré (barres empilées par composante de score), calculé sans appel Groq.

NOUVEAU : sélecteur de secteur dans la sidebar. Les données marketing
et télécom ont des formats différents à la source ; ce dashboard les
uniformise au chargement vers un schéma commun (agence, source, texte,
likes, commentaires, date, url, theme, sentiment, type_contenu, langue),
et utilise un AGENT GÉNÉRIQUE (défini dans ce fichier, pas dépendant
d'un secteur précis) pour l'analyse IA — donc pas besoin d'un script
d'agent séparé par secteur.

PREREQUIS :
    pip install streamlit plotly pandas groq

USAGE :
    streamlit run dashboard.py

FICHIERS ATTENDUS DANS LE MÊME DOSSIER :
    Marketing : posts_analyzed.csv, agences_region_domaine.csv,
                agences_avec_instagram.csv, agences_avec_facebook.csv
    Télécom   : posts_telecom_instagram_analyses.csv,
                posts_telecom_facebook_analyses.csv,
                telecom_comptes_sociaux.csv
========================================================================
"""

import json
import os
import re
import time
import unicodedata
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from groq import Groq

from dashboard_pipeline_section import lister_secteurs_disponibles, section_nouveau_secteur

st.set_page_config(page_title="Competitive Pulse", layout="wide", page_icon="◆")

# ========================================================================
# CONFIGURATION DES SECTEURS
# ========================================================================

SECTEURS = {
    "Marketing": {
        "a_region_domaine": True,
        "analyst_role": "agences marketing et digitales tunisiennes",
    },
    "Télécommunications": {
        "a_region_domaine": False,
        "analyst_role": "opérateurs de télécommunications tunisiens",
    },
}

FICHIER_POSTS_MARKETING = "agences de marketing/posts_analyzed.csv"
FICHIER_REGIONS_MARKETING = "agences de marketing/agences_region_domaine.csv"
FICHIER_IG_MARKETING = "agences de marketing/agences_avec_instagram.csv"
FICHIER_FB_MARKETING = "agences de marketing/agences_avec_facebook.csv"

FICHIERS_TELECOM = ["Telecom/posts_telecom_instagram_analyses.csv", "Telecom/posts_telecom_facebook_analyses.csv"]
FICHIER_COMPTES_TELECOM = "Telecom/telecom_comptes_sociaux.csv"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
MODEL = "openai/gpt-oss-120b"

POIDS = {"engagement": 0.45, "sentiment": 0.20, "frequence": 0.20, "diversite": 0.15}

# ========================================================================
# TOKENS DE DESIGN — palette officielle Brima Digital, en version claire :
# fond quasi-blanc, Oxford Blue comme encre de texte (déjà une couleur de
# marque, pas besoin d'en inventer une), cyan et fuchsia réservés aux
# accents — boutons, graphiques, logo — pas étalés sur tout le thème.
# Structure et typo (Fraunces + IBM Plex Sans, classement pondéré)
# inchangées, seule la peau change.
# ========================================================================

BG = "#F5F6FA"
BG_PANEL = "#FFFFFF"
BG_PANEL_SOLID = "#FFFFFF"
BORDER = "rgba(33,31,68,0.12)"
ACCENT_BLUE = "#01FFFF"
ACCENT_BLUE_TEXT = "#067A85"  # cyan assombri : le cyan pur est illisible en texte sur fond clair
ACCENT_VIOLET = "#841171"
ACCENT_GRADIENT = "linear-gradient(135deg, #01FFFF 0%, #841171 100%)"
TEXT_PRIMARY = "#211F44"  # Oxford Blue — encre de la marque
TEXT_MUTED = "#6B6690"
SUCCESS = "#1F8A63"
DANGER = "#C23A52"
WARNING = "#B8791F"

CHART_COLORWAY = ["#01FFFF", "#4A9BB0", "#6B4F8C", "#841171", SUCCESS, DANGER]
GRADIENT_SCALE = [[0, "#B8ECEC"], [0.5, "#4DA8D9"], [1, "#01FFFF"]]

# Poids visuel = poids réel dans le score : un vrai dégradé à 4 crans entre
# les deux couleurs de marque (cyan → fuchsia), pas 2 accents vifs encadrant
# des tons choisis séparément — chaque cran est un peu plus foncé que le
# précédent, la transition se voit plutôt qu'elle ne saute.
COULEURS_SCORE = {
    "Engagement": "#01FFFF", "Sentiment": "#4A9BB0",
    "Frequence": "#6B4F8C", "Diversite": "#841171",
}
INK = "#211F44"  # Oxford Blue — encre de secours pour le texte sur fonds clairs (badges, boutons)

# ========================================================================
# CSS
# ========================================================================

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..900&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
:root {{
    --bg: {BG}; --bg-panel: {BG_PANEL}; --border: {BORDER};
    --accent-blue: {ACCENT_BLUE}; --accent-violet: {ACCENT_VIOLET};
    --text-primary: {TEXT_PRIMARY}; --text-muted: {TEXT_MUTED};
}}
html, body, [class*="css"] {{ font-family: 'IBM Plex Sans', sans-serif; }}
.stApp {{
    background:
        radial-gradient(ellipse 900px 500px at 15% -5%, rgba(1,255,255,0.05), transparent 60%),
        radial-gradient(ellipse 800px 500px at 100% 10%, rgba(132,17,113,0.05), transparent 60%),
        {BG};
    color: {TEXT_PRIMARY};
}}
section[data-testid="stSidebar"] {{ background: {BG_PANEL_SOLID}; border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] * {{ color: {TEXT_PRIMARY} !important; }}
section[data-testid="stSidebar"] label {{ color: {TEXT_MUTED} !important; font-size: 0.82rem; }}
h1, h2, h3 {{ font-family: 'Fraunces', serif !important; letter-spacing: -0.01em; color: {TEXT_PRIMARY}; }}
.pulse-logo {{
    font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.9rem;
    background: {ACCENT_GRADIENT}; -webkit-background-clip: text; background-clip: text;
    color: transparent; letter-spacing: -0.02em;
}}
.pulse-sub {{ color: {TEXT_MUTED}; font-size: 0.95rem; margin-top: -6px; }}
.pulse-live {{ color: {TEXT_MUTED}; font-size: 0.85rem; }}
.kpi-card {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 18px 20px; box-shadow: 0 1px 3px rgba(33,31,68,0.05), 0 1px 2px rgba(33,31,68,0.04);
}}
.kpi-label {{ color: {TEXT_MUTED}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }}
.kpi-value {{ font-family: 'Fraunces', serif; font-weight: 700; font-size: 2.1rem; color: {TEXT_PRIMARY}; margin-top: 2px; }}
.section-title {{
    font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.15rem;
    color: {TEXT_PRIMARY}; margin: 6px 0 2px 0; display: flex; align-items: center; gap: 8px;
}}
.section-title::before {{ content: ""; width: 4px; height: 18px; border-radius: 3px; background: {ACCENT_GRADIENT}; display: inline-block; }}
.chart-panel {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 14px 16px 6px 16px; box-shadow: 0 1px 3px rgba(33,31,68,0.05), 0 1px 2px rgba(33,31,68,0.04);
}}
div[data-testid="stExpander"] {{
    background: {BG_PANEL}; border: 1px solid {BORDER} !important; border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(33,31,68,0.05);
}}
div[data-testid="stExpander"] summary {{ font-family: 'Fraunces', serif; font-weight: 600; color: {TEXT_PRIMARY}; }}
.swot-box {{ border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; border-left: 3px solid transparent; background: rgba(33,31,68,0.025); }}
.swot-forces {{ border-left-color: {SUCCESS}; }}
.swot-faiblesses {{ border-left-color: {DANGER}; }}
.swot-opportunites {{ border-left-color: {ACCENT_BLUE_TEXT}; }}
.swot-menaces {{ border-left-color: {WARNING}; }}
.swot-title {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: {TEXT_MUTED}; margin-bottom: 4px; }}
.swot-item {{ font-size: 0.92rem; margin: 3px 0; color: {TEXT_PRIMARY}; }}
.insight-banner {{
    background: linear-gradient(135deg, rgba(1,255,255,0.07), rgba(132,17,113,0.07));
    border: 1px solid rgba(1,255,255,0.18); border-radius: 14px; padding: 16px 20px; color: {TEXT_PRIMARY};
}}
.stButton>button {{
    background: {ACCENT_BLUE} !important; color: {INK} !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important; padding: 0.55rem 1.4rem !important;
    box-shadow: 0 4px 14px rgba(1,255,255,0.22);
}}
.stButton>button:hover {{ filter: brightness(0.92) !important; }}
div[data-baseweb="select"] > div, .stTextInput input {{
    background: {BG_PANEL_SOLID} !important; border-color: {BORDER} !important; color: {TEXT_PRIMARY} !important;
}}
hr {{ border-color: {BORDER}; }}
.agency-header {{
    display: flex; align-items: center; justify-content: space-between;
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 20px 24px; box-shadow: 0 1px 3px rgba(33,31,68,0.05); margin-bottom: 4px;
}}
.agency-name {{ font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.6rem; color: {TEXT_PRIMARY}; }}
.social-link {{
    display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 8px;
    text-decoration: none !important; font-size: 0.85rem; font-weight: 600; margin-right: 8px; border: 1px solid {BORDER};
}}
.social-link.ig {{ background: rgba(132,17,113,0.08); color: {ACCENT_VIOLET} !important; }}
.social-link.fb {{ background: rgba(1,255,255,0.10); color: {ACCENT_BLUE_TEXT} !important; }}
.social-link.disabled {{ background: rgba(33,31,68,0.05); color: {TEXT_MUTED} !important; cursor: default; }}
.post-card {{
    background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 14px;
    padding: 14px 16px; box-shadow: 0 1px 3px rgba(33,31,68,0.05); margin-bottom: 10px;
}}
.post-meta {{ display: flex; gap: 10px; align-items: center; font-size: 0.78rem; color: {TEXT_MUTED}; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.04em; }}
.post-badge {{ padding: 2px 9px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; }}
.badge-ig {{ background: rgba(132,17,113,0.12); color: {ACCENT_VIOLET}; }}
.badge-fb {{ background: rgba(1,255,255,0.14); color: {ACCENT_BLUE_TEXT}; }}
.post-text {{ font-size: 0.92rem; color: {TEXT_PRIMARY}; line-height: 1.5; margin-bottom: 8px; }}
.post-stats {{ font-size: 0.8rem; color: {TEXT_MUTED}; }}
</style>
""", unsafe_allow_html=True)


def kpi_card(label: str, value: str) -> str:
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'


def derniere_maj(fichier):
    """Date de dernière écriture du fichier source — plus honnête qu'un
    point 'live' animé, vu que les données sont un instantané d'un
    scraping, pas un flux temps réel."""
    if not fichier or not os.path.exists(fichier):
        return None
    return datetime.fromtimestamp(os.path.getmtime(fichier)).strftime("%d/%m/%Y à %H:%M")


def plotly_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=TEXT_MUTED, size=12),
        colorway=CHART_COLORWAY, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(font=dict(color=TEXT_MUTED)),
    )
    fig.update_xaxes(gridcolor="rgba(33,31,68,0.08)", zerolinecolor="rgba(33,31,68,0.14)")
    fig.update_yaxes(gridcolor="rgba(33,31,68,0.08)", zerolinecolor="rgba(33,31,68,0.14)")
    return fig


def _normaliser(texte: str) -> str:
    texte = str(texte or "")
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    texte = texte.lower()
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def trouver_lien(agence: str, liens: dict):
    if agence in liens:
        return liens[agence]
    cible = _normaliser(agence)
    if not cible:
        return None
    meilleur, meilleur_score = None, 0
    for nom, url in liens.items():
        nom_norm = _normaliser(nom)
        if cible == nom_norm:
            return url
        if cible in nom_norm or nom_norm in cible:
            score = min(len(cible), len(nom_norm))
            if score > meilleur_score:
                meilleur, meilleur_score = url, score
    return meilleur


def normaliser_sentiment(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        s = ""
    s = str(s).lower().strip()
    if s in ("positif", "positive"):
        return "positif"
    if s in ("neutre", "neutral"):
        return "neutre"
    if s in ("negatif", "négatif", "negative"):
        return "négatif"
    return "neutre"


# ========================================================================
# CHARGEMENT DES DONNÉES — uniformisé vers un schéma commun, peu importe
# le secteur : agence, source, texte, likes, commentaires, date, url,
# theme, sentiment, type_contenu, langue
# ========================================================================

@st.cache_data
def load_data_marketing():
    with open(FICHIER_POSTS_MARKETING, encoding="utf-8", errors="replace") as f:
        df = pd.read_csv(f)
    df["sentiment"] = df["sentiment"].apply(normaliser_sentiment)
    df["likes"] = pd.to_numeric(df.get("likes", 0), errors="coerce").fillna(0)
    df["commentaires"] = pd.to_numeric(df.get("commentaires", 0), errors="coerce").fillna(0)

    regions_df = pd.DataFrame()
    if os.path.exists(FICHIER_REGIONS_MARKETING):
        regions_df = pd.read_csv(FICHIER_REGIONS_MARKETING)

    return df, regions_df


@st.cache_data
def load_data_telecom():
    """Charge Instagram + Facebook télécom, canonicalise les noms d'opérateur
    (IG et FB utilisent des identifiants différents pour le même opérateur),
    et renomme les colonnes vers le schéma commun."""
    table_canon = {}
    if os.path.exists(FICHIER_COMPTES_TELECOM):
        with open(FICHIER_COMPTES_TELECOM, encoding="utf-8", errors="replace") as f:
            for row in pd.read_csv(f).to_dict("records"):
                operateur = str(row.get("operateur", "")).strip()
                if not operateur:
                    continue
                for col in ("instagram_url", "facebook_url"):
                    url = str(row.get(col, "") or "")
                    identifiant = url.strip().split("?")[0].rstrip("/").split("/")[-1].lower()
                    if identifiant:
                        table_canon[identifiant] = operateur

    lignes = []
    for fichier in FICHIERS_TELECOM:
        if not os.path.exists(fichier):
            continue
        with open(fichier, encoding="utf-8", errors="replace") as f:
            for row in pd.read_csv(f).to_dict("records"):
                auteur_brut = str(row.get("auteur", "")).strip().lower()
                agence = table_canon.get(auteur_brut, row.get("auteur", ""))
                lignes.append({
                    "agence": agence,
                    "source": row.get("source", ""),
                    "texte": row.get("contenu_original", ""),
                    "likes": row.get("likes", 0),
                    "commentaires": 0,
                    "date": row.get("date", ""),
                    "url": row.get("post_url", ""),
                    "theme": row.get("theme", ""),
                    "sentiment": normaliser_sentiment(row.get("sentiment", "")),
                    "type_contenu": row.get("type_contenu", ""),
                    "langue": row.get("langue", ""),
                })

    df = pd.DataFrame(lignes)
    if not df.empty:
        df["likes"] = pd.to_numeric(df["likes"], errors="coerce").fillna(0)

    return df, pd.DataFrame()  # pas de région/domaine pour télécom


@st.cache_data
def load_liens_marketing():
    ig, fb = {}, {}
    if os.path.exists(FICHIER_IG_MARKETING):
        for _, row in pd.read_csv(FICHIER_IG_MARKETING).iterrows():
            if str(row.get("instagram_url", "")).strip():
                ig[row["title"]] = row["instagram_url"]
    if os.path.exists(FICHIER_FB_MARKETING):
        for _, row in pd.read_csv(FICHIER_FB_MARKETING).iterrows():
            if str(row.get("facebook_url", "")).strip():
                fb[row["title"]] = row["facebook_url"]
    return ig, fb


@st.cache_data
def load_liens_telecom():
    ig, fb = {}, {}
    if os.path.exists(FICHIER_COMPTES_TELECOM):
        for _, row in pd.read_csv(FICHIER_COMPTES_TELECOM).iterrows():
            operateur = row.get("operateur", "")
            if str(row.get("instagram_url", "")).strip():
                ig[operateur] = row["instagram_url"]
            if str(row.get("facebook_url", "")).strip():
                fb[operateur] = row["facebook_url"]
    return ig, fb


@st.cache_data
def load_data_dynamique(secteur_slug):
    """Charge un secteur produit par secteur_dynamique.py
    (<slug>_entreprises.csv / <slug>_posts_analyses.csv dans le dossier
    courant). Même principe de canonicalisation que load_data_telecom : le
    nom Instagram/Facebook scrapé (auteur) peut différer du nom officiel
    (title) trouvé sur Google Maps."""
    fichier_entreprises = f"{secteur_slug}_entreprises.csv"
    fichier_posts = f"{secteur_slug}_posts_analyses.csv"

    entreprises_df = pd.DataFrame()
    table_canon = {}
    if os.path.exists(fichier_entreprises):
        entreprises_df = pd.read_csv(fichier_entreprises)
        for row in entreprises_df.to_dict("records"):
            nom = str(row.get("title", "")).strip()
            if not nom:
                continue
            for col in ("instagram_url", "facebook_url"):
                url = str(row.get(col, "") or "")
                identifiant = url.strip().split("?")[0].rstrip("/").split("/")[-1].lower()
                if identifiant:
                    table_canon[identifiant] = nom

    lignes = []
    if os.path.exists(fichier_posts):
        with open(fichier_posts, encoding="utf-8", errors="replace") as f:
            for row in pd.read_csv(f).to_dict("records"):
                auteur_brut = str(row.get("auteur", "")).strip().lower()
                agence = table_canon.get(auteur_brut, row.get("auteur", ""))
                lignes.append({
                    "agence": agence,
                    "source": row.get("source", ""),
                    "texte": row.get("contenu_original", ""),
                    "likes": row.get("likes", 0),
                    "commentaires": 0,  # non capturé par le scraper dynamique
                    "date": row.get("date", ""),
                    "url": row.get("post_url", ""),
                    "theme": row.get("theme", ""),
                    "sentiment": normaliser_sentiment(row.get("sentiment", "")),
                    "type_contenu": row.get("type_contenu", ""),
                    "langue": row.get("langue", ""),
                })

    df = pd.DataFrame(lignes)
    if not df.empty:
        df["likes"] = pd.to_numeric(df["likes"], errors="coerce").fillna(0)

    return df, entreprises_df


@st.cache_data
def load_liens_dynamique(secteur_slug):
    ig, fb = {}, {}
    fichier_entreprises = f"{secteur_slug}_entreprises.csv"
    if os.path.exists(fichier_entreprises):
        for _, row in pd.read_csv(fichier_entreprises).iterrows():
            nom = row.get("title", "")
            if str(row.get("instagram_url", "")).strip():
                ig[nom] = row["instagram_url"]
            if str(row.get("facebook_url", "")).strip():
                fb[nom] = row["facebook_url"]
    return ig, fb


# ========================================================================
# AGENT GÉNÉRIQUE — indépendant du secteur, opère sur le schéma commun.
# Même principe anti-hallucination que les agents CLI : les verdicts
# au-dessus/en-dessous de la moyenne sont calculés en Python, le LLM
# ne fait que rédiger le SWOT à partir de verdicts déjà corrects.
# ========================================================================

def profil_brut(df, nom_entite):
    sous_df = df[df["agence"] == nom_entite]
    if sous_df.empty:
        return {}

    themes = sous_df["theme"].value_counts()
    return {
        "nom": nom_entite,
        "nb_posts": len(sous_df),
        "engagement_moyen": round(sous_df["likes"].mean(), 1),
        "sentiment_positif_pct": round((sous_df["sentiment"] == "positif").mean() * 100),
        "diversite_ratio": round(themes.nunique() / len(sous_df), 2) if len(sous_df) else 0,
        "top_themes": themes.head(4).index.tolist(),
    }


def normaliser_0_100(valeur, mini, maxi):
    if maxi == mini:
        return 50.0
    return round((valeur - mini) / (maxi - mini) * 100, 1)


def verdict_vs_moyenne(valeur, moyenne, unite=""):
    if moyenne == 0:
        return "moyenne non calculable"
    ecart_pct = round((valeur - moyenne) / moyenne * 100)
    if abs(ecart_pct) < 3:
        return f"proche de la moyenne ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"
    elif ecart_pct > 0:
        return f"AU-DESSUS de la moyenne ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"
    else:
        return f"EN DESSOUS de la moyenne ({valeur}{unite} vs {moyenne}{unite}, {ecart_pct:+d}%)"


def calculer_scores(profils):
    engagements = [p["engagement_moyen"] for p in profils]
    sentiments = [p["sentiment_positif_pct"] for p in profils]
    frequences = [p["nb_posts"] for p in profils]
    diversites = [p["diversite_ratio"] for p in profils]

    moyennes = {
        "moy_engagement": round(sum(engagements) / len(engagements), 1),
        "moy_sentiment": round(sum(sentiments) / len(sentiments), 1),
        "moy_frequence": round(sum(frequences) / len(frequences), 1),
        "moy_diversite": round(sum(diversites) / len(diversites), 2),
    }

    for p in profils:
        d = {
            "engagement": round(normaliser_0_100(p["engagement_moyen"], min(engagements), max(engagements)) * POIDS["engagement"], 1),
            "sentiment": round(normaliser_0_100(p["sentiment_positif_pct"], min(sentiments), max(sentiments)) * POIDS["sentiment"], 1),
            "frequence": round(normaliser_0_100(p["nb_posts"], min(frequences), max(frequences)) * POIDS["frequence"], 1),
            "diversite": round(normaliser_0_100(p["diversite_ratio"], min(diversites), max(diversites)) * POIDS["diversite"], 1),
        }
        p["detail_score"] = d
        p["score_final"] = round(sum(d.values()), 1)
        p["verdict_engagement"] = verdict_vs_moyenne(p["engagement_moyen"], moyennes["moy_engagement"])
        p["verdict_frequence"] = verdict_vs_moyenne(p["nb_posts"], moyennes["moy_frequence"], " posts")
        p["verdict_sentiment"] = verdict_vs_moyenne(p["sentiment_positif_pct"], moyennes["moy_sentiment"], "%")
        p["verdict_diversite"] = verdict_vs_moyenne(p["diversite_ratio"], moyennes["moy_diversite"])

    profils.sort(key=lambda p: p["score_final"], reverse=True)
    for i, p in enumerate(profils):
        p["priorite"] = i + 1

    return profils, moyennes


def render_classement(df, agences):
    """Classement pondéré des entités filtrées : agrégats et score calculés
    en Python (calculer_scores, déjà utilisé par l'agent IA plus bas), donc
    disponible instantanément et sans consommer de budget Groq. C'est la
    méthode de scoring du projet rendue visible, pas un graphique générique."""
    profils_bruts = [profil_brut(df, nom) for nom in agences]
    profils_bruts = [p for p in profils_bruts if p]
    if len(profils_bruts) < 2:
        st.info("Sélectionne au moins 2 entités dans la sidebar pour voir le classement pondéré.")
        return None, None

    profils, moyennes = calculer_scores(profils_bruts)
    ordre = [p["nom"] for p in profils]

    lignes = []
    for p in profils:
        for composante, valeur in p["detail_score"].items():
            lignes.append({"entreprise": p["nom"], "composante": composante.capitalize(), "valeur": valeur})
    df_classement = pd.DataFrame(lignes)

    fig = px.bar(
        df_classement, x="valeur", y="entreprise", color="composante", orientation="h",
        color_discrete_map=COULEURS_SCORE,
    )
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(ordre)))
    fig.update_xaxes(range=[0, 114])
    fig = plotly_theme(fig)
    fig.update_layout(
        barmode="stack", height=max(64 * len(profils), 200),
        legend_title_text="", xaxis_title="", yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=44, t=36, b=10),
    )
    for p in profils:
        fig.add_annotation(
            x=p["score_final"] + 3, y=p["nom"], text=f"<b>{p['score_final']}</b>",
            showarrow=False, xanchor="left", font=dict(size=13, color=TEXT_PRIMARY),
        )

    return fig, (profils, moyennes)
PROMPT_TEMPLATE = """Tu es un consultant en intelligence concurrentielle rigoureux, spécialisé
dans les {analyst_role}.

RÈGLE ABSOLUE N°1 : ne cite jamais un fait ou un chiffre absent des données ci-dessous.

RÈGLE ABSOLUE N°2 : chaque profil contient déjà des champs "verdict_engagement",
"verdict_frequence", "verdict_sentiment", "verdict_diversite", DÉJÀ CALCULÉS et CORRECTS.
INTERDICTION de les recalculer toi-même — utilise-les tels quels.

Contexte : {contexte}
Données (moyennes du groupe : engagement {moy_engagement}, fréquence {moy_frequence} posts,
sentiment positif {moy_sentiment}%, diversité {moy_diversite}) :
{profils_json}

{question_section}

Pour CHAQUE entité, génère un SWOT basé UNIQUEMENT sur les chiffres et verdicts fournis :
- Forces : max 2, appuyées sur un verdict "AU-DESSUS de la moyenne"
- Faiblesses : max 2, appuyées sur un verdict "EN DESSOUS de la moyenne" (sinon "Aucune faiblesse notable")
- Opportunités : basées sur ce que font mieux les autres
- Menaces : basées sur l'écart avec le leader

Réponds au format JSON STRICT, en respectant CET ORDRE de clés :
{{
  "reponse_question": "réponse détaillée, chiffrée",
  "synthese_secteur": "3-4 phrases de synthèse globale, chiffrée",
  "swot_par_agence": [{{"priorite": 1, "nom": "...", "forces": ["..."], "faiblesses": ["..."], "opportunites": ["..."], "menaces": ["..."]}}]
}}
"""


def generer_analyse(profils, moyennes, contexte, analyst_role, question=None, retries=4):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY n'est pas définie dans l'environnement.")

    client = Groq(api_key=GROQ_API_KEY)

    if question:
        question_section = f'QUESTION MÉTIER : "{question}"\nRéponds dans "reponse_question".'
    else:
        question_section = ('QUESTION PAR DÉFAUT : "Pourquoi l\'entité en priorité 1 est-elle devant les '
                             'autres, et comment les suivantes pourraient-elles la rattraper ?"\n'
                             'Réponds dans "reponse_question".')

    prompt = PROMPT_TEMPLATE.format(
        analyst_role=analyst_role, contexte=contexte,
        moy_engagement=moyennes["moy_engagement"], moy_frequence=moyennes["moy_frequence"],
        moy_sentiment=moyennes["moy_sentiment"], moy_diversite=moyennes["moy_diversite"],
        profils_json=json.dumps(profils, ensure_ascii=False, indent=2),
        question_section=question_section,
    )

    derniere_raison = "raison inconnue"

    for tentative in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=min(600 + 350 * len(profils), 8000),
                response_format={"type": "json_object"},
            )
            texte = (response.choices[0].message.content or "").strip()
            texte = texte.replace("```json", "").replace("```", "").strip()
            if not texte:
                derniere_raison = "réponse vide renvoyée par le modèle"
                time.sleep(2)
                continue
            resultat = json.loads(texte)
            cles_attendues = {"swot_par_agence", "reponse_question", "synthese_secteur"}
            cles_manquantes = cles_attendues - resultat.keys()
            if cles_manquantes:
                derniere_raison = f"clés manquantes dans la réponse : {', '.join(cles_manquantes)}"
                time.sleep(2)
                continue
            return resultat
        except json.JSONDecodeError as e:
            derniere_raison = f"JSON invalide ({e})"
            time.sleep(2)
        except Exception as e:
            derniere_raison = f"{type(e).__name__} : {e}"
            if "rate_limit" in str(e).lower() or "429" in str(e):
                break  # inutile de retenter dans la minute contre un plafond de tokens/jour
            time.sleep(min(2 ** tentative, 15))

    raise RuntimeError(
        f"Impossible d'obtenir une réponse JSON valide après {retries} tentatives. "
        f"Dernière raison observée : {derniere_raison}"
    )


# ========================================================================
# SIDEBAR — SÉLECTEUR DE SECTEUR + FILTRES
# ========================================================================

secteurs_dynamiques = lister_secteurs_disponibles()  # {slug: nom affichable}

st.sidebar.markdown("### ◆ Secteur")
options_secteur = list(SECTEURS.keys()) + list(secteurs_dynamiques.values())
secteur = st.sidebar.selectbox("Choisir un secteur", options_secteur, key="secteur_select")

section_nouveau_secteur()  # formulaire "Nouveau secteur" + suivi de progression en direct

st.sidebar.markdown("### ◆ Filtres")

if secteur in SECTEURS:
    config_secteur = SECTEURS[secteur]
    if secteur == "Marketing":
        posts_df, regions_df = load_data_marketing()
        instagram_links, facebook_links = load_liens_marketing()
        fichier_reference = FICHIER_POSTS_MARKETING
    else:
        posts_df, regions_df = load_data_telecom()
        instagram_links, facebook_links = load_liens_telecom()
        fichier_reference = next((f for f in FICHIERS_TELECOM if os.path.exists(f)), None)
else:
    # Secteur découvert dynamiquement (produit par secteur_dynamique.py)
    config_secteur = {
        "a_region_domaine": False,
        "analyst_role": f"entreprises tunisiennes du secteur « {secteur} »",
    }
    slug_choisi = next(s for s, nom in secteurs_dynamiques.items() if nom == secteur)
    posts_df, entreprises_df = load_data_dynamique(slug_choisi)
    regions_df = pd.DataFrame()
    instagram_links, facebook_links = load_liens_dynamique(slug_choisi)
    fichier_reference = f"{slug_choisi}_posts_analyses.csv"


if posts_df.empty:
    st.error(f"Aucune donnée trouvée pour le secteur « {secteur} ». Vérifie que les fichiers attendus sont présents.")
    st.stop()

region_choisie, domaine_choisi = "Toutes", "Tous"

if config_secteur["a_region_domaine"] and not regions_df.empty:
    regions_disponibles = sorted(regions_df["ville"].dropna().unique().tolist())
    domaines_disponibles = sorted(regions_df["domaine"].dropna().unique().tolist())
    region_choisie = st.sidebar.selectbox("Région", ["Toutes"] + regions_disponibles)
    domaine_choisi = st.sidebar.selectbox("Domaine", ["Tous"] + domaines_disponibles)

    filtre = regions_df.copy()
    if region_choisie != "Toutes":
        filtre = filtre[filtre["ville"].str.contains(region_choisie, case=False, na=False)]
    if domaine_choisi != "Tous":
        filtre = filtre[filtre["domaine"].str.contains(domaine_choisi, case=False, na=False)]
    agences_filtrees = filtre["agence"].tolist() if not filtre.empty else regions_df["agence"].tolist()
else:
    agences_filtrees = sorted(posts_df["agence"].dropna().unique().tolist())

agences_selection = st.sidebar.multiselect("Agences (vide = toutes)", sorted(set(agences_filtrees)), default=[])
if agences_selection:
    agences_filtrees = agences_selection

df_filtre = posts_df[posts_df["agence"].isin(agences_filtrees)].copy()

st.sidebar.divider()
st.sidebar.caption(f"Competitive Pulse v2 · {secteur}")

tab1, tab2 = st.tabs(["📊 Vue d'ensemble", "🏢 Fiche agence"])

with tab1:
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown('<div class="pulse-logo">◆ COMPETITIVE PULSE</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pulse-sub">{secteur} · {region_choisie} · {domaine_choisi} · '
                    f'{len(agences_filtrees)} entité(s) suivie(s)</div>', unsafe_allow_html=True)
    with h2:
        maj = derniere_maj(fichier_reference)
        texte_maj = f"Données du {maj}" if maj else "Date de collecte inconnue"
        st.markdown(f'<div style="text-align:right; padding-top:14px;">'
                     f'<span class="pulse-live">{texte_maj}</span></div>',
                     unsafe_allow_html=True)

    st.write("")

    sentiment_pos_pct = round((df_filtre["sentiment"] == "positif").mean() * 100) if len(df_filtre) else 0
    eng_moyen = f"{df_filtre['likes'].mean():.1f}" if len(df_filtre) else "—"

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("Entités suivies", str(df_filtre["agence"].nunique())), unsafe_allow_html=True)
    k2.markdown(kpi_card("Posts analysés", str(len(df_filtre))), unsafe_allow_html=True)
    k3.markdown(kpi_card("Engagement moyen", eng_moyen), unsafe_allow_html=True)
    k4.markdown(kpi_card("Sentiment positif", f"{sentiment_pos_pct}%"), unsafe_allow_html=True)

    st.write("")

    st.markdown('<div class="section-title">Classement pondéré</div>', unsafe_allow_html=True)
    st.caption("Engagement 45 % · Sentiment 20 % · Fréquence 20 % · Diversité 15 % — score normalisé sur 100, sans appel IA.")
    st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
    fig_classement, donnees_classement = render_classement(df_filtre, agences_filtrees)
    if fig_classement is not None:
        st.plotly_chart(fig_classement, width='stretch', config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    g2, g3 = st.columns(2)
    with g2:
        st.markdown('<div class="section-title">Répartition du sentiment</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
        sentiment_counts = df_filtre["sentiment"].value_counts().reset_index()
        sentiment_counts.columns = ["sentiment", "nb"]
        couleurs_sentiment = {"positif": SUCCESS, "neutre": TEXT_MUTED, "négatif": DANGER}
        fig = go.Figure(data=[go.Pie(
            labels=sentiment_counts["sentiment"], values=sentiment_counts["nb"], hole=0.62,
            marker=dict(colors=[couleurs_sentiment.get(s, ACCENT_VIOLET) for s in sentiment_counts["sentiment"]],
                        line=dict(color=BG_PANEL, width=3)),
            textfont=dict(color=TEXT_PRIMARY),
        )])
        fig.update_layout(height=320, showlegend=True)
        st.plotly_chart(plotly_theme(fig), width='stretch', config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with g3:
        st.markdown('<div class="section-title">Engagement moyen par entité</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
        eng_par_agence = df_filtre.groupby("agence")["likes"].mean().sort_values(ascending=False).reset_index()
        fig = px.bar(eng_par_agence, x="agence", y="likes", color="likes", color_continuous_scale=GRADIENT_SCALE)
        fig.update_layout(height=320, coloraxis_showscale=False)
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(plotly_theme(fig), width='stretch', config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Types de contenu</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
    if "type_contenu" in df_filtre.columns:
        types_counts = df_filtre["type_contenu"].value_counts().head(8).reset_index()
        types_counts.columns = ["type_contenu", "nb"]
        fig = px.bar(types_counts, x="nb", y="type_contenu", orientation="h",
                     color="nb", color_continuous_scale=GRADIENT_SCALE)
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=280, coloraxis_showscale=False)
        st.plotly_chart(plotly_theme(fig), width='stretch', config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    st.write("")

    st.markdown('<div class="section-title">Analyse stratégique par l\'agent IA</div>', unsafe_allow_html=True)
    st.caption("Rédige le SWOT et répond à ta question à partir du classement ci-dessus — c'est le seul bloc qui appelle Groq.")

    if not GROQ_API_KEY:
        st.warning("GROQ_API_KEY n'est pas définie — définis-la dans le terminal avant de lancer streamlit.")

    question_libre = st.text_input(
        "Question métier optionnelle", placeholder="Ex : Comment X peut-elle dépasser Y ?",
        label_visibility="collapsed",
    )

    if st.button("Lancer l'analyse IA", type="primary"):
        if len(agences_filtrees) < 2:
            st.warning("Sélectionne au moins 2 entités pour une comparaison pertinente.")
        else:
            with st.spinner("L'agent calcule les scores et génère le SWOT..."):
                profils_bruts = [profil_brut(df_filtre, nom) for nom in agences_filtrees]
                profils_bruts = [p for p in profils_bruts if p]

                if not profils_bruts:
                    st.error("Aucune donnée exploitable pour ces entités.")
                else:
                    profils, moyennes = calculer_scores(profils_bruts)
                    contexte = f"{secteur} — {region_choisie} / {domaine_choisi}" if config_secteur["a_region_domaine"] else secteur
                    try:
                        resultat = generer_analyse(profils, moyennes, contexte, config_secteur["analyst_role"], question_libre or None)
                    except Exception as e:
                        st.error(f"Erreur lors de la génération : {e}")
                        resultat = None

                    if resultat:
                        st.write("")
                        st.markdown(f'<div class="insight-banner"><b>Réponse à la question métier</b><br><br>'
                                    f'{resultat.get("reponse_question", "Non générée.")}</div>', unsafe_allow_html=True)
                        st.write("")
                        st.markdown('<div class="section-title">Synthèse du secteur</div>', unsafe_allow_html=True)
                        st.write(resultat.get("synthese_secteur", "Non générée."))
                        st.write("")
                        st.markdown('<div class="section-title">SWOT détaillé</div>', unsafe_allow_html=True)

                        for s in resultat.get("swot_par_agence", []):
                            with st.expander(f"№{s.get('priorite', '?')} · {s.get('nom', 'Inconnu')}"):
                                c1, c2 = st.columns(2)
                                with c1:
                                    forces_html = "".join(f'<div class="swot-item">✓ {f}</div>' for f in s.get("forces", []))
                                    faiblesses_html = "".join(f'<div class="swot-item">△ {f}</div>' for f in s.get("faiblesses", []))
                                    st.markdown(f'<div class="swot-box swot-forces"><div class="swot-title">Forces</div>{forces_html}</div>', unsafe_allow_html=True)
                                    st.markdown(f'<div class="swot-box swot-faiblesses"><div class="swot-title">Faiblesses</div>{faiblesses_html}</div>', unsafe_allow_html=True)
                                with c2:
                                    opp_html = "".join(f'<div class="swot-item">→ {o}</div>' for o in s.get("opportunites", []))
                                    menaces_html = "".join(f'<div class="swot-item">! {m}</div>' for m in s.get("menaces", []))
                                    st.markdown(f'<div class="swot-box swot-opportunites"><div class="swot-title">Opportunités</div>{opp_html}</div>', unsafe_allow_html=True)
                                    st.markdown(f'<div class="swot-box swot-menaces"><div class="swot-title">Menaces</div>{menaces_html}</div>', unsafe_allow_html=True)

# ========================================================================
# ONGLET 2 — FICHE AGENCE / OPÉRATEUR
# ========================================================================

with tab2:
    st.markdown('<div class="section-title">Fiche agence</div>', unsafe_allow_html=True)
    st.caption("Nom, liens sociaux, dernières publications, et analyse complète.")

    toutes_agences = sorted(posts_df["agence"].dropna().unique().tolist())
    if not toutes_agences:
        st.warning("Aucune entité disponible dans les données.")
        st.stop()

    agence_choisie = st.selectbox("Choisir une entité", toutes_agences, key="fiche_agence_select")
    st.write("")

    lien_ig = trouver_lien(agence_choisie, instagram_links)
    lien_fb = trouver_lien(agence_choisie, facebook_links)

    liens_html = ""
    liens_html += (f'<a class="social-link ig" href="{lien_ig}" target="_blank">◆ Instagram</a>' if lien_ig
                   else '<span class="social-link disabled">◆ Instagram non trouvé</span>')
    liens_html += (f'<a class="social-link fb" href="{lien_fb}" target="_blank">◆ Facebook</a>' if lien_fb
                   else '<span class="social-link disabled">◆ Facebook non trouvé</span>')

    st.markdown(f'<div class="agency-header"><div class="agency-name">{agence_choisie}</div>'
                f'<div>{liens_html}</div></div>', unsafe_allow_html=True)
    st.write("")

    posts_agence = posts_df[posts_df["agence"] == agence_choisie].copy()
    posts_agence["likes"] = pd.to_numeric(posts_agence["likes"], errors="coerce").fillna(0)
    posts_agence["commentaires"] = pd.to_numeric(posts_agence.get("commentaires", 0), errors="coerce").fillna(0)

    if posts_agence.empty:
        st.info("Aucun post trouvé pour cette entité.")
    else:
        posts_agence_triee = posts_agence.sort_values("date", ascending=False, na_position="last")

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi_card("Total posts", str(len(posts_agence))), unsafe_allow_html=True)
        k2.markdown(kpi_card("Likes moyens", f"{posts_agence['likes'].mean():.1f}"), unsafe_allow_html=True)
        sentiment_pos = round((posts_agence["sentiment"] == "positif").mean() * 100) if len(posts_agence) else 0
        k3.markdown(kpi_card("Sentiment positif", f"{sentiment_pos}%"), unsafe_allow_html=True)
        theme_principal = posts_agence["theme"].value_counts().idxmax() if posts_agence["theme"].notna().any() else "—"
        k4.markdown(kpi_card("Thème principal", str(theme_principal)[:22]), unsafe_allow_html=True)

        st.write("")
        st.markdown('<div class="section-title">Dernières publications</div>', unsafe_allow_html=True)

        for _, post in posts_agence_triee.head(2).iterrows():
            source = post.get("source", "")
            badge_class = "badge-ig" if source == "instagram" else "badge-fb"
            date_aff = str(post.get("date", ""))[:10] or "date inconnue"
            texte_aff = (str(post.get("texte", "")) or "")[:280]
            if len(str(post.get("texte", ""))) > 280:
                texte_aff += "…"

            st.markdown(f"""
            <div class="post-card">
                <div class="post-meta">
                    <span class="post-badge {badge_class}">{source}</span>
                    <span>{date_aff}</span>
                    <span>· {post.get('theme', 'thème non précisé')}</span>
                    <span>· sentiment {post.get('sentiment', '—')}</span>
                </div>
                <div class="post-text">{texte_aff}</div>
                <div class="post-stats">👍 {int(post['likes'])} likes · 💬 {int(post['commentaires'])} commentaires</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown('<div class="section-title">Analyse complète des publications</div>', unsafe_allow_html=True)

        langues = posts_agence["langue"].value_counts()
        langue_dominante = langues.idxmax() if len(langues) else "non détectée"
        types_contenu = posts_agence["type_contenu"].value_counts()
        type_dominant = types_contenu.idxmax() if len(types_contenu) else "non détecté"
        themes_top3 = posts_agence["theme"].value_counts().head(3).index.tolist()

        synthese_agence = (
            f"Sur {len(posts_agence)} publications analysées, {agence_choisie} communique "
            f"majoritairement en {langue_dominante}, avec un contenu à dominante « {type_dominant} ». "
            f"Les thèmes les plus récurrents sont : {', '.join(themes_top3) if themes_top3 else 'non déterminés'}. "
            f"Le sentiment général des publications est positif dans {sentiment_pos}% des cas, "
            f"pour un engagement moyen de {posts_agence['likes'].mean():.1f} likes par post."
        )
        st.markdown(f'<div class="insight-banner">{synthese_agence}</div>', unsafe_allow_html=True)

        st.write("")
        st.markdown('<div class="section-title">Analyse SWOT</div>', unsafe_allow_html=True)
        st.caption("Compare cette entité aux autres entités du même secteur (et, pour le marketing, de la même région/domaine si sélectionnés).")

        if st.button("Générer le SWOT de cette entité", type="primary", key="swot_fiche_agence"):
            concurrents = agences_filtrees if agence_choisie in agences_filtrees else toutes_agences

            if len(concurrents) < 2:
                st.warning("Pas assez d'entités comparables trouvées avec les filtres actuels.")
            else:
                with st.spinner("L'agent compare cette entité à ses concurrents..."):
                    profils_bruts = [profil_brut(posts_df, nom) for nom in concurrents]
                    profils_bruts = [p for p in profils_bruts if p]
                    profils, moyennes = calculer_scores(profils_bruts)
                    contexte = f"{secteur} — {region_choisie} / {domaine_choisi}" if config_secteur["a_region_domaine"] else secteur

                    try:
                        resultat = generer_analyse(profils, moyennes, contexte, config_secteur["analyst_role"])
                    except Exception as e:
                        st.error(f"Erreur lors de la génération : {e}")
                        resultat = None

                    if resultat:
                        swot_agence = next((s for s in resultat.get("swot_par_agence", []) if s.get("nom") == agence_choisie), None)
                        if not swot_agence:
                            st.warning("Cette entité n'apparaît pas dans le SWOT généré (données insuffisantes).")
                        else:
                            st.write("")
                            c1, c2 = st.columns(2)
                            with c1:
                                forces_html = "".join(f'<div class="swot-item">✓ {f}</div>' for f in swot_agence.get("forces", []))
                                faiblesses_html = "".join(f'<div class="swot-item">△ {f}</div>' for f in swot_agence.get("faiblesses", []))
                                st.markdown(f'<div class="swot-box swot-forces"><div class="swot-title">Forces</div>{forces_html}</div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="swot-box swot-faiblesses"><div class="swot-title">Faiblesses</div>{faiblesses_html}</div>', unsafe_allow_html=True)
                            with c2:
                                opp_html = "".join(f'<div class="swot-item">→ {o}</div>' for o in swot_agence.get("opportunites", []))
                                menaces_html = "".join(f'<div class="swot-item">! {m}</div>' for m in swot_agence.get("menaces", []))
                                st.markdown(f'<div class="swot-box swot-opportunites"><div class="swot-title">Opportunités</div>{opp_html}</div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="swot-box swot-menaces"><div class="swot-title">Menaces</div>{menaces_html}</div>', unsafe_allow_html=True)

                            st.caption(f"Priorité {swot_agence.get('priorite', '?')}/{len(concurrents)}.")