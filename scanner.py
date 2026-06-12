#!/usr/bin/env python3
"""
Canadian Car Scanner
Scans 20+ Canadian sources for used Ferrari F12 and Porsche 911 GT3 Touring Manual
listings, verifies they're live, and emails the results.
"""

import os
import re
import json
import smtplib
import ssl
import urllib3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import requests
import cloudscraper

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL_TO = "jeffrey.dyck@gmail.com"
EMAIL_FROM = "jeffrey.dyck@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
}

SESSION = cloudscraper.create_scraper()

# Plain requests session (used as fallback for SSL cert issues)
RAW_SESSION = requests.Session()
RAW_SESSION.verify = False
RAW_SESSION.headers.update(HEADERS)


def http_get(url, **kwargs):
    """Fetch a URL — try cloudscraper first, fallback to verify=False on SSL errors,
    and retry with requests on 403/406 status codes."""
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 20)
    try:
        r = SESSION.get(url, **kwargs)
        if r.status_code in (403, 406):
            kwargs.pop("headers", None)
            return RAW_SESSION.get(url, **kwargs)
        return r
    except Exception:
        kwargs.pop("headers", None)
        return RAW_SESSION.get(url, **kwargs)


def fetch_autotrader(url, label):
    """Fetch F12 listings from AutoTrader.ca or AutoHebdo.net via Next.js data."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text, re.DOTALL,
        )
        if not m:
            return [], "No __NEXT_DATA__ found"

        data = json.loads(m.group(1))
        listings = data.get("props", {}).get("pageProps", {}).get("listings", [])
        results = []
        for lst in listings:
            veh = lst.get("vehicle", {})
            loc = lst.get("location", {})
            price = lst.get("price", {})
            seller = lst.get("seller", {})
            u = lst.get("url", "")
            if u and not u.startswith("http"):
                u = f"https://www.autotrader.ca{u}"
            results.append({
                "id": lst.get("id", ""),
                "source": label,
                "year": veh.get("modelYear", ""),
                "make": veh.get("make", ""),
                "model": veh.get("model", ""),
                "price": price.get("priceFormatted", "N/A"),
                "mileage": veh.get("mileageInKm", "N/A"),
                "transmission": veh.get("transmission", ""),
                "city": loc.get("city", ""),
                "province": loc.get("provinceCode", ""),
                "country": loc.get("countryCode", ""),
                "seller_type": seller.get("type", ""),
                "url": u,
                "description": lst.get("description", ""),
                "subtitle": veh.get("subtitle", ""),
            })
        return results, None
    except Exception as e:
        return [], str(e)


def fetch_sr_autogroup(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        text = r.text
        text_lower = text.lower()

        # Check for sold indicators
        if re.search(r'>sold<', text_lower):
            return [], "Listing sold"

        price_m = re.search(r'\$([\d,]+)', text)
        year_m = re.search(r'\b(201[3-7])\b', text)
        km_m = re.search(r'(\d[\d,]*)\s*kms', text, re.I)

        price = f"${price_m.group(1)}" if price_m else "N/A"
        year = year_m.group(1) if year_m else ""
        mileage = f"{km_m.group(1)} km" if km_m else ""

        return [{
            "id": url,
            "source": label,
            "year": year,
            "make": "Ferrari",
            "model": "F12",
            "price": price,
            "mileage": mileage,
            "city": "Vancouver",
            "province": "BC",
            "country": "CA",
            "seller_type": "Dealer",
            "url": url,
        }], None
    except Exception as e:
        return [], str(e)


def fetch_toybox(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        text = r.text
        text_lower = text.lower()
        if re.search(r'>sold<', text_lower):
            return [], "Listing sold"

        price_m = re.search(r'\$([\d,]+)', text)
        year_m = re.search(r'\b(201[3-7])\b', text)
        price = f"${price_m.group(1)}" if price_m else "N/A"
        year = year_m.group(1) if year_m else ""

        return [{
            "id": url,
            "source": label,
            "year": year,
            "make": "Ferrari",
            "model": "F12",
            "price": price,
            "mileage": "",
            "city": "Vancouver",
            "province": "BC",
            "country": "CA",
            "seller_type": "Dealer",
            "url": url,
        }], None
    except Exception as e:
        return [], str(e)


def fetch_luxurypulse(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text
        if "no longer available" in text.lower() or "listing has ended" in text.lower():
            return [], "Listing ended"
        price_m = re.search(r'\$\s*([0-9,]+)', text)
        price = f"${price_m.group(1)}" if price_m else "N/A"
        return [{
            "id": url,
            "source": label,
            "year": "2017",
            "make": "Ferrari",
            "model": "F12 TDF",
            "price": price,
            "mileage": "600 km",
            "city": "Montreal",
            "province": "QC",
            "country": "CA",
            "seller_type": "Dealer (Ferrari Quebec)",
            "url": url,
        }], None
    except Exception as e:
        return [], str(e)


def fetch_drivemotorsports(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text:
            return [], "No F12 in inventory"
        results = []
        for m in re.finditer(r'F12', r.text):
            start = max(0, m.start() - 100)
            end = min(len(r.text), m.end() + 100)
            ctx = r.text[start:end]
            price_m = re.search(r'\$\s*([0-9,]+)', ctx)
            year_m = re.search(r'\b(201[3-7])\b', ctx)
            if year_m:
                results.append({
                    "id": f"dms-{year_m.group(1)}",
                    "source": label,
                    "year": year_m.group(1),
                    "make": "Ferrari",
                    "model": "F12",
                    "price": f"${price_m.group(1)}" if price_m else "N/A",
                    "mileage": "",
                    "city": "Richmond",
                    "province": "BC",
                    "country": "CA",
                    "seller_type": "Dealer",
                    "url": url,
                })
                break
        return results, None
    except Exception as e:
        return [], str(e)


# ---------- NEW SOURCES ----------

def fetch_ferrari_dealer(url, label):
    """Fetch from official Ferrari dealer (uses ferraridealers.com platform)."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text

        # Check if F12 is mentioned as an actual listing (not just filter options)
        # These pages show vehicle cards with prices for each car
        # Search for vehicle listing patterns: nearby year + $price + F12 model name
        price_near_f12 = False
        for m in re.finditer(r'F12berlinetta|F12 Berlinetta|F12\b', r.text):
            start = max(0, m.start() - 200)
            end = min(len(r.text), m.end() + 200)
            ctx = r.text[start:end]
            # Skip image URLs and model filter options
            if re.search(r'(src=|href=|image|\.jpg|\.png|count["\']?\s*[:=])', ctx, re.I):
                continue
            price_m = re.search(r'\$\s*([0-9,]+)', ctx)
            year_m = re.search(r'\b(201[3-7])\b', ctx)
            if price_m and year_m:
                price_near_f12 = True
                city_prov = {
                    "Ontario": ("Vaughan", "ON"),
                    "Vancouver": ("Vancouver", "BC"),
                    "Alberta": ("Calgary", "AB"),
                    "Quebec": ("Montreal", "QC"),
                }
                city, prov = city_prov.get(label.replace("Ferrari ", ""), ("", ""))
                return [{
                    "id": f"ferrari-{label}-{year_m.group(1)}",
                    "source": f"Ferrari {label}",
                    "year": year_m.group(1),
                    "make": "Ferrari",
                    "model": "F12",
                    "price": f"${price_m.group(1)}",
                    "mileage": "",
                    "city": city,
                    "province": prov,
                    "country": "CA",
                    "seller_type": "Official Ferrari Dealer",
                    "url": url,
                }], None
        if not price_near_f12:
            return [], "No F12 listing in inventory (filter reference only)"
        return [], None
    except Exception as e:
        return [], str(e)


