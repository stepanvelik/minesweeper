"""Небольшой TCP-протокол для сетевых крестиков-ноликов в локальной сети."""
import json
import queue
import socket
import threading

PORT = 50008


def lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        value = sock.getsockname()[0]
        sock.close()
        return value
    except OSError:
        return "127.0.0.1"


def _send(conn, payload):
    conn.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


class Host:
    """Хост принимает ровно одного соперника; события забирает pygame-поток."""
    def __init__(self, name, size=3):
        self.name, self.events, self.conn = name, queue.Queue(), None
        self.size = size
        self.server, self.alive = None, True

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", PORT))
        self.server.listen(1)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        try:
            self.server.settimeout(12)
            conn, _ = self.server.accept()
            line = conn.makefile("r", encoding="utf-8").readline()
            hello = json.loads(line)
            if hello.get("t") != "join":
                raise ValueError("bad handshake")
            self.conn = conn
            opponent = str(hello.get("name", "Player"))[:16] or "Player"
            _send(conn, {"t": "welcome", "host": self.name, "size": self.size})
            self.events.put({"t": "joined", "name": opponent, "size": self.size})
            self._read(conn)
        except Exception:
            if self.alive:
                self.events.put({"t": "error", "msg": "Player could not connect"})

    def _read(self, conn):
        try:
            file = conn.makefile("r", encoding="utf-8")
            while self.alive:
                line = file.readline()
                if not line:
                    break
                self.events.put(json.loads(line))
        except Exception:
            pass
        finally:
            self.events.put({"t": "left"})

    def send(self, payload):
        if self.conn:
            try: _send(self.conn, payload)
            except OSError: self.events.put({"t": "left"})

    def stop(self):
        self.alive = False
        for item in (self.conn, self.server):
            try:
                if item: item.close()
            except OSError: pass


class Client:
    def __init__(self, ip, name, size=3):
        self.ip, self.name, self.events, self.conn = ip, name, queue.Queue(), None
        self.size = size
        self.alive = True

    def start(self):
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        try:
            self.conn = socket.create_connection((self.ip, PORT), timeout=6)
            _send(self.conn, {"t": "join", "name": self.name})
            file = self.conn.makefile("r", encoding="utf-8")
            hello = json.loads(file.readline())
            if hello.get("t") != "welcome": raise ValueError("no welcome")
            self.events.put(hello)
            while self.alive:
                line = file.readline()
                if not line: break
                self.events.put(json.loads(line))
        except Exception:
            self.events.put({"t": "error", "msg": "Cannot reach host"})
        finally:
            self.events.put({"t": "left"})

    def send(self, payload):
        if self.conn:
            try: _send(self.conn, payload)
            except OSError: self.events.put({"t": "left"})

    def stop(self):
        self.alive = False
        try:
            if self.conn: self.conn.close()
        except OSError: pass
