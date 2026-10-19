#!/usr/bin/env python3
"""
op0p_catbridge.py - Pont CAT local pour le cluster OP0P (cluster.op0p.be)
==========================================================================

A quoi ca sert ?
-----------------
Un navigateur ne peut PAS piloter un port serie/COM: seul un programme qui
tourne sur VOTRE ordinateur le peut. Ce petit script (bibliotheque standard
Python uniquement, aucune dependance a installer) fait deux choses :

  1. Il sert de "miroir" local du site https://cluster.op0p.be : il recoit
     toutes les requetes que votre navigateur ferait normalement vers le
     site et les relaie telles quelles vers le vrai serveur, puis renvoie
     la reponse. Vu de votre navigateur, http://127.0.0.1:5005/ est donc
     IDENTIQUE au vrai site.
  2. Dans chaque page HTML renvoyee, il ajoute un petit indicateur
     (window.OP0P_CATBRIDGE = true) que le Javascript du site sait
     detecter. Quand ce drapeau est present, cliquer sur la frequence
     d'un spot envoie une requete a ce script (sur /catbridge/tune), qui la
     transmet a votre radio via rigctld (Hamlib).

C'est exactement le principe utilise par Holy Cluster (holycluster.iarc.org)
avec son "CAT server" local - voir https://github.com/iarc-il/HolyCluster.
On evite ainsi le blocage "contenu mixte" des navigateurs recents, qui
empechent de plus en plus une page HTTPS publique de contacter directement
votre http://127.0.0.1 (Private Network Access).

Hamlib (rigctld) sait piloter la quasi-totalite des transceivers du marche
(Icom, Yaesu, Kenwood, Elecraft, Ten-Tec, Flex, Elad, ...) : c'est pour ca
qu'il a ete choisi comme pont vers la radio, plutot qu'un backend limite a
une seule marque.

Mode graphique (recommande, pour tout le monde)
-------------------------------------------------
Sous Windows, le plus simple est de telecharger la copie .pyw (double-clic
direct, sans invite de commandes ni fenetre noire - voir cluster.op0p.be,
page CAT). Sinon, lancez simplement :

    python3 op0p_catbridge.py

(ou double-cliquez sur le fichier si Python est associe aux fichiers .py)
Une petite fenetre s'ouvre : choisissez la MARQUE puis le MODELE de votre
radio dans les listes deroulantes (elles viennent directement de Hamlib,
donc TOUTES les marques supportees par Hamlib apparaissent), choisissez le
port serie/COM (une liste de ports detectes est proposee, modifiable), puis
cliquez sur "Demarrer". Le script lance rigctld pour vous, demarre le pont,
et ouvre votre navigateur automatiquement. Vos choix sont memorises pour la
prochaine fois.

Piloter la radio depuis un telephone/tablette (meme reseau WiFi)
-------------------------------------------------------------------
Par defaut, le pont ne repond qu'a CET ordinateur (127.0.0.1) - c'est le
mode normal pour Firefox/Safari en local. Pour cliquer une frequence depuis
votre telephone, cochez "Accessible depuis le reseau local" dans la fenetre
(ou lancez en ligne de commande avec --lan), donnez-lui un code PIN, puis
demarrez : la fenetre affiche alors une adresse du style

    http://192.168.1.XX:5005/?pin=VOTRE_PIN

a ouvrir UNE FOIS dans le navigateur du telephone (il doit etre sur le meme
WiFi que ce PC). Un cookie garde ensuite l'acces sur cet appareil - plus
besoin de retaper le PIN. Sans PIN, n'importe quel appareil de votre reseau
WiFi/maison pourrait piloter la radio : a n'activer sans PIN que si vous
faites confiance a tout ce qui est connecte a ce reseau.
Le Bluetooth n'est pas utilisable pour ceci (il ne fournit pas de reseau IP
entre les deux appareils) - seul le WiFi (meme reseau que ce PC) fonctionne.

Pre-requis sur votre ordinateur pour ce mode : Python 3.8+ avec tkinter
(inclus par defaut sous Windows/Mac ; sous Debian/Ubuntu, si la fenetre ne
s'ouvre pas : `sudo apt install python3-tk`), et Hamlib installe (le
programme `rigctld` doit etre trouvable - voir plus bas selon votre OS).

Mode avance / ligne de commande (sans fenetre, ex: Raspberry Pi headless)
---------------------------------------------------------------------------
Si vous preferez tout faire a la main (ou si vous lancez ce script sans
ecran), passez n'importe quelle option en ligne de commande pour desactiver
la fenetre, par exemple :

    rigctld -m <numero_modele> -r /dev/ttyUSB0 -s 9600 &
    python3 op0p_catbridge.py --no-gui

Options (toutes facultatives) :
    --gui / --no-gui          force ou desactive la fenetre (par defaut :
                               fenetre si aucune autre option n'est donnee)
    --port PORT               port local du pont (defaut: 5005)
    --upstream URL            site cluster a relayer (defaut: https://cluster.op0p.be)
    --rigctld-host HOST       adresse de rigctld (defaut: 127.0.0.1)
    --rigctld-port PORT       port de rigctld (defaut: 4532, le defaut Hamlib)
    --lan                     ecoute sur le reseau local (0.0.0.0) au lieu de
                               ce PC seul (127.0.0.1) - pour un telephone/
                               tablette sur le meme WiFi (voir section dediee
                               plus haut)
    --pin PIN                 code PIN exige une fois par appareil (conseille
                               avec --lan)

Installer Hamlib (fournit rigctl et rigctld)
-----------------------------------------------
    Windows      : https://github.com/Hamlib/Hamlib/releases/latest (archive w32/w64)
    Debian/Ubuntu: sudo apt install libhamlib-utils
    Fedora       : sudo dnf install hamlib
    macOS        : brew install hamlib

Limite connue (volontaire, pour la fiabilite) : seule la FREQUENCE est
envoyee a la radio. Le mode (CW/SSB/FT8/...) n'est pas toujours fiable dans
les donnees du cluster, donc il reste a regler manuellement sur votre poste.

Licence : fourni tel quel pour les utilisateurs de cluster.op0p.be (ON6DP).
"""
import argparse
import glob
import http.cookies
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# En-tetes qui ne doivent jamais etre transmis tels quels d'un bout a
# l'autre d'un proxy HTTP (RFC 7230 section 6.1 - en-tetes "hop-by-hop").
HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    # On retire aussi accept-encoding : on prefere recevoir du HTML en clair
    # (non compresse) du vrai serveur, pour pouvoir y inserer notre petit
    # script sans avoir a decompresser/recompresser du gzip.
    "accept-encoding",
}

