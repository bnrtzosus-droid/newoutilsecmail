#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║         DÉTECTEUR DE COMPTES - v1.0                  ║
║   Retrouvez vos emails par numéro de téléphone       ║
╚══════════════════════════════════════════════════════╝
"""

import asyncio
import sys
import os

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERREUR: Playwright non installé.")
    print("Lancez d'abord: pip install playwright && playwright install chromium")
    sys.exit(1)

# ─── Couleurs terminal ────────────────────────────────
GRN  = '\033[92m'
RED  = '\033[91m'
YLW  = '\033[93m'
BLU  = '\033[94m'
CYN  = '\033[96m'
WHT  = '\033[97m'
GRY  = '\033[90m'
BLD  = '\033[1m'
RST  = '\033[0m'

# Windows: activer les couleurs ANSI
if sys.platform == 'win32':
    os.system('color')

# ─── Liste des services ───────────────────────────────
SERVICES = [
    {
        'id'      : 'facebook',
        'name'    : 'Facebook',
        'emoji'   : '👤',
        'url'     : 'https://www.facebook.com/login/identify/',
        'input'   : '#identify_email, input[name="email"]',
        'submit'  : '#did_submit, button[type="submit"]',
        'found'   : ['profile_picture', 'account', 'compte', '_5f0v', 'profil'],
        'notfound': ['no account found', 'aucun compte', 'not find', 'introuvable'],
        'mode'    : 'auto',
    },
    {
        'id'      : 'gmail',
        'name'    : 'Gmail / Google',
        'emoji'   : '📧',
        'url'     : 'https://accounts.google.com/signin/recovery',
        'input'   : 'input[type="email"], input[type="tel"]',
        'submit'  : '#identifierNext, button[type="submit"]',
        'found'   : ['recovery', 'phone', 'verify', 'code'],
        'notfound': ['couldn\'t find', 'not found', 'introuvable'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'instagram',
        'name'    : 'Instagram',
        'emoji'   : '📸',
        'url'     : 'https://www.instagram.com/accounts/password/reset/',
        'input'   : 'input[name="email"]',
        'submit'  : 'button[type="submit"]',
        'found'   : ['nous avons envoyé', 'we sent', 'check your', 'code'],
        'notfound': ['no users found', 'aucun utilisateur', 'not found'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'yahoo',
        'name'    : 'Yahoo Mail',
        'emoji'   : '📮',
        'url'     : 'https://login.yahoo.com/forgot',
        'input'   : '#username',
        'submit'  : '#login-signin, button[type="submit"]',
        'found'   : ['recovery', 'verify', 'code', 'phone'],
        'notfound': ['invalid', 'invalide', 'not exist', 'n\'existe pas'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'outlook',
        'name'    : 'Outlook / Microsoft',
        'emoji'   : '💼',
        'url'     : 'https://account.live.com/acsr',
        'input'   : '#ContactEmailAddress, input[type="email"]',
        'submit'  : '#idSIButton9, input[type="submit"]',
        'found'   : ['verification', 'code', 'phone', 'confirm'],
        'notfound': ['doesn\'t exist', 'n\'existe pas', 'not found'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'twitter',
        'name'    : 'X (Twitter)',
        'emoji'   : '🐦',
        'url'     : 'https://twitter.com/account/begin_password_reset',
        'input'   : 'input[name="account_identifier"]',
        'submit'  : 'div[data-testid="LoginForm_Login_Button"], button[type="submit"]',
        'found'   : ['phone', 'email', 'verify', 'code'],
        'notfound': ['couldn\'t find', 'not found', 'introuvable'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'snapchat',
        'name'    : 'Snapchat',
        'emoji'   : '👻',
        'url'     : 'https://accounts.snapchat.com/accounts/password_reset_request',
        'input'   : 'input[name="username"], input[type="email"]',
        'submit'  : 'button[type="submit"]',
        'found'   : ['email sent', 'envoyé', 'check', 'code'],
        'notfound': ['not found', 'introuvable', 'invalid'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'tiktok',
        'name'    : 'TikTok',
        'emoji'   : '🎵',
        'url'     : 'https://www.tiktok.com/login/phone-or-email/phone',
        'input'   : 'input[type="tel"]',
        'submit'  : 'button[type="submit"]',
        'found'   : ['verification', 'code', 'phone'],
        'notfound': ['not registered', 'pas enregistré', 'not found'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'apple',
        'name'    : 'Apple / iCloud',
        'emoji'   : '🍎',
        'url'     : 'https://iforgot.apple.com/',
        'input'   : '#account_name_text_field, input[type="email"]',
        'submit'  : '#sign-in, button[type="submit"]',
        'found'   : ['phone', 'verify', 'code', 'recovery'],
        'notfound': ['invalid', 'doesn\'t exist', 'not found'],
        'mode'    : 'assist',
    },
    {
        'id'      : 'linkedin',
        'name'    : 'LinkedIn',
        'emoji'   : '💼',
        'url'     : 'https://www.linkedin.com/uas/request-password-reset',
        'input'   : '#email-or-phone',
        'submit'  : 'button[type="submit"]',
        'found'   : ['email sent', 'envoyé', 'check', 'sent'],
        'notfound': ['not found', 'introuvable', 'doesn\'t match'],
        'mode'    : 'assist',
    },
]

results = {}

# ─── Affichage ────────────────────────────────────────
def banner():
    print(f"""
{CYN}{BLD}╔══════════════════════════════════════════════════╗
║        DÉTECTEUR DE COMPTES  v1.0                ║
║   Retrouvez vos emails par numéro de téléphone   ║
╚══════════════════════════════════════════════════╝{RST}
""")

def line():
    print(f"{GRY}{'─'*52}{RST}")

def status_icon(s):
    return {
        'found'   : f'{GRN}✓ TROUVÉ{RST}',
        'notfound': f'{RED}✗ Pas trouvé{RST}',
        'error'   : f'{YLW}⚠ Erreur{RST}',
        'skip'    : f'{GRY}– Ignoré{RST}',
        'manual'  : f'{YLW}? Vérification manuelle{RST}',
    }.get(s, f'{GRY}…{RST}')

# ─── Vérification automatique (Facebook) ─────────────
async def check_auto(page, svc, phone):
    """Tente une détection automatique."""
    try:
        await page.goto(svc['url'], timeout=20000, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        inp = await page.query_selector(svc['input'])
        if not inp:
            return 'manual'

        await inp.click()
        await inp.fill(phone)
        await asyncio.sleep(1)

        btn = await page.query_selector(svc['submit'])
        if btn:
            await btn.click()
            await asyncio.sleep(3)

        content = (await page.content()).lower()

        for kw in svc['notfound']:
            if kw.lower() in content:
                return 'notfound'

        for kw in svc['found']:
            if kw.lower() in content:
                return 'found'

        return 'manual'

    except PWTimeout:
        return 'manual'
    except Exception:
        return 'manual'

# ─── Mode assisté (ouvre la page, l'utilisateur confirme) ─
async def check_assist(page, svc, phone):
    """Ouvre la page et demande à l'utilisateur de confirmer."""
    try:
        await page.goto(svc['url'], timeout=20000, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        # Essayer de pré-remplir le numéro
        try:
            inp = await page.query_selector(svc['input'])
            if inp:
                await inp.click()
                await inp.fill(phone)
        except Exception:
            pass

        print(f"\n  {YLW}→ La page {svc['name']} est ouverte dans le navigateur.{RST}")
        print(f"  {WHT}Entrez votre numéro et vérifiez si un compte existe.{RST}")
        print(f"  Résultat → {GRN}[1] Trouvé{RST}  {RED}[2] Pas trouvé{RST}  {GRY}[3] Ignorer{RST}")

        while True:
            choix = input(f"  Votre choix: ").strip()
            if choix == '1': return 'found'
            if choix == '2': return 'notfound'
            if choix == '3': return 'skip'
            print(f"  {YLW}Entrez 1, 2 ou 3{RST}")

    except Exception as e:
        print(f"\n  {RED}Impossible d'ouvrir {svc['name']}: {e}{RST}")
        return 'error'

# ─── Vérification d'un service ────────────────────────
async def check_service(browser, svc, phone):
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    )
    page = await context.new_page()

    print(f"\n{BLD}{svc['emoji']}  {svc['name']}{RST}")

    if svc['mode'] == 'auto':
        print(f"  {GRY}Détection automatique…{RST}", end='', flush=True)
        result = await check_auto(page, svc, phone)
        print(f"\r  {status_icon(result)}              ")

        if result == 'manual':
            print(f"  {YLW}→ Vérification manuelle nécessaire…{RST}")
            result = await check_assist(page, svc, phone)
    else:
        result = await check_assist(page, svc, phone)

    await context.close()
    return result

