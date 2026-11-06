#!/usr/bin/env python3
"""
Email Finder - Scrape public emails/phones from social media profiles
Networks: Instagram, TikTok, Twitter/X, LinkedIn, YouTube, Facebook
"""

import re
import json
import time
import random
import argparse
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright, Error as PWError

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://qbyxezgkmhikfqytiruj.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFieXhlemdrbWhpa2ZxeXRpcnVqIiwicm9sZSI6ImFub24i"
    "LCJpYXQiOjE3OTM4ODk5NzQsImV4cCI6MjEwOTQ2NTk3NH0"
    ".PUgo1DX8cW6fce3PUgaOCWP6kQRiuAYQUkI4SAsKMSs"
)

# ── Regex ─────────────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# European phone formats (FR, BE, CH, DE, UK, ES, IT, NL, PT, PL…)
PHONE_RE = re.compile(
    r"(?:\+|00)(?:33|32|41|49|44|34|39|31|351|48|43|45|46|47|358|353|352|356|357|420|421|386|385|381|40|359|371|370|372|36|30|90|7)"
    r"[\s.\-]?\d[\d\s.\-]{6,13}\d"
    r"|0[1-9](?:[\s.\-]?\d{2}){4}"  # local FR format
)

# ── Country → hashtags ────────────────────────────────────────────────────────
COUNTRY_TAGS = {
    "france":      ["france", "paris", "lyon", "marseille", "entreprise", "freelance"],
    "belgique":    ["belgique", "bruxelles", "liège", "anvers", "freelance"],
    "suisse":      ["suisse", "genève", "zurich", "lausanne", "freelance"],
    "allemagne":   ["deutschland", "berlin", "münchen", "hamburg", "freelancer"],
    "espagne":     ["españa", "madrid", "barcelona", "freelance"],
    "italie":      ["italia", "roma", "milano", "freelance"],
    "angleterre":  ["uk", "london", "manchester", "freelancer", "business"],
    "pays-bas":    ["nederland", "amsterdam", "rotterdam", "freelance"],
    "portugal":    ["portugal", "lisboa", "porto", "freelance"],
    "pologne":     ["polska", "warszawa", "kraków", "freelance"],
}

NICHE_TAGS = {
    "business":  ["ceo", "entrepreneur", "startup", "business", "coaching"],
    "marketing": ["marketing", "digitalmarketing", "seo", "socialmedia"],
    "tech":      ["developer", "programmer", "tech", "coding", "webdev"],
    "art":       ["art", "design", "photography", "creative"],
    "fitness":   ["fitness", "coach", "sport", "nutrition"],
}

# ── Supabase helper ───────────────────────────────────────────────────────────

def fetch_whatsapp_numbers() -> list[dict]:
    """Fetch all phone numbers from contacts_whatsapp table."""
    url = f"{SUPABASE_URL}/rest/v1/contacts_whatsapp?select=phone,pays&order=date_ajout.desc"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [!] Erreur lecture WhatsApp: {e}")
        return []


def save_contact(contact: dict) -> bool:
    """Insert a contact into contacts_email via Supabase REST."""
    url = f"{SUPABASE_URL}/rest/v1/contacts_email"
    data = json.dumps(contact).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "resolution=ignore-duplicates",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"  [!] Supabase error: {e}")
        return False


def extract_contact(text: str) -> tuple[list[str], list[str]]:
    """Return (emails, phones) found in text."""
    emails = list(set(EMAIL_RE.findall(text or "")))
    phones = list(set(PHONE_RE.findall(text or "")))
    return emails, phones