def fetch_generic_dealer(url, label, city, province, search_term="F12"):
    """Generic fetcher for dealer inventory pages."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text
        if search_term.lower() not in text.lower():
            return [], f"No {search_term} found"

        # Check for actual F12 vehicle listing (not image URLs or hashes)
        # Look for year + model name near each other with a price
        for m in re.finditer(r'(?:201[3-7]).{0,100}(?:F12|F12berlinetta)', r.text, re.I):
            ctx_start = max(0, m.start() - 50)
            ctx_end = min(len(r.text), m.end() + 50)
            ctx = r.text[ctx_start:ctx_end]
            # Skip image URLs
            if re.search(r'\.(jpg|png|webp|svg|gif)\b', ctx, re.I):
                continue
            price_m = re.search(r'\$\s*([0-9,]+)', ctx)
            year_m = re.search(r'\b(201[3-7])\b', ctx)
            if year_m:
                return [{
                    "id": f"{label.lower().replace(' ','')}-{year_m.group(1)}",
                    "source": label,
                    "year": year_m.group(1),
                    "make": "Ferrari",
                    "model": "F12",
                    "price": f"${price_m.group(1)}" if price_m else "N/A",
                    "mileage": "",
                    "city": city,
                    "province": province,
                    "country": "CA",
                    "seller_type": "Dealer",
                    "url": url,
                }], None
        return [], "F12 referenced but no active listing detected"
    except Exception as e:
        return [], str(e)


def fetch_kijiji(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        # Check for actual listings (not just search page header references)
        # Look for a year + F12 pattern near each other with a price
        for m in re.finditer(r'(?:201[3-7]).{0,100}(?:f12|f12berlinetta)', text):
            ctx = m.group()
            if re.search(r'\.(jpg|png|webp)', ctx):
                continue
            return [{
                "id": f"kijiji-{len(m.group())}",
                "source": label,
                "year": re.search(r'201[3-7]', ctx).group(),
                "make": "Ferrari",
                "model": "F12",
                "price": "N/A",
                "mileage": "",
                "city": "",
                "province": "",
                "country": "CA",
                "seller_type": "Private/Dealer",
                "url": url,
            }], None
        return [], "No F12 listings found on Kijiji"
    except Exception as e:
        return [], str(e)


def fetch_cargurus(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text or "0 results" in text:
            return [], "No F12 listings on CarGurus.ca"
        return [], "F12 model referenced but no active listings detected"
    except Exception as e:
        return [], str(e)


def fetch_jamesedition(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text:
            return [], "No F12 found"
        results = []
        for m in re.finditer(r'\$\s*[\d,]+', r.text):
            ctx_start = max(0, m.start() - 200)
            ctx_end = min(len(r.text), m.end() + 200)
            ctx = r.text[ctx_start:ctx_end].lower()
            if "f12" in ctx and ("canada" in ctx or "montr" in ctx or "toronto" in ctx or "vancouver" in ctx):
                year_m = re.search(r'\b(201[3-7])\b', ctx)
                results.append({
                    "id": f"jamesedition-{len(results)}",
                    "source": label,
                    "year": year_m.group(1) if year_m else "",
                    "make": "Ferrari",
                    "model": "F12",
                    "price": m.group(0),
                    "mileage": "",
                    "city": "",
                    "province": "",
                    "country": "CA",
                    "seller_type": "Aggregator",
                    "url": url,
                })
                break
        return results, None
    except Exception as e:
        return [], str(e)


def fetch_pfaff_reserve(url, label):
    """Fetch from Pfaff Reserve (D2C Media platform - limited data without JS)."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text and "f12berlinetta" not in text:
            if "ferrari" in text:
                return [], "No F12 referenced in inventory"
            return [], "No F12 found"

        price_m = re.search(r'\$\s*([\d,]+)', r.text)
        year_m = re.search(r'\b(201[3-7])\b', r.text)

        if year_m:
            return [{
                "id": "pfaff-reserve",
                "source": label,
                "year": year_m.group(1),
                "make": "Ferrari",
                "model": "F12",
                "price": f"${price_m.group(1)}" if price_m else "See AutoTrader.ca",
                "mileage": "",
                "city": "Vaughan",
                "province": "ON",
                "country": "CA",
                "seller_type": "Dealer",
                "url": "https://www.autotrader.ca/cars/ferrari/f12/",
            }], None
        return [], "F12 page exists but no listing data in HTML (JS-rendered)"
    except Exception as e:
        return [], str(e)


