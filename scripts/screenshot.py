#!/usr/bin/env python3
"""Takes the website's screenshot (assets/screenshot.jpg) from a computer
running Dazzle, by its remote control: four apps with something in them.

    scripts/screenshot.py --host 192.168.1.92 --code 408938

The computer needs (all on the same network as this one):

- the remote control on (Settings, Debug: or dazzle.remote=<code> on the
  kernel's command line), and its code;
- a 1920x1080 screen (the website's picture is that size);
- Text Editor, Chat and Globe installed.

It arranges, from the top left: Text Editor with a note about dazzle
camouflage (the note "Dazzle camouflage.txt" in the user's files, written
over each time), Chat in a room with a conversation (this script joins the
room as the other people in it, by Chat's protocol: see Chat's
src/protocol.zig), Globe, and Settings showing the board. Then it takes the
screenshot and saves it as a JPEG (with Pillow, if it is installed; or as
the PNG the computer gives, beside it).

The pointer is moved out of the way; any other windows are closed first
(asked to: an app with unsaved work may stay). Nothing else of the
computer's is changed.
"""

import argparse
import os
import random
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# --- What the apps show -------------------------------------------------------

NOTE_NAME = "Dazzle camouflage.txt"
NOTE = [
    "Dazzle camouflage",
    "",
    "In the First World War, ships were painted in bold stripes and clashing "
    "shapes of black, white, grey and blue. The aim was not to hide them, "
    "which is impossible on the open sea, but to confuse. A submarine "
    "commander looking through a periscope had seconds to judge a ship's "
    "speed, heading and range; broken lines made the bow hard to find and "
    "the course hard to read, and torpedoes missed.",
    "",
    "The idea is credited to the marine artist Norman Wilkinson, who "
    "persuaded the British Admiralty to try it in 1917. Thousands of ships "
    "were painted, each in its own pattern, designed on small wooden models "
    "and checked through a periscope in a studio at the Royal Academy.",
    "",
    "Whether it worked is still argued about, but it left its mark on art: "
    "the Vorticist Edward Wadsworth oversaw the painting of hundreds of ships.",
]

ROOM = "Ship spotting"
# (who, what they say): the people this script plays. The last line is
# typed on the computer itself, as its user.
CONVERSATION = [
    ("Ada", "Has anyone seen the dazzle ship at the docks?"),
    ("Grace", "The one with the zigzags? It looks like it's going three ways at once"),
    ("Alan", "That's the idea. You can't tell which end is the front through a periscope"),
    ("Ada", "Norman Wilkinson came up with it in 1917, painting on little wooden models first"),
    ("Grace", "I'm going to paint my bike like that"),
    ("Alan", "Then nobody will know which way you're going either"),
]
REPLY = "Count me in. Meet at the harbour at 3?"

# Where the windows go on the 1920x1080 screen (x, y, width, height), the
# dock along the bottom.
PLACES = {
    "dazzle-text-editor": (40, 40, 900, 470),
    "dazzle-chat": (980, 40, 900, 470),
    "dazzle-maps": (40, 550, 900, 440),
    "dazzle-settings": (980, 550, 900, 440),
}

# --- Chat's protocol (see Chat's src/protocol.zig) -----------------------------

DISCOVERY_PORT = 48100
MAGIC = b"DZCH"
VERSION = 1
HELLO, PEERS, MESSAGE, SYNC, PING, RENAME = 1, 2, 3, 4, 5, 6


def short_str(s):
    b = s.encode()
    return bytes([len(b)]) + b


def frame(kind, body):
    return struct.pack(">HB", len(body) + 1, kind) + body