RIGCTLD_TIMEOUT = 3.0  # secondes
INJECT_SNIPPET = b"<script>window.OP0P_CATBRIDGE = true;</script></body>"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".op0p_catbridge.json")

# Quand ce script est lance en mode "sans console" (ex: double-clic sur une
# copie renommee en .pyw sous Windows, ouverte par pythonw.exe au lieu de
# python.exe), sys.stdout/sys.stderr valent None - il n'y a tout simplement
# aucune console a ecrire dedans. Sans cette protection, le moindre print()
# ou appel a sys.stderr.write() (voir log_message plus bas) planterait avec
# "AttributeError: 'NoneType' object has no attribute 'write'". On redirige
# donc vers un puits sans fond : aucun impact sur le mode graphique (qui
# affiche tout dans sa propre fenetre de toute facon), et le mode ligne de
# commande continue de fonctionner normalement partout ou une vraie console
# existe (stdout/stderr ne sont alors jamais None).
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


def rigctld_command(host, port, command):
    """Envoie une commande texte Hamlib ('F 14195000', 'f', ...) a rigctld
    et renvoie la ou les lignes de reponse. Ouvre une connexion TCP courte
    a chaque appel (rigctld supporte tres bien ca) pour ne jamais rester
    bloque sur une connexion morte entre deux clics."""
    with socket.create_connection((host, port), timeout=RIGCTLD_TIMEOUT) as sock:
        sock.sendall((command.strip() + "\n").encode("ascii"))
        sock.settimeout(RIGCTLD_TIMEOUT)
        data = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                # rigctld repond une ligne (+ "RPRT 0" en fin de commande
                # d'ecriture) ; on arrete des qu'on a recu quelque chose et
                # qu'il n'y a plus rien d'immediatement disponible.
                if b"\n" in data:
                    break
        except socket.timeout:
            pass
    return data.decode("ascii", errors="replace").strip()


class CatBridgeHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "op0p-catbridge/1.0"

    # ---- PIN (optionnel, utile surtout avec --lan: sans lui, n'importe
    # quel appareil sur le meme WiFi pourrait piloter la radio). Un premier
    # acces avec ?pin=XXXX pose un cookie longue duree ; tous les acces
    # suivants depuis le meme navigateur/appareil n'ont plus besoin de le
    # repeter (le site est rechargee via fetch() avec des chemins relatifs,
    # donc le cookie suit automatiquement). self.server.pin est None quand
    # aucun PIN n'est configure - comportement identique a avant dans ce cas.

    def _pin_cookie_ok(self):
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return False
        try:
            jar = http.cookies.SimpleCookie()
            jar.load(cookie_header)
        except Exception:
            return False
        return "op0p_pin" in jar and jar["op0p_pin"].value == self.server.pin

    def _pin_query_ok(self):
        query = urllib.parse.urlsplit(self.path).query
        supplied = urllib.parse.parse_qs(query).get("pin", [None])[0]
        return supplied == self.server.pin

    def _client_pin_valid(self):
        if not self.server.pin:
            return True
        return self._pin_cookie_ok() or self._pin_query_ok()

    def _maybe_set_pin_cookie(self):
        # IMPORTANT: gated on self._pin_ok (set by do_GET/do_POST/do_HEAD
        # from _client_pin_valid()), NOT just on a PIN being configured -
        # otherwise a request that FAILED pin validation would still get
        # handed the correct cookie value via _send_pin_required() below
        # (which calls _send_json() for /catbridge/* paths), handing out
        # the PIN to whoever asks for it.
        if self.server.pin and getattr(self, "_pin_ok", False):
            # Max-Age ~ 1 an ; SameSite=Lax suffit (meme site, requetes
            # same-origin uniquement, pas de contexte cross-site ici).
            self.send_header(
                "Set-Cookie",
                "op0p_pin=%s; Path=/; Max-Age=31536000; SameSite=Lax" % self.server.pin,
            )

    def _send_pin_required(self):
        if self.path.startswith("/catbridge/"):
            self._send_json(
                {"ok": False, "error": "PIN requis ou incorrect - voir /?pin=VOTRE_PIN"},
                status=403,
            )
            return
        host = self.headers.get("Host", "<adresse-de-ce-pc>:PORT")
        body = (
            "<!doctype html><html><body style='font-family:sans-serif;padding:2rem'>"
            "<h2>Pont CAT OP0P</h2>"
            "<p>PIN requis. Ouvrez cette adresse <strong>une seule fois</strong> "
            "sur cet appareil, PIN inclus :</p>"
            "<p><code>http://" + host + "/?pin=VOTRE_PIN</code></p>"
            "<p>Vous n'aurez plus besoin de le retaper ensuite sur cet appareil "
            "tant que vous ne videz pas les cookies du navigateur.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- endpoints locaux (jamais relayes vers le vrai site) ----

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self._maybe_set_pin_cookie()
        self.end_headers()
        self.wfile.write(body)

    def _handle_tune(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "JSON invalide"}, status=400)
            return
        freq_khz = payload.get("freq_khz")
        if freq_khz is None:
            self._send_json({"ok": False, "error": "champ 'freq_khz' manquant"}, status=400)
            return
        try:
            freq_hz = int(round(float(freq_khz) * 1000))
        except (TypeError, ValueError):
            self._send_json({"ok": False, "error": "freq_khz invalide"}, status=400)
            return
        try:
            reply = rigctld_command(self.server.rigctld_host, self.server.rigctld_port,
                                     "F %d" % freq_hz)
            ok = ("RPRT 0" in reply) or (reply == "")
            self._send_json({"ok": ok, "freq_hz": freq_hz, "rigctld_reply": reply})
        except OSError as e:
            self._send_json({"ok": False, "error": "rigctld injoignable: %s" % e}, status=502)

    def _handle_status(self):
        try:
            reply = rigctld_command(self.server.rigctld_host, self.server.rigctld_port, "f")
            freq_hz = int(reply.splitlines()[0]) if reply.splitlines() and reply.splitlines()[0].lstrip("-").isdigit() else None
            self._send_json({"ok": True, "freq_hz": freq_hz})
        except OSError as e:
            self._send_json({"ok": False, "error": "rigctld injoignable: %s" % e}, status=502)

    # ---- proxy generique vers le site cluster ----

    def _proxy(self, method):
        url = self.server.upstream + self.path
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else None

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                resp_headers = resp.getheaders()
                resp_body = resp.read()
        except urllib.error.HTTPError as e:
            status = e.code
            resp_headers = e.headers.items() if e.headers else []
            resp_body = e.read() or b""
        except urllib.error.URLError as e:
            self._send_json(
                {"ok": False, "error": "Impossible de contacter %s : %s" % (self.server.upstream, e)},
                status=502,
            )
            return

        content_type = ""
        for k, v in resp_headers:
            if k.lower() == "content-type":
                content_type = v
                break

        if "text/html" in content_type and b"</body>" in resp_body:
            resp_body = resp_body.replace(b"</body>", INJECT_SNIPPET, 1)

        self.send_response(status)
        for k, v in resp_headers:
            if k.lower() in HOP_BY_HOP_HEADERS or k.lower() == "content-length":
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self._maybe_set_pin_cookie()
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(resp_body)

    def do_GET(self):
        self._pin_ok = self._client_pin_valid()
        if not self._pin_ok:
            self._send_pin_required()
            return
        # Compare against the path only (no query string) - a request can
        # legitimately carry ?pin=... (first visit from a new device), which
        # must not stop /catbridge/status from matching.
        if urllib.parse.urlsplit(self.path).path == "/catbridge/status":
            self._handle_status()
        else:
            self._proxy("GET")

    def do_POST(self):
        self._pin_ok = self._client_pin_valid()
        if not self._pin_ok:
            self._send_pin_required()
            return
        if urllib.parse.urlsplit(self.path).path == "/catbridge/tune":
            self._handle_tune()
        else:
            self._proxy("POST")

    def do_HEAD(self):
        self._pin_ok = self._client_pin_valid()
        if not self._pin_ok:
            self._send_pin_required()
            return
        self._proxy("HEAD")

    def log_message(self, fmt, *args):
        sys.stderr.write("[op0p_catbridge] " + (fmt % args) + "\n")


class CatBridgeServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, upstream, rigctld_host, rigctld_port, pin=None):
        super().__init__(addr, CatBridgeHandler)
        self.upstream = upstream.rstrip("/")
        self.pin = (pin or "").strip() or None
        self.rigctld_host = rigctld_host
        self.rigctld_port = rigctld_port


# =====================================================================
# Aide "mode graphique" : decouverte des modeles Hamlib, des ports serie,
# et petite configuration persistante. Tout ceci est volontairement
# independant de tkinter (fonctions pures, testables sans fenetre) - seule
# run_gui() importe tkinter, et seulement au moment ou on en a besoin.
# =====================================================================

def find_rigctld_binary():
    """Cherche le programme rigctld dans le PATH (et quelques emplacements
    Windows usuels ou Hamlib s'installe parfois sans modifier le PATH)."""
    found = shutil.which("rigctld")
    if found:
        return found
    if sys.platform.startswith("win"):
        candidates = glob.glob(r"C:\Program Files*\hamlib*\bin\rigctld.exe") + \
            glob.glob(r"C:\hamlib*\bin\rigctld.exe")
        if candidates:
            return candidates[0]
    return None


def find_rigctl_binary():
    """Meme chose pour rigctl (utilise seulement pour lister les modeles)."""
    found = shutil.which("rigctl")
    if found:
        return found
    if sys.platform.startswith("win"):
        candidates = glob.glob(r"C:\Program Files*\hamlib*\bin\rigctl.exe") + \
            glob.glob(r"C:\hamlib*\bin\rigctl.exe")
        if candidates:
            return candidates[0]
    return None


def get_hamlib_version():
    """Renvoie une courte chaine decrivant la version de Hamlib installee
    (ex: "4.5.5"), ou None si elle n'a pas pu etre determinee. Sert juste a
    l'affichage dans le journal, pour qu'un utilisateur dont la liste de
    modeles semble incomplete (ex: un tout nouveau poste absent de la
    liste) comprenne tout de suite qu'il s'agit d'une vieille version de
    Hamlib a mettre a jour, plutot que d'un bug de ce script."""
    rigctl_bin = find_rigctl_binary()
    if not rigctl_bin:
        return None
    try:
        proc = subprocess.run([rigctl_bin, "--version"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    m = re.search(r"Hamlib\s+(\d+\.\d+(?:\.\d+)?)", proc.stdout)
    return m.group(1) if m else None


_RIGCTL_LIST_ROW = re.compile(r"^\s*(\d+)\s{2,}")


def list_hamlib_rigs():
    """Interroge `rigctl -l` (liste livree par VOTRE installation de Hamlib
    - donc toujours a jour, quelle que soit la version) et renvoie la liste
    des radios supportees sous la forme [{"id": 311, "mfg": "Yaesu",
    "model": "FT-847"}, ...]. Toutes les marques que Hamlib connait
    (Icom, Yaesu, Kenwood, Elecraft, Ten-Tec, Flex, Elad, ...) ressortent
    de la meme facon, sans liste a maintenir nous-memes.

    Renvoie (rigs, error) : error est None si tout s'est bien passe, sinon
    un message explicatif (binaire absent, erreur de lancement, ...).
    """
    rigctl_bin = find_rigctl_binary()
    if not rigctl_bin:
        return [], "Le programme 'rigctl' (fourni par Hamlib) est introuvable sur cet ordinateur."
    try:
        proc = subprocess.run([rigctl_bin, "-l"], capture_output=True, text=True, timeout=10)
    except Exception as e:
        return [], "Impossible de lancer rigctl -l : %s" % e

    rigs = []
    for line in proc.stdout.splitlines():
        if not _RIGCTL_LIST_ROW.match(line):
            continue  # ligne d'en-tete ou vide
        fields = re.split(r"\s{2,}", line.strip())
        # format attendu (varie legerement selon les versions de Hamlib) :
        # [id, mfg, model, version, status, macro(optionnel)]
        if len(fields) < 3:
            continue
        rig_id, mfg, model = fields[0], fields[1], fields[2]
        if not rig_id.isdigit():
            continue
        rigs.append({"id": int(rig_id), "mfg": mfg.strip(), "model": model.strip()})
    if not rigs:
        return [], "rigctl -l n'a renvoye aucun modele exploitable (sortie inattendue)."
    return rigs, None


def scan_serial_ports():
    """Liste best-effort des ports serie/COM probables - juste pour
    pre-remplir la liste deroulante, l'utilisateur peut toujours taper
    autre chose a la main. Aucune dependance externe (pas de pyserial)."""
    ports = []
    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "[System.IO.Ports.SerialPort]::getportnames()"],
                capture_output=True, text=True, timeout=5,
            )
            ports = [p.strip() for p in out.stdout.splitlines() if p.strip()]
        except Exception:
            ports = []
    elif sys.platform == "darwin":
        ports = sorted(glob.glob("/dev/tty.*") + glob.glob("/dev/cu.*"))
    else:  # Linux et assimiles
        ports = sorted(
            glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") +
            glob.glob("/dev/serial/by-id/*")
        )
    return ports


