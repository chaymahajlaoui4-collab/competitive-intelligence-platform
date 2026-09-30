@echo off
REM ========================================================================
REM Lance le pipeline de veille marketing et garde une trace dans un log.
REM A adapter : remplace le chemin ci-dessous par ton vrai dossier projet.
REM ========================================================================

cd /d "C:\Users\chaym\OneDrive\Bureau\PROJET STAGE BRIMA"

echo ============================================ >> log_veille.txt
echo Lancement : %date% %time% >> log_veille.txt
echo ============================================ >> log_veille.txt

if not exist "run_pipeline.py" (
    echo ERREUR : run_pipeline.py est introuvable dans %cd% >> log_veille.txt
    echo Verifie que le fichier est bien sauvegarde dans ce dossier. >> log_veille.txt
    goto :fin
)

py run_pipeline.py marketing >> log_veille.txt 2>&1

:fin
echo Termine : %date% %time% >> log_veille.txt
echo. >> log_veille.txt