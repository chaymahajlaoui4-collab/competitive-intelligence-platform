"""
Analyse automatique de posts via LLM (Groq, gratuit) - gère 3 formats de sources :
- LinkedIn (colonnes : postContent, postUrl, author, likeCount, postDate)
- Facebook  (colonnes : content, url, page_name, likes, date_posted)
- Instagram (colonnes : account, posts [JSON imbriqué avec caption/likes/datetime/url])

Le script détecte automatiquement le format et normalise tout vers une structure commune
avant de lancer l'analyse.

Usage :
    py analyze_multi_source.py mon_fichier.csv
"""
import csv
import json
import sys
import time
from groq import Groq

# ============================================
# METS TA CLÉ API GROQ ICI
# ============================================
import os
client = Groq(api_key=os.environ.get("GROQ_API_KEY",""))

MODELE = " openai/gpt-oss-120b"

PROMPT_TEMPLATE = """Tu es un analyste marketing. Analyse ce post de réseau social d'une banque tunisienne et extrais les informations suivantes au format JSON STRICT (rien d'autre que le JSON, pas de texte avant/après, pas de ```json) :

{{
  "langue": "français|arabe|mixte|anglais",
  "type_contenu": "promotion produit|information pratique|relations publiques|actualité|recrutement|autre",
  "theme": "résumé en 3-5 mots du sujet principal",
  "produit_service": "nom du produit/service mentionné, ou null",
  "promotion": "description de l'offre/promo si présente, ou null",
  "hashtags": ["liste", "des", "hashtags"],
  "sentiment": "positif|neutre|négatif"
}}

Post à analyser :
\"\"\"{post_content}\"\"\"
"""


# ============================================
# NORMALISATION : ramène chaque format vers une structure commune
# {source, auteur, post_url, date, likes, contenu}
# ============================================

def normaliser_linkedin(rows):
    normalises = []
    for r in rows:
        contenu = r.get("postContent", "")
        if not contenu.strip():
            continue
        normalises.append({
            "source": "linkedin",
            "auteur": r.get("author", ""),
            "post_url": r.get("postUrl", ""),
            "date": r.get("postDate", ""),
            "likes": r.get("likeCount", ""),
            "contenu": contenu,
        })
    return normalises


def normaliser_facebook(rows):
    normalises = []
    for r in rows:
        contenu = r.get("content", "")
        if not contenu.strip():
            continue
        normalises.append({
            "source": "facebook",
            "auteur": r.get("page_name", ""),
            "post_url": r.get("url", ""),
            "date": r.get("date_posted", ""),
            "likes": r.get("likes", ""),
            "contenu": contenu,
        })
    return normalises


def normaliser_instagram(rows):
    """Chaque ligne = un compte, avec une colonne 'posts' contenant un JSON de plusieurs posts."""
    normalises = []
    for r in rows:
        compte = r.get("account", "") or r.get("profile_name", "")
        posts_brut = r.get("posts", "")
        if not posts_brut or not posts_brut.strip():
            continue
        try:
            posts = json.loads(posts_brut)
        except json.JSONDecodeError:
            continue
        for p in posts:
            contenu = p.get("caption", "") or ""
            if not contenu.strip():
                continue
            normalises.append({
                "source": "instagram",
                "auteur": compte,
                "post_url": p.get("url", ""),
                "date": p.get("datetime", ""),
                "likes": p.get("likes", ""),
                "contenu": contenu,
            })
    return normalises


def detecter_et_normaliser(chemin_csv):
    with open(chemin_csv, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        colonnes = reader.fieldnames or []

    if "postContent" in colonnes:
        print("Format détecté : LinkedIn")
        return normaliser_linkedin(rows)
    elif "posts" in colonnes and "account" in colonnes:
        print("Format détecté : Instagram (profils avec posts imbriqués)")
        return normaliser_instagram(rows)
    elif "content" in colonnes and "page_name" in colonnes:
        print("Format détecté : Facebook")
        return normaliser_facebook(rows)
    else:
        raise ValueError(
            "Format de CSV non reconnu. Colonnes trouvées : " + str(colonnes)
        )


# ============================================
# ANALYSE LLM (identique pour toutes les sources une fois normalisées)
# ============================================

def analyser_post(post_content):
    if not post_content or not post_content.strip():
        return {"erreur": "post vide"}

    texte_reponse = ""
    try:
        response = client.chat.completions.create(
            model=MODELE,
            messages=[{
                "role": "user",
                "content": PROMPT_TEMPLATE.format(post_content=post_content)
            }],
            temperature=0.2,
            max_tokens=500,
        )
        texte_reponse = response.choices[0].message.content.strip()
        texte_reponse = texte_reponse.replace("```json", "").replace("```", "").strip()
        return json.loads(texte_reponse)
    except json.JSONDecodeError:
        return {"erreur": "réponse non parsable", "brut": texte_reponse}
    except Exception as e:
        return {"erreur": str(e)}


def analyser_csv(chemin_csv, chemin_sortie="posts_analyses.csv"):
    posts_normalises = detecter_et_normaliser(chemin_csv)
    print(f"{len(posts_normalises)} posts valides trouvés à analyser.\n")

    resultats = []
    for i, post in enumerate(posts_normalises):
        print(f"Analyse du post {i+1}/{len(posts_normalises)} ({post['source']})...")
        analyse = analyser_post(post["contenu"])

        resultats.append({
            "source": post["source"],
            "auteur": post["auteur"],
            "post_url": post["post_url"],
            "date": post["date"],
            "likes": post["likes"],
            "contenu_original": post["contenu"][:200],
            **analyse,
        })

        time.sleep(1)

    if resultats:
        toutes_colonnes = set()
        for r in resultats:
            toutes_colonnes.update(r.keys())

        with open(chemin_sortie, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(toutes_colonnes))
            writer.writeheader()
            writer.writerows(resultats)

        print(f"\n{len(resultats)} posts analysés -> sauvegardés dans {chemin_sortie}")
    else:
        print("Aucun post valide à analyser.")


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "result.csv"
    sortie = sys.argv[2] if len(sys.argv) > 2 else "posts_analyses.csv"
    analyser_csv(chemin, sortie)