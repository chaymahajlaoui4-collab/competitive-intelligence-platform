"""
Analyse automatique de posts (LinkedIn/Facebook/Instagram) via Groq (GRATUIT, rapide).
Prend un CSV de posts scrapés (colonne 'postContent') et produit un CSV enrichi
avec : type de contenu, thème, produit/service, promotion, langue, hashtags...

Usage :
    py analyze_posts_groq.py result.csv
"""

import csv
import json
import sys
import time
from groq import Groq

# ============================================
# METS TA CLÉ API GROQ ICI (gratuite sur console.groq.com)
# ============================================
import os
client = Groq(api_key=os.environ.get("GROQ_API_KEY","")) 
              
MODELE = " openai/gpt-oss-120b"  # bon modèle gratuit et performant sur Groq

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


def analyser_post(post_content: str) -> dict:
    """Envoie un post au LLM (via Groq) et retourne l'extraction structurée."""
    if not post_content or not post_content.strip():
        return {"erreur": "post vide"}

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


def analyser_csv(chemin_csv: str, chemin_sortie: str = "posts_analyses.csv"):
    with open(chemin_csv, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        posts = list(reader)

    resultats = []
    for i, post in enumerate(posts):
        contenu = post.get("postContent", "")
        if not contenu.strip():
            continue

        print(f"Analyse du post {i+1}/{len(posts)}...")
        analyse = analyser_post(contenu)

        resultats.append({
            "post_url": post.get("postUrl", ""),
            "auteur": post.get("author", ""),
            "date": post.get("postDate", ""),
            "likes": post.get("likeCount", ""),
            "contenu_original": contenu[:200],
            **analyse,
        })

        time.sleep(1)  # petite pause pour rester dans les limites gratuites

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
    analyser_csv(chemin)