def fetch_marianetti(url, label):
    """Fetch from Marianetti Motors (Woodbridge ON)."""
    SOLID_PATTERNS = re.compile(r'\b(?:sold|vehicle\s+sold)\b', re.I)
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text
        if "f12" not in text.lower() and "f12berlinetta" not in text.lower():
            return [], "No F12 found"

        # Parse embedded vehicleArray JSON (edealer platform)
        m = re.search(r'vehicleArray\s*=\s*(\{)', text)
        if not m:
            return [], "No vehicleArray found in HTML"

        start = m.start(1)
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    raw = text[start:i + 1]
                    break
        else:
            return [], "Could not parse vehicleArray JSON"

        data = json.loads(raw)
        results = []
        for vid, v in data.items():
            if not isinstance(v, dict):
                continue
            model = (v.get("model") or "").lower()
            desc = (v.get("description") or "").lower()
            year = v.get("year", "")
            vin = v.get("vin", "")

            if "f12" not in model:
                continue

            if SOLID_PATTERNS.search(desc):
                continue

            mileage = v.get("mileage", "")
            price_raw = v.get("price", 0) or 0
            price_str = f"${price_raw:,}" if price_raw else "Contact dealer"

            results.append({
                "id": f"marianetti-{vin or vid}",
                "source": label,
                "year": year,
                "make": "Ferrari",
                "model": "F12",
                "price": price_str,
                "mileage": f"{mileage} km" if mileage else "",
                "city": "Woodbridge",
                "province": "ON",
                "country": "CA",
                "seller_type": "Dealer",
                "url": url,
            })

        if results:
            return results, None
        return [], "All F12 listings sold"
    except Exception as e:
        return [], str(e)