class ChatPeer:
    """One person in a Chat room. Every one of them has the room's whole
    history (with messages from all of them), and gives it to whoever joins
    (the computer's Chat). The first announces the room, and tells those
    who join where the others are (so they connect to them too, as Chat's
    own do)."""

    def __init__(self, room, room_name, name, messages, members):
        self.room = room
        self.room_name = room_name
        self.node = random.getrandbits(63)
        self.name = name
        self.messages = messages  # (lamport, author, seq, name, text)
        self.members = members
        self.others = []  # (node, port): the other people here
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("", 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        self.udp = None
        self.stopped = False

    def datagram(self, kind):
        return (MAGIC + bytes([VERSION, ord(kind)]) + struct.pack(">Q", self.room)
                + short_str(self.room_name) + struct.pack(">QHB", self.node, self.port, self.members))

    def start(self, announce):
        if announce:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            threading.Thread(target=self.announce, daemon=True).start()
        threading.Thread(target=self.accept, daemon=True).start()

    def stop(self):
        self.stopped = True
        if self.udp:
            try:
                self.udp.sendto(self.datagram("L"), ("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass

    def announce(self):
        while not self.stopped:
            try:
                self.udp.sendto(self.datagram("A"), ("255.255.255.255", DISCOVERY_PORT))
            except OSError as e:
                print(f"chat: cannot announce the room: {e}", file=sys.stderr)
            time.sleep(1)

    def accept(self):
        while not self.stopped:
            conn, _ = self.server.accept()
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        buf = b""
        print(f"chat: {self.name} joined by {conn.getpeername()[0]}")
        try:
            # Hello first, then who else is here and what it has.
            conn.sendall(frame(HELLO, struct.pack(">Q", self.room) + short_str(self.room_name)
                               + struct.pack(">QH", self.node, self.port) + short_str(self.name)))
            # The others are where this is: the address the joiner reached.
            here = socket.inet_aton(conn.getsockname()[0])
            conn.sendall(frame(PEERS, bytes([len(self.others)])
                               + b"".join(struct.pack(">Q", n) + here + struct.pack(">H", p) for n, p in self.others)))
            have = {}
            for _, author, seq, _, _ in self.messages:
                have[author] = max(have.get(author, 1), seq + 1)
            conn.sendall(frame(SYNC, bytes([len(have)]) + b"".join(struct.pack(">QI", a, n) for a, n in have.items())))
            conn.settimeout(4)
            while not self.stopped:
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    conn.sendall(frame(PING, b""))
                    continue
                if not data:
                    return
                buf += data
                while len(buf) >= 2:
                    (n,) = struct.unpack(">H", buf[:2])
                    if len(buf) < 2 + n:
                        break
                    kind, body = buf[2], buf[3:2 + n]
                    buf = buf[2 + n:]
                    if kind == SYNC:
                        count = body[0]
                        theirs = {}
                        for i in range(count):
                            a, nxt = struct.unpack(">QI", body[1 + 12 * i:13 + 12 * i])
                            theirs[a] = nxt
                        for lamport, author, seq, name, text in self.messages:
                            if seq >= theirs.get(author, 1):
                                t = text.encode()
                                conn.sendall(frame(MESSAGE, struct.pack(">QQI", lamport, author, seq)
                                                   + short_str(name) + struct.pack(">H", len(t)) + t))
        except OSError:
            return


class ChatRoom:
    """The room: a `ChatPeer` for each person in the conversation."""

    def __init__(self, room_name, lines):
        room = random.getrandbits(63)
        messages = []
        authors = {}
        seqs = {}
        for lamport, (who, text) in enumerate(lines, start=1):
            author = authors.setdefault(who, random.getrandbits(63))
            seqs[author] = seqs.get(author, 0) + 1
            messages.append((lamport, author, seqs[author], who, text))
        self.people = [ChatPeer(room, room_name, who, messages, len(authors)) for who in authors]
        for p in self.people:
            p.others = [(q.node, q.port) for q in self.people if q is not p]

    def start(self):
        for i, p in enumerate(self.people):
            p.start(announce=i == 0)

    def stop(self):
        for p in self.people:
            p.stop()


# --- The remote control ----------------------------------------------------------

class Remote:
    def __init__(self, host, code):
        self.base = f"http://{host}:8080"
        self.code = code

    def get(self, path, timeout=30, **params):
        q = urllib.parse.urlencode({"code": self.code, **params}, quote_via=urllib.parse.quote)
        with urllib.request.urlopen(f"{self.base}{path}?{q}", timeout=timeout) as r:
            return r.read()

    def key(self, code, pressed=None):
        if pressed is None:
            self.get("/key", key=code)
        else:
            self.get("/key", key=code, pressed=1 if pressed else 0)

    def type(self, text):
        # In pieces; each is typed whole or not at all (503: the keys
        # typed before are still going in), so try again.
        for i in range(0, len(text), 40):
            for _ in range(100):
                try:
                    self.get("/type", text=text[i:i + 40])
                    break
                except urllib.error.HTTPError as e:
                    if e.code != 503:
                        raise
                    time.sleep(0.2)
            else:
                raise RuntimeError("the computer is too busy to type")

    def title(self, app):
        """The title of `app`'s window (the first in /status's list of
        windows, top first, whose size matches where it was put)."""
        x, y, w, h = PLACES[app]
        for line in self.get("/status").decode().splitlines():
            line = line.strip()
            if line.startswith('"') and f" at {x},{y} " in line:
                return line[1:line.index('"', 1)]
        return None

    def select_all(self):
        self.key(KEY_LEFTCTRL, True)
        self.key(KEY_A)
        self.key(KEY_LEFTCTRL, False)


KEY_ENTER = 28
KEY_LEFTCTRL = 29
KEY_A = 30
KEY_HOME = 102
KEY_DELETE = 111


def place(r, app):
    x, y, w, h = PLACES[app]
    r.get("/window", do="place", app=app, x=x, y=y, w=w, h=h)


def launch(r, app, wait=4):
    r.get("/launch", app=app)
    time.sleep(wait)
    place(r, app)
    time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True, help="the computer running Dazzle (its address)")
    ap.add_argument("--code", required=True, help="its remote control code")
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "screenshot.jpg"))
    args = ap.parse_args()
    r = Remote(args.host, args.code)

    chat = ChatRoom(ROOM, CONVERSATION)
    chat.start()

    # A clean desktop.
    for app in PLACES:
        try:
            r.get("/quit", app=app)
        except Exception:
            pass
    time.sleep(2)

    # Globe first (bottom left), as it is.
    launch(r, "dazzle-maps", wait=6)

    # Settings (bottom right), on the board's page.
    launch(r, "dazzle-settings")
    x, y, _, _ = PLACES["dazzle-settings"]
    # The tabs down the left: Board is the sixth.
    r.get("/click", x=x + 86, y=y + 338)
    time.sleep(1)

    # Chat (top right): in the room, which this script has announced.
    launch(r, "dazzle-chat", wait=6)
    x, y, w, h = PLACES["dazzle-chat"]
    # The room, first in the list.
    r.get("/click", x=x + 286, y=y + 235)
    # Time to meet everyone in it.
    time.sleep(10)
    r.type(REPLY)
    r.key(KEY_ENTER)
    time.sleep(1)

    # Text Editor (top left): the note, written over. Its start screen
    # makes a new file of the name typed; if there is one of that name
    # already, it stays there, and the note is opened from its list of
    # recent files.
    launch(r, "dazzle-text-editor")
    r.select_all()
    r.type(NOTE_NAME)
    r.key(KEY_ENTER)
    time.sleep(2)
    # Not made (there is one already): it is one of the recent files, the
    # first few tried in turn (Text Editor started again for each).
    x, y, w, _ = PLACES["dazzle-text-editor"]
    for row in range(5):
        if r.title("dazzle-text-editor") == NOTE_NAME:
            break
        r.get("/quit", app="dazzle-text-editor")
        time.sleep(2)
        launch(r, "dazzle-text-editor")
        r.get("/click", x=x + w // 2, y=y + 200 + 72 * row)
        time.sleep(2)
    title = r.title("dazzle-text-editor")
    if title != NOTE_NAME:
        sys.exit(f"Text Editor shows {title!r}, not the note: open {NOTE_NAME} in it once, and try again")
    r.select_all()
    r.key(KEY_DELETE)
    for i, line in enumerate(NOTE):
        if line:
            r.type(line)
        if i + 1 < len(NOTE):
            r.key(KEY_ENTER)
    # Back to the top, so the title shows.
    r.key(KEY_LEFTCTRL, True)
    r.key(KEY_HOME)
    r.key(KEY_LEFTCTRL, False)

    # The pointer out of the way, and the picture.
    r.get("/pointer", x=1919, y=540)
    time.sleep(2)
    png = r.get("/screenshot", timeout=60)
    chat.stop()
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(png)).convert("RGB").save(args.out, quality=90, optimize=True)
        print(f"saved {args.out}")
    except ImportError:
        out = os.path.splitext(args.out)[0] + ".png"
        with open(out, "wb") as f:
            f.write(png)
        print(f"saved {out} (no Pillow to make a JPEG)")


if __name__ == "__main__":
    main()
