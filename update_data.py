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
LOG_EDGE = float(os.environ.get("LOG_EDGE", 5))      # ventaja para ALTO VALOR (entra en el registro)
LOG_PROB = float(os.environ.get("LOG_PROB", 55))
MIN_SHOWN = int(os.environ.get("MIN_SHOWN", 4))      # apuestas mínimas que se enseñan por partido
MIN_BOOKS = int(os.environ.get("MIN_BOOKS", 3))      # casas mínimas (sin Winamax) para fiarse
HORIZON_H = int(os.environ.get("HORIZON_H", 48))     # solo partidos de las próximas horas
MAX_PROP_EVENTS = int(os.environ.get("MAX_PROP_EVENTS", 1))  # partidos NBA con props (gasta créditos)
OUT = "data/picks.json"
PROPS = {"player_points": "Puntos de jugador", "player_rebounds": "Rebotes de jugador", "player_assists": "Asistencias de jugador"}
STAT = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST"}
INJ = {"Out": "baja", "Day-To-Day": "duda"}
SKIP = {"FC", "Real", "BC", "KK", "AS", "CB", "BK"}
NBA = {"Hawks":("ATL",37),"Celtics":("BOS",38),"Cavaliers":("CLE",39),"Pelicans":("NOP",40),"Bulls":("CHI",41),"Mavericks":("DAL",42),"Nuggets":("DEN",43),"Warriors":("GSW",44),"Rockets":("HOU",45),"Clippers":("LAC",46),"Lakers":("LAL",47),"Heat":("MIA",48),"Bucks":("MIL",49),"Timberwolves":("MIN",50),"Nets":("BKN",51),"Knicks":("NYK",52),"Magic":("ORL",53),"Pacers":("IND",54),"76ers":("PHI",55),"Suns":("PHX",56),"Blazers":("POR",57),"Kings":("SAC",58),"Spurs":("SAS",59),"Thunder":("OKC",60),"Raptors":("TOR",61),"Jazz":("UTA",62),"Grizzlies":("MEM",63),"Wizards":("WAS",64),"Pistons":("DET",65),"Hornets":("CHA",66)}
NBA_COL = {"ATL":"#e03a3e","BOS":"#007a33","BKN":"#5b5f66","CHA":"#00788c","CHI":"#ce1141","CLE":"#860038","DAL":"#00538c","DEN":"#fec524","DET":"#c8102e","GSW":"#1d428a","HOU":"#ce1141","IND":"#fdbb30","LAC":"#c8102e","LAL":"#552583","MEM":"#5d76a9","MIA":"#98002e","MIL":"#00471b","MIN":"#236192","NOP":"#85714d","NYK":"#006bb6","ORL":"#0077c0","PHI":"#006bb6","PHX":"#e56020","POR":"#e03a3e","SAC":"#5a2d81","SAS":"#8a9299","OKC":"#007ac1","TOR":"#ce1141","UTA":"#f9a01b","WAS":"#e31837"}
EURO_COL = {"madrid": "#e9e9f2", "barcelona": "#a50044", "olympiacos": "#d4161c", "panathinaikos": "#0b8a42", "fenerbahce": "#ffd400", "efes": "#1a3a8a", "monaco": "#d4161c", "baskonia": "#c8102e", "maccabi": "#ffd400", "partizan": "#3a3a3a", "zalgiris": "#0b8a42", "bayern": "#c8102e", "milano": "#d4161c", "virtus": "#3a3a3a", "valencia": "#f58220", "asvel": "#3a7bd5", "paris": "#3a7bd5", "crvena": "#d4161c", "dubai": "#c8102e", "hapoel": "#d4161c"}
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
        t["color"] = NBA_COL.get(a, t["color"])
        t["abbr"], t["logo"] = a, f"https://cdn.nba.com/logos/nba/1610612{700 + n}/global/L/logo.svg"
    else:
        w = [x for x in name.split() if x not in SKIP]
        t["abbr"] = (w[0] if w else name)[:3].upper()
        for k, cc in EURO_COL.items():
            if k in name.lower(): t["color"] = cc
        for k, u in EURO_LOGOS.items():
            if k in name.lower(): t["logo"] = u
    return t

def label(k):
    mk, name, desc, pt = k
    if mk == "h2h": return "Resultado", f"Gana {name}"
    if mk == "spreads": return "Hándicap", f"{name} {('%+g' % pt).replace('.', ',')}"
    if mk == "totals": return "Total de puntos", f"{'Más' if name == 'Over' else 'Menos'} de {num(pt)}"
    return PROPS[mk], f"{desc} {'más' if name == 'Over' else 'menos'} de {num(pt)}"

def collect(bookmakers, win, fair, best=None):
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
                    else:
                        fair[k].append(i / s)
                        if best is not None: best[k] = max(best.get(k, 0), o["price"])