def fetch_kar_auto(url, label):
    """Fetch from KAR Auto Sales (Mississauga ON)."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text:
            return [], "No F12 found"
        year_m = re.search(r'\b(201[3-7])\b', r.text)
        if year_m:
            return [{
                "id": "kar-auto",
                "source": label,
                "year": year_m.group(1),
                "make": "Ferrari",
                "model": "F12",
                "price": "Contact dealer",
                "mileage": "",
                "city": "Mississauga",
                "province": "ON",
                "country": "CA",
                "seller_type": "Dealer",
                "url": url,
            }], None
        return [], "F12 referenced but no listing data"
    except Exception as e:
        return [], str(e)


FORUM_SALE_RE = re.compile(r'\b(?:for\s*sale|fs[\s:]|wts[\s:]|wtt[\s:]|sale\b)', re.I)
FORUM_CA_RE = re.compile(r'\b(?:canada|ontario|qu[eé]bec|b\.?c\.?|alberta|british\s*columbia|toronto|vancouver|montr[ée]al|calgary|woodbridge|mississauga|vaughan|oakville|markham|richmond|surrey|gta)\b', re.I)
FORUM_YEAR_RE = re.compile(r'\b(201[3-7])\b')


def fetch_ferrarichat(url, label):
    """Fetch from FerrariChat F12/812 forum for for-sale posts mentioning Canada."""
    try:
        r = http_get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        threads = []
        for m in re.finditer(
            r'<a href="threads/([^"]+)"[^>]*class="PreviewTooltip"[^>]*>([^<]+)</a>',
            r.text,
        ):
            slug = m.group(1)
            title = m.group(2).strip()

            tid_match = re.search(r'\.(\d+)/', slug)
            tid = tid_match.group(1) if tid_match else ""

            url_full = f"https://www.ferrarichat.com/forum/threads/{slug}"

            title_lower = title.lower()

            # Check if thread mentions F12 (not just 812)
            has_f12 = 'f12' in title_lower or 'f12berlinetta' in title_lower or 'tdf' in title_lower

            # Check for for-sale indicators
            is_sale = bool(FORUM_SALE_RE.search(title))

            # Check for Canada mentions
            is_ca = bool(FORUM_CA_RE.search(title))

            # Check for year
            year_m = FORUM_YEAR_RE.search(title)
            year = year_m.group(1) if year_m else ""

            # Priority: for-sale threads get scored higher
            if has_f12 and (is_sale or is_ca):
                threads.append({
                    "id": f"fchat-{tid}",
                    "source": label,
                    "year": year,
                    "make": "Ferrari",
                    "model": "F12",
                    "price": "See thread",
                    "mileage": "",
                    "city": "",
                    "province": "",
                    "country": "",
                    "seller_type": "Forum",
                    "url": url_full,
                    "title": title,
                    "reason": ("For-sale" if is_sale else "Canada mention"),
                })

        if not threads:
            return [], "No relevant F12 for-sale/Canada threads found"

        # Fetch content for the most promising thread
        for t in threads[:1]:
            try:
                tr = http_get(t["url"], headers=HEADERS, timeout=20)
                if tr.status_code == 200:
                    body = tr.text
                    # Get first post content
                    pm = re.search(
                        r'<blockquote[^>]*class="messageText[^>]*>(.*?)</blockquote>',
                        body, re.DOTALL,
                    )
                    if pm:
                        content = re.sub(r'<[^>]+>', ' ', pm.group(1))
                        content = re.sub(r'\s+', ' ', content).strip()[:500]
                        t["content_snippet"] = content
                    # Also search for Canada/location in the post
                    if FORUM_CA_RE.search(body):
                        t["reason"] = "Canada mention"
            except Exception:
                pass

        return threads, None
    except Exception as e:
        return [], str(e)


def fetch_dupontregistry(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text:
            return [], "No F12 on Dupont Registry"
        # Check for actual Canadian listing
        for m in re.finditer(r'\$\s*[\d,]+.{0,200}(?:canada|ontario|quebec|bc\b|alberta)', r.text, re.I | re.DOTALL):
            ctx = m.group().lower()
            if "f12" in ctx:
                return [{
                    "id": f"dupont-canada",
                    "source": label,
                    "year": "",
                    "make": "Ferrari",
                    "model": "F12",
                    "price": m.group(0).split("$")[1].split()[0] if "$" in m.group(0) else "N/A",
                    "mileage": "",
                    "city": "",
                    "province": "",
                    "country": "CA",
                    "seller_type": "Aggregator",
                    "url": url,
                }], None
        return [], "F12 referenced but no Canadian listing found"
    except Exception as e:
        return [], str(e)


def fetch_classiccom(url, label):
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text.lower()
        if "f12" not in text:
            return [], "No F12 found"
        results = []
        for m in re.finditer(r'kelowna|canada\b', text):
            ctx_start = max(0, m.start() - 500)
            ctx_end = min(len(r.text), m.end() + 300)
            ctx = r.text[ctx_start:ctx_end]
            if "f12" in ctx.lower():
                price_m = re.search(r'\$\s*[\d,]+', ctx)
                year_m = re.search(r'\b(201[3-7])\b', ctx)
                if year_m:
                    detail_url = url
                    link_m = re.search(r'href="(/(?:veh|inventory)/[^"]+)"', ctx)
                    if link_m:
                        detail_url = f"https://www.classic.com{link_m.group(1)}"
                    results.append({
                        "id": f"classic-{len(results)}",
                        "source": label,
                        "year": year_m.group(1),
                        "make": "Ferrari",
                        "model": "F12",
                        "price": f"${price_m.group(1)}" if price_m else "N/A",
                        "mileage": "",
                        "city": "Kelowna" if "kelowna" in ctx.lower() else "",
                        "province": "BC",
                        "country": "CA",
                        "seller_type": "Aggregator",
                        "url": detail_url,
                    })
                    break
        return results, None
    except Exception as e:
        return [], str(e)


# ---------- PORSCHE 911 GT3 TOURING MANUAL ----------

def _is_gt3_touring_manual(lst):
    """Check if a listing is a GT3 with Touring package and Manual transmission."""
    desc = (lst.get("description") or "").lower()
    subtitle = (lst.get("subtitle") or "").lower()
    trans = (lst.get("transmission") or "").lower()

    is_touring = (
        "touring" in desc or "touring" in subtitle
    )

    is_manual = trans in ("manual", "manuelle") or "6-speed manual" in desc

    return is_touring and is_manual


def fetch_porsche_gt3_autotrader(url, label):
    """Fetch 911 GT3 Touring Manual listings from AutoTrader.ca."""
    results, err = fetch_autotrader(url, label)
    if err:
        return results, err
    filtered = [r for r in results if _is_gt3_touring_manual(r)]
    for r in filtered:
        r["model"] = "911 GT3 Touring"
    return filtered, None


def fetch_porsche_gt3_autohebdo(url, label):
    """Fetch 911 GT3 Touring Manual listings from AutoHebdo.net (French)."""
    results, err = fetch_autotrader(url, label)
    if err:
        return results, err
    filtered = [r for r in results if _is_gt3_touring_manual(r)]
    for r in filtered:
        r["model"] = "911 GT3 Touring"
        r["source"] = label  # Keep the original source label
    return filtered, None


# ---------- PORSCHE FINDER (finder.porsche.com) ----------

_POSTAL_PROVINCE = {
    "A": "NL", "B": "NS", "C": "PE", "E": "NB",
    "G": "QC", "H": "QC", "J": "QC",
    "K": "ON", "L": "ON", "M": "ON", "N": "ON", "P": "ON",
    "R": "MB", "S": "SK", "T": "AB", "V": "BC",
    "X": "NT", "Y": "YT",
}


def _extract_rsc_items(text):
    """Extract the items array from a Porsche Finder RSC page response."""
    import re, json
    rsc_parts = re.findall(
        r'self\.__next_f\.push\(\[(\d+),"((?:[^"\\]|\\.)*)"\]\)',
        text, re.DOTALL,
    )
    if not rsc_parts:
        return [], 0, 0
    all_raw = "".join(chunk for _, chunk in rsc_parts)
    all_data = all_raw.encode().decode("unicode_escape")

    tp = re.search(r'"totalPages":(\d+)', all_data)
    ap = re.search(r'"activePage":(\d+)', all_data)
    total_pages = int(tp.group(1)) if tp else 1
    active_page = int(ap.group(1)) if ap else 1

    idx = all_data.find('"items":[')
    if idx < 0:
        return [], active_page, total_pages

    start = idx + len('"items":[')
    depth = 1
    i = start
    while i < len(all_data) and depth > 0:
        if all_data[i] == "[":
            depth += 1
        elif all_data[i] == "]":
            depth -= 1
        if depth == 0:
            end = i
            break
        i += 1

    items_str = all_data[start:end]
    items = []
    pos = 0
    while pos < len(items_str):
        while pos < len(items_str) and items_str[pos] in " ,\n\r\t":
            pos += 1
        if pos >= len(items_str) or items_str[pos] != "{":
            break
        depth = 0
        j = pos
        while j < len(items_str) and (depth > 0 or j == pos):
            if items_str[j] == "{":
                depth += 1
            elif items_str[j] == "}":
                depth -= 1
            j += 1
        try:
            items.append(json.loads(items_str[pos:j]))
        except json.JSONDecodeError:
            break
        pos = j
    return items, active_page, total_pages


def fetch_porsche_finder(url, label):
    """Fetch 911 GT3 Touring Manual listings from finder.porsche.com."""
    results = []
    seen_ids = set()
    page = 1
    total_pages = 1

    while page <= total_pages:
        page_url = f"{url}&page={page}"
        try:
            r = http_get(page_url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                break
        except Exception:
            break

        items, active_page, total_pages = _extract_rsc_items(r.text)
        if not items or active_page != page:
            break

        for item in items:
            meta = item.get("meta", {}) or {}
            dlm = item.get("dataLayerListingMeta", {}) or {}
            car = dlm.get("car", {}) or {}
            seller = meta.get("seller", {}) or {}
            addr = seller.get("addressComponents", {}) or {}

            model_name = (
                car.get("modelName") or meta.get("title") or ""
            )
            trans = meta.get("transmission", "")
            model_str = str(model_name)

            if "GT3" not in model_str or "Touring" not in model_str:
                continue
            if str(trans).lower() != "manual":
                continue

            lid = item.get("id", "")
            if lid in seen_ids:
                continue
            seen_ids.add(lid)

            price = car.get("priceTotalTotal")
            mileage_val = car.get("mileageValue")
            mileage_unit = car.get("mileageUnit", "KM")
            mileage = f"{mileage_val} {mileage_unit}" if mileage_val else ""

            city = addr.get("city", "")
            postal = addr.get("postalCode", "") or seller.get("formattedCity", "")
            province = _POSTAL_PROVINCE.get((postal or "")[:1].upper(), "")

            details_url = meta.get("detailsUrl", "")
            if not details_url:
                slug = item.get("listingUrlSlug", "")
                details_url = (
                    f"https://finder.porsche.com/ca/en-CA/details/{slug}"
                    if slug else ""
                )

            color = meta.get("exteriorColor") or meta.get("color") or ""
            year = meta.get("modelYear", "")
            dealer_name = seller.get("name", "")

            results.append({
                "id": lid,
                "source": label,
                "year": str(year),
                "make": "Porsche",
                "model": "911 GT3 Touring",
                "price": f"${price:,}" if isinstance(price, int) else "N/A",
                "mileage": mileage or "N/A",
                "transmission": trans,
                "city": city,
                "province": province,
                "country": "CA",
                "seller_type": f"Dealer ({dealer_name})",
                "url": details_url,
                "description": f"{model_str} - {color}",
            })

        page += 1
        if page > total_pages:
            break

    return results, None


def fetch_winding_road(url, label):
    """Fetch GT3 listings from Winding Road Motorcars (Langley, BC)."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        # Split page by car card wrappers to isolate individual listings
        parts = re.split(r'<div[^>]*class="[^"]*Car_car__[^"]*"[^>]*>', r.text)
        if len(parts) < 2:
            return [], "No car cards found"

        results = []
        seen = set()
        # Skip first part (before first car card)
        for part in parts[1:]:
            # Close the div at the end of this card (find the matching close)
            depth = 0
            close_idx = -1
            for i, ch in enumerate(part):
                if ch == "<":
                    next_ch = part[i:i+2] if i+1 < len(part) else ""
                    if next_ch == "</":
                        depth -= 1
                    elif next_ch == "<!":
                        continue  # comment
                    else:
                        depth += 1
                if depth < 0:
                    close_idx = i + len("</div>")
                    break
            card_html = part[:close_idx] if close_idx > 0 else part

            slug_m = re.search(r'href="(/inventory/[^"]+)"', card_html)
            if not slug_m:
                continue
            lid = slug_m.group(1)
            if lid in seen:
                continue
            seen.add(lid)

            card_lower = card_html.lower()
            if "porsche" not in card_lower or "911" not in card_lower or "gt3" not in card_lower:
                continue
            if "touring" not in card_lower:
                continue
            if "manual" not in card_lower and "6-speed" not in card_lower:
                continue

            title_m = re.search(r'<p[^>]*class="[^"]*Car_title__[^"]*"[^>]*>(.*?)</p>', card_html)
            title = title_m.group(1).strip() if title_m else ""

            price_m = re.search(r'<p>\$\s*([\d\s]+)</p>', card_html)
            price_raw = price_m.group(1).strip() if price_m else ""
            price = f"${price_raw}" if price_raw else "N/A"

            year_m = re.search(r'<p[^>]*class="[^"]*Car_year__[^"]*"[^>]*>\s*(\d{4})\s*</p>', card_html)
            year = year_m.group(1) if year_m else ""

            mileage_m = re.search(r'<p[^>]*class="[^"]*Car_miles__[^"]*"[^>]*>\s*([\d,]+)\s*</p>', card_html)
            mileage = mileage_m.group(1) if mileage_m else ""

            detail_url = f"https://www.windingroad.ca{slug_m.group(1)}"

            results.append({
                "id": f"windingroad-{lid}",
                "source": label,
                "year": year,
                "make": "Porsche",
                "model": "911 GT3 Touring",
                "price": price,
                "mileage": mileage or "N/A",
                "transmission": "Manual",
                "city": "Langley",
                "province": "BC",
                "country": "CA",
                "seller_type": "Dealer (Winding Road Motorcars)",
                "url": detail_url,
                "description": title,
            })

        return results, None
    except Exception as e:
        return [], str(e)


