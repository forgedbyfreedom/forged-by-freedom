#!/usr/bin/env python3
"""
ThinkSteroids.com Compound Profile Scraper
Scrapes all 90 steroid/ancillary compound profiles into @ThinkSteroids channel dir.
"""

import re
import time
from pathlib import Path

try:
    from curl_cffi import requests  # Chrome TLS fingerprint — bypasses Incapsula WAF
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(["pip3", "install", "curl_cffi", "beautifulsoup4", "--break-system-packages"],
                   capture_output=True)
    from curl_cffi import requests
    from bs4 import BeautifulSoup

IMPERSONATE = "chrome124"  # curl_cffi Chrome fingerprint profile

OUTPUT_DIR = Path(__file__).parent / "channels" / "@ThinkSteroids"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# All 90 compound profiles from thinksteroids.com/steroid-profiles/
PROFILES = [
    # Anabolic Steroids
    ("anabolicum-vister", "https://thinksteroids.com/steroid-profiles/anabolicum-vister/"),
    ("anadrol-oxymetholone", "https://thinksteroids.com/steroid-profiles/anadrol/"),
    ("anadur-nandrolone-hexylphenylpropionate", "https://thinksteroids.com/steroid-profiles/anadur/"),
    ("anavar-oxandrolone", "https://thinksteroids.com/steroid-profiles/anavar/"),
    ("andriol-testosterone-undecanoate", "https://thinksteroids.com/steroid-profiles/andriol/"),
    ("androgel-transdermal-testosterone", "https://thinksteroids.com/steroid-profiles/androgel/"),
    ("bolasterone-myagen", "https://thinksteroids.com/steroid-profiles/bolasterone/"),
    ("cheque-drops-mibolerone", "https://thinksteroids.com/steroid-profiles/cheque-drops/"),
    ("danocrine-danazol", "https://thinksteroids.com/steroid-profiles/danocrine/"),
    ("deca-durabolin-nandrolone-decanoate", "https://thinksteroids.com/steroid-profiles/deca-durabolin/"),
    ("dht-dihydrotestosterone", "https://thinksteroids.com/steroid-profiles/dht/"),
    ("dianabol-methandrostenolone", "https://thinksteroids.com/steroid-profiles/dianabol/"),
    ("dynabolon-nandrolone-undecanoate", "https://thinksteroids.com/steroid-profiles/dynabolon/"),
    ("equipoise-boldenone-undecylenate", "https://thinksteroids.com/steroid-profiles/equipoise/"),
    ("esiclene-formebolone", "https://thinksteroids.com/steroid-profiles/esiclene/"),
    ("halotestin", "https://thinksteroids.com/steroid-profiles/halotestin/"),
    ("laurabolin-nandrolone-laurate", "https://thinksteroids.com/steroid-profiles/laurabolin/"),
    ("masteron-drostanolone-propionate", "https://thinksteroids.com/steroid-profiles/masteron/"),
    ("megagrisevit-clostebol-acetate", "https://thinksteroids.com/steroid-profiles/megagrisevit/"),
    ("methandriol-dipropionate", "https://thinksteroids.com/steroid-profiles/methandriol-dipropionate/"),
    ("methyltestosterone", "https://thinksteroids.com/steroid-profiles/methyltestosterone/"),
    ("methyltrienolone", "https://thinksteroids.com/steroid-profiles/methyltrienolone/"),
    ("miotolan-furazabol", "https://thinksteroids.com/steroid-profiles/miotolan/"),
    ("nilevar-norethandrolone", "https://thinksteroids.com/steroid-profiles/nilevar/"),
    ("omnadren-250", "https://thinksteroids.com/steroid-profiles/omnadren-250/"),
    ("oral-turinabol", "https://thinksteroids.com/steroid-profiles/oral-turinabol/"),
    ("parabolan-trenbolone-cyclohexylmethylcarbonate", "https://thinksteroids.com/steroid-profiles/parabolan/"),
    ("primobolan-methenolone-acetate", "https://thinksteroids.com/steroid-profiles/primobolan/"),
    ("primobolan-depot-methenolone-enanthate", "https://thinksteroids.com/steroid-profiles/primobolan-depot/"),
    ("primoteston-depot-testosterone-enanthate", "https://thinksteroids.com/steroid-profiles/primoteston-depot/"),
    ("proviron-mesterolone", "https://thinksteroids.com/steroid-profiles/proviron/"),
    ("sten-testosterone-dhea", "https://thinksteroids.com/steroid-profiles/sten/"),
    ("stenox-fluoxymesterone", "https://thinksteroids.com/steroid-profiles/stenox/"),
    ("sustanon-250", "https://thinksteroids.com/steroid-profiles/sustanon-250/"),
    ("testosterone-cypionate", "https://thinksteroids.com/steroid-profiles/testosterone-cypionate/"),
    ("testosterone-enanthate", "https://thinksteroids.com/steroid-profiles/testosterone-enanthate/"),
    ("testosterone-phenylpropionate", "https://thinksteroids.com/steroid-profiles/testosterone-phenylpropionate/"),
    ("testosterone", "https://thinksteroids.com/steroid-profiles/testosterone/"),
    ("testosterone-propionate", "https://thinksteroids.com/steroid-profiles/testosterone-propionate/"),
    ("testosterone-suspension", "https://thinksteroids.com/steroid-profiles/testosterone-suspension/"),
    ("testoviron", "https://thinksteroids.com/steroid-profiles/testoviron/"),
    ("thg", "https://thinksteroids.com/steroid-profiles/thg/"),
    ("thioderon", "https://thinksteroids.com/steroid-profiles/thioderon/"),
    ("transdermal-testosterone", "https://thinksteroids.com/steroid-profiles/transdermal-testosterone/"),
    ("trenbolone-acetate", "https://thinksteroids.com/steroid-profiles/trenbolone-acetate/"),
    ("trenbolone-enanthate", "https://thinksteroids.com/steroid-profiles/trenbolone-enanthate/"),
    ("trestolone-acetate-ment", "https://thinksteroids.com/steroid-profiles/trestolone-acetate-ment/"),
    ("winstrol-stanozolol", "https://thinksteroids.com/steroid-profiles/winstrol/"),
    ("winstrol-depot-stanozolol", "https://thinksteroids.com/steroid-profiles/winstrol-depot/"),
    # Ancillaries & PEDs
    ("aicar", "https://thinksteroids.com/steroid-profiles/aicar/"),
    ("albuterol-salbutamol", "https://thinksteroids.com/steroid-profiles/albuterol/"),
    ("arimidex-anastrozole", "https://thinksteroids.com/steroid-profiles/arimidex/"),
    ("aromasin-exemestane", "https://thinksteroids.com/steroid-profiles/aromasin/"),
    ("dutasteride-avodart", "https://thinksteroids.com/steroid-profiles/dutasteride/"),
    ("cialis-tadalafil", "https://thinksteroids.com/steroid-profiles/cialis/"),
    ("cjc-1295", "https://thinksteroids.com/steroid-profiles/cjc-1295/"),
    ("clenbuterol", "https://thinksteroids.com/steroid-profiles/clenbuterol/"),
    ("clomid-clomiphene-citrate", "https://thinksteroids.com/steroid-profiles/clomid/"),
    ("cytadren-aminoglutethimide", "https://thinksteroids.com/steroid-profiles/cytadren/"),
    ("cytomel-t3", "https://thinksteroids.com/steroid-profiles/cytomel/"),
    ("deprenyl-selegiline", "https://thinksteroids.com/steroid-profiles/deprenyl/"),
    ("dnp-2-4-dinitrophenol", "https://thinksteroids.com/steroid-profiles/dnp/"),
    ("dostinex-cabergoline", "https://thinksteroids.com/steroid-profiles/dostinex/"),
    ("ephedrine", "https://thinksteroids.com/steroid-profiles/ephedrine/"),
    ("epogen-epo-erythropoietin", "https://thinksteroids.com/steroid-profiles/epogen/"),
    ("evista-raloxifene", "https://thinksteroids.com/steroid-profiles/evista/"),
    ("fareston-toremifene-citrate", "https://thinksteroids.com/steroid-profiles/fareston/"),
    ("femara-letrozole", "https://thinksteroids.com/steroid-profiles/letrozole/"),
    ("ghrp-6", "https://thinksteroids.com/steroid-profiles/ghrp-6/"),
    ("hcg-human-chorionic-gonadotropin", "https://thinksteroids.com/steroid-profiles/hcg/"),
    ("hexarelin", "https://thinksteroids.com/steroid-profiles/hexarelin/"),
    ("hgh-human-growth-hormone", "https://thinksteroids.com/steroid-profiles/hgh/"),
    ("igf-1", "https://thinksteroids.com/steroid-profiles/igf-1/"),
    ("igf-1-bp3", "https://thinksteroids.com/steroid-profiles/igf-1-bp3/"),
    ("insulin", "https://thinksteroids.com/steroid-profiles/insulin/"),
    ("ketotifen", "https://thinksteroids.com/steroid-profiles/ketotifen/"),
    ("levitra-vardenafil", "https://thinksteroids.com/steroid-profiles/levitra/"),
    ("melanotan-ii", "https://thinksteroids.com/steroid-profiles/melanotan-ii/"),
    ("mgf-mechano-growth-factor", "https://thinksteroids.com/steroid-profiles/mgf/"),
    ("mod-grf-1-29", "https://thinksteroids.com/steroid-profiles/mod-grf-1-29/"),
    ("nolvadex-tamoxifen-citrate", "https://thinksteroids.com/steroid-profiles/nolvadex/"),
    ("parlodel-bromocriptine", "https://thinksteroids.com/steroid-profiles/bromocriptine/"),
    ("peg-mgf", "https://thinksteroids.com/steroid-profiles/peg-mgf/"),
    ("proscar-finasteride", "https://thinksteroids.com/steroid-profiles/proscar/"),
    ("prostaglandin-pgf2a", "https://thinksteroids.com/steroid-profiles/pgf2a/"),
    ("tb-500", "https://thinksteroids.com/steroid-profiles/tb-500/"),
    ("telmisartan", "https://thinksteroids.com/steroid-profiles/telmisartan/"),
    ("teslac-testolactone", "https://thinksteroids.com/steroid-profiles/teslac/"),
    ("thyroxine-t4", "https://thinksteroids.com/steroid-profiles/synthroid/"),
    ("viagra-sildenafil-citrate", "https://thinksteroids.com/steroid-profiles/viagra/"),
]