def make_picks(win, fair, bajas, best=None):
    cands = []
    for k, odds in win.items():
        ps = fair.get(k, [])
        if not ps: continue
        p, imp = mean(ps) * 100, 100 / odds
        market, sel = label(k)
        cands.append({"market": market, "selection": sel, "odds": odds, "prob": round(p, 1), "edge": round(p - imp, 1), "k": list(k),
                      "_n": len(ps), "_imp": imp, "_low": len(ps) < MIN_BOOKS})
    good = [c for c in cands if not c["_low"]]
    value = sorted([c for c in good if c["edge"] >= MIN_EDGE and c["prob"] >= MIN_PROB], key=lambda c: -c["edge"])[:10]
    for c in value: c["v"] = "yes" if c["edge"] >= LOG_EDGE and c["prob"] >= LOG_PROB else "caution"
    value.sort(key=lambda c: (c["v"] != "yes", -c["edge"]))
    strong = sorted([c for c in good if c not in value and c["prob"] >= 55 and c["odds"] >= 1.2], key=lambda c: -c["prob"])
    picks = value + strong[:max(0, 14 - len(value))]
    if len(picks) < MIN_SHOWN:  # si hay pocas, completar con las más probables aunque no destaquen
        extra = sorted([c for c in cands if c not in picks and c["odds"] >= 1.15], key=lambda c: (c["_low"], -c["prob"]))
        picks += extra[:MIN_SHOWN - len(picks)]
    if len(picks) < MIN_SHOWN and best:  # Winamax no ofrece (o aún no ha publicado) estas apuestas: referencia de otras casas
        refs = sorted([k for k, ps in fair.items() if k not in win and len(ps) >= 2 and best.get(k, 0) >= 1.15], key=lambda k: -mean(fair[k]))
        for k in refs[:MIN_SHOWN - len(picks)]:
            market, sel = label(k)
            p = mean(fair[k]) * 100
            picks.append({"market": market, "selection": sel, "odds": best[k], "prob": round(p, 1), "edge": 0, "k": list(k), "ref": True,
                          "why": f"Winamax todavía no ofrece esta apuesta. Referencia: {len(fair[k])} casas le dan un {p:.0f}% y el mejor precio que he visto es {best[k]:.2f} en otra casa. No sé si en Winamax habrá ventaja."})
    for c in picks:
        if c.get("ref"):
            c["rec"] = True
            c["v"] = "pass"
        elif c in value:
            c["why"] = (f"Winamax paga {c['odds']:.2f} (implica un {c['_imp']:.0f}%), pero la media de {c['_n']} casas sin Winamax, "
                        f"descontado su margen, estima un {c['prob']:.0f}%.") + (" " + bajas if bajas else "")
        else:
            c["rec"] = True
            c["v"] = "pass"
            c["why"] = (f"Es de las opciones más probables de este partido: las otras casas le dan un {c['prob']:.0f}%, pero Winamax paga {c['odds']:.2f} "
                        f"(implica un {c['_imp']:.0f}%). No hay ventaja: es una recomendación por probabilidad y no una apuesta de valor."
                        + (f" Solo {c['_n']} casa{'s' if c['_n'] > 1 else ''} la cotiza{'n' if c['_n'] > 1 else ''}, así que la estimación es menos fiable." if c["_low"] else ""))
    for c in picks:
        for x in ("_n", "_imp", "_low"): c.pop(x, None)
    return picks

def summary(e, fair, win, h, a):
    out = []
    ph, pa = fair.get(("h2h", h, None, None)), fair.get(("h2h", a, None, None))
    if ph and pa:
        mh, ma = mean(ph) * 100, mean(pa) * 100
        fav, pf = (h, mh) if mh >= ma else (a, ma)
        wp = win.get(("h2h", fav, None, None))
        out.append(f"Favorito del mercado: {fav}, con un {pf:.0f}% de probabilidad de ganar" + (f" (Winamax paga {wp:.2f})." if wp else "."))
        pts = sorted(o["point"] for b in e.get("bookmakers", []) for m in b.get("markets", []) if m["key"] == "spreads"
                     for o in m["outcomes"] if o["name"] == fav and "point" in o)
        if pts: out.append(f"Hándicap habitual: {fav} {('%+g' % pts[len(pts) // 2]).replace('.', ',')} ({len(pts)} casas).")
    tots = sorted(o["point"] for b in e.get("bookmakers", []) for m in b.get("markets", []) if m["key"] == "totals"
                  for o in m["outcomes"] if o["name"] == "Over" and "point" in o)
    if tots: out.append(f"El mercado espera unos {num(tots[len(tots) // 2])} puntos en total ({len(tots)} casas).")
    return out