def detect_account_type(page, network: str) -> str:
    """Return 'entreprise', 'personnel', or 'inconnu'."""
    try:
        html = page.evaluate("() => document.documentElement.innerHTML") or ""
        text = (page.inner_text("body") or "").lower()

        if network == "instagram":
            # Business/creator indicators
            biz_keywords = ["compte professionnel", "professional account", "creator",
                            "créateur", "business", "boutique", "artiste", "musicien",
                            "marque personnelle", "coach", "entreprise"]
            if any(k in text for k in biz_keywords):
                return "entreprise"
            if '"is_business":true' in html or '"is_business": true' in html:
                return "entreprise"
            if '"is_professional_account":true' in html:
                return "entreprise"
            return "personnel"

        if network == "linkedin":
            # /company/ URL = business, /in/ = personal
            url = page.url
            if "/company/" in url or "/school/" in url:
                return "entreprise"
            return "personnel"

        if network == "facebook":
            url = page.url
            # Pages have /pages/ in URL or "Aimer" button
            if "/pages/" in url.lower():
                return "entreprise"
            if "j'aime cette page" in text or "aimer la page" in text or "like page" in text:
                return "entreprise"
            if '"page_type"' in html or '"category":' in html:
                return "entreprise"
            return "personnel"

        if network == "twitter":
            if "professional" in text or "entreprise" in text or "business" in text:
                return "entreprise"
            if '"professional_type"' in html:
                return "entreprise"
            return "personnel"

        if network == "tiktok":
            if "tiktok for business" in text or "business account" in text:
                return "entreprise"
            return "personnel"

        if network == "youtube":
            # Channels with many subscribers or brand accounts
            if "marque" in text or "entreprise" in text or "official" in text or "officiel" in text:
                return "entreprise"
            return "personnel"
    except Exception:
        pass
    return "inconnu"


def extract_full_name(page, network: str) -> str:
    """Try to extract the full name from a profile page."""
    selectors = {
        "instagram": ["h2._aacl", "h1", "span._ap3a._aaco._aacu._aacx._aad7._aade"],
        "tiktok":    ["h1[data-e2e='user-title']", "h2[data-e2e='user-subtitle']"],
        "twitter":   ["div[data-testid='UserName'] span", "[data-testid='UserName']"],
        "linkedin":  ["h1.text-heading-xlarge", "h1.top-card-layout__title"],
        "youtube":   ["#channel-name yt-formatted-string", "ytd-channel-name yt-formatted-string"],
        "facebook":  ["h1", "[data-key='profile-name']"],
    }
    for sel in selectors.get(network, ["h1"]):
        try:
            el = page.query_selector(sel)
            if el:
                name = el.inner_text().strip()
                if name and len(name) > 1:
                    return name
        except Exception:
            pass
    return ""


def get_all_contact_text(page) -> str:
    """
    Collect every piece of text that could contain emails/phones:
    - All visible text
    - All href attributes (mailto: and tel: links reveal contact directly)
    - All JSON script tags (social networks embed contact info in JSON)
    """
    parts = []
    try:
        # Visible text
        parts.append(page.inner_text("body") or "")
    except Exception:
        pass
    try:
        # mailto: and tel: links — direct gold
        hrefs = page.eval_on_selector_all(
            "a[href^='mailto:'], a[href^='tel:']",
            "els => els.map(e => e.href)"
        )
        for h in hrefs:
            # mailto:contact@example.com → extract cleanly
            parts.append(h.replace("mailto:", " ").replace("tel:", " "))
    except Exception:
        pass
    try:
        # JSON in <script> tags (Instagram, Facebook, LinkedIn embed data here)
        scripts = page.eval_on_selector_all(
            "script[type='application/ld+json'], script[type='application/json']",
            "els => els.map(e => e.textContent)"
        )
        for s in scripts:
            parts.append(s or "")
    except Exception:
        pass
    try:
        # Instagram / Facebook store data in window.__additionalData or similar
        raw = page.evaluate("() => document.documentElement.innerHTML")
        # pull out any JSON-looking email fields
        for match in re.finditer(r'"(?:email|business_email|contact_email|phone|business_phone_number|phone_number)"\s*:\s*"([^"]+)"', raw or ""):
            parts.append(match.group(1))
    except Exception:
        pass
    return " ".join(parts)


