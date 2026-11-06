#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Checker Pro - Détection automatique via WhatsApp Web
Connexion unique par QR code, vérification automatique de chaque numéro.
"""

import os, sys, csv, time, re, json
try:
    import urllib.request, urllib.error
    HAS_HTTP = True
except ImportError:
    HAS_HTTP = False
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://qbyxezgkmhikfqytiruj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFieXhlemdrbWhpa2ZxeXRpcnVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM4ODk5NzQsImV4cCI6MjEwOTQ2NTk3NH0.PUgo1DX8cW6fce3PUgaOCWP6kQRiuAYQUkI4SAsKMSs"

def supabase_insert(phone, pays):
    """Envoie un contact confirmé sur WhatsApp vers Supabase."""
    if not HAS_HTTP:
        return False
    try:
        data = json.dumps({"phone": phone, "pays": pays}).encode('utf-8')
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/contacts_whatsapp",
            data=data,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=ignore-duplicates"
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False

# ── Couleurs terminal ─────────────────────────────────────────────────────────
GRN = "\033[92m"; RED = "\033[91m"; YLW = "\033[93m"
BLU = "\033[94m"; CYN = "\033[96m"; GRY = "\033[90m"
BLD = "\033[1m";  RST = "\033[0m"

def ok(msg):   print(f"  {GRN}✓{RST} {msg}")
def err(msg):  print(f"  {RED}✗{RST} {msg}")
def inf(msg):  print(f"  {BLU}→{RST} {msg}")
def warn(msg): print(f"  {YLW}!{RST} {msg}")

# ── Détection pays ────────────────────────────────────────────────────────────
PAYS = [
    ('+243','Congo RDC 🇨🇩'),('+242','Congo Brazza 🇨🇬'),('+225','Côte d\'Ivoire 🇨🇮'),
    ('+221','Sénégal 🇸🇳'),('+229','Bénin 🇧🇯'),('+228','Togo 🇹🇬'),('+223','Mali 🇲🇱'),
    ('+226','Burkina Faso 🇧🇫'),('+227','Niger 🇳🇪'),('+237','Cameroun 🇨🇲'),
    ('+241','Gabon 🇬🇦'),('+236','RCA 🇨🇫'),('+235','Tchad 🇹🇩'),
    ('+234','Nigeria 🇳🇬'),('+233','Ghana 🇬🇭'),('+254','Kenya 🇰🇪'),
    ('+255','Tanzanie 🇹🇿'),('+256','Ouganda 🇺🇬'),('+27','Afrique du Sud 🇿🇦'),
    ('+212','Maroc 🇲🇦'),('+213','Algérie 🇩🇿'),('+216','Tunisie 🇹🇳'),
    ('+33','France 🇫🇷'),('+32','Belgique 🇧🇪'),('+41','Suisse 🇨🇭'),
    ('+44','Royaume-Uni 🇬🇧'),('+49','Allemagne 🇩🇪'),('+55','Brésil 🇧🇷'),
    ('+91','Inde 🇮🇳'),('+1','USA/Canada 🇺🇸'),
    ('+46','Suède 🇸🇪'),('+47','Norvège 🇳🇴'),('+45','Danemark 🇩🇰'),
    ('+358','Finlande 🇫🇮'),('+31','Pays-Bas 🇳🇱'),('+34','Espagne 🇪🇸'),
    ('+39','Italie 🇮🇹'),('+7','Russie 🇷🇺'),('+86','Chine 🇨🇳'),
    ('+81','Japon 🇯🇵'),('+82','Corée du Sud 🇰🇷'),
]

def detecter_pays(phone):
    n = re.sub(r'[\s\-\(\)\.]', '', phone)
    if not n.startswith('+'): n = '+' + n
    for code, nom in sorted(PAYS, key=lambda x: -len(x[0])):
        if n.startswith(code):
            return nom
    return 'Inconnu 🌍'

def normaliser(phone):
    n = re.sub(r'[\s\-\(\)\.]', '', phone.strip())
    if not n.startswith('+') and len(n) > 6: n = '+' + n
    return n

# ── Connexion WhatsApp Web ────────────────────────────────────────────────────
SESSION_DIR = os.path.join(os.path.dirname(__file__), '.wa_session')

def connecter_whatsapp(playwright):
    """Ouvre WhatsApp Web. Si déjà connecté (session sauvegardée), passe direct."""
    print(f"\n{BLD}{CYN}Connexion à WhatsApp Web...{RST}")
    browser = playwright.chromium.launch_persistent_context(
        SESSION_DIR,
        headless=False,
        args=['--no-sandbox', '--disable-dev-shm-usage'],
        viewport={'width': 1100, 'height': 750},
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto('https://web.whatsapp.com', timeout=60000)

    # Attendre: soit le QR code (première connexion), soit la page d'accueil (déjà connecté)
    try:
        page.wait_for_selector('[data-testid="qrcode"], [data-testid="default-user"], canvas[aria-label="Scan this QR code"]', timeout=20000)
    except PWTimeout:
        pass

    # Si QR affiché → attendre que l'utilisateur scanne (jusqu'à 3 min)
    if page.query_selector('[data-testid="qrcode"], canvas[aria-label="Scan this QR code"]'):
        print(f"\n  {YLW}📱 SCANNEZ LE QR CODE avec votre téléphone WhatsApp{RST}")
        print(f"  {GRY}(WhatsApp → Appareils connectés → Connecter un appareil){RST}\n")
        try:
            # Attendre que le QR disparaisse = connexion réussie
            page.wait_for_selector('[data-testid="default-user"], [title="WhatsApp"]', timeout=180000)
        except PWTimeout:
            err("Timeout — QR code non scanné.")
            browser.close()
            sys.exit(1)

    # Attendre chargement complet
    try:
        page.wait_for_selector('[data-testid="chat-list"], [data-testid="default-user"]', timeout=30000)
    except PWTimeout:
        pass

    ok("Connecté à WhatsApp Web !")
    return browser, page

# ── Vérification d'un numéro ──────────────────────────────────────────────────
def verifier_numero(page, phone):
    """
    Retourne True si le numéro est sur WhatsApp, False sinon.
    Méthode: ouvrir https://web.whatsapp.com/send?phone=NUMERO
    - Numéro valide  → boîte de composition apparaît
    - Numéro invalide → popup / dialog d'erreur apparaît
    """
    num_propre = phone.replace('+', '').replace(' ', '')
    url = f'https://web.whatsapp.com/send?phone={num_propre}'

    try:
        page.goto(url, timeout=30000, wait_until='domcontentloaded')

        # Étape 1 : attendre la boîte de saisie (succès)
        try:
            page.wait_for_selector(
                'div[contenteditable="true"][data-tab="10"], '
                'div[contenteditable="true"][data-tab="1"], '
                'footer div[contenteditable="true"], '
                'div[role="textbox"][contenteditable="true"]',
                timeout=12000
            )
            return True  # Boîte trouvée = numéro sur WhatsApp
        except PWTimeout:
            pass

        # Étape 2 : vérifier si un dialog d'erreur est apparu
        try:
            page.wait_for_selector(
                'div[data-animate-modal-popup="true"], '
                'div[role="dialog"], '
                'div[data-testid="popup-contents"]',
                timeout=5000
            )
            return False  # Dialog = numéro invalide / pas sur WhatsApp
        except PWTimeout:
            pass

        # Étape 3 : analyser le texte de la page comme dernier recours
        try:
            texte = page.inner_text('body').lower()
            mots_erreur = [
                'phone number shared via url is invalid',
                'invalid phone',
                'numéro invalide',
                "n'existe pas",
                'not found',
            ]
            for mot in mots_erreur:
                if mot in texte:
                    return False
            # Si la page contient une zone de saisie visible
            if page.query_selector('div[contenteditable="true"]'):
                return True
        except Exception:
            pass

        return None  # Vraiment indéterminé

    except PWTimeout:
        return None
    except Exception:
        return None

# ── Génération numéros séquentiels ────────────────────────────────────────────
def generer_numeros(base, quantite):
    """Génère une séquence de numéros à partir d'un numéro de base."""
    base = normaliser(base)
    # On fait varier les 4 derniers chiffres
    prefixe = base[:-4]
    debut = int(base[-4:])
    nums = []
    for i in range(quantite):
        num = prefixe + str((debut + i) % 10000).zfill(4)
        nums.append(num)
    return nums