def verdict(picks, win):
    if not win: return {"level": "pass", "text": "Winamax aún no ha publicado cuotas de este partido, así que no puedo medir ventajas. Te enseño lo más probable según otras casas, solo como referencia."}
    yes = [p for p in picks if p.get("v") == "yes"]; cau = [p for p in picks if p.get("v") == "caution"]
    if yes:
        b = yes[0]
        return {"level": "yes", "text": f"Hay {len(yes)} apuesta{'s' if len(yes) > 1 else ''} de alto valor. La mejor: «{b['selection']}» a {b['odds']:.2f} "
                f"(el mercado le da un {b['prob']:.0f}% y Winamax implica un {100 / b['odds']:.0f}%). Las de alto valor son las que entran en el registro."}
    if cau:
        b = cau[0]
        return {"level": "caution", "text": f"Hay algo de valor, pero la ventaja es pequeña: «{b['selection']}» a {b['odds']:.2f}. Con cautela. No entra en el registro."}
    return {"level": "pass", "text": "No hay ventaja clara frente al mercado, así que la app pasaría de este partido. Las recomendadas son las más probables, pero Winamax ya las paga a su precio justo o por debajo."}

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
    inj, leagues, errors, diag = injuries(), {}, 0, {}
    try:  # consultar la lista de deportes no gasta créditos
        known = [x["key"] for x in api("/sports", all="true")]
        for lg in LEAGUES:
            if LEAGUES[lg] not in known:
                alt = [k for k in known if "basketball" in k and lg[:5] in k]
                if alt: LEAGUES[lg] = alt[0]
    except Exception as e:
        print("  No se pudo listar deportes:", e)
    for lg, sport in LEAGUES.items():
        print(lg, sport)
        try:
            odds = {e["id"]: e for e in api(f"/sports/{sport}/odds", regions="eu", markets="h2h,spreads,totals", oddsFormat="decimal", dateFormat="iso")}
        except Exception as e:
            print("  Error al pedir cuotas:", e); errors += 1; odds = {}
        try:  # el calendario (sin cuotas) tampoco gasta créditos
            events = api(f"/sports/{sport}/events", dateFormat="iso")
        except Exception as e:
            print("  Sin calendario:", e); events = list(odds.values())
        events = sorted([e for e in events if 0 < (pdate(e["commence_time"]) - now).total_seconds() / 3600 <= HORIZON_H], key=lambda e: e["commence_time"])
        games, n_props, n_odds, n_win = [], 0, 0, 0
        for e in events:
            e = odds.get(e["id"], e)
            win, fair, best = {}, defaultdict(list), {}
            collect(e.get("bookmakers", []), win, fair, best)
            if lg == "nba" and e.get("bookmakers") and n_props < MAX_PROP_EVENTS:
                n_props += 1
                try:
                    pe = api(f"/sports/{sport}/events/{e['id']}/odds", regions="eu", markets=",".join(PROPS), oddsFormat="decimal", dateFormat="iso")
                    collect(pe.get("bookmakers", []), win, fair, best)
                except Exception as ex: print("  Sin props:", ex)
            h, a = e["home_team"], e["away_team"]
            bajas = bajas_text(inj, h, a) if lg == "nba" else ""
            picks = make_picks(win, fair, bajas, best)
            n_odds += bool(e.get("bookmakers")); n_win += bool(win)
            note = bajas
            if not win: note = (note + " " if note else "") + "Winamax aún no ha publicado cuotas de este partido."
            elif not any(not p.get("rec") for p in picks): note = (note + " " if note else "") + "Sin apuestas de valor; estas son las más probables."
            games.append({"id": e["id"], "time": e["commence_time"], "note": note.strip(), "home": team(h, lg), "away": team(a, lg), "picks": picks, "verdict": verdict(picks, win), "summary": summary(e, fair, win, h, a),
                          "inj": {"home": inj.get(nick(h), []) if lg == "nba" else [], "away": inj.get(nick(a), []) if lg == "nba" else []}})
            for p in picks:
                pid = f"{e['id']}|{p['k']}"
                if p.get("v") == "yes" and not any(l["id"] == pid for l in log):
                    log.append({"id": pid, "date": now.strftime("%Y-%m-%d"), "match": f"{nick(h)} – {nick(a)}", "pick": p["selection"],
                                "odds": p["odds"], "prob": p["prob"], "result": "pending", "league": lg, "ev": e["commence_time"], "home": h, "away": a, "k": p["k"]})
        leagues[lg] = games
        diag[lg] = {"partidos": len(games), "con_cuotas": n_odds, "con_winamax": n_win}
        print(f"  {len(games)} partidos")
    if errors == len(LEAGUES): sys.exit("No se pudo descargar ninguna liga; no toco los datos.")
    resolve(log, now)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"demo": False, "stake": 10, "min_edge": MIN_EDGE, "min_prob": MIN_PROB, "log_edge": LOG_EDGE, "log_prob": LOG_PROB, "updated": now.isoformat(), "diag": diag, "leagues": leagues, "log": log},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Listo:", OUT)

if __name__ == "__main__":
    main()