def pause(a=1.5, b=3.5):
    time.sleep(random.uniform(a, b))

# ── Instagram ─────────────────────────────────────────────────────────────────

def scrape_instagram(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            page.goto(f"https://www.instagram.com/explore/tags/{tag}/", timeout=20000)
            pause(2, 4)
            # collect post links
            links = page.eval_on_selector_all(
                "a[href*='/p/']",
                "els => [...new Set(els.map(e => e.href))]"
            )
            for link in links[:8]:
                if found >= limit:
                    break
                try:
                    page.goto(link, timeout=15000)
                    pause()
                    # get author username
                    username = ""
                    try:
                        username = page.query_selector("a.x1i10hfl[href^='/']").get_attribute("href").strip("/")
                    except Exception:
                        pass
                    # visit profile
                    if username:
                        page.goto(f"https://www.instagram.com/{username}/", timeout=15000)
                        pause()
                        # Try clicking "Contact" button (business accounts)
                        try:
                            contact_btn = page.query_selector("a[href^='mailto:'], a[href^='tel:'], button:has-text('Contact'), button:has-text('Email')")
                            if contact_btn:
                                contact_btn.click()
                                pause(0.5, 1)
                        except Exception:
                            pass
                        full_text = get_all_contact_text(page)
                        bio = ""
                        try:
                            bio_el = page.query_selector("div._aa_c") or page.query_selector("span._ap3a")
                            bio = bio_el.inner_text() if bio_el else ""
                        except Exception:
                            pass
                        emails, phones = extract_contact(full_text)
                        if emails or phones:
                            full_name    = extract_full_name(page, "instagram")
                            account_type = detect_account_type(page, "instagram")
                            for em in emails or [None]:
                                contact = {
                                    "username":     username,
                                    "full_name":    full_name or username,
                                    "network":      "instagram",
                                    "profile_url":  f"https://www.instagram.com/{username}/",
                                    "country":      country,
                                    "bio":          bio[:500],
                                    "email":        em,
                                    "phone":        phones[0] if phones else None,
                                    "account_type": account_type,
                                }
                                if save_contact(contact):
                                    found += 1
                                    label = full_name or username
                                    print(f"  ✓ Instagram {label} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] Instagram tag #{tag}: {e}")
    return found

# ── TikTok ────────────────────────────────────────────────────────────────────

def scrape_tiktok(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            page.goto(f"https://www.tiktok.com/tag/{tag}", timeout=20000)
            pause(2, 4)
            links = page.eval_on_selector_all(
                "a[href*='/@']",
                "els => [...new Set(els.map(e => e.href))]"
            )
            for link in links[:6]:
                if found >= limit:
                    break
                try:
                    page.goto(link, timeout=15000)
                    pause()
                    username = link.split("/@")[-1].split("?")[0]
                    bio = ""
                    try:
                        bio_el = page.query_selector("h2[data-e2e='user-bio']") or page.query_selector("span[data-e2e='user-bio']")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    full_text = get_all_contact_text(page)
                    emails, phones = extract_contact(full_text)
                    if emails or phones:
                        full_name    = extract_full_name(page, "tiktok")
                        account_type = detect_account_type(page, "tiktok")
                        for em in emails or [None]:
                            contact = {
                                "username": username, "full_name": full_name or username,
                                "network": "tiktok", "profile_url": link,
                                "country": country, "bio": bio[:500],
                                "email": em, "phone": phones[0] if phones else None,
                                "account_type": account_type,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ TikTok {full_name or username} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] TikTok tag #{tag}: {e}")
    return found

# ── Twitter/X ─────────────────────────────────────────────────────────────────

def scrape_twitter(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            query = urllib.parse.quote(f"#{tag} email OR contact")
            page.goto(f"https://x.com/search?q={query}&src=typed_query&f=user", timeout=20000)
            pause(2, 4)
            links = page.eval_on_selector_all(
                "a[href^='/']",
                "els => [...new Set(els.filter(e => /^\\/[a-zA-Z0-9_]+$/.test(e.getAttribute('href'))).map(e => 'https://x.com' + e.getAttribute('href')))]"
            )
            for link in links[:6]:
                if found >= limit:
                    break
                try:
                    page.goto(link, timeout=15000)
                    pause()
                    username = link.split("x.com/")[-1].split("/")[0]
                    bio = ""
                    try:
                        bio_el = page.query_selector("[data-testid='UserDescription']")
                        bio = bio_el.inner_text() if bio_el else ""
                        web_el = page.query_selector("[data-testid='UserUrl']")
                        bio += " " + (web_el.inner_text() if web_el else "")
                    except Exception:
                        pass
                    full_text = get_all_contact_text(page)
                    emails, phones = extract_contact(full_text)
                    if emails or phones:
                        full_name    = extract_full_name(page, "twitter")
                        account_type = detect_account_type(page, "twitter")
                        for em in emails or [None]:
                            contact = {
                                "username": username, "full_name": full_name or username,
                                "network": "twitter", "profile_url": link,
                                "country": country, "bio": bio[:500],
                                "email": em, "phone": phones[0] if phones else None,
                                "account_type": account_type,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ Twitter {full_name or username} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] Twitter tag #{tag}: {e}")
    return found

# ── LinkedIn ──────────────────────────────────────────────────────────────────

def scrape_linkedin(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            query = urllib.parse.quote(f"{tag} {niche}")
            page.goto(
                f"https://www.linkedin.com/search/results/people/?keywords={query}&origin=GLOBAL_SEARCH_HEADER",
                timeout=20000
            )
            pause(2, 4)
            links = page.eval_on_selector_all(
                "a.app-aware-link[href*='/in/']",
                "els => [...new Set(els.map(e => e.href.split('?')[0]))]"
            )
            for link in links[:6]:
                if found >= limit:
                    break
                try:
                    page.goto(link, timeout=15000)
                    pause()
                    username = link.split("/in/")[-1].strip("/")
                    bio = ""
                    try:
                        bio_el = page.query_selector(".pv-about__summary-text") or page.query_selector(".text-body-medium")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    # Try to open contact info panel
                    try:
                        ci_btn = page.query_selector("a[href*='contact-info'], a:has-text('Coordonnées'), a:has-text('Contact info')")
                        if ci_btn:
                            ci_btn.click()
                            pause(0.8, 1.5)
                    except Exception:
                        pass
                    full_text = get_all_contact_text(page)
                    emails, phones = extract_contact(full_text)
                    if emails or phones:
                        full_name    = extract_full_name(page, "linkedin")
                        account_type = detect_account_type(page, "linkedin")
                        for em in emails or [None]:
                            contact = {
                                "username": username, "full_name": full_name or username,
                                "network": "linkedin", "profile_url": link,
                                "country": country, "bio": bio[:500],
                                "email": em, "phone": phones[0] if phones else None,
                                "account_type": account_type,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ LinkedIn {full_name or username} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] LinkedIn keyword '{tag}': {e}")
    return found

# ── YouTube ───────────────────────────────────────────────────────────────────

def scrape_youtube(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            query = urllib.parse.quote(f"{tag} {niche}")
            page.goto(f"https://www.youtube.com/results?search_query={query}&sp=EgIQAg%3D%3D", timeout=20000)
            pause(2, 4)
            links = page.eval_on_selector_all(
                "a#channel-thumbnail",
                "els => [...new Set(els.map(e => 'https://www.youtube.com' + e.getAttribute('href')))]"
            )
            for link in links[:6]:
                if found >= limit:
                    break
                try:
                    page.goto(link + "/about", timeout=15000)
                    pause()
                    username = link.split("/@")[-1] if "/@" in link else link.split("/channel/")[-1]
                    bio = ""
                    try:
                        bio_el = page.query_selector("#description-container") or page.query_selector("yt-formatted-string#description")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    full_text = get_all_contact_text(page)
                    emails, phones = extract_contact(full_text)
                    if emails or phones:
                        full_name    = extract_full_name(page, "youtube")
                        account_type = detect_account_type(page, "youtube")
                        for em in emails or [None]:
                            contact = {
                                "username": username, "full_name": full_name or username,
                                "network": "youtube", "profile_url": link,
                                "country": country, "bio": bio[:500],
                                "email": em, "phone": phones[0] if phones else None,
                                "account_type": account_type,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ YouTube {full_name or username} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] YouTube query '{tag}': {e}")
    return found

# ── Facebook ──────────────────────────────────────────────────────────────────

def scrape_facebook(page, country: str, niche: str, limit: int) -> int:
    tags = COUNTRY_TAGS.get(country, [country]) + NICHE_TAGS.get(niche, [])
    found = 0
    for tag in tags:
        if found >= limit:
            break
        try:
            query = urllib.parse.quote(f"{tag} {niche}")
            page.goto(f"https://www.facebook.com/public/{query}", timeout=20000)
            pause(2, 4)
            links = page.eval_on_selector_all(
                "a[href*='facebook.com/']",
                "els => [...new Set(els.map(e => e.href).filter(h => /facebook\\.com\\/(?!public|search)[a-zA-Z0-9.]+/.test(h)))]"
            )
            for link in links[:6]:
                if found >= limit:
                    break
                try:
                    page.goto(link, timeout=15000)
                    pause()
                    username = link.split("facebook.com/")[-1].split("?")[0]
                    bio = ""
                    # Visit About/contact page directly
                    try:
                        page.goto(link.rstrip("/") + "/about_contact_and_basic_info", timeout=12000)
                        pause(1, 2)
                    except Exception:
                        try:
                            page.goto(link.rstrip("/") + "/about", timeout=10000)
                            pause(1, 2)
                        except Exception:
                            pass
                    try:
                        bio_el = page.query_selector("div[data-pagelet='ProfileAppSection_0']") or page.query_selector("div[dir='auto']")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    full_text = get_all_contact_text(page)
                    emails, phones = extract_contact(full_text)
                    if emails or phones:
                        full_name    = extract_full_name(page, "facebook")
                        account_type = detect_account_type(page, "facebook")
                        for em in emails or [None]:
                            contact = {
                                "username": username, "full_name": full_name or username,
                                "network": "facebook", "profile_url": link,
                                "country": country, "bio": bio[:500],
                                "email": em, "phone": phones[0] if phones else None,
                                "account_type": account_type,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ Facebook {full_name or username} [{account_type}] → {em or phones[0]}")
                except Exception:
                    pass
        except (PWError, KeyboardInterrupt):
            raise
        except Exception as e:
            print(f"  [!] Facebook query '{tag}': {e}")
    return found

# ── Main ──────────────────────────────────────────────────────────────────────

SCRAPERS = {
    "instagram": scrape_instagram,
    "tiktok":    scrape_tiktok,
    "twitter":   scrape_twitter,
    "linkedin":  scrape_linkedin,
    "youtube":   scrape_youtube,
    "facebook":  scrape_facebook,
}

# ── Recherche par nom / numéro ────────────────────────────────────────────────

SITE_QUERIES = {
    "instagram": "site:instagram.com",
    "tiktok":    "site:tiktok.com",
    "twitter":   "site:x.com OR site:twitter.com",
    "linkedin":  "site:linkedin.com/in",
    "youtube":   "site:youtube.com",
    "facebook":  "site:facebook.com",
}


def google_search_profiles(page, query: str, network: str) -> list[str]:
    """Search Google for a query on a specific network, return profile URLs."""
    site = SITE_QUERIES.get(network, "")
    q = urllib.parse.quote(f'"{query}" {site}')
    try:
        page.goto(f"https://www.google.com/search?q={q}&num=10", timeout=20000)
        pause(1.5, 3)
        # Accept cookies if needed
        try:
            btn = page.query_selector("button:has-text('Tout accepter'), button:has-text('Accept all')")
            if btn:
                btn.click()
                pause(0.5, 1)
        except Exception:
            pass
        links = page.eval_on_selector_all(
            "a[href]",
            """els => [...new Set(
              els.map(e => e.href)
                 .filter(h => h.includes('instagram.com/') || h.includes('tiktok.com/@') ||
                              h.includes('x.com/') || h.includes('twitter.com/') ||
                              h.includes('linkedin.com/in/') || h.includes('youtube.com/') ||
                              h.includes('facebook.com/'))
            )]"""
        )
        # Filter out generic pages
        skip = ["login", "signup", "help", "about", "policies", "terms", "search", "hashtag", "explore"]
        return [l for l in links if not any(s in l.lower() for s in skip)][:8]
    except Exception as e:
        print(f"  [!] Google search error: {e}")
        return []


def scrape_profile_url(page, url: str, network: str, query: str, country: str) -> dict | None:
    """Visit a profile URL and extract contact info."""
    try:
        page.goto(url, timeout=18000)
        pause(1.5, 3)
        # LinkedIn: try contact info panel
        if network == "linkedin":
            try:
                ci_btn = page.query_selector("a[href*='contact-info'], a:has-text('Coordonnées')")
                if ci_btn:
                    ci_btn.click()
                    pause(0.8, 1.5)
            except Exception:
                pass
        # Instagram: try contact button
        if network == "instagram":
            try:
                cb = page.query_selector("a[href^='mailto:'], a[href^='tel:']")
                if cb:
                    cb.click()
                    pause(0.5, 1)
            except Exception:
                pass
        # Facebook: go to about page
        if network == "facebook":
            try:
                page.goto(url.rstrip("/") + "/about_contact_and_basic_info", timeout=10000)
                pause(1, 2)
            except Exception:
                pass
        full_text = get_all_contact_text(page)
        emails, phones = extract_contact(full_text)
        if not emails and not phones:
            return None
        username     = url.rstrip("/").split("/")[-1].split("?")[0]
        full_name    = extract_full_name(page, network)
        account_type = detect_account_type(page, network)
        return {
            "username":     username,
            "full_name":    full_name or username,
            "network":      network,
            "profile_url":  url,
            "country":      country,
            "bio":          query,
            "email":        emails[0] if emails else None,
            "phone":        phones[0] if phones else None,
            "account_type": account_type,
        }
    except Exception:
        return None


def search_by_query(page, query: str, networks: list, country: str) -> int:
    """Search all networks for a name or phone number."""
    total = 0
    for net in networks:
        print(f"\n  [{net.upper()}] Recherche : {query}")
        profile_urls = google_search_profiles(page, query, net)
        if not profile_urls:
            print(f"  → Aucun profil trouvé sur Google")
            continue
        for url in profile_urls:
            contact = scrape_profile_url(page, url, net, query, country)
            if contact:
                if save_contact(contact):
                    total += 1
                    info = contact.get("email") or contact.get("phone") or "trouvé"
                    print(f"  ✓ {net} @{contact['username']} → {info}")
            pause(1, 2)
    return total


def ask(prompt: str, options: list[str] | None = None, default: str = "") -> str:
    """Ask a question in the terminal and return the answer."""
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            try:
                raw = input(f"\n  Votre choix (1-{len(options)}) : ").strip()
            except (EOFError, KeyboardInterrupt):
                raise KeyboardInterrupt
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            print(f"  → Entrez un numéro entre 1 et {len(options)}")
    else:
        try:
            raw = input(f"  {prompt} [{default}] : ").strip()
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt
        return raw if raw else default


def interactive_menu() -> dict:
    """Display interactive menu and return configuration dict."""
    SEP = "=" * 60
    print(f"\n{SEP}")
    print(f"  Email Finder — WhatsApp Checker Pro")
    print(f"{SEP}\n")

    print("  Quelle méthode de recherche souhaitez-vous utiliser ?\n")
    MODE_OPTS = [
        "Recherche par pays + niche  (parcourir les hashtags)",
        "Recherche par nom / prénom  (trouver une personne)",
        "Recherche par numéro        (trouver le profil d'un numéro)",
        "Depuis mes numéros WhatsApp (chercher tous les profils)",
    ]
    mode_label = ask("Mode", MODE_OPTS)
    mode = ["hashtag", "name", "phone", "whatsapp"][MODE_OPTS.index(mode_label)]

    # ── Réseaux ──
    print(f"\n  Sur quels réseaux sociaux ?\n")
    NET_OPTS = ["Tous les réseaux"] + [n.capitalize() for n in SCRAPERS]
    net_label = ask("Réseau", NET_OPTS)
    if net_label == "Tous les réseaux":
        networks = list(SCRAPERS)
    else:
        networks = [net_label.lower()]

    cfg = {"mode": mode, "networks": networks, "headless": False, "skip": 0}

    # ── Mode spécifique ──
    if mode == "hashtag":
        print(f"\n  Pays cible ?\n")
        pays_opts = [p.capitalize() for p in COUNTRY_TAGS]
        cfg["country"] = ask("Pays", pays_opts).lower()

        print(f"\n  Niche / secteur ?\n")
        niche_opts = [n.capitalize() for n in NICHE_TAGS]
        cfg["niche"] = ask("Niche", niche_opts).lower()

        print(f"\n  Nombre maximum de contacts par réseau ?\n")
        LIMIT_OPTS = ["10", "20", "50", "100"]
        cfg["limit"] = int(ask("Limite", LIMIT_OPTS))

    elif mode == "name":
        print(f"\n  Entrez le nom et prénom à rechercher :")
        cfg["query"] = ask("Nom prénom", default="")
        if not cfg["query"]:
            print("  [!] Nom vide, annulation.")
            raise SystemExit(0)
        cfg["country"] = "france"

    elif mode == "phone":
        print(f"\n  Entrez le numéro de téléphone (avec indicatif, ex: +33612345678) :")
        cfg["query"] = ask("Numéro", default="")
        if not cfg["query"]:
            print("  [!] Numéro vide, annulation.")
            raise SystemExit(0)
        cfg["country"] = "france"

    elif mode == "whatsapp":
        numbers = fetch_whatsapp_numbers()
        total_nb = len(numbers)
        if total_nb == 0:
            print("\n  [!] Aucun numéro dans contacts_whatsapp.")
            raise SystemExit(0)
        print(f"\n  {total_nb} numéro(s) disponible(s) dans la base.")
        print(f"\n  Reprendre depuis le début ou depuis un numéro précis ?\n")
        SKIP_OPTS = ["Depuis le début", "Choisir à partir de quel numéro"]
        skip_label = ask("Reprise", SKIP_OPTS)
        if skip_label == SKIP_OPTS[1]:
            raw_skip = ask(f"Ignorer les N premiers (0-{total_nb})", default="0")
            cfg["skip"] = int(raw_skip) if raw_skip.isdigit() else 0
        else:
            cfg["skip"] = 0
        cfg["country"] = "france"

    # ── Mode fenêtre ──
    print(f"\n  Mode navigateur ?\n")
    NAV_OPTS = ["Visible (recommandé pour les connexions)", "Silencieux (sans fenêtre)"]
    nav_label = ask("Navigateur", NAV_OPTS)
    cfg["headless"] = (nav_label == NAV_OPTS[1])

    # ── Résumé ──
    print(f"\n{SEP}")
    print(f"  RÉCAPITULATIF")
    print(f"{SEP}")
    print(f"  Mode     : {mode_label}")
    print(f"  Réseaux  : {', '.join(cfg['networks'])}")
    if mode == "hashtag":
        print(f"  Pays     : {cfg['country']}")
        print(f"  Niche    : {cfg['niche']}")
        print(f"  Limite   : {cfg['limit']} par réseau")
    elif mode in ("name", "phone"):
        print(f"  Requête  : {cfg['query']}")
    elif mode == "whatsapp":
        print(f"  Skip     : {cfg.get('skip', 0)}")
    print(f"  Fenêtre  : {'Non (silencieux)' if cfg['headless'] else 'Oui (visible)'}")
    print(f"{SEP}\n")

    print("  Appuyez sur Entrée pour démarrer (Ctrl+C pour annuler) ...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(0)

    return cfg


def main():
    parser = argparse.ArgumentParser(description="Email Finder — scrape public emails/phones from social media", add_help=True)
    parser.add_argument("--network", "-n", choices=list(SCRAPERS) + ["all"], default=None)
    parser.add_argument("--country", "-c", default=None)
    parser.add_argument("--niche", "-ni", default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--search", "-s", type=str, default=None)
    parser.add_argument("--from-whatsapp", action="store_true", default=False)
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()

    # Si aucun argument passé → menu interactif
    no_args = (args.network is None and args.country is None and args.niche is None
               and args.limit is None and not args.search and not args.from_whatsapp)

    if no_args:
        cfg = interactive_menu()
        mode      = cfg["mode"]
        networks  = cfg["networks"]
        country   = cfg.get("country", "france")
        niche     = cfg.get("niche", "business")
        limit     = cfg.get("limit", 20)
        headless  = cfg.get("headless", False)
        query     = cfg.get("query", "")
        skip      = cfg.get("skip", 0)
    else:
        # Mode ligne de commande (comme avant)
        networks = list(SCRAPERS) if (args.network is None or args.network == "all") else [args.network]
        country  = (args.country or "france").lower()
        niche    = (args.niche or "business").lower()
        limit    = args.limit or 20
        headless = args.headless
        query    = args.search or ""
        skip     = args.skip
        if args.from_whatsapp:
            mode = "whatsapp"
        elif args.search:
            mode = "name"
        else:
            mode = "hashtag"

    print(f"\n{'='*60}")
    print(f"  Email Finder — WhatsApp Checker Pro")
    print(f"{'='*60}\n")

    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # ── Mode numéros WhatsApp ──
            if mode == "whatsapp":
                numbers = fetch_whatsapp_numbers()
                if not numbers:
                    print("  [!] Aucun numéro dans contacts_whatsapp.")
                else:
                    numbers = numbers[skip:]
                    print(f"  {len(numbers)} numéro(s) à traiter...\n")
                    for i, row in enumerate(numbers):
                        phone = row.get("phone", "")
                        pays  = row.get("pays", country)
                        if not phone:
                            continue
                        print(f"\n  [{i+1}/{len(numbers)}] {phone} ({pays})")
                        try:
                            n = search_by_query(page, phone, networks, pays or country)
                            total += n
                        except KeyboardInterrupt:
                            print(f"\n  [!] Arrêt — reprendre avec --skip {skip + i}")
                            break

            # ── Mode recherche par nom / numéro ──
            elif mode in ("name", "phone"):
                total = search_by_query(page, query, networks, country)

            # ── Mode hashtag par pays ──
            else:
                for net in networks:
                    print(f"\n[{net.upper()}]")
                    scraper = SCRAPERS[net]
                    try:
                        n = scraper(page, country, niche, limit)
                        total += n
                        print(f"  → {n} contact(s) trouvé(s)")
                    except KeyboardInterrupt:
                        print("\n[!] Arrêt demandé par l'utilisateur.")
                        break
                    except Exception as e:
                        print(f"  [!] Erreur {net}: {e}")
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

    print(f"\n{'='*60}")
    print(f"  TOTAL : {total} contact(s) enregistré(s) dans Supabase")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