def fetch_kijiji_gt3(url, label):
    """Fetch GT3 listings from Kijiji using embedded JSON-LD structured data."""
    try:
        r = http_get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"

        # Kijiji embeds listing data in JSON-LD script tags
        jsonld_matches = re.finditer(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            r.text, re.DOTALL,
        )
        items = []
        for m in jsonld_matches:
            try:
                data = json.loads(m.group(1))
                if data.get("@type") == "ItemList":
                    elements = data.get("itemListElement", [])
                    for elem in elements:
                        item = elem.get("item", {})
                        if item.get("@type") != "Car":
                            continue
                        items.append(item)
            except (json.JSONDecodeError, KeyError):
                continue

        if not items:
            return [], "No structured data found on Kijiji"

        results = []
        seen = set()
        for item in items:
            name = item.get("name", "")
            model_cfg = item.get("vehicleConfiguration", "") or ""
            model = item.get("model", "")
            year = str(item.get("vehicleModelDate", ""))
            offers = item.get("offers", {})
            price_raw = offers.get("price", "")
            try:
                price_int = int(float(price_raw))
                price_str = f"${price_int:,}"
            except (ValueError, TypeError):
                price_str = f"${price_raw}" if price_raw else "N/A"
            mileage_obj = item.get("mileageFromOdometer", {})
            mileage_val = mileage_obj.get("value", "") if mileage_obj else ""
            mileage = f"{mileage_val} km" if mileage_val else ""
            trans = item.get("vehicleTransmission", "") or ""
            url_val = item.get("url", "")
            vin = item.get("vehicleIdentificationNumber", "")
            color = item.get("color", "")
            drive = item.get("driveWheelConfiguration", "")

            # Check if it's a GT3 Touring Manual
            name_lower = name.lower()
            cfg_lower = model_cfg.lower()
            trans_lower = str(trans).lower()

            if "gt3" not in name_lower and "gt3" not in cfg_lower:
                continue
            is_touring = "touring" in name_lower or "touring" in cfg_lower
            is_manual = trans_lower == "manual"

            if not (is_touring and is_manual):
                continue

            if vin in seen:
                continue
            seen.add(vin or url_val)

            # Extract city from Kijiji URL path: /v-cars-trucks/<city>/...
            city = ""
            province = ""
            if url_val:
                city_m = re.search(r'/v-cars-trucks/([^/]+)/', url_val)
                if city_m:
                    city = city_m.group(1).replace("-", " ").title().strip()
                    # Map known Kijiji city slugs to city/province
                    city_map = {
                        "Mississauga Peel Region": ("Mississauga", "ON"),
                        "City Of Toronto": ("Toronto", "ON"),
                        "Ottawa": ("Ottawa", "ON"),
                        "London": ("London", "ON"),
                        "Barrie": ("Barrie", "ON"),
                    }
                    if city in city_map:
                        city, province = city_map[city]

            results.append({
                "id": f"kijiji-gt3-{vin or len(results)}",
                "source": label,
                "year": year,
                "make": "Porsche",
                "model": "911 GT3 Touring",
                "price": price_str,
                "mileage": mileage or "N/A",
                "transmission": trans,
                "city": city,
                "province": province,
                "country": "CA",
                "seller_type": "Private/Dealer",
                "url": url_val,
                "description": name,
            })

        return results, None
    except Exception as e:
        return [], str(e)


