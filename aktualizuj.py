"""Stiahne najnovšie inzeráty áut z Bazoš.sk a uloží ich do site/data.json.

Beží automaticky v GitHub Actions (.github/workflows/aktualizacia.yml).
Filter: cena 200 – 20 000 €, nájazd 5 000 – 250 000 km.
Spustenie:  python aktualizuj.py [pocet_stranok]   (predvolene 50 strán = ~2000 inzerátov)
"""
import html, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site", "data.json")
BASE = "https://auto.bazos.sk"
MAX_PRICE = 20000
MAX_KM = 250_000
Q = f"?hledat=&hlokalita=&humkreis=25&cenaod=200&cenado={MAX_PRICE}&order="
BAD = re.compile(r"disk|pneu|kolies|koles|karavan|príves|prives|vozík|\bmotor\b|diel|hlava|skúter|motocykel|štvorkolk|traktor|leasing|odstúpim|odstupim|havarovan|hydraulick", re.I)
KM = re.compile(r"(\d{1,3}(?:[ . ]\d{3})+|\d{4,7}|\d{2,3}(?:[.,]\d)?\s*(?:tis\.?|tisíc|k))\s*(?:km|kilometr)", re.I)
YR = re.compile(r"\b(199\d|200\d|201\d|202\d)\b")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def get(url):
    for attempt in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            print("pokus", attempt + 1, url, e)
            time.sleep(3)
    return ""


def parse_km(txt):
    for k in KM.finditer(txt):
        s = k.group(1).lower()
        if re.search(r"tis|k", s):
            v = float(s.replace(",", ".").split("t")[0].rstrip("k").strip()) * 1000
        else:
            v = int(re.sub(r"[ . ]", "", s))
        if 1000 <= v < 1_000_000:
            return int(v)
    return None


def scrape(pages):
    out, seen = [], set()
    for p in range(0, pages * 40, 40):
        h = get(f"{BASE}/{str(p) + '/' if p else ''}{Q}")
        for chunk in h.split('class="inzeraty inzeratyflex"')[1:]:
            m = re.search(r'class="?nadpis"?><a href="([^"]+)">(.*?)</a>', chunk, re.S)
            if not m:
                continue
            href, title = m.group(1), strip(m.group(2))
            if href in seen:
                continue
            seen.add(href)
            dm = re.search(r'class="?popis"?>(.*?)</div>', chunk, re.S)
            desc = strip(dm.group(1)) if dm else ""
            pm = re.search(r'inzeratycena[^>]*>(.*?)</div>', chunk, re.S)
            price = int(re.sub(r"\D", "", strip(pm.group(1))) or 0) if pm else 0
            lm = re.search(r'inzeratylok[^>]*>(.*?)</div>', chunk, re.S)
            loc = " · ".join(x for x in (strip(t) for t in re.split(r"<br\s*/?>", lm.group(1) if lm else "")) if x)
            im = re.search(r'<img src="([^"]+)"', chunk)
            txt = title + " " + desc
            y = YR.search(txt)
            out.append(dict(t=title, p=price, km=parse_km(txt), y=int(y.group(1)) if y else None, l=loc,
                            u=href if href.startswith("http") else BASE + href,
                            img=im.group(1) if im else "", d=re.sub(r"\s+", " ", desc)[:200]))
        time.sleep(0.5)
    return out


def main():
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    allads = scrape(pages)
    good = [o for o in allads if o["km"] and 5000 <= o["km"] <= MAX_KM and 0 < o["p"] <= MAX_PRICE
            and not BAD.search(o["t"] + " " + o["d"][:60])]
    print(f"Prezreté: {len(allads)}, uložené: {len(good)}")
    if len(good) < 50:
        sys.exit(f"CHYBA: našlo sa len {len(good)} ponúk (možno Bazoš zablokoval prístup alebo zmenil stránku).")
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=1)))  # SEČ
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": now.strftime("%d. %m. %Y %H:%M"), "ads": good}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
