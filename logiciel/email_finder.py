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
                        bio = ""
                        try:
                            bio_el = page.query_selector("div._aa_c")
                            bio = bio_el.inner_text() if bio_el else ""
                        except Exception:
                            pass
                        emails, phones = extract_contact(bio)
                        if emails or phones:
                            for em in emails or [None]:
                                contact = {
                                    "username": username,
                                    "network": "instagram",
                                    "profile_url": f"https://www.instagram.com/{username}/",
                                    "country": country,
                                    "bio": bio[:500],
                                    "email": em,
                                    "phone": phones[0] if phones else None,
                                }
                                if save_contact(contact):
                                    found += 1
                                    print(f"  ✓ Instagram @{username} → {em or phones[0]}")
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
                    bio = ""
                    username = link.split("/@")[-1].split("?")[0]
                    try:
                        bio_el = page.query_selector("h2[data-e2e='user-bio']") or page.query_selector("span[data-e2e='user-bio']")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    emails, phones = extract_contact(bio)
                    if emails or phones:
                        for em in emails or [None]:
                            contact = {
                                "username": username,
                                "network": "tiktok",
                                "profile_url": link,
                                "country": country,
                                "bio": bio[:500],
                                "email": em,
                                "phone": phones[0] if phones else None,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ TikTok @{username} → {em or phones[0]}")
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
                    bio = ""
                    username = link.split("x.com/")[-1].split("/")[0]
                    try:
                        bio_el = page.query_selector("[data-testid='UserDescription']")
                        bio = bio_el.inner_text() if bio_el else ""
                        # also check website field
                        web_el = page.query_selector("[data-testid='UserUrl']")
                        bio += " " + (web_el.inner_text() if web_el else "")
                    except Exception:
                        pass
                    emails, phones = extract_contact(bio)
                    if emails or phones:
                        for em in emails or [None]:
                            contact = {
                                "username": username,
                                "network": "twitter",
                                "profile_url": link,
                                "country": country,
                                "bio": bio[:500],
                                "email": em,
                                "phone": phones[0] if phones else None,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ Twitter @{username} → {em or phones[0]}")
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
                    bio = ""
                    username = link.split("/in/")[-1].strip("/")
                    try:
                        bio_el = page.query_selector(".pv-about__summary-text") or page.query_selector(".text-body-medium")
                        bio = bio_el.inner_text() if bio_el else ""
                        # contact info section (sometimes visible without login)
                        ci = page.query_selector(".pv-contact-info__contact-type")
                        bio += " " + (ci.inner_text() if ci else "")
                    except Exception:
                        pass
                    emails, phones = extract_contact(bio)
                    if emails or phones:
                        for em in emails or [None]:
                            contact = {
                                "username": username,
                                "network": "linkedin",
                                "profile_url": link,
                                "country": country,
                                "bio": bio[:500],
                                "email": em,
                                "phone": phones[0] if phones else None,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ LinkedIn {username} → {em or phones[0]}")
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
                    bio = ""
                    username = link.split("/@")[-1] if "/@" in link else link.split("/channel/")[-1]
                    try:
                        bio_el = page.query_selector("#description-container") or page.query_selector("yt-formatted-string#description")
                        bio = bio_el.inner_text() if bio_el else ""
                        # links section often has contact email
                        links_el = page.query_selector_all("a.yt-simple-endpoint")
                        for lnk in links_el:
                            bio += " " + (lnk.get_attribute("href") or "")
                    except Exception:
                        pass
                    emails, phones = extract_contact(bio)
                    if emails or phones:
                        for em in emails or [None]:
                            contact = {
                                "username": username,
                                "network": "youtube",
                                "profile_url": link,
                                "country": country,
                                "bio": bio[:500],
                                "email": em,
                                "phone": phones[0] if phones else None,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ YouTube @{username} → {em or phones[0]}")
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
                    bio = ""
                    username = link.split("facebook.com/")[-1].split("?")[0]
                    try:
                        bio_el = page.query_selector("[data-key='about']") or page.query_selector("div[dir='auto']")
                        bio = bio_el.inner_text() if bio_el else ""
                    except Exception:
                        pass
                    # also try About page
                    try:
                        page.goto(link.rstrip("/") + "/about", timeout=10000)
                        pause(1, 2)
                        about_el = page.query_selector("div[data-pagelet='ProfileAppSection_0']")
                        bio += " " + (about_el.inner_text() if about_el else "")
                    except Exception:
                        pass
                    emails, phones = extract_contact(bio)
                    if emails or phones:
                        for em in emails or [None]:
                            contact = {
                                "username": username,
                                "network": "facebook",
                                "profile_url": link,
                                "country": country,
                                "bio": bio[:500],
                                "email": em,
                                "phone": phones[0] if phones else None,
                            }
                            if save_contact(contact):
                                found += 1
                                print(f"  ✓ Facebook {username} → {em or phones[0]}")
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


def main():
    parser = argparse.ArgumentParser(description="Email Finder — scrape public emails/phones from social media")
    parser.add_argument("--network", "-n", choices=list(SCRAPERS) + ["all"], default="all",
                        help="Network to scrape (default: all)")
    parser.add_argument("--country", "-c", default="france",
                        help=f"Country (default: france). Options: {', '.join(COUNTRY_TAGS)}")
    parser.add_argument("--niche", "-ni", default="business",
                        help=f"Niche (default: business). Options: {', '.join(NICHE_TAGS)}")
    parser.add_argument("--limit", "-l", type=int, default=20,
                        help="Max contacts per network (default: 20)")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run browser in headless mode")
    args = parser.parse_args()

    networks = list(SCRAPERS) if args.network == "all" else [args.network]
    country = args.country.lower()
    niche = args.niche.lower()

    print(f"\n{'='*60}")
    print(f"  Email Finder — WhatsApp Checker Pro")
    print(f"{'='*60}")
    print(f"  Pays    : {country}")
    print(f"  Niche   : {niche}")
    print(f"  Réseaux : {', '.join(networks)}")
    print(f"  Limite  : {args.limit} par réseau")
    print(f"{'='*60}\n")

    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
        )
        page = context.new_page()
        # hide webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            for net in networks:
                print(f"\n[{net.upper()}]")
                scraper = SCRAPERS[net]
                try:
                    n = scraper(page, country, niche, args.limit)
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