SOURCES = [
    # Original sources
    ("autotrader", "https://www.autotrader.ca/cars/ferrari/f12", "AutoTrader.ca", fetch_autotrader),
    ("autohebdo", "https://www.autohebdo.net/cars/ferrari/f12", "AutoHebdo.net", fetch_autotrader),
    ("sr_auto", "https://www.srautogroup.com/2015-ferrari-f12", "SR Auto Group (Vancouver)", fetch_sr_autogroup),
    ("toybox", "https://www.toyboxauto.ca/cars/2017-ferrari-f12---70th-anniversary", "Toybox (Vancouver)", fetch_toybox),
    ("luxurypulse", "https://luxurypulse.com/sales/show/2505-ferrari-f12tdf", "Ferrari Quebec (LuxuryPulse)", fetch_luxurypulse),
    ("drivemotorsports", "https://www.drivemotorsports.ca/vehicles/ferrari/", "Drive Motor Sports (Richmond BC)", fetch_drivemotorsports),

    # Official Ferrari dealers (same platform by CDK Global)
    ("ferrari_ontario", "https://ontario.ferraridealers.com/en-US/r/used-ferrari/f", "Ferrari of Ontario", fetch_ferrari_dealer),
    ("ferrari_vancouver", "https://vancouver.ferraridealers.com/en-US/r/used-ferrari/f", "Ferrari of Vancouver", fetch_ferrari_dealer),
    ("ferrari_alberta", "https://alberta.ferraridealers.com/en-US/r/used-ferrari/f", "Ferrari of Alberta", fetch_ferrari_dealer),
    ("ferrari_quebec", "https://quebec.ferraridealers.com/en-US/r/used-ferrari/f", "Ferrari Quebec", fetch_ferrari_dealer),

    # Luxury/exotic dealers
    ("grandtouring", "https://www.grandtouringautos.com/", "Grand Touring Automobiles", lambda u, l: fetch_generic_dealer(u, l, "Oakville", "ON")),
    ("sherwood", "https://www.sherwoodmotorcars.com/ferrari-inventory", "Sherwood Motorcars (AB)", lambda u, l: fetch_generic_dealer(u, l, "Sherwood Park", "AB")),
    ("johnscotti", "https://johnscottiluxuryprestige.com/en/pre-owned", "John Scotti Luxury-Prestige (QC)", lambda u, l: fetch_generic_dealer(u, l, "Montreal", "QC")),
    ("worldfinecars", "https://www.worldfinecars.ca/", "World Fine Cars (ON)", lambda u, l: fetch_generic_dealer(u, l, "Etobicoke", "ON")),
    ("weissach", "https://www.weissach.com/vehicles/", "Weissach Performance (BC)", lambda u, l: fetch_generic_dealer(u, l, "Vancouver", "BC")),
    ("silverarrow", "https://silverarrowcars.com/collections/cars", "Silver Arrow Cars (BC)", lambda u, l: fetch_generic_dealer(u, l, "Victoria", "BC")),
    ("august", "https://www.augustmotorcars.com/", "August Motorcars (BC)", lambda u, l: fetch_generic_dealer(u, l, "Kelowna", "BC")),

    # Aggregator / marketplace sources
    ("kijiji", "https://www.kijiji.ca/b-cars/ontario/ferrari-f12/k0c174l9004", "Kijiji Autos", fetch_kijiji),
    ("cargurus", "https://www.cargurus.ca/Cars/l-Used-Ferrari-F12-Berlinetta-c24242", "CarGurus.ca", fetch_cargurus),
    ("jamesedition", "https://www.jamesedition.com/cars/ferrari/f12", "JamesEdition", fetch_jamesedition),
    ("dupont", "https://www.dupontregistry.com/used-ferrari-f12--berlinetta-for-sale", "Dupont Registry", fetch_dupontregistry),
    ("classiccom", "https://www.classic.com/m/ferrari/f12/", "Classic.com", fetch_classiccom),

    # D2C Media platform (JS-rendered; listing data on AutoTrader.ca)
    ("pfaff", "https://www.pfaffreserve.com/used/Ferrari-F12berlinetta.html", "Pfaff Reserve (ON)", fetch_pfaff_reserve),

    # Marianetti Motors - D2C Media platform
    ("marianetti", "https://www.marianettimotors.com/used/Ferrari-F12berlinetta.html", "Marianetti Motors (ON)", fetch_marianetti),

    # KAR Auto Sales - used cars Mississauga
    ("karauto", "https://www.karautosales.ca/", "KAR Auto Sales (ON)", fetch_kar_auto),

    # FerrariChat F12/812 forum - monitor for-sale / Canada mentions
    ("ferrarichat", "https://www.ferrarichat.com/forum/forums/f12-812.360/", "FerrariChat F12/812 Forum", fetch_ferrarichat),

    # ---------- Porsche 911 GT3 Touring Manual ----------
    ("porsche_autotrader", "https://www.autotrader.ca/cars/porsche/911/?trim=GT3", "AutoTrader.ca (911 GT3)", fetch_porsche_gt3_autotrader),
    ("porsche_autohebdo", "https://www.autohebdo.net/cars/porsche/911/?trim=GT3", "AutoHebdo.net (911 GT3)", fetch_porsche_gt3_autohebdo),

    # finder.porsche.com - official Porsche dealer inventory
    ("porsche_finder", "https://finder.porsche.com/ca/en_CA/search/911?condition=used", "Porsche Finder CA", fetch_porsche_finder),

    # Winding Road Motorcars - independent exotic dealer (Langley, BC)
    ("winding_road", "https://www.windingroad.ca/inventory/", "Winding Road Motorcars (BC)", fetch_winding_road),

    # Kijiji Autos - GT3 search (includes private party + dealer listings)
    ("kijiji_gt3", "https://www.kijiji.ca/b-cars/ontario/porsche-911-gt3/k0c174l9004", "Kijiji Autos (911 GT3)", fetch_kijiji_gt3),
]