# ─── Résumé final ─────────────────────────────────────
def show_summary(phone):
    found    = [s for s in SERVICES if results.get(s['id']) == 'found']
    notfound = [s for s in SERVICES if results.get(s['id']) == 'notfound']

    print(f"\n{CYN}{BLD}{'═'*52}{RST}")
    print(f"{BLD}  RÉSULTATS POUR: {YLW}{phone}{RST}")
    print(f"{CYN}{'═'*52}{RST}\n")

    if found:
        print(f"{GRN}{BLD}  ✓ COMPTES TROUVÉS ({len(found)}) :{RST}")
        for s in found:
            print(f"    {s['emoji']}  {BLD}{s['name']}{RST} {GRN}← email associé à ce numéro{RST}")
        print()

    if notfound:
        print(f"{RED}  ✗ Aucun compte ({len(notfound)}) :{RST}")
        for s in notfound:
            print(f"    {s['emoji']}  {GRY}{s['name']}{RST}")
        print()

    if not found:
        print(f"  {YLW}Aucun compte trouvé avec ce numéro.{RST}")
        print(f"  {GRY}Essayez avec un autre format de numéro (+XX, 00XX…){RST}")

    print(f"{GRY}{'─'*52}{RST}\n")

# ─── Point d'entrée ───────────────────────────────────
async def main():
    banner()

    # Formats du numéro
    phone_raw = input(f"{CYN}  Entrez votre numéro de téléphone : {RST}").strip()
    if not phone_raw:
        print(f"{RED}  Numéro requis.{RST}")
        return

    # Proposer les formats
    n = phone_raw.replace(' ','').replace('-','').replace('(','').replace(')','')
    formats = [n]
    if n.startswith('+'): formats += ['00'+n[1:], n[1:]]
    elif n.startswith('00'): formats += ['+'+n[2:], n[2:]]
    else: formats += ['+'+n, '00'+n]
    formats = list(dict.fromkeys(formats))

    print(f"\n  {GRY}Formats détectés : {', '.join(formats)}{RST}")
    print(f"  {YLW}Conseil : choisissez le format avec l'indicatif pays (+XXX){RST}\n")

    if len(formats) > 1:
        print(f"  Quel format utiliser ?")
        for i, f in enumerate(formats):
            print(f"    {BLD}[{i+1}]{RST} {f}")
        choix = input(f"  Votre choix (1-{len(formats)}) [défaut: 1]: ").strip()
        try:
            phone = formats[int(choix)-1] if choix else formats[0]
        except Exception:
            phone = formats[0]
    else:
        phone = formats[0]

    # Choisir les services à vérifier
    line()
    print(f"\n  {BLD}Services disponibles :{RST}")
    for i, s in enumerate(SERVICES):
        print(f"    {BLD}[{i+1:2}]{RST} {s['emoji']}  {s['name']}")
    print(f"    {BLD}[ 0]{RST} Vérifier TOUS les services\n")

    choix_svc = input(f"  Services à vérifier (ex: 0 pour tous, ou 1 3 5) : ").strip()

    if choix_svc == '0' or choix_svc == '':
        to_check = SERVICES
    else:
        indices = []
        for c in choix_svc.split():
            try:
                idx = int(c) - 1
                if 0 <= idx < len(SERVICES):
                    indices.append(idx)
            except ValueError:
                pass
        to_check = [SERVICES[i] for i in indices] if indices else SERVICES

    line()
    print(f"\n{BLD}  Démarrage de la vérification pour : {YLW}{phone}{RST}\n")
    print(f"  {GRY}Le navigateur va s'ouvrir — ne le fermez pas.{RST}\n")
    input(f"  {WHT}Appuyez sur ENTRÉE pour commencer…{RST}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )

        for svc in to_check:
            result = await check_service(browser, svc, phone)
            results[svc['id']] = result

        await browser.close()

    show_summary(phone)

    input(f"  {GRY}Appuyez sur ENTRÉE pour quitter…{RST}")

if __name__ == '__main__':
    asyncio.run(main())
