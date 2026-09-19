#!/usr/bin/env python3
"""Сетевая гонка Сапёра по Wi-Fi (TCP, JSON-строки).

Один игрок — хост (сервер), остальные подключаются по его IP.
Карта у всех одинаковая: хост раздаёт seed + уровень сложности.
Кто раньше открыл все клетки — выиграл. Взрыв = поражение (DNF).

Протокол (каждая строка — один JSON):
  C->H {"t":"join","name":...}
  H->C {"t":"welcome","seed":N,"diff":"normal","players":[...]}
      | {"t":"error","msg":...}
  H->* {"t":"players","players":[...]}      — состав лобби
  H->* {"t":"start"}                        — старт гонки
  C->H {"t":"progress","opened":N,"total":M}
  C->H {"t":"finish","elapsed":SEC}         — SEC<0 значит DNF (взрыв)
  H->* {"t":"table","rows":[{name,opened,total,finished,elapsed}]}
  H->* {"t":"result","places":[{name,elapsed}]}  — когда все финишировали
  H->* {"t":"bye"}                          — хост закрыл игру
"""

import json
import queue
import socket
import threading

PORT = 50007
BUFSIZE = 65536


def get_lan_ip():
    """Локальный IP в Wi-Fi сети (показать игрокам для подключения)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _send(conn, obj):
    conn.sendall((json.dumps(obj) + "\n").encode("utf-8"))


class _Reader(threading.Thread):
    """Читает JSON-строки из сокета, кладёт dict в очередь. daemon."""

    def __init__(self, conn, out_queue, on_close):
        super().__init__(daemon=True)
        self.conn = conn
        self.out = out_queue
        self.on_close = on_close
        try:
            self.conn.settimeout(0.5)
        except Exception:
            pass

    def run(self):
        buf = b""
        try:
            while True:
                try:
                    chunk = self.conn.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        self.out.put(json.loads(line.decode("utf-8")))
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            try:
                self.on_close()
            except Exception:
                pass


class RaceHost:
    """Хост гонки. События для главного потока — в self.events (queue.Queue)."""

    def __init__(self, name, diff_key):
        import random as _random
        self.name = name
        self.diff = diff_key
        self.seed = _random.randint(1, 999999999)
        self.events = queue.Queue()
        self.players = {}  # name -> {conn, opened, total, finished, elapsed}
        self.started = False
        self._lock = threading.Lock()
        self._server = None
        self._alive = True
        self.players[name] = {"conn": None, "opened": 0, "total": 0,
                              "finished": False, "elapsed": -1}

    # -- управление из главного потока --
    def serve(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("0.0.0.0", PORT))
        self._server.listen(8)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def start_race(self):
        with self._lock:
            self.started = True
        self._broadcast({"t": "start"})

    def report_self(self, opened, total, finished=False, elapsed=-1):
        with self._lock:
            me = self.players.get(self.name)
            if me is None:
                return
            me["opened"] = opened
            me["total"] = total
            if finished and not me["finished"]:
                me["finished"] = True
                me["elapsed"] = elapsed
        self._broadcast_table()
        self._maybe_result()

    def stop(self):
        self._alive = False
        try:
            self._broadcast({"t": "bye"})
        except Exception:
            pass
        with self._lock:
            conns = [p["conn"] for p in self.players.values() if p["conn"]]
        for c in conns:
            try:
                c.close()
            except Exception:
                pass
        try:
            if self._server:
                self._server.close()
        except Exception:
            pass

    # -- внутреннее --
    def _accept_loop(self):
        while self._alive:
            try:
                self._server.settimeout(0.5)
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=self._handshake, args=(conn,), daemon=True).start()

    def _handshake(self, conn):
        try:
            conn.settimeout(8)
            f = conn.makefile("r", encoding="utf-8")
            line = f.readline()
            msg = json.loads(line)
            name = str(msg.get("name", ""))[:12] or "Player"
            with self._lock:
                if self.started:
                    _send(conn, {"t": "error", "msg": "race already started"})
                    conn.close()
                    return
                if name in self.players:
                    _send(conn, {"t": "error", "msg": "name taken"})
                    conn.close()
                    return
                self.players[name] = {"conn": conn, "opened": 0, "total": 0,
                                      "finished": False, "elapsed": -1}
                _send(conn, {"t": "welcome", "seed": self.seed,
                             "diff": self.diff, "players": sorted(self.players)})
            self.events.put({"t": "peer_joined", "name": name})
            self._broadcast_players()
            threading.Thread(target=self._client_reader, args=(name, conn),
                             daemon=True).start()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def _client_reader(self, name, conn):
        """Поток чтения одного клиента (запускается из _handshake)."""
        buf = b""
        conn.settimeout(0.5)
        try:
            while self._alive:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self._on_client_msg(name, line)
        except Exception:
            pass
        finally:
            self._drop(name)

    def _on_client_msg(self, name, line):
        try:
            msg = json.loads(line.decode("utf-8"))
        except Exception:
            return
        t = msg.get("t")
        with self._lock:
            p = self.players.get(name)
            if p is None:
                return
            if t == "progress":
                p["opened"] = int(msg.get("opened", 0))
                p["total"] = int(msg.get("total", 0))
            elif t == "finish":
                if not p["finished"]:
                    p["finished"] = True
                    p["elapsed"] = float(msg.get("elapsed", -1))
                    self.events.put({"t": "peer_finished", "name": name})
            else:
                return
        if t == "progress":
            self._broadcast_table()
        else:
            self._broadcast_table()
            self._maybe_result()

    def _drop(self, name):
        with self._lock:
            p = self.players.pop(name, None)
        if p is not None:
            try:
                if p["conn"]:
                    p["conn"].close()
            except Exception:
                pass
            self.events.put({"t": "peer_left", "name": name})
            self._broadcast_players()
            self._broadcast_table()
            self._maybe_result()

    def _names(self):
        return sorted(self.players)

    def _table_rows(self):
        return [{"name": n, "opened": p["opened"], "total": p["total"],
                 "finished": p["finished"], "elapsed": p["elapsed"]}
                for n, p in sorted(self.players.items())]

    def _broadcast(self, obj):
        with self._lock:
            conns = [p["conn"] for p in self.players.values() if p["conn"]]
        dead = []
        for c in conns:
            try:
                _send(c, obj)
            except Exception:
                dead.append(c)
        for c in dead:
            try:
                c.close()
            except Exception:
                pass

    def _broadcast_players(self):
        if self._alive:
            self._broadcast({"t": "players", "players": self._names()})

    def _broadcast_table(self):
        if self._alive:
            with self._lock:
                rows = self._table_rows()
            self._broadcast({"t": "table", "rows": rows})
            self.events.put({"t": "table", "rows": rows})

    def _maybe_result(self):
        with self._lock:
            if not self.players:
                return
            if any(not p["finished"] for p in self.players.values()):
                return
            places = [{"name": n, "elapsed": p["elapsed"]}
                      for n, p in sorted(self.players.items())
                      if p["elapsed"] is not None and p["elapsed"] >= 0]
            places.sort(key=lambda r: r["elapsed"])
            for n, p in sorted(self.players.items()):
                if p["elapsed"] is None or p["elapsed"] < 0:
                    places.append({"name": n, "elapsed": -1})
        self._broadcast({"t": "result", "places": places})
        self.events.put({"t": "result", "places": places})


class RaceClient:
    """Клиент гонки. События для главного потока — в self.events."""

    def __init__(self, host_ip, name):
        self.host_ip = host_ip
        self.name = name
        self.events = queue.Queue()
        self._conn = None
        self._alive = True

    def connect(self):
        threading.Thread(target=self._run, daemon=True).start()

    def send_progress(self, opened, total):
        self._try_send({"t": "progress", "opened": opened, "total": total})

    def send_finish(self, elapsed):
        self._try_send({"t": "finish", "elapsed": elapsed})

    def stop(self):
        self._alive = False
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass

    def _try_send(self, obj):
        try:
            if self._conn:
                _send(self._conn, obj)
        except Exception:
            pass

    def _run(self):
        try:
            conn = socket.create_connection((self.host_ip, PORT), timeout=8)
        except Exception:
            self.events.put({"t": "conn_fail"})
            return
        self._conn = conn
        try:
            _send(conn, {"t": "join", "name": self.name})
            f = conn.makefile("r", encoding="utf-8")
            line = f.readline()
            if not line:
                self.events.put({"t": "conn_fail"})
                return
            hello = json.loads(line)
            if hello.get("t") == "error":
                self.events.put({"t": "join_error", "msg": hello.get("msg", "?")})
                conn.close()
                return
            if hello.get("t") != "welcome":
                self.events.put({"t": "conn_fail"})
                conn.close()
                return
            self.events.put(hello)  # welcome с seed/diff/players
            conn.settimeout(0.5)
            buf = b""
            while self._alive:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line_b, buf = buf.split(b"\n", 1)
                    if line_b.strip():
                        try:
                            self.events.put(json.loads(line_b.decode("utf-8")))
                        except Exception:
                            pass
        except Exception:
            pass
        finally:
            self.events.put({"t": "disconnected"})
            try:
                conn.close()
            except Exception:
                pass