# FMP Motorcars: website could not be found.


def validate_listing(listing_url):
    """Verify a listing page is still live and shows the car for sale."""
    try:
        r = http_get(listing_url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text, re.DOTALL,
        )
        if m:
            try:
                data = json.loads(m.group(1))
                ld = data.get("props", {}).get("pageProps", {}).get("listingDetails", {})
                if ld:
                    status = ld.get("status", "")
                    if status == "Active":
                        return True, "Active"
                    elif status in ("Sold", "Inactive", "Deleted"):
                        return False, f"Status: {status}"
            except (json.JSONDecodeError, KeyError):
                pass

        # Porsche Finder validation: check for priceValue in RSC data
        if "finder.porsche.com" in listing_url:
            rsc_parts = re.findall(
                r'self\.__next_f\.push\(\[(\d+),"((?:[^"\\]|\\.)*)"\]\)',
                r.text, re.DOTALL,
            )
            if rsc_parts:
                all_raw = "".join(chunk for _, chunk in rsc_parts)
                all_data = all_raw.encode().decode("unicode_escape")
                # If priceValue exists, the listing is active
                if '"priceValue":' in all_data:
                    return True, "Active"
                # If listingDeleted or listingPaused title is shown, it's dead
                if '"listingDeleted"' in all_data or '"listingPaused"' in all_data:
                    return False, "Not available"
                return False, "No price data"

        text_lower = r.text.lower()
        dead_phrases = [
            "no longer available",
            "this vehicle is no longer for sale",
            "listing removed",
            "this listing has ended",
            "this car has been sold",
            "listing expired",
            "either sold, or removed",
        ]
        # Check for standalone "sold" badge in HTML (like <span>SOLD</span>)
        if re.search(r'>sold<', text_lower):
            return False, "Not available (sold)"
        for phrase in dead_phrases:
            if phrase in text_lower:
                return False, "Not available"

        return True, "Live"
    except Exception as e:
        return False, str(e)