def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    # Target the main content area
    main = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|entry|post"))
    text = (main or soup).get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) > 3]
    # Deduplicate consecutive identical lines
    deduped = []
    prev = ""
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line
    return "\n".join(deduped)


def fetch_profile(slug, url):
    out = OUTPUT_DIR / f"{slug}.txt"
    if out.exists():
        print(f"  ⏭  {slug}")
        return True
    try:
        r = requests.get(url, headers=HEADERS, impersonate=IMPERSONATE, timeout=30)
        if r.status_code != 200:
            print(f"  ❌ {slug} — HTTP {r.status_code}")
            return False
        text = clean_text(r.text)
        if len(text.split()) < 50:
            print(f"  ⚠️  {slug} — too short")
            return False
        content = f"Source: ThinkSteroids.com — Compound Profile\n"
        content += f"Compound: {slug.replace('-', ' ').title()}\n"
        content += f"URL: {url}\n"
        content += f"Speaker: ThinkSteroids Reference Database\n"
        content += "=" * 60 + "\n\n"
        content += text
        out.write_text(content, encoding="utf-8")
        print(f"  ✅ {slug} ({len(text.split())} words)")
        return True
    except Exception as e:
        print(f"  ❌ {slug} — {e}")
        return False


def main():
    print("=" * 60)
    print("  THINKSTEROIDS COMPOUND PROFILE SCRAPER")
    print(f"  {len(PROFILES)} profiles — output: {OUTPUT_DIR}")
    print("=" * 60)
    ok = fail = 0
    for slug, url in PROFILES:
        if fetch_profile(slug, url):
            ok += 1
        else:
            fail += 1
        time.sleep(1.5)
    (OUTPUT_DIR / "channel.url").write_text("https://thinksteroids.com/steroid-profiles/\n")
    print(f"\n✅ Done — {ok} saved, {fail} failed")


if __name__ == "__main__":
    main()
