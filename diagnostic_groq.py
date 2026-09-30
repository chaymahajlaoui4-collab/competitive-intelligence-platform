"""
Script de diagnostic : identifie précisément pourquoi la connexion à Groq échoue
depuis Python, alors que curl fonctionne.

USAGE :
    python diagnostic_groq.py
"""

import os
import sys
import traceback

print("=" * 60)
print("DIAGNOSTIC CONNEXION GROQ")
print("=" * 60)

# 1. Vérifie la clé API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY n'est pas définie dans cette session.")
    sys.exit(1)
print(f"✓ GROQ_API_KEY trouvée (commence par {GROQ_API_KEY[:10]}...)")

# 2. Vérifie s'il y a un proxy configuré (souvent la cause sur réseau d'entreprise/école)
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    val = os.environ.get(var)
    if val:
        print(f"⚠ Variable de proxy détectée : {var}={val}")
print()

# 3. Test avec 'requests' (souvent plus permissif que httpx utilisé par le SDK groq)
print("--- Test 1 : requests brut vers l'API Groq ---")
try:
    import requests
    r = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=15,
    )
    print(f"✓ requests a réussi ! Status: {r.status_code}")
except Exception as e:
    print(f"❌ requests a échoué : {type(e).__name__}: {e}")
    traceback.print_exc()

print()

# 4. Test avec le SDK groq officiel (celui utilisé par ton script principal)
print("--- Test 2 : SDK groq officiel (chat.completions) ---")
try:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "Réponds juste 'ok'"}],
        max_tokens=10,
    )
    print(f"✓ SDK groq a réussi ! Réponse : {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ SDK groq a échoué : {type(e).__name__}: {e}")
    print()
    print("Détail complet de l'erreur :")
    traceback.print_exc()

print()

# 5. Vérifie la version de openssl utilisée par Python (souvent la cause sur Windows)
print("--- Info système ---")
import ssl
print("Version Python :", sys.version)
print("Version OpenSSL utilisée par Python :", ssl.OPENSSL_VERSION)

print()
print("=" * 60)
print("Copie-colle TOUT ce qui s'affiche ci-dessus.")
print("=" * 60)