def detect_lan_ip():
    """Best-effort: l'adresse IP de CET ordinateur sur le reseau local (celle
    qu'un telephone sur le meme WiFi utiliserait pour le joindre). N'envoie
    aucun trafic reseau - c'est juste l'OS qui indique quelle interface/IP
    locale il choisirait pour atteindre une adresse externe ; le socket UDP
    n'est jamais "connecte" au sens reseau (UDP est sans connexion), aucun
    paquet ne part reellement vers 8.8.8.8. Renvoie None si indetectable
    (ex: pas de reseau) - l'appelant retombe alors sur un message generique."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass  # la config est un simple confort, jamais bloquant


def wait_tcp_open(host, port, timeout_total=5.0):
    """Attend qu'une connexion TCP soit possible (rigctld pret a repondre),
    jusqu'a timeout_total secondes. Renvoie True/False."""
    deadline = time.time() + timeout_total
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


# =====================================================================
# Mode graphique
# =====================================================================

def run_gui(default_bridge_port, default_upstream, default_rigctld_host, default_rigctld_port):
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext

    root = tk.Tk()  # leve TclError ici si aucun affichage disponible
    root.title("Pont CAT OP0P - cluster.op0p.be")
    root.geometry("560x540")

    state = {
        "rigctld_proc": None,
        "bridge_server": None,
        "rigs": [],
        "rigs_by_mfg": {},
    }
    cfg = load_config()

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="1. Marque de votre radio :").grid(row=0, column=0, sticky="w", pady=2)
    mfg_var = tk.StringVar(value=cfg.get("mfg", ""))
    mfg_combo = ttk.Combobox(frm, textvariable=mfg_var, state="readonly", width=40)
    mfg_combo.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="2. Modele :").grid(row=1, column=0, sticky="w", pady=2)
    model_var = tk.StringVar(value=cfg.get("model_label", ""))
    model_combo = ttk.Combobox(frm, textvariable=model_var, state="readonly", width=40)
    model_combo.grid(row=1, column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="   (ou numero de modele Hamlib manuel :)").grid(row=2, column=0, sticky="w")
    manual_id_var = tk.StringVar(value="")
    ttk.Entry(frm, textvariable=manual_id_var, width=10).grid(row=2, column=1, sticky="w")

    ttk.Label(frm, text="3. Port serie / COM :").grid(row=3, column=0, sticky="w", pady=2)
    port_var = tk.StringVar(value=cfg.get("port", ""))
    port_combo = ttk.Combobox(frm, textvariable=port_var, width=40)
    port_combo.grid(row=3, column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="4. Vitesse (bauds) :").grid(row=4, column=0, sticky="w", pady=2)
    baud_var = tk.StringVar(value=str(cfg.get("baud", 9600)))
    baud_combo = ttk.Combobox(frm, textvariable=baud_var, width=40,
                               values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
    baud_combo.grid(row=4, column=1, sticky="ew", pady=2)

    frm.columnconfigure(1, weight=1)

    # 5. Reseau local : expose le pont a tout le WiFi/reseau maison (pas
    # seulement ce PC), pour pouvoir cliquer une frequence depuis un
    # telephone/tablette connecte au meme reseau. Desactive par defaut :
    # sans ca, le pont ne repond qu'a 127.0.0.1 (ce PC uniquement), comme
    # avant - aucun changement de comportement pour qui ne coche pas la case.
    lan_var = tk.BooleanVar(value=bool(cfg.get("lan", False)))
    ttk.Checkbutton(
        frm, text="5. Accessible depuis le reseau local (telephone, tablette...)",
        variable=lan_var,
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

    ttk.Label(
        frm, text="   Code PIN (recommande si la case ci-dessus est cochee) :"
    ).grid(row=6, column=0, sticky="w", pady=(0, 2))
    pin_var = tk.StringVar(value=cfg.get("pin", ""))
    ttk.Entry(frm, textvariable=pin_var, width=16).grid(row=6, column=1, sticky="w", pady=(0, 2))

    status_var = tk.StringVar(value="Pret.")
    status_lbl = ttk.Label(frm, textvariable=status_var, foreground="#444")
    status_lbl.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 2))

    log_box = scrolledtext.ScrolledText(frm, height=14, state="disabled", font=("Courier", 9))
    log_box.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(4, 8))
    frm.rowconfigure(9, weight=1)

    def log(msg):
        def _do():
            log_box.configure(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")
        root.after(0, _do)

    def set_status(msg, color="#444"):
        status_var.set(msg)
        status_lbl.configure(foreground=color)

    def populate_rigs():
        rigs, error = list_hamlib_rigs()
        if error:
            log("Attention : " + error)
            log("Vous pouvez quand meme saisir un numero de modele Hamlib a la main ci-dessus.")
            return
        state["rigs"] = rigs
        by_mfg = {}
        for r in rigs:
            by_mfg.setdefault(r["mfg"], []).append(r)
        state["rigs_by_mfg"] = by_mfg
        hamlib_version = get_hamlib_version()

        def _apply():
            mfg_combo["values"] = sorted(by_mfg.keys(), key=str.upper)
            if mfg_var.get() in by_mfg:
                update_models()
            if hamlib_version:
                log("%d modeles Hamlib charges (%d marques) - Hamlib version %s."
                    % (len(rigs), len(by_mfg), hamlib_version))
                log("(Si votre radio est tres recente et absente de la liste : "
                    "mettez Hamlib a jour - github.com/Hamlib/Hamlib/releases/latest)")
            else:
                log("%d modeles Hamlib charges (%d marques)." % (len(rigs), len(by_mfg)))
        root.after(0, _apply)

    def update_models(*_args):
        mfg = mfg_var.get()
        # Sorted alphabetically (case-insensitive) by model name, so users can
        # find their exact radio quickly instead of scrolling through Hamlib's
        # internal ordering (by model id, unrelated to the model name).
        rigs = sorted(state["rigs_by_mfg"].get(mfg, []), key=lambda r: r["model"].upper())
        labels = ["%s (#%d)" % (r["model"], r["id"]) for r in rigs]
        model_combo["values"] = labels
        if cfg.get("mfg") == mfg and cfg.get("model_label") in labels:
            # Reprend le modele choisi la derniere fois pour cette marque.
            model_var.set(cfg.get("model_label"))
        else:
            # Ne jamais pre-selectionner un modele au hasard (ex: le premier
            # par ordre alphabetique) : l'utilisateur doit choisir SON poste
            # explicitement, sinon il risque de demarrer sans s'en rendre
            # compte avec un mauvais modele (symptome : "rien ne fonctionne").
            model_var.set("")

    mfg_combo.bind("<<ComboboxSelected>>", update_models)

    def populate_ports():
        ports = scan_serial_ports()

        def _apply():
            port_combo["values"] = ports
            if not port_var.get() and ports:
                port_var.set(ports[0])
            if ports:
                log("Ports detectes : " + ", ".join(ports))
            else:
                log("Aucun port detecte automatiquement - saisissez-le a la main (ex: COM3 ou /dev/ttyUSB0).")
        root.after(0, _apply)

    threading.Thread(target=populate_rigs, daemon=True).start()
    threading.Thread(target=populate_ports, daemon=True).start()

    def resolve_model_id():
        manual = manual_id_var.get().strip()
        if manual:
            if not manual.isdigit():
                raise ValueError("Le numero de modele manuel doit etre un nombre.")
            return int(manual)
        mfg = mfg_var.get()
        label = model_var.get()
        for r in state["rigs_by_mfg"].get(mfg, []):
            if "%s (#%d)" % (r["model"], r["id"]) == label:
                return r["id"]
        raise ValueError("Choisissez une marque et un modele (ou un numero manuel).")

    def on_start():
        try:
            model_id = resolve_model_id()
        except ValueError as e:
            messagebox.showerror("Pont CAT OP0P", str(e))
            return
        port = port_var.get().strip()
        if not port:
            messagebox.showerror("Pont CAT OP0P", "Indiquez le port serie/COM de votre radio.")
            return
        try:
            baud = int(baud_var.get().strip())
        except ValueError:
            messagebox.showerror("Pont CAT OP0P", "La vitesse (bauds) doit etre un nombre.")
            return

        lan = lan_var.get()
        pin = pin_var.get().strip()
        if lan and not pin:
            if not messagebox.askyesno(
                "Pont CAT OP0P",
                "Reseau local active sans code PIN : n'importe quel appareil connecte "
                "a votre WiFi pourrait piloter la radio (changer la frequence).\n\n"
                "Continuer sans PIN ?",
            ):
                return

        save_config({
            "mfg": mfg_var.get(), "model_label": model_var.get(), "port": port, "baud": baud,
            "lan": lan, "pin": pin,
        })

        rigctld_bin = find_rigctld_binary()
        if not rigctld_bin:
            messagebox.showerror(
                "Pont CAT OP0P",
                "Le programme 'rigctld' (fourni par Hamlib) est introuvable.\n\n"
                "Installez Hamlib puis reessayez :\n"
                "  Windows : https://github.com/Hamlib/Hamlib/releases/latest\n"
                "  Debian/Ubuntu : sudo apt install libhamlib-utils\n"
                "  Fedora : sudo dnf install hamlib\n"
                "  macOS : brew install hamlib",
            )
            return

        start_btn.configure(state="disabled")
        set_status("Demarrage de rigctld...", "#b8860b")
        log("Lancement : %s -m %d -r %s -s %d" % (rigctld_bin, model_id, port, baud))

        try:
            proc = subprocess.Popen(
                [rigctld_bin, "-m", str(model_id), "-r", port, "-s", str(baud)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror("Pont CAT OP0P", "Impossible de lancer rigctld : %s" % e)
            start_btn.configure(state="normal")
            set_status("Echec.", "#b00020")
            return
        state["rigctld_proc"] = proc

        def read_rigctld_output():
            if proc.stdout:
                for line in proc.stdout:
                    log("[rigctld] " + line.rstrip())
        threading.Thread(target=read_rigctld_output, daemon=True).start()

        def finish_start():
            if proc.poll() is not None:
                log("rigctld s'est arrete immediatement (code %s) - verifiez le port et le modele choisis."
                    % proc.returncode)
                set_status("Echec : rigctld ne demarre pas.", "#b00020")
                start_btn.configure(state="normal")
                return
            if not wait_tcp_open(default_rigctld_host, default_rigctld_port, timeout_total=5.0):
                log("rigctld ne repond pas sur %s:%d apres 5s." % (default_rigctld_host, default_rigctld_port))
                set_status("Echec : rigctld ne repond pas.", "#b00020")
                start_btn.configure(state="normal")
                return

            bind_host = "0.0.0.0" if lan else "127.0.0.1"
            try:
                server = CatBridgeServer(
                    (bind_host, default_bridge_port), default_upstream,
                    default_rigctld_host, default_rigctld_port, pin=pin,
                )
            except OSError as e:
                log("Impossible de demarrer le pont local : %s" % e)
                set_status("Echec : port local %d deja utilise ?" % default_bridge_port, "#b00020")
                start_btn.configure(state="normal")
                return
            state["bridge_server"] = server
            threading.Thread(target=server.serve_forever, daemon=True).start()

            import webbrowser
            # On ouvre toujours 127.0.0.1 sur CE PC (fonctionne que --lan
            # soit actif ou non, puisque 0.0.0.0 accepte aussi les connexions
            # locales) ; l'adresse reseau local (pour le telephone) est
            # calculee et affichee separement ci-dessous. Si un PIN est
            # configure, on l'inclut directement ici - sinon l'onglet qui
            # s'ouvre tout seul affiche la page "PIN requis" au lieu du
            # cluster, ce qui donne l'impression que quelque chose est casse.
            local_url = "http://127.0.0.1:%d/" % default_bridge_port
            if pin:
                local_url += "?pin=" + pin
            log("Pont pret - ouverture de " + local_url + " sur cet ordinateur.")
            webbrowser.open(local_url)

            if lan:
                lan_ip = detect_lan_ip()
                pin_suffix = ("?pin=" + pin) if pin else ""
                if lan_ip:
                    phone_url = "http://%s:%d/%s" % (lan_ip, default_bridge_port, pin_suffix)
                    log("Depuis votre telephone/tablette (meme reseau WiFi) : " + phone_url)
                    if pin:
                        log("(le PIN n'est a saisir qu'une fois sur cet appareil - garde en memoire ensuite)")
                    set_status("Connecte - radio prete. Telephone : " + phone_url, "#0a7d28")
                    # Une fenetre qui saute aux yeux, en plus de la ligne dans
                    # le journal (facile a manquer) - c'est l'adresse a taper
                    # sur le telephone, donc elle doit etre impossible a
                    # rater. messagebox doit s'executer sur le thread
                    # principal de Tk (comme log()), d'ou le root.after(0, ..).
                    root.after(0, lambda: messagebox.showinfo(
                        "Pont CAT OP0P - acces telephone/tablette",
                        "Depuis votre telephone ou tablette, connecte au MEME reseau WiFi "
                        "que cet ordinateur, ouvrez cette adresse UNE FOIS dans le navigateur :\n\n"
                        + phone_url
                        + "\n\nVous n'aurez plus besoin de la retaper ensuite sur cet appareil.",
                    ))
                else:
                    log("Reseau local active mais impossible de determiner l'adresse IP de ce PC "
                        "automatiquement - regardez dans vos parametres reseau Windows (ipconfig).")
                    set_status("Connecte - radio prete (reseau local actif, port %d)" % default_bridge_port,
                               "#0a7d28")
            else:
                set_status("Connecte - radio prete (" + local_url + ")", "#0a7d28")
            stop_btn.configure(state="normal")

        threading.Thread(target=finish_start, daemon=True).start()

    def on_stop():
        server = state.get("bridge_server")
        if server:
            server.shutdown()
            server.server_close()
            state["bridge_server"] = None
        proc = state.get("rigctld_proc")
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        state["rigctld_proc"] = None
        set_status("Arrete.", "#444")
        log("Pont CAT arrete.")
        start_btn.configure(state="normal")
        stop_btn.configure(state="disabled")

    btn_frame = ttk.Frame(frm)
    btn_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 4))
    start_btn = ttk.Button(btn_frame, text="Demarrer", command=on_start)
    start_btn.pack(side="left")
    stop_btn = ttk.Button(btn_frame, text="Arreter", command=on_stop, state="disabled")
    stop_btn.pack(side="left", padx=(8, 0))

    def on_close():
        on_stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    log("Bienvenue. Choisissez votre radio et son port, puis cliquez sur Demarrer.")
    log("(Hamlib/rigctld sera lance automatiquement pour vous.)")
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Pont CAT local pour cluster.op0p.be")
    parser.add_argument("--gui", action="store_true", help="force l'ouverture de la fenetre")
    parser.add_argument("--no-gui", action="store_true", help="desactive la fenetre (mode ligne de commande)")
    parser.add_argument("--port", type=int, default=5005, help="port local du pont (defaut: 5005)")
    parser.add_argument("--upstream", default="https://cluster.op0p.be",
                         help="site cluster a relayer (defaut: https://cluster.op0p.be)")
    parser.add_argument("--rigctld-host", default="127.0.0.1", help="adresse de rigctld (defaut: 127.0.0.1)")
    parser.add_argument("--rigctld-port", type=int, default=4532, help="port de rigctld (defaut: 4532)")
    parser.add_argument("--lan", action="store_true",
                         help="ecoute sur le reseau local (0.0.0.0) au lieu de ce PC uniquement (127.0.0.1) - "
                              "necessaire pour piloter la radio depuis un telephone/tablette sur le meme WiFi")
    parser.add_argument("--pin", default=None,
                         help="code PIN optionnel exige en ?pin=... la premiere fois depuis chaque appareil "
                              "(fortement conseille avec --lan)")
    args = parser.parse_args()

    want_gui = args.gui or (not args.no_gui and len(sys.argv) == 1)

    if want_gui:
        try:
            run_gui(args.port, args.upstream, args.rigctld_host, args.rigctld_port)
            return
        except Exception as e:
            print("Interface graphique indisponible (%s) - bascule en mode ligne de commande." % e)
            print("(pas d'ecran, ou tkinter manquant - sous Debian/Ubuntu : sudo apt install python3-tk)")
            print("Dans ce mode, lancez rigctld vous-meme avant de relancer ce script.")

    bind_host = "0.0.0.0" if args.lan else "127.0.0.1"
    server = CatBridgeServer((bind_host, args.port), args.upstream, args.rigctld_host, args.rigctld_port,
                              pin=args.pin)

    print("=" * 70)
    print(" Pont CAT OP0P pret (mode ligne de commande).")
    print(" Ouvrez cette adresse dans votre navigateur (pas cluster.op0p.be) :")
    print("   http://127.0.0.1:%d/" % args.port)
    if args.lan:
        lan_ip = detect_lan_ip()
        pin_suffix = ("?pin=" + args.pin) if args.pin else ""
        if lan_ip:
            print(" Depuis un telephone/tablette sur le meme reseau WiFi :")
            print("   http://%s:%d/%s" % (lan_ip, args.port, pin_suffix))
        else:
            print(" --lan actif mais IP locale indetectable automatiquement - verifiez avec "
                  "`ip addr` / `ifconfig` / `ipconfig`.")
        if not args.pin:
            print(" ATTENTION: --lan sans --pin - n'importe quel appareil sur ce WiFi peut piloter la radio.")
    print()
    print(" Verification : rigctld doit deja tourner sur %s:%d" %
          (args.rigctld_host, args.rigctld_port))
    print(" (sinon : voir les instructions sur cluster.op0p.be, page CAT)")
    print(" Ctrl+C pour arreter.")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret du pont CAT.")
        server.shutdown()


if __name__ == "__main__":
    main()
