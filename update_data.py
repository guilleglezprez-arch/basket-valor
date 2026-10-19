#!/usr/bin/env python3
"""Basket Valor: descarga cuotas reales (NBA y Euroliga) y genera data/picks.json.
Solo usa la librería estándar de Python. Necesita la variable ODDS_API_KEY."""
import os, sys, json, colorsys, hashlib, unicodedata, datetime as dt
import urllib.request, urllib.parse
from collections import defaultdict
from statistics import mean

KEY = os.environ.get("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4"
BOOK = "winamax_fr"
LEAGUES = {"nba": "basketball_nba", "euroleague": "basketball_euroleague"}
MIN_EDGE = float(os.environ.get("MIN_EDGE", 3))      # ventaja mínima (puntos) para marcar VALOR
MIN_PROB = float(os.environ.get("MIN_PROB", 50))     # probabilidad mínima (%) para marcar VALOR
MIN_BOOKS = int(os.environ.get("MIN_BOOKS", 3))      # casas mínimas (sin Winamax) para fiarse
HORIZON_H = int(os.environ.get("HORIZON_H", 40))     # solo partidos de las próximas horas
MAX_PROP_EVENTS = int(os.environ.get("MAX_PROP_EVENTS", 1))  # partidos NBA con props (gasta créditos)
OUT = "data/picks.json"
PROPS = {"player_points": "Puntos de jugador", "player_rebounds": "Rebotes de jugador", "player_assists": "Asistencias de jugador"}
STAT = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST"}
INJ = {"Out": "baja", "Day-To-Day": "duda"}
SKIP = {"FC", "Real", "BC", "KK", "AS", "CB", "BK"}
NBA = {"Hawks":("ATL",37),"Celtics":("BOS",38),"Cavaliers":("CLE",39),"Pelicans":("NOP",40),"Bulls":("CHI",41),"Mavericks":("DAL",42),"Nuggets":("DEN",43),"Warriors":("GSW",44),"Rockets":("HOU",45),"Clippers":("LAC",46),"Lakers":("LAL",47),"Heat":("MIA",48),"Bucks":("MIL",49),"Timberwolves":("MIN",50),"Nets":("BKN",51),"Knicks":("NYK",52),"Magic":("ORL",53),"Pacers":("IND",54),"76ers":("PHI",55),"Suns":("PHX",56),"Blazers":("POR",57),"Kings":("SAC",58),"Spurs":("SAS",59),"Thunder":("OKC",60),"Raptors":("TOR",61),"Jazz":("UTA",62),"Grizzlies":("MEM",63),"Wizards":("WAS",64),"Pistons":("DET",65),"Hornets":("CHA",66)}
EURO_LOGOS = {"madrid": "https://logotyp.us/file/real-madrid.svg", "barcelona": "https://logotyp.us/file/fc-barcelona.svg",
              "olympiacos": "https://logotyp.us/file/olympiacos-bc.svg", "panathinaikos": "https://logotyp.us/file/panathinaikos-bc.svg"}

def api(path, **params):
    params["apiKey"] = KEY
    with urllib.request.urlopen(f"{BASE}{path}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        print(f"  {path}: créditos restantes {r.headers.get('x-requests-remaining')}")
        return json.load(r)

def espn(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def pdate(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def nick(n): return n.split()[-1] if n else ""
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
def num(x): return ("%g" % x).replace(".", ",")

def color(name):
    h = int(hashlib.md5(name.encode()).hexdigest(), 16) % 360
    r, g, b = colorsys.hls_to_rgb(h / 360, .55, .65)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

def team(name, lg):
    t = {"name": name, "color": color(name)}
    if lg == "nba" and nick(name) in NBA:
        a, n = NBA[nick(name)]
        t["abbr"], t["logo"] = a, f"https://cdn.nba.com/logos/nba/1610612{700 + n}/global/L/logo.svg"
    else:
        w = [x for x in name.split() if x not in SKIP]
        t["abbr"] = (w[0] if w else name)[:3].upper()
        for k, u in EURO_LOGOS.items():
            if k in name.lower(): t["logo"] = u
    return t

def label(k):
    mk, name, desc, pt = k
    if mk == "h2h": return "Resultado", f"Gana {name}"
    if mk == "spreads": return "Hándicap", f"{name} {('%+g' % pt).replace('.', ',')}"
    if mk == "totals": return "Total de puntos", f"{'Más' if name == 'Over' else 'Menos'} de {num(pt)}"
    return PROPS[mk], f"{desc} {'más' if name == 'Over' else 'menos'} de {num(pt)}"

def collect(bookmakers, win, fair):
    """Winamax -> win[k]=cuota. Resto de casas -> fair[k]=[prob. sin margen]."""
    for bm in bookmakers:
        for mk in bm.get("markets", []):
            groups = defaultdict(list)
            for o in mk["outcomes"]:
                pt = o.get("point")
                gk = abs(pt) if mk["key"] == "spreads" and pt is not None else pt
                groups[(o.get("description"), gk)].append(o)
            for g in groups.values():
                if len(g) != 2: continue
                inv = [1 / o["price"] for o in g]; s = sum(inv)
                for o, i in zip(g, inv):
                    k = (mk["key"], o["name"], o.get("description"), o.get("point"))
                    if bm["key"] == BOOK: win[k] = o["price"]
                    else: fair[k].append(i / s)

def make_picks(win, fair, bajas):
    out = []
    for k, odds in win.items():
        ps = fair.get(k, [])
        if len(ps) < MIN_BOOKS: continue
        p, imp = mean(ps) * 100, 100 / odds
        if p - imp < 1: continue
        market, sel = label(k)
        why = f"Winamax paga {odds:.2f} (implica un {imp:.0f}%), pero la media de {len(ps)} casas sin Winamax, descontado su margen, estima un {p:.0f}%."
        if bajas: why += " " + bajas
        out.append({"market": market, "selection": sel, "odds": odds, "prob": round(p, 1), "edge": round(p - imp, 1), "why": why, "k": list(k)})
    return sorted(out, key=lambda x: -x["edge"])[:6]

def injuries():
    out = {}
    try:
        for t in espn("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries").get("injuries", []):
            it = [f"{i['athlete']['displayName']} ({INJ.get(i.get('status'), i.get('status', '?'))})" for i in t.get("injuries", [])]
            if it: out[nick(t["displayName"])] = it[:4]
    except Exception as e:
        print("  Sin datos de bajas:", e)
    return out

def bajas_text(inj, home, away):
    parts = [f"{nick(n)}: {', '.join(inj[nick(n)])}" for n in (home, away) if inj.get(nick(n))]
    return "Bajas y dudas — " + ". ".join(parts) + "." if parts else ""

# ---------- resultados de apuestas ya recomendadas ----------
def prop_value(l):
    d = (pdate(l["ev"]) - dt.timedelta(hours=6)).strftime("%Y%m%d")
    for ev in espn(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}").get("events", []):
        names = " ".join(c["team"]["displayName"] for c in ev["competitions"][0]["competitors"])
        if nick(l["home"]) in names and nick(l["away"]) in names:
            sm = espn(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={ev['id']}")
            for t in sm["boxscore"]["players"]:
                for st in t["statistics"]:
                    for a in st["athletes"]:
                        if norm(a["athlete"]["displayName"]) == norm(l["k"][2]):
                            return float(a["stats"][st["labels"].index(STAT[l["k"][0]])])
    return None

def grade(l, s):
    mk, name, desc, pt = l["k"]
    sc = {x["name"]: float(x["score"]) for x in s["scores"]}
    rival = lambda n: max(v for m, v in sc.items() if m != n)
    if mk == "h2h": return "won" if sc[name] > rival(name) else "lost"
    if mk == "spreads":
        d = sc[name] + pt - rival(name); return "void" if d == 0 else ("won" if d > 0 else "lost")
    if mk == "totals":
        t = sum(sc.values()); return "void" if t == pt else ("won" if (t > pt) == (name == "Over") else "lost")
    v = prop_value(l)
    if v is None: return "pending"
    return "void" if v == pt else ("won" if (v > pt) == (name == "Over") else "lost")

def resolve(log, now):
    pend = [l for l in log if l["result"] == "pending" and pdate(l["ev"]) + dt.timedelta(hours=4) < now]
    if not pend: return
    done = {}
    for lg in {l["league"] for l in pend}:
        try:
            for s in api(f"/sports/{LEAGUES[lg]}/scores", daysFrom=3):
                if s.get("completed") and s.get("scores"): done[s["id"]] = s
        except Exception as e:
            print("  Error al pedir resultados:", e)
    for l in pend:
        s = done.get(l["id"].split("|")[0])
        if not s: continue
        try: l["result"] = grade(l, s)
        except Exception as e: print("  No se pudo resolver", l["pick"], e)

def main():
    if not KEY: sys.exit("Falta la variable ODDS_API_KEY")
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: old = {}
    log = [] if old.get("demo", True) else old.get("log", [])
    now = dt.datetime.now(dt.timezone.utc)
    inj, leagues, errors = injuries(), {}, 0
    for lg, sport in LEAGUES.items():
        print(lg)
        try:
            events = api(f"/sports/{sport}/odds", regions="eu", markets="h2h,spreads,totals", oddsFormat="decimal", dateFormat="iso")
        except Exception as e:
            print("  Error:", e); errors += 1; leagues[lg] = []; continue
        events = sorted([e for e in events if 0 < (pdate(e["commence_time"]) - now).total_seconds() / 3600 <= HORIZON_H], key=lambda e: e["commence_time"])
        games = []
        for i, e in enumerate(events):
            win, fair = {}, defaultdict(list)
            collect(e.get("bookmakers", []), win, fair)
            if lg == "nba" and i < MAX_PROP_EVENTS:
                try:
                    pe = api(f"/sports/{sport}/events/{e['id']}/odds", regions="eu", markets=",".join(PROPS), oddsFormat="decimal", dateFormat="iso")
                    collect(pe.get("bookmakers", []), win, fair)
                except Exception as ex: print("  Sin props:", ex)
            h, a = e["home_team"], e["away_team"]
            bajas = bajas_text(inj, h, a) if lg == "nba" else ""
            picks = make_picks(win, fair, bajas)
            note = bajas or ("Winamax aún no ofrece cuotas de este partido." if not win else "")
            if win and not picks: note = (note + " " if note else "") + "Sin ventajas frente al resto de casas."
            games.append({"id": e["id"], "time": e["commence_time"], "note": note.strip(), "home": team(h, lg), "away": team(a, lg), "picks": picks})
            for p in picks:
                pid = f"{e['id']}|{p['k']}"
                if p["edge"] >= MIN_EDGE and p["prob"] >= MIN_PROB and not any(l["id"] == pid for l in log):
                    log.append({"id": pid, "date": now.strftime("%Y-%m-%d"), "match": f"{nick(h)} – {nick(a)}", "pick": p["selection"],
                                "odds": p["odds"], "prob": p["prob"], "result": "pending", "league": lg, "ev": e["commence_time"], "home": h, "away": a, "k": p["k"]})
        leagues[lg] = games
        print(f"  {len(games)} partidos")
    if errors == len(LEAGUES): sys.exit("No se pudo descargar ninguna liga; no toco los datos.")
    resolve(log, now)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"demo": False, "stake": 10, "min_edge": MIN_EDGE, "min_prob": MIN_PROB, "updated": now.isoformat(), "leagues": leagues, "log": log},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Listo:", OUT)

if __name__ == "__main__":
    main()