# ── Lire fichier de numéros ───────────────────────────────────────────────────
def lire_fichier(chemin):
    nums = []
    with open(chemin, 'r', encoding='utf-8') as f:
        for ligne in f:
            n = normaliser(ligne)
            if len(n) > 6:
                nums.append(n)
    return nums

# ── Exporter CSV ──────────────────────────────────────────────────────────────
def exporter_csv(resultats, chemin='resultats_whatsapp.csv'):
    with open(chemin, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Numéro', 'Pays', 'Sur WhatsApp', 'Lien WhatsApp'])
        for r in resultats:
            statut = 'OUI' if r['wa'] is True else ('NON' if r['wa'] is False else 'INDÉTERMINÉ')
            lien = f"https://wa.me/{r['phone'].replace('+','')}" if r['wa'] else ''
            w.writerow([r['phone'], r['pays'], statut, lien])
    return chemin

# ── Affichage résultats ───────────────────────────────────────────────────────
def afficher_bilan(resultats):
    oui  = [r for r in resultats if r['wa'] is True]
    non  = [r for r in resultats if r['wa'] is False]
    ind  = [r for r in resultats if r['wa'] is None]

    print(f"\n{'─'*54}")
    print(f"{BLD}  BILAN FINAL{RST}")
    print(f"{'─'*54}")
    print(f"  Total vérifié  : {BLD}{len(resultats)}{RST}")
    print(f"  Sur WhatsApp   : {GRN}{BLD}{len(oui)}{RST}")
    print(f"  Pas sur WA     : {RED}{len(non)}{RST}")
    print(f"  Indéterminé    : {GRY}{len(ind)}{RST}")

    if oui:
        print(f"\n{GRN}{BLD}  Numéros actifs sur WhatsApp :{RST}")
        for r in oui:
            print(f"    {GRN}✓{RST}  {r['phone']}  {GRY}({r['pays']}){RST}")
    print(f"{'─'*54}")

# ── MENU PRINCIPAL ────────────────────────────────────────────────────────────
def main():
    os.system('cls' if os.name=='nt' else 'clear')
    print(f"""
{GRN}{BLD}╔══════════════════════════════════════════════╗
║       WhatsApp Checker Pro  v2.0             ║
║   Détection automatique via WhatsApp Web     ║
╚══════════════════════════════════════════════╝{RST}
""")

    print(f"{BLD}Mode de saisie des numéros :{RST}")
    print(f"  {CYN}1{RST} — Entrer les numéros manuellement")
    print(f"  {CYN}2{RST} — Scan automatique (numéros séquentiels)")
    print(f"  {CYN}3{RST} — Importer depuis un fichier (.txt / .csv)")

    choix = input(f"\n{BLD}Votre choix (1/2/3) : {RST}").strip()

    phones = []

    if choix == '1':
        print(f"\n{GRY}Entrez les numéros (un par ligne). Ligne vide pour terminer.{RST}")
        while True:
            n = input("  Numéro : ").strip()
            if not n: break
            phones.append(normaliser(n))

    elif choix == '2':
        base = input(f"\n  Numéro de départ (ex: +243812345000) : ").strip()
        qte  = input(f"  Combien de numéros à scanner ? (ex: 100) : ").strip()
        try:
            phones = generer_numeros(base, int(qte))
            inf(f"{len(phones)} numéros générés depuis {base}")
        except Exception as e:
            err(f"Erreur : {e}"); sys.exit(1)

    elif choix == '3':
        chemin = input(f"\n  Chemin du fichier : ").strip().strip('"')
        if not os.path.exists(chemin):
            err("Fichier introuvable."); sys.exit(1)
        phones = lire_fichier(chemin)
        inf(f"{len(phones)} numéros importés")

    else:
        err("Choix invalide."); sys.exit(1)

    if not phones:
        err("Aucun numéro à vérifier."); sys.exit(1)

    # Afficher les numéros et pays détectés
    print(f"\n{BLD}Numéros à vérifier :{RST}")
    for p in phones[:10]:
        pays = detecter_pays(p)
        print(f"  {GRY}→{RST} {p}  {GRY}({pays}){RST}")
    if len(phones) > 10:
        print(f"  {GRY}... et {len(phones)-10} autres{RST}")

    input(f"\n{YLW}Appuyez sur Entrée pour démarrer...{RST}")

    # Lancer Playwright + WhatsApp Web
    resultats = []
    with sync_playwright() as pw:
        browser, page = connecter_whatsapp(pw)

        print(f"\n{BLD}Vérification en cours...{RST}\n")
        for idx, phone in enumerate(phones, 1):
            pays = detecter_pays(phone)
            print(f"  [{idx:>3}/{len(phones)}] {phone}  {GRY}{pays}{RST}", end='  ', flush=True)

            wa = verifier_numero(page, phone)

            if wa is True:
                print(f"{GRN}✓ Sur WhatsApp{RST}", end='')
                if supabase_insert(phone, pays):
                    print(f"  {CYN}↑ Supabase{RST}")
                else:
                    print()
            elif wa is False:
                print(f"{RED}✗ Pas sur WhatsApp{RST}")
            else:
                print(f"{GRY}? Indéterminé{RST}")

            resultats.append({'phone': phone, 'pays': pays, 'wa': wa})

            # Petite pause entre chaque numéro
            time.sleep(0.8)

        browser.close()

    # Bilan
    afficher_bilan(resultats)

    # Export CSV
    sauver = input(f"\n{BLD}Exporter les résultats en CSV ? (o/n) : {RST}").strip().lower()
    if sauver in ('o', 'oui', 'y', 'yes'):
        fichier = exporter_csv(resultats)
        ok(f"Résultats sauvegardés : {fichier}")

    print(f"\n{GRY}À bientôt !{RST}\n")

if __name__ == '__main__':
    main()
