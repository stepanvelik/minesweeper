"""Встроенный экран крестиков-ноликов для главного pygame-цикла."""
import queue
import random
import time

import pygame
import tictactoe_netplay as network


def win_length(size):
    return 3 if size == 3 else 4


def winner(board, size):
    need = win_length(size)
    for row in range(size):
        for col in range(size):
            mark = board[row * size + col]
            if not mark:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(row + dr * step, col + dc * step) for step in range(need)]
                if all(0 <= r < size and 0 <= c < size and board[r * size + c] == mark
                       for r, c in cells):
                    return mark, tuple(r * size + c for r, c in cells)
    return ("DRAW", ()) if all(board) else (None, ())


class TicTacToeScreen:
    """Меню, сольная и Wi-Fi игры. Возвращает ``back`` главному приложению."""
    def __init__(self, ui, settings):
        self.ui, self.settings = ui, settings
        self.scene, self.kind, self.size = "menu", None, 3
        self.board, self.turn, self.result, self.line = [], "X", None, ()
        self.peer, self.role, self.name, self.ip, self.editing = None, None, "Игрок", "", None
        self.status, self.status_until, self.rects = "", 0, {}
        self.skin = settings.get("ttt_skin", "classic")

    def note(self, text, seconds=3):
        self.status, self.status_until = text, time.time() + seconds

    def close_network(self):
        if self.peer:
            self.peer.stop()
        self.peer, self.role = None, None

    def new_game(self, size=None, first="X"):
        if size:
            self.size = size
        self.board = [None] * (self.size * self.size)
        self.turn, self.result, self.line = first, None, ()
        self.scene = "game"

    def can_play(self):
        return self.kind != "online" or (self.role == "host" and self.turn == "X") or (self.role == "client" and self.turn == "O")

    def send(self, payload):
        if self.peer:
            self.peer.send(payload)

    def _network_events(self):
        if not self.peer:
            return
        while True:
            try:
                event = self.peer.events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("t")
            if kind == "joined":
                self.new_game(event.get("size", self.size)); self.note("Соперник подключился. Вы играете X")
            elif kind == "welcome":
                remote_size = event.get("size", self.size)
                if remote_size != self.size:
                    self.note("У хоста выбран другой размер поля"); self.close_network(); self.scene = "menu"
                else:
                    self.new_game(remote_size); self.note("Подключено. Вы играете O")
            elif kind == "move":
                cell, mark = event.get("cell"), event.get("mark")
                if isinstance(cell, int) and 0 <= cell < len(self.board) and not self.board[cell] and mark in ("X", "O"):
                    self.board[cell] = mark; self.result, self.line = winner(self.board, self.size)
                    self.turn = "O" if mark == "X" else "X"
            elif kind == "rematch":
                self.new_game(event.get("size", self.size), event.get("first", "X"))
            elif kind == "error":
                self.note(event.get("msg", "Ошибка сети")); self.close_network(); self.scene = "online"
            elif kind == "left" and self.scene == "game":
                self.note("Соперник вышел"); self.close_network(); self.scene = "online"

    def _ai_move(self):
        if self.kind != "solo" or self.turn != "O" or self.result:
            return
        empty = [i for i, value in enumerate(self.board) if value is None]
        # Выиграть, затем блокировать; при прочих ходах — центр/углы/случайный.
        for mark in ("O", "X"):
            for cell in empty:
                probe = self.board[:]; probe[cell] = mark
                if winner(probe, self.size)[0] == mark:
                    self.board[cell] = "O"; self.result, self.line = winner(self.board, self.size); self.turn = "X"; return
        center = (self.size * self.size) // 2
        choices = ([center] if center in empty else []) + [i for i in empty if i != center]
        if choices:
            self.board[random.choice(choices)] = "O"
            self.result, self.line = winner(self.board, self.size); self.turn = "X"

    def handle(self, event, pos):
        self._network_events()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.scene == "menu": self.close_network(); return "back"
                if self.scene == "game": self.close_network(); self.scene = "menu"
                else: self.scene = "menu"
                self.editing = None
                return None
            if self.editing:
                value = self.name if self.editing == "name" else self.ip
                if event.key == pygame.K_BACKSPACE: value = value[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): self.editing = None; return None
                elif event.unicode and len(event.unicode) == 1:
                    allowed = event.unicode.isalnum() or event.unicode in "_.- "
                    if allowed and len(value) < (16 if self.editing == "name" else 15): value += event.unicode
                if self.editing == "name": self.name = value
                else: self.ip = value
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        for key, rect in self.rects.items():
            if rect.collidepoint(pos):
                return self._click(key, pos)
        return None

    def _click(self, key, pos):
        if key == "back": self.close_network(); return "back"
        if key == "solo": self.kind, self.scene = "solo", "size"
        elif key == "online": self.kind, self.scene = "online", "size"
        elif key.startswith("size_"):
            self.size = int(key.split("_")[1])
            if self.kind == "solo": self.new_game()
            else: self.scene = "online"
        elif key == "menu": self.close_network(); self.scene = "menu"
        elif key == "name": self.editing = "name"
        elif key == "ip": self.editing = "ip"
        elif key == "host":
            try:
                self.peer = network.Host(self.name or "Игрок", self.size); self.peer.start(); self.role = "host"; self.note("Ожидание соперника…", 10)
            except OSError: self.note("Порт уже занят")
        elif key == "join":
            if not self._valid_ip(self.ip): self.note("Введите IP хоста")
            else:
                self.peer = network.Client(self._valid_ip(self.ip), self.name or "Игрок", self.size); self.peer.start(); self.role = "client"; self.note("Подключение…", 8)
        elif key == "skin":
            skins = ["classic", "neon", "warm"]; self.skin = skins[(skins.index(self.skin) + 1) % len(skins)]
            self.settings["ttt_skin"] = self.skin; self.ui["save"]()
        elif key == "again" and self.result:
            first = "O" if self.turn == "X" else "X"; self.new_game(first); self.send({"t": "rematch", "first": first, "size": self.size})
        elif key.startswith("cell_") and not self.result and self.can_play():
            cell = int(key.split("_")[1])
            if not self.board[cell]:
                mark = self.turn; self.board[cell] = mark; self.result, self.line = winner(self.board, self.size); self.turn = "O" if mark == "X" else "X"
                if self.kind == "online": self.send({"t": "move", "cell": cell, "mark": mark})
                else: self._ai_move()
        return None

    @staticmethod
    def _valid_ip(value):
        if value.lower() == "localhost": return "127.0.0.1"
        parts = value.split(".")
        return value if len(parts) == 4 and all(item.isdigit() and 0 <= int(item) <= 255 for item in parts) else None

    def draw(self, surface, mouse, down, ticks, width, height):
        self._network_events(); self.rects = {}; u = self.ui
        surface.fill(u["header"]()); pygame.draw.line(surface, u["gold"](), (0, 72), (width, 72), 2)
        u["text"](surface, "КРЕСТИКИ-НОЛИКИ", 28, u["fg"](), (18, 14), bold=True)
        skin_rect = pygame.Rect(width - 154, 12, 136, 46)
        self.rects["skin"] = u["button"](surface, skin_rect.x, skin_rect.y, skin_rect.w, skin_rect.h, "СКИН X/O", active=True, hover=skin_rect.collidepoint(mouse), pressed=down, ticks=ticks)
        if self.scene == "menu":
            u["text"](surface, "Выберите режим", 28, u["fg"](), (width // 2, 130), center=True, bold=True)
            self._button(surface, "solo", "ОДИНОЧНАЯ ИГРА", width, 190, mouse, down, ticks)
            self._button(surface, "online", "ОНЛАЙН-ИГРА", width, 264, mouse, down, ticks)
            self._button(surface, "back", "← САПЁР", width, 354, mouse, down, ticks)
        elif self.scene == "size":
            u["text"](surface, "Выберите размер поля", 26, u["fg"](), (width // 2, 120), center=True, bold=True)
            for index, size in enumerate((3, 4, 5, 6)):
                x = width // 2 - 214 + (index % 2) * 220; y = 164 + (index // 2) * 76
                rect = pygame.Rect(x, y, 208, 58); self.rects[f"size_{size}"] = u["button"](surface, x, y, 208, 58, f"{size} × {size}", hover=rect.collidepoint(mouse), pressed=down, ticks=ticks)
            self._button(surface, "back", "← САПЁР", width, 336, mouse, down, ticks)
        elif self.scene == "online":
            u["text"](surface, f"ОНЛАЙН {self.size} × {self.size}", 26, u["fg"](), (width // 2, 115), center=True, bold=True)
            u["text"](surface, f"Ваш IP: {network.lan_ip()}", 18, u["gold"](), (width // 2, 152), center=True, bold=True)
            for key, label, value, y in (("name", "Имя", self.name, 184), ("ip", "IP хоста", self.ip, 246)):
                rect = pygame.Rect(width // 2 - 210, y, 420, 48); pygame.draw.rect(surface, u["button_bg"](), rect, border_radius=10); pygame.draw.rect(surface, u["gold"]() if self.editing == key else u["border"](), rect, 3 if self.editing == key else 2, border_radius=10); u["text"](surface, value or label, 20, u["fg"]() if value else u["muted"](), (rect.x + 14, rect.y + 12), bold=True); self.rects[key] = rect
            self._pair(surface, "host", "СОЗДАТЬ", "join", "ПОДКЛЮЧИТЬСЯ", width, 320, mouse, down, ticks)
            self._button(surface, "menu", "НАЗАД", width, 400, mouse, down, ticks)
        else:
            header = "НИЧЬЯ" if self.result == "DRAW" else f"ПОБЕДА: {self.result}" if self.result else ("ВАШ ХОД" if self.can_play() else "ХОД СОПЕРНИКА")
            u["text"](surface, header, 25, u["green"]() if self.result else u["gold"](), (width // 2, 98), center=True, bold=True)
            cell = min(64, max(42, (height - 190) // self.size)); total = cell * self.size; ox, oy = (width - total) // 2, 128
            colors = {"classic": ((96,165,250),(248,113,113)), "neon": ((34,211,238),(232,121,249)), "warm": ((251,191,36),(74,222,128))}[self.skin]
            for i, mark in enumerate(self.board):
                rect = pygame.Rect(ox + (i % self.size) * cell, oy + (i // self.size) * cell, cell, cell); pygame.draw.rect(surface, u["button_bg"](), rect); pygame.draw.rect(surface, u["green"]() if i in self.line else u["border"](), rect, 3)
                if mark: u["text"](surface, mark, int(cell * .63), colors[0] if mark == "X" else colors[1], rect.center, center=True, bold=True)
                self.rects[f"cell_{i}"] = rect
            bottom = min(height - 58, oy + total + 16); self._pair(surface, "again", "НОВАЯ ИГРА", "back", "← САПЁР", width, bottom, mouse, down, ticks, disabled=not bool(self.result))
        if self.status and time.time() < self.status_until: u["text"](surface, self.status, 17, u["muted"](), (width // 2, height - 22), center=True, bold=True)

    def _button(self, surface, key, label, width, y, mouse, down, ticks):
        rect = pygame.Rect(width // 2 - 210, y, 420, 56); self.rects[key] = self.ui["button"](surface, rect.x, rect.y, rect.w, rect.h, label, hover=rect.collidepoint(mouse), pressed=down, ticks=ticks)

    def _pair(self, surface, left_key, left_label, right_key, right_label, width, y, mouse, down, ticks, disabled=False):
        for key, label, x in ((left_key, left_label, width // 2 - 210), (right_key, right_label, width // 2 + 6)):
            rect = pygame.Rect(x, y, 204, 50); self.rects[key] = self.ui["button"](surface, x, y, 204, 50, label, hover=rect.collidepoint(mouse), pressed=down, ticks=ticks, disabled=disabled if key == left_key else False)