def build_html_table(listings, source_results):
    f12_count = sum(1 for l in listings if l.get("make") == "Ferrari")
    gt3_count = sum(1 for l in listings if "GT3" in (l.get("model") or ""))
    model_parts = []
    if f12_count:
        model_parts.append(f"{f12_count} F12")
    if gt3_count:
        model_parts.append(f"{gt3_count} 911 GT3 Touring Manual")
    summary_text = f"{' & '.join(model_parts)} listing(s) found in Canada" if model_parts else "No listings found"

    rows = ""
    for l in listings:
        badge = (
            '<span style="color:green;font-weight:bold">LIVE</span>'
            if l.get("verified")
            else f'<span style="color:red">DEAD: {l.get("verify_msg", "")}</span>'
        )
        rows += f"""<tr>
            <td>{l['year']}</td>
            <td>{l.get('model', '')}</td>
            <td>{l['price']}</td>
            <td>{l['mileage']}</td>
            <td>{l['city']}, {l['province']}</td>
            <td>{l['source']}</td>
            <td>{l['seller_type']}</td>
            <td><a href="{l['url']}">Link</a></td>
            <td>{badge}</td>
        </tr>"""

    src_rows = ""
    for label, result in source_results:
        color = "#333"
        if result.startswith("Error") or result.startswith("Blocked") or "sold" in result.lower():
            color = "#c0392b"
        elif "listing" in result.lower():
            color = "#27ae60"
        elif result.startswith("No "):
            color = "#888"
        src_rows += f"""<tr>
            <td>{label}</td>
            <td style="color:{color}">{result}</td>
        </tr>"""

    return f"""<html>
<head><style>
    body {{ font-family: Arial, sans-serif; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #c0392b; color: white; }}
    tr:nth-child(even) {{ background-color: #f2f2f2; }}
    .header {{ color: #c0392b; }}
    .summary {{ margin: 10px 0; padding: 10px; background: #f9f9f9; }}
</style></head>
<body>
    <h2 class="header">Canadian Listings Scan</h2>
    <p>{datetime.now().strftime("%B %d, %Y")}</p>
    <div class="summary">
        <strong>{summary_text}</strong>
    </div>
    <table>
        <tr>
            <th>Year</th><th>Model</th><th>Price</th><th>Mileage</th><th>Location</th>
            <th>Source</th><th>Seller</th><th>URL</th><th>Status</th>
        </tr>
        {rows}
    </table>
    <h3 style="margin-top:24px;color:#c0392b;">Sources Checked ({len(source_results)})</h3>
    <table>
        <tr><th>Source</th><th>Result</th></tr>
        {src_rows}
    </table>
    <p style="color: #888; font-size: 12px; margin-top: 20px;">
        Generated by F12 &amp; GT3 Scanner | Verified at listing source
    </p>
</body></html>"""


def get_app_password():
    """Get Gmail app password from env var, .env file, or registry."""
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    if pwd:
        return pwd
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GMAIL_APP_PASSWORD="):
                    return line.split("=", 1)[1]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            pwd, _ = winreg.QueryValueEx(key, "GMAIL_APP_PASSWORD")
            return pwd
    except Exception:
        pass
    return None


def send_email(html_body, listings):
    """Send the email via Gmail SMTP."""
    app_password = get_app_password()
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD not found (set in .env file or as env var)")
        return False

    f12_count = sum(1 for l in listings if l.get("make") == "Ferrari")
    gt3_count = sum(1 for l in listings if "GT3" in (l.get("model") or ""))
    parts = []
    if f12_count:
        parts.append(f"{f12_count} F12")
    if gt3_count:
        parts.append(f"{gt3_count} GT3 TM")
    total_str = f"{' & '.join(parts)} in Canada" if parts else "No listings"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"Car Scanner - {total_str} "
        f"({datetime.now().strftime('%b %d')})"
    )
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_FROM, app_password)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print(f"Email sent to {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


def main():
    all_listings = []
    seen_ids = set()
    source_results = []

    print("=" * 60)
    print(f"Car Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Models: Ferrari F12 + Porsche 911 GT3 Touring Manual")
    print("=" * 60)

    print("\n--- Phase 1: Fetching ---")
    print(f"Scanning {len(SOURCES)} sources (F12 + 911 GT3 Touring Manual)...\n")

    for key, url, label, fetcher in SOURCES:
        lsts, err = fetcher(url, label)
        if err:
            print(f"  {label}: {err}")
            source_results.append((label, err))
            continue
        n = len(lsts)
        print(f"  {label}: {n} listing(s)")
        source_results.append((label, f"{n} listing(s)" if n else "No listings found"))
        for nl in lsts:
            dedup = nl.get("id") or nl.get("url", "")
            if dedup in seen_ids:
                continue
            seen_ids.add(dedup)
            prov = nl.get("province", "")
            ctry = nl.get("country", "")
            ca_provs = ("ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU")
            if ctry == "CA" or prov in ca_provs or not prov:
                all_listings.append(nl)
                print(f"    + {nl['year']} {nl['model']} - {nl['price']} - {nl.get('city','')}")

    print(f"\n  Total unique Canadian listings: {len(all_listings)}")

    print("\n--- Phase 2: Verification ---")
    for lst in all_listings:
        if lst.get("url"):
            live, msg = validate_listing(lst["url"])
            lst["verified"] = live
            lst["verify_msg"] = msg
            print(f"  {lst['year']} {lst['model']} - {'LIVE' if live else f'DEAD ({msg})'}")
        else:
            lst["verified"] = False

    live = [l for l in all_listings if l.get("verified")]

    print("\n--- Phase 3: Email ---")
    if live:
        html = build_html_table(live, source_results)
        sent = send_email(html, live)
    else:
        print("  No live listings to email")
        sent = False

    f12_live = sum(1 for l in live if l.get("make") == "Ferrari")
    gt3_live = sum(1 for l in live if "GT3" in (l.get("model") or ""))
    parts = []
    if f12_live:
        parts.append(f"{f12_live} F12")
    if gt3_live:
        parts.append(f"{gt3_live} GT3 Touring Manual")
    live_summary = f"{' & '.join(parts)} live" if parts else "No live listings"
    print(f"\nSUMMARY: {live_summary}")
    print(f"Email: {'Yes' if sent else 'No'}")


if __name__ == "__main__":
    main()
