"""Test complet : inscription -> auth -> génération PDF -> téléchargement"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000"

# ── Etape 1 : Inscription ────────────────────────────────────────────
print("=== ETAPE 1 : Inscription ===")
payload = json.dumps({
    "email": "admin@mitchobenin.org",
    "name": "Admin MITCHO",
    "password": "mitcho2026",
    "subscribe": True,
}).encode()

req = urllib.request.Request(
    BASE + "/auth/register",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    data = json.loads(r.read().decode())
    token = data["access_token"]
    name = data["user"]["name"]
    print(f"  OK — Bienvenue {name}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if e.code == 400:
        print("  Compte existant, connexion...")
        form = urllib.parse.urlencode({
            "username": "admin@mitchobenin.org",
            "password": "mitcho2026",
        }).encode()
        req2 = urllib.request.Request(
            BASE + "/auth/login",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        r2 = urllib.request.urlopen(req2, timeout=10)
        data = json.loads(r2.read().decode())
        token = data["access_token"]
        print(f"  OK — Connecte : {data['user']['name']}")
    else:
        print(f"  ERREUR {e.code}: {body}")
        raise

# ── Etape 2 : Vérifier le token ───────────────────────────────────────
print()
print("=== ETAPE 2 : Vérification /auth/me ===")
req = urllib.request.Request(
    BASE + "/auth/me",
    headers={"Authorization": f"Bearer {token}"},
)
r = urllib.request.urlopen(req, timeout=10)
me = json.loads(r.read().decode())
print(f"  OK — {me}")

# ── Etape 3 : Génération et téléchargement du rapport PDF ─────────────
print()
print("=== ETAPE 3 : Génération du rapport PDF ===")
print("  Appel GET /report/pdf/stream (30-90s selon connexion)...")
t0 = time.time()
req = urllib.request.Request(
    BASE + "/report/pdf/stream",
    headers={"Authorization": f"Bearer {token}"},
    method="GET",
)
try:
    r = urllib.request.urlopen(req, timeout=180)
    pdf_bytes = r.read()
    elapsed = round(time.time() - t0, 1)
    print(f"  OK — PDF reçu en {elapsed}s : {len(pdf_bytes):,} octets")

    output_path = "test_rapport_mitchou.pdf"
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"  Sauvegardé : {output_path}")

    # Vérification rapide (les PDFs commencent par %PDF)
    if pdf_bytes[:4] == b"%PDF":
        print("  Format PDF valide.")
    else:
        print("  ATTENTION — le fichier ne semble pas être un PDF valide")
        print(f"  Premiers octets : {pdf_bytes[:50]}")
except urllib.error.HTTPError as e:
    print(f"  ERREUR {e.code}: {e.read().decode()[:500]}")
    raise

print()
print("=" * 40)
print("SUCCÈS — Téléchargement PDF fonctionnel !")
print("=" * 40)
