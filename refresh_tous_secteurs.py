"""
refresh_tous_secteurs.py — rafraîchit tous les secteurs dynamiques connus
en une seule commande, pensé pour être appelé par le Planificateur de
tâches Windows (une seule tâche planifiée au lieu d'une par secteur).

Ajoute une ligne à SECTEURS à chaque nouveau secteur scrapé — pas besoin
de créer une nouvelle tâche planifiée à chaque fois, celle-ci les couvre
toutes.

USAGE (identique à ce que ferait le Planificateur) :
    py refresh_tous_secteurs.py
"""

import subprocess
import sys
from pathlib import Path

# Ajoute ici chaque secteur déjà scrapé, avec la région utilisée au départ.
SECTEURS = [
    ("assurance", "Sfax"),
    ("immobilier", "Sfax"),
]

MAX_ENTREPRISES = "10"  # volume prudent : tâche planifiée, personne pour réagir à un rate limit
MAX_POSTS = "10"

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs_refresh"
LOG_DIR.mkdir(exist_ok=True)


def main():
    for secteur, ville in SECTEURS:
        print(f"\n=== Rafraîchissement : {secteur} / {ville} ===")
        log_path = LOG_DIR / f"{secteur}.log"
        with open(log_path, "w", encoding="utf-8") as log_file:
            resultat = subprocess.run(
                [sys.executable, str(BASE_DIR / "secteur_dynamique.py"), secteur, ville,
                 "--max-entreprises", MAX_ENTREPRISES, "--max-posts", MAX_POSTS],
                cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT,
            )
        if resultat.returncode == 0:
            print(f"  -> OK (détails dans {log_path.name})")
        else:
            print(f"  -> ÉCHEC, code {resultat.returncode} (détails dans {log_path.name})")


if __name__ == "__main__":
    main()
