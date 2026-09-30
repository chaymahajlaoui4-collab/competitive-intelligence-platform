"""
========================================================================
 ORCHESTRATEUR : lance le pipeline complet pour un ou plusieurs secteurs
========================================================================

Enchaîne automatiquement les étapes 0a -> 0 -> 1 -> 1b -> 2 -> 2b -> 2c -> 3
pour chaque secteur demandé.

USAGE :
    python run_pipeline.py marketing
    python run_pipeline.py marketing banques immobilier
    python run_pipeline.py tous          (lance les 11 secteurs définis)

Astuce : si le script s'arrête sur une erreur (ex: quota Groq/Apify
dépassé), relance simplement la même commande — chaque étape reprend
automatiquement là où elle s'était arrêtée grâce aux fichiers déjà
présents dans data/<secteur>/.
========================================================================
"""

import subprocess
import sys
from sectors_config import SECTORS

STEPS = [
    "0a_scrape_google_maps.py",
    "0_prepare_data_v2.py",
    "1_find_instagram_v2.py",
    "1b_find_facebook_v2.py",
    "2_scrape_instagram_posts_v2.py",
    "2b_scrape_facebook_posts_v2.py",
    "2c_clean_merge_posts_v2.py",
    "3_analyze_posts_groq_v2.py",
]


def run_step(script, sector_key):
    print()
    print("=" * 70)
    print(f"  {script}  —  secteur : {sector_key}")
    print("=" * 70)
    result = subprocess.run([sys.executable, script, sector_key])
    if result.returncode != 0:
        print(f"⚠ L'étape {script} a échoué pour le secteur '{sector_key}'.")
        print("  Corrige le problème puis relance la même commande pour reprendre.")
        return False
    return True


def run_sector(sector_key):
    print()
    print("#" * 70)
    print(f"#  SECTEUR : {sector_key}")
    print("#" * 70)
    for script in STEPS:
        ok = run_step(script, sector_key)
        if not ok:
            return False
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python run_pipeline.py <secteur1> [secteur2 ...] | tous")
        print(f"Secteurs disponibles : {', '.join(SECTORS.keys())}")
        sys.exit(1)

    if sys.argv[1] == "tous":
        sectors_to_run = list(SECTORS.keys())
    else:
        sectors_to_run = sys.argv[1:]

    for key in sectors_to_run:
        if key not in SECTORS:
            print(f"Secteur inconnu ignoré : '{key}'")
            continue
        success = run_sector(key)
        if not success:
            print(f"\nArrêt du pipeline sur le secteur '{key}'. Corrige puis relance.")
            sys.exit(1)

    print("\n✓ Pipeline terminé pour tous les secteurs demandés.")
