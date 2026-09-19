#!/usr/bin/env python3
"""
Сапёр на pygame.

Управление:
- ЛКМ — открыть клетку / клик по цифре — открыть 3х3 вокруг
- ПКМ — поставить / снять флажок
- СКМ (колесо) по цифре — тоже открыть 3х3 вокруг
- 1 — подсказка: безопасный ход (3 шт)
- 2 — подсказка: найти мину (3 шт)
- 3 — бонус-щит от взрыва (1 шт)
- S — меню магазина/уровней, T — светлая/тёмная тема, Esc — назад
- G — Wi-Fi гонка (кто быстрее на одинаковой карте), R — новая игра
- Клик по круглой кнопке сверху — новая игра
- Уровни: EASY 8x8 (+100), NORMAL 10x10 (+250), HARD 14x14 (+600).
  Победа даёт очки (минус 25 за каждую подсказку, минимум 1/4).
  За очки покупаются скины бомб и флажков.

Первый клик всегда безопасный.
"""

import random
import time
import queue
import pygame

try:
    import netplay
except Exception:
    netplay = None

# --- Настройки (высокое разрешение, чёткий текст) ---
# Уровни сложности: размер поля и награда за победу
DIFFICULTY = {
    "easy": {"rows": 8, "cols": 8, "mines": 10, "reward": 100, "label": "EASY 8x8 +100"},
    "normal": {"rows": 10, "cols": 10, "mines": 15, "reward": 250, "label": "NORMAL 10x10 +250"},
    "hard": {"rows": 14, "cols": 14, "mines": 40, "reward": 600, "label": "HARD 14x14 +600"},
}
DIFF_ORDER = ["easy", "normal", "hard"]
ROWS, COLS, MINES = 10, 10, 15
CELL = 64  # крупнее = чётче на Retina, кнопки и цифры больше
HEADER = 210  # больше места под крупные кнопки
MIN_WIDTH = 640  # окно не уже (шапка и меню рассчитаны на 640)
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL + HEADER
BOARD_X = 0  # сдвиг поля если окно шире (лёгкий уровень)

# Размеры шрифтов (крупные против «мыла»)
FONT_CELL = 44
FONT_INFO = 30
FONT_BTN = 22
FONT_MSG = 21
FONT_FACE = 44

# Подсказки / бонусы (как в мобильных аналогах)
HINTS_SAFE_START = 3   # «безопасный ход»
HINTS_MINE_START = 3   # «найти мину»
SHIELDS_START = 1      # «щит» — спасает от 1 взрыва

# --- Темы: тёмная Midnight Felt + светлая Classic (по UI UX Pro Max) ---
THEMES = {
    "dark": {
        "BG": (25, 33, 52), "LIGHT": (58, 75, 110), "DARK": (10, 15, 28),
        "OPEN_BG": (15, 23, 42), "OPEN_BORDER": (42, 58, 85),
        "RED": (220, 38, 38), "BLACK": (0, 0, 0), "WHITE": (255, 255, 255),
        "FG": (255, 255, 255), "MUTED": (148, 163, 184),
        "GOLD": (217, 119, 6), "GOLD_LIGHT": (245, 158, 11), "GREEN": (34, 197, 94),
        "HEADER_BG": (15, 23, 42), "HEADER_BORDER": (42, 58, 85),
        "BTN_BG": (25, 33, 52), "BTN_FG": (255, 255, 255),
        "BTN_DIS_BG": (30, 41, 59), "BTN_DIS_FG": (100, 116, 139),
        "BTN_DIS_BORDER": (51, 65, 85), "LOST_BG": (30, 41, 59),
        "NUM_COLORS": {
            1: (96, 165, 250), 2: (74, 222, 128), 3: (248, 113, 113),
            4: (167, 139, 250), 5: (251, 191, 36), 6: (34, 211, 238),
            7: (226, 232, 240), 8: (148, 163, 184),
        },
    },
    "light": {
        "BG": (189, 189, 189), "LIGHT": (255, 255, 255), "DARK": (123, 123, 123),
        "OPEN_BG": (214, 214, 214), "OPEN_BORDER": (140, 140, 140),
        "RED": (220, 38, 38), "BLACK": (0, 0, 0), "WHITE": (255, 255, 255),
        "FG": (20, 20, 25), "MUTED": (90, 90, 100),
        "GOLD": (217, 119, 6), "GOLD_LIGHT": (245, 158, 11), "GREEN": (21, 128, 61),
        "HEADER_BG": (205, 205, 210), "HEADER_BORDER": (140, 140, 145),
        "BTN_BG": (235, 235, 240), "BTN_FG": (20, 20, 25),
        "BTN_DIS_BG": (185, 185, 190), "BTN_DIS_FG": (130, 130, 135),
        "BTN_DIS_BORDER": (150, 150, 155), "LOST_BG": (200, 200, 200),
        "NUM_COLORS": {
            1: (0, 0, 255), 2: (0, 128, 0), 3: (255, 0, 0),
            4: (0, 0, 128), 5: (128, 0, 0), 6: (0, 128, 128),
            7: (0, 0, 0), 8: (128, 128, 128),
        },
    },
}

TEXT_BG = (0, 0, 0)

# активная палитра (переключается через apply_theme)
for _k, _v in THEMES["dark"].items():
    globals()[_k] = _v
del _k, _v

# --- Скины, очки и настройки (сохраняются в файл) ---
SETTINGS_FILE = "skins_settings.json"
SETTINGS = {"theme": "dark", "bomb_skin": "fuse", "flag_skin": "wave",
            "difficulty": "normal", "points": 0,
            "owned_bombs": ["fuse"], "owned_flags": ["wave"]}
BOMB_SKINS = ["fuse", "classic", "neon"]
FLAG_SKINS = ["wave", "triangle", "pirate"]
BOMB_NAMES = {"fuse": "Fuse", "classic": "Classic", "neon": "Neon"}
FLAG_NAMES = {"wave": "Wave", "triangle": "Classic", "pirate": "Pirate"}
# цены магазина: базовые скины бесплатны
SKIN_PRICES = {"fuse": 0, "classic": 150, "neon": 300,
               "wave": 0, "triangle": 150, "pirate": 300}
# сообщение магазина (показывается в меню)
_SHOP_MSG = {"text": "", "until": 0}


def shop_message(text, dur=3.0):
    _SHOP_MSG["text"] = text
    _SHOP_MSG["until"] = time.time() + dur


def get_shop_message():
    if _SHOP_MSG["text"] and time.time() < _SHOP_MSG["until"]:
        return _SHOP_MSG["text"]
    return ""


def load_settings():
    import json, os
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("theme") in THEMES:
                SETTINGS["theme"] = data["theme"]
            if data.get("bomb_skin") in BOMB_SKINS:
                SETTINGS["bomb_skin"] = data["bomb_skin"]
            if data.get("flag_skin") in FLAG_SKINS:
                SETTINGS["flag_skin"] = data["flag_skin"]
            if data.get("difficulty") in DIFFICULTY:
                SETTINGS["difficulty"] = data["difficulty"]
            if isinstance(data.get("points"), int) and data["points"] >= 0:
                SETTINGS["points"] = data["points"]
            if isinstance(data.get("owned_bombs"), list):
                SETTINGS["owned_bombs"] = [s for s in data["owned_bombs"] if s in BOMB_SKINS] or ["fuse"]
            if isinstance(data.get("owned_flags"), list):
                SETTINGS["owned_flags"] = [s for s in data["owned_flags"] if s in FLAG_SKINS] or ["wave"]
            # выбранное должно быть куплено
            if SETTINGS["bomb_skin"] not in SETTINGS["owned_bombs"]:
                SETTINGS["bomb_skin"] = SETTINGS["owned_bombs"][0]
            if SETTINGS["flag_skin"] not in SETTINGS["owned_flags"]:
                SETTINGS["flag_skin"] = SETTINGS["owned_flags"][0]
    except Exception:
        pass
    apply_theme(SETTINGS["theme"])
    apply_difficulty(SETTINGS.get("difficulty", "normal"))


def save_settings():
    import json
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f)
    except Exception:
        pass


def apply_theme(name=None):
    global BG, LIGHT, DARK, OPEN_BG, OPEN_BORDER, RED, BLACK, WHITE
    global FG, MUTED, GOLD, GOLD_LIGHT, GREEN, HEADER_BG, HEADER_BORDER
    global BTN_BG, BTN_FG, BTN_DIS_BG, BTN_DIS_FG, BTN_DIS_BORDER, LOST_BG
    global NUM_COLORS
    t = THEMES.get(name or SETTINGS.get("theme", "dark"), THEMES["dark"])
    BG, LIGHT, DARK = t["BG"], t["LIGHT"], t["DARK"]
    OPEN_BG, OPEN_BORDER = t["OPEN_BG"], t["OPEN_BORDER"]
    RED, BLACK, WHITE = t["RED"], t["BLACK"], t["WHITE"]
    FG, MUTED = t["FG"], t["MUTED"]
    GOLD, GOLD_LIGHT, GREEN = t["GOLD"], t["GOLD_LIGHT"], t["GREEN"]
    HEADER_BG, HEADER_BORDER = t["HEADER_BG"], t["HEADER_BORDER"]
    BTN_BG, BTN_FG = t["BTN_BG"], t["BTN_FG"]
    BTN_DIS_BG, BTN_DIS_FG = t["BTN_DIS_BG"], t["BTN_DIS_FG"]
    BTN_DIS_BORDER, LOST_BG = t["BTN_DIS_BORDER"], t["LOST_BG"]
    NUM_COLORS = dict(t["NUM_COLORS"])
    SETTINGS["theme"] = "light" if t is THEMES["light"] else "dark"


def toggle_theme():
    apply_theme("light" if SETTINGS.get("theme") == "dark" else "dark")
    save_settings()


def apply_difficulty(key):
    """Смена уровня: размер поля + размер окна. Новое поле создаёт main."""
    global ROWS, COLS, MINES, WIDTH, HEIGHT, BOARD_X
    if key not in DIFFICULTY:
        key = "normal"
    d = DIFFICULTY[key]
    ROWS, COLS, MINES = d["rows"], d["cols"], d["mines"]
    WIDTH = max(COLS * CELL, MIN_WIDTH)
    BOARD_X = (WIDTH - COLS * CELL) // 2
    HEIGHT = ROWS * CELL + HEADER
    SETTINGS["difficulty"] = key


def buy_or_select(kind, skin):
    """Магазин: выбрать купленный или купить за очки. Возвращает True если выбрано."""
    owned_key = "owned_bombs" if kind == "bomb" else "owned_flags"
    sel_key = "bomb_skin" if kind == "bomb" else "flag_skin"
    names = BOMB_NAMES if kind == "bomb" else FLAG_NAMES
    owned = SETTINGS.setdefault(owned_key, [])
    if skin in owned:
        SETTINGS[sel_key] = skin
        save_settings()
        return True
    price = SKIN_PRICES.get(skin, 0)
    pts = SETTINGS.get("points", 0)
    if pts >= price:
        SETTINGS["points"] = pts - price
        owned.append(skin)
        SETTINGS[sel_key] = skin
        save_settings()
        shop_message(f"Bought {names.get(skin, skin)}! -{price} pts")
        return True
    shop_message(f"Need {price - pts} more pts - win levels!")
    return False

# --- Кэш картинок и шрифтов ---
_BOMB_IMG = None
_FLAG_IMG = None
_FONT_CACHE = {}


def get_font(size, bold=True, name="arial"):
    key = (name, size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont(name, size, bold=bold)
    return _FONT_CACHE[key]


def draw_text_crisp(screen, text, size, color, pos, center=False, bold=True, name="arial", ss=3):
    """Чёткий текст: рендер в ss раз крупнее + smoothscale вниз (против мыла)."""
    big = get_font(size * ss, bold, name).render(text, True, color)
    bw, bh = big.get_size()
    small = pygame.transform.smoothscale(big, (max(1, bw // ss), max(1, bh // ss)))
    rect = small.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    screen.blit(small, rect)
    return rect


def _load_external(name, target_size):
    """Если в папке assets/ есть bomb.png / flag.png — используем их."""
    import os
    for fname in (f"assets/{name}.png", f"assets/{name}.jpg", f"{name}.png"):
        if os.path.exists(fname):
            try:
                img = pygame.image.load(fname).convert_alpha()
                return pygame.transform.smoothscale(img, (target_size, target_size))
            except Exception:
                pass
    return None


def _make_bomb_fuse(S):
    """Скин Fuse: чёрный шар с бликом, фитиль и искра."""
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    cx, cy, R = int(S * 0.46), int(S * 0.58), int(S * 0.32)
    # тень
    pygame.draw.circle(surf, (0, 0, 0, 60), (cx + 6, cy + 10), R)
    # тело бомбы — градиент из концентрических кругов
    for i in range(R, 0, -1):
        t = i / R  # 1 край, 0 центр
        # светлее к верхнему-левому краю
        shade = int(20 + 50 * (1 - t))
        pygame.draw.circle(surf, (shade, shade, shade + 10), (cx, cy), i)
    # основной шар
    pygame.draw.circle(surf, (15, 15, 20), (cx, cy), R)
    # блик
    pygame.draw.circle(surf, (255, 255, 255, 230),
                       (int(cx - R * 0.35), int(cy - R * 0.38)), int(R * 0.22))
    pygame.draw.circle(surf, (200, 200, 210, 160),
                       (int(cx - R * 0.3), int(cy - R * 0.32)), int(R * 0.12))
    # металлический колпачок
    cap = pygame.Rect(cx - R * 0.18, cy - R - 18, R * 0.36, 26)
    pygame.draw.rect(surf, (90, 90, 100), cap, border_radius=6)
    pygame.draw.rect(surf, (40, 40, 50), cap, 2, border_radius=6)
    # фитиль
    start = (cx + 5, cy - R - 16)
    mid = (cx + R * 0.5, cy - R - 45)
    end = (cx + R * 0.75, cy - R - 30)
    pygame.draw.lines(surf, (139, 90, 43), False, [start, mid, end], 10)
    pygame.draw.lines(surf, (210, 170, 110), False, [start, mid, end], 4)
    # искра — звезда с glow
    for rad, col in ((26, (255, 100, 0, 90)), (18, (255, 180, 0, 200)), (10, (255, 240, 150, 255))):
        pts = []
        import math
        for k in range(12):
            ang = k * math.pi / 6
            rr = rad * (1.0 if k % 2 == 0 else 0.55)
            pts.append((end[0] + rr * math.cos(ang), end[1] + rr * math.sin(ang)))
        pygame.draw.polygon(surf, col, pts)
    return surf


def _make_bomb_classic(S):
    """Скин Classic: шар с шипами как в классическом Сапёре."""
    import math
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    cx, cy, R = S // 2, int(S * 0.52), int(S * 0.30)
    # шипы
    for deg in (0, 45, 90, 135):
        a = math.radians(deg)
        dx, dy = int((R + 20) * math.cos(a)), int((R + 20) * math.sin(a))
        pygame.draw.line(surf, (25, 25, 32), (cx - dx, cy - dy), (cx + dx, cy + dy), 16)
        pygame.draw.line(surf, (70, 70, 80), (cx - dx, cy - dy), (cx + dx, cy + dy), 6)
    # тень + шар
    pygame.draw.circle(surf, (0, 0, 0, 60), (cx + 6, cy + 10), R)
    pygame.draw.circle(surf, (15, 15, 20), (cx, cy), R)
    pygame.draw.circle(surf, (120, 120, 135), (cx, cy), R, 4)
    # блик
    pygame.draw.circle(surf, (255, 255, 255, 230),
                       (int(cx - R * 0.35), int(cy - R * 0.38)), int(R * 0.24))
    return surf


def _make_bomb_neon(S):
    """Скин Neon: светящаяся бомба для тёмной темы."""
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    cx, cy, R = S // 2, int(S * 0.52), int(S * 0.30)
    for rad, col in ((R + 30, (0, 255, 255, 45)), (R + 15, (0, 255, 255, 90))):
        pygame.draw.circle(surf, col, (cx, cy), rad)
    pygame.draw.circle(surf, (0, 0, 0, 60), (cx + 6, cy + 10), R)
    pygame.draw.circle(surf, (35, 20, 70), (cx, cy), R)
    pygame.draw.circle(surf, (190, 40, 200), (cx, cy), int(R * 0.58))
    pygame.draw.circle(surf, (255, 150, 255), (cx, cy), int(R * 0.28))
    pygame.draw.circle(surf, (255, 255, 255, 235),
                       (int(cx - R * 0.35), int(cy - R * 0.38)), int(R * 0.16))
    pygame.draw.circle(surf, (0, 255, 255), (cx, cy), R, 5)
    return surf


_BOMB_CACHE = {}


def get_bomb_image(size=None, skin=None):
    """Бомба выбранного скина (fuse/classic/neon). Суперсэмплинг для чёткости."""
    global _BOMB_IMG
    skin = skin or SETTINGS.get("bomb_skin", "fuse")
    if skin not in BOMB_SKINS:
        skin = "fuse"
    target = size or (CELL - 10)
    key = (skin, target)
    if key in _BOMB_CACHE:
        _BOMB_IMG = _BOMB_CACHE[key]
        return _BOMB_IMG
    ext = _load_external("bomb", target)
    if ext is not None:
        _BOMB_CACHE[key] = ext
        _BOMB_IMG = ext
        return ext
    S = 256
    if skin == "classic":
        surf = _make_bomb_classic(S)
    elif skin == "neon":
        surf = _make_bomb_neon(S)
    else:
        surf = _make_bomb_fuse(S)
    small = pygame.transform.smoothscale(surf, (target, target))
    _BOMB_CACHE[key] = small
    _BOMB_IMG = small
    return small


def _make_flag_wave(S):
    """Скин Wave: развевающийся красный флаг."""
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    # основание
    pygame.draw.rect(surf, (30, 30, 30), (S // 2 - 40, S - 40, 80, 16), border_radius=5)
    pygame.draw.rect(surf, (90, 90, 95), (S // 2 - 40, S - 40, 80, 8), border_radius=5)
    # древко с градиентом
    pole_x = S // 2 - 10
    pygame.draw.rect(surf, (60, 60, 65), (pole_x - 7, 30, 14, S - 65), border_radius=5)
    pygame.draw.rect(surf, (180, 180, 185), (pole_x - 7, 30, 5, S - 65), border_radius=3)
    pygame.draw.circle(surf, (220, 220, 230), (pole_x, 28), 10)
    pygame.draw.circle(surf, (80, 80, 90), (pole_x, 28), 10, 2)
    # полотнище — волна
    wave = [(pole_x + 7, 35), (pole_x + 85, 50),
            (pole_x + 70, 75), (pole_x + 85, 100), (pole_x + 7, 95)]
    pygame.draw.polygon(surf, (200, 0, 0), wave)
    wave_hi = [(pole_x + 7, 35), (pole_x + 85, 50),
               (pole_x + 75, 62), (pole_x + 7, 55)]
    pygame.draw.polygon(surf, (255, 70, 70), wave_hi)
    return surf


def _make_flag_triangle(S):
    """Скин Classic: простое треугольное полотнище."""
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.rect(surf, (30, 30, 30), (S // 2 - 40, S - 40, 80, 16), border_radius=5)
    pole_x = S // 2 - 10
    pygame.draw.rect(surf, (60, 60, 65), (pole_x - 7, 30, 14, S - 65), border_radius=5)
    pygame.draw.rect(surf, (180, 180, 185), (pole_x - 7, 30, 5, S - 65), border_radius=3)
    pygame.draw.circle(surf, (220, 220, 230), (pole_x, 28), 10)
    tri = [(pole_x + 7, 38), (pole_x + 88, 64), (pole_x + 7, 90)]
    pygame.draw.polygon(surf, (200, 0, 0), tri)
    pygame.draw.polygon(surf, (120, 0, 0), tri, 4)
    return surf


def _make_flag_pirate(S):
    """Скин Pirate: чёрный флаг с черепом."""
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    pole_x = S // 2 - 60
    pygame.draw.rect(surf, (30, 30, 30), (pole_x - 33, S - 40, 80, 16), border_radius=5)
    pygame.draw.rect(surf, (60, 60, 65), (pole_x - 7, 30, 14, S - 65), border_radius=5)
    pygame.draw.rect(surf, (180, 180, 185), (pole_x - 7, 30, 5, S - 65), border_radius=3)
    flag = pygame.Rect(pole_x + 7, 36, 130, 66)
    pygame.draw.rect(surf, (12, 12, 16), flag, border_radius=6)
    pygame.draw.rect(surf, (200, 200, 210), flag, 3, border_radius=6)
    sx, sy = flag.centerx, flag.centery - 6
    pygame.draw.circle(surf, (240, 240, 245), (sx, sy), 16)
    pygame.draw.circle(surf, (10, 10, 14), (sx - 6, sy - 2), 4)
    pygame.draw.circle(surf, (10, 10, 14), (sx + 6, sy - 2), 4)
    pygame.draw.rect(surf, (240, 240, 245), (sx - 8, sy + 12, 16, 8), border_radius=3)
    # скрещенные кости
    pygame.draw.line(surf, (240, 240, 245), (sx - 22, sy + 26), (sx + 22, sy + 26), 5)
    pygame.draw.line(surf, (240, 240, 245), (sx - 22, sy + 26), (sx + 22, sy + 26), 5)
    return surf


_FLAG_CACHE = {}


def get_flag_image(size=None, skin=None):
    """Флажок выбранного скина (wave/triangle/pirate)."""
    global _FLAG_IMG
    skin = skin or SETTINGS.get("flag_skin", "wave")
    if skin not in FLAG_SKINS:
        skin = "wave"
    target = size or (CELL - 10)
    key = (skin, target)
    if key in _FLAG_CACHE:
        _FLAG_IMG = _FLAG_CACHE[key]
        return _FLAG_IMG
    ext = _load_external("flag", target)
    if ext is not None:
        _FLAG_CACHE[key] = ext
        _FLAG_IMG = ext
        return ext
    S = 256
    if skin == "triangle":
        surf = _make_flag_triangle(S)
    elif skin == "pirate":
        surf = _make_flag_pirate(S)
    else:
        surf = _make_flag_wave(S)
    small = pygame.transform.smoothscale(surf, (target, target))
    _FLAG_CACHE[key] = small
    _FLAG_IMG = small
    return small


def neighbours(r, c):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                yield nr, nc


def create_empty_board():
    return {
        "mines": [[False] * COLS for _ in range(ROWS)],
        "opened": [[False] * COLS for _ in range(ROWS)],
        "flagged": [[False] * COLS for _ in range(ROWS)],
        "numbers": [[0] * COLS for _ in range(ROWS)],
        "mines_placed": False,
        "game_over": False,   # True после проигрыша или победы
        "won": False,
        "exploded": None,
        "start_time": None,
        "elapsed": 0,
        # подсказки и бонусы
        "hints_safe": HINTS_SAFE_START,
        "hints_mine": HINTS_MINE_START,
        "shields_stock": SHIELDS_START,
        "shield_on": False,
        "hints_used": 0,
        "bonus_next": 30,
        "message": "",
        "message_until": 0,
        # уровень и награда
        "difficulty": SETTINGS.get("difficulty", "normal"),
        "awarded": False,
        "award": 0,
    }


def set_message(board, text, dur=3.0):
    board["message"] = text
    board["message_until"] = time.time() + dur


def get_message(board):
    if board.get("message") and time.time() < board.get("message_until", 0):
        return board["message"]
    return ""


def ensure_mines(board):
    if not board["mines_placed"]:
        place_mines(board, ROWS // 2, COLS // 2)


def build_race_board(seed):
    """Одинаковая карта для сетевой гонки: сид + фикс. зона без мин в центре.
    Центр предоткрыт всем — честный общий старт."""
    rng = random.Random(seed)
    cr, cc = ROWS // 2, COLS // 2
    b = create_empty_board()
    place_mines(b, cr, cc, rng=rng)
    open_cell(b, cr, cc)  # центр безопасен (в запретной зоне)
    b["start_time"] = None  # время стартует по команде со всех
    b["message"] = ""
    b["message_until"] = 0
    return b


def place_mines(board, safe_r, safe_c, rng=None):
    """Расставить мины после первого клика, избегая safe-клетки и соседей.
    rng — random.Random с сидом (для одинаковой карты в сетевой гонке)."""
    shuffler = (rng or random).shuffle
    forbidden = {(safe_r, safe_c)} | set(neighbours(safe_r, safe_c))
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)
             if (r, c) not in forbidden]
    shuffler(cells)
    for r, c in cells[:MINES]:
        board["mines"][r][c] = True
    # посчитать числа
    for r in range(ROWS):
        for c in range(COLS):
            if board["mines"][r][c]:
                continue
            board["numbers"][r][c] = sum(
                1 for nr, nc in neighbours(r, c) if board["mines"][nr][nc]
            )
    board["mines_placed"] = True
    board["start_time"] = time.time()


def open_cell(board, r, c):
    """Открыть клетку. Возвращает False если взрыв."""
    if board["game_over"] or board["flagged"][r][c] or board["opened"][r][c]:
        return True
    if not board["mines_placed"]:
        place_mines(board, r, c)
    if board["mines"][r][c]:
        # бонус-щит спасает от взрыва (как в аналогах)
        if board.get("shield_on"):
            board["shield_on"] = False
            board["flagged"][r][c] = True
            set_message(board, "🛡 Щит спас! Мина обезврежена", 3.0)
            return True
        board["opened"][r][c] = True
        board["game_over"] = True
        board["won"] = False
        board["exploded"] = (r, c)
        board["elapsed"] = time.time() - board["start_time"]
        return False
    # flood fill для пустых
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if board["opened"][cr][cc] or board["flagged"][cr][cc]:
            continue
        board["opened"][cr][cc] = True
        if board["numbers"][cr][cc] == 0 and not board["mines"][cr][cc]:
            for nr, nc in neighbours(cr, cc):
                if not board["opened"][nr][nc] and not board["flagged"][nr][nc]:
                    stack.append((nr, nc))
    check_win(board)
    return True


def toggle_flag(board, r, c):
    if board["game_over"] or board["opened"][r][c]:
        return
    if board["start_time"] is None:
        # чтобы таймер не тикал до первого открытия — флаги разрешаем,
        # но время стартует только после place_mines
        pass
    board["flagged"][r][c] = not board["flagged"][r][c]


def chord_open(board, r, c):
    """Клик по открытой цифре — открыть всё 3х3 вокруг, кроме флажков."""
    if board["game_over"] or not board["opened"][r][c]:
        return True
    if board["numbers"][r][c] == 0:
        return True
    for nr, nc in list(neighbours(r, c)):
        if board["game_over"]:
            break
        if not board["opened"][nr][nc] and not board["flagged"][nr][nc]:
            ok = open_cell(board, nr, nc)
            if not ok:
                return False
    return True


def cheat_win(board):
    """Чит HESOYAM: мгновенно пройти уровень с начислением очков."""
    if board["game_over"]:
        return False
    ensure_mines(board)
    for r in range(ROWS):
        for c in range(COLS):
            if board["mines"][r][c]:
                board["flagged"][r][c] = True
            else:
                board["flagged"][r][c] = False
                board["opened"][r][c] = True
    check_win(board)
    if board.get("won"):
        set_message(board, f"HESOYAM! +{board.get('award', 0)}pts", 4.0)
        return True
    return False


def check_win(board):
    opened_count = sum(sum(row) for row in board["opened"])
    if opened_count == ROWS * COLS - MINES:
        board["game_over"] = True
        board["won"] = True
        if board["start_time"]:
            board["elapsed"] = time.time() - board["start_time"]
        # очки за уровень: база минус 25 за подсказку, минимум четверть
        if not board.get("awarded"):
            board["awarded"] = True
            base = DIFFICULTY.get(board.get("difficulty", "normal"),
                                  DIFFICULTY["normal"])["reward"]
            award = max(base // 4, base - 25 * board.get("hints_used", 0))
            board["award"] = award
            SETTINGS["points"] = SETTINGS.get("points", 0) + award
            save_settings()
    else:
        maybe_grant_bonus(board, opened_count)


def maybe_grant_bonus(board, opened_count=None):
    """Бонус из аналогов: за серию открытий даём +1 подсказку (макс. 3)."""
    if board["game_over"]:
        return
    if opened_count is None:
        opened_count = sum(sum(row) for row in board["opened"])
    bonus_at = board.get("bonus_next", 30)
    if opened_count >= bonus_at:
        board["bonus_next"] = bonus_at + 30
        if board.get("hints_safe", 0) < 3:
            board["hints_safe"] = board.get("hints_safe", 0) + 1
            set_message(board, "🎁 Бонус: +1 безопасный ход!", 3.0)
        elif board.get("hints_mine", 0) < 3:
            board["hints_mine"] = board.get("hints_mine", 0) + 1
            set_message(board, "🎁 Бонус: +1 поиск мины!", 3.0)


def use_safe_hint(board):
    """Подсказка 1: открыть случайную безопасную клетку."""
    if board["game_over"]:
        return False
    if board.get("hints_safe", 0) <= 0:
        set_message(board, "Нет безопасных подсказок", 2.0)
        return False
    ensure_mines(board)
    candidates = [(r, c) for r in range(ROWS) for c in range(COLS)
                  if not board["opened"][r][c]
                  and not board["flagged"][r][c]
                  and not board["mines"][r][c]]
    if not candidates:
        set_message(board, "Нет безопасных клеток", 2.0)
        return False
    r, c = random.choice(candidates)
    board["hints_safe"] -= 1
    board["hints_used"] = board.get("hints_used", 0) + 1
    open_cell(board, r, c)
    maybe_grant_bonus(board)
    if not board["game_over"]:
        set_message(board, f"💡 Открыта безопасная ({r+1},{c+1})", 2.5)
    return True


def use_mine_hint(board):
    """Подсказка 2: поставить флажок на случайную мину."""
    if board["game_over"]:
        return False
    if board.get("hints_mine", 0) <= 0:
        set_message(board, "Нет подсказок-поиска мин", 2.0)
        return False
    ensure_mines(board)
    candidates = [(r, c) for r in range(ROWS) for c in range(COLS)
                  if board["mines"][r][c] and not board["flagged"][r][c]]
    if not candidates:
        set_message(board, "Все мины уже помечены", 2.0)
        return False
    r, c = random.choice(candidates)
    board["flagged"][r][c] = True
    board["hints_mine"] -= 1
    board["hints_used"] = board.get("hints_used", 0) + 1
    set_message(board, f"🚩 Мина помечена ({r+1},{c+1})", 2.5)
    return True


def toggle_shield(board):
    """Бонус 3: щит — вкл/выкл защиту от 1 взрыва."""
    if board["game_over"]:
        return False
    if board.get("shield_on"):
        board["shield_on"] = False
        board["shields_stock"] = board.get("shields_stock", 0) + 1
        set_message(board, "Щит снят", 2.0)
        return True
    if board.get("shields_stock", 0) <= 0:
        set_message(board, "Нет щитов", 2.0)
        return False
    board["shields_stock"] -= 1
    board["shield_on"] = True
    set_message(board, "🛡 Щит включён — спасёт от 1 взрыва", 2.5)
    return True


def count_flags(board):
    return sum(sum(row) for row in board["flagged"])


def draw_cell(screen, font, board, r, c):
    x = BOARD_X + c * CELL
    y = r * CELL + HEADER
    rect = pygame.Rect(x, y, CELL, CELL)

    is_exploded = board["exploded"] == (r, c)

    if board["opened"][r][c]:
        color = (127, 29, 29) if is_exploded else OPEN_BG
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, RED if is_exploded else OPEN_BORDER, rect, 2 if is_exploded else 1)
        if board["mines"][r][c]:
            # glow-подложка чтобы чёрная бомба читалась на тёмном
            glow = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.circle(glow, (220, 38, 38, 70 if is_exploded else 45),
                               (CELL // 2, CELL // 2), CELL // 2 - 2)
            screen.blit(glow, (x, y))
            img = get_bomb_image()
            screen.blit(img, img.get_rect(center=rect.center))
        elif board["numbers"][r][c] > 0:
            n = board["numbers"][r][c]
            # чёткий текст через суперсэмплинг
            draw_text_crisp(screen, str(n), FONT_CELL, NUM_COLORS.get(n, WHITE),
                            rect.center, center=True, bold=True)
    else:
        # закрытая HUD-клетка: card + неоновая фаска
        pygame.draw.rect(screen, BG, rect)
        b = 5
        pygame.draw.line(screen, LIGHT, (x, y), (x + CELL - 1, y), b)
        pygame.draw.line(screen, LIGHT, (x, y), (x, y + CELL - 1), b)
        pygame.draw.line(screen, DARK, (x, y + CELL - 1), (x + CELL - 1, y + CELL - 1), b)
        pygame.draw.line(screen, DARK, (x + CELL - 1, y), (x + CELL - 1, y + CELL - 1), b)
        pygame.draw.rect(screen, HEADER_BORDER, rect, 1)
        if board["flagged"][r][c]:
            img = get_flag_image()
            screen.blit(img, img.get_rect(center=(rect.centerx, rect.centery + 2)))
            # неверный флаг после проигрыша — красный крест
            if board["game_over"] and not board["won"] and not board["mines"][r][c]:
                pygame.draw.line(screen, (248, 113, 113), (x + 10, y + 10),
                                 (x + CELL - 10, y + CELL - 10), 5)
                pygame.draw.line(screen, (248, 113, 113), (x + CELL - 10, y + 10),
                                 (x + 10, y + CELL - 10), 5)
        elif board["game_over"] and not board["won"] and board["mines"][r][c]:
            img = get_bomb_image()
            pygame.draw.rect(screen, LOST_BG, rect)
            pygame.draw.rect(screen, OPEN_BORDER, rect, 1)
            glow = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.circle(glow, (220, 38, 38, 40), (CELL // 2, CELL // 2), CELL // 2 - 2)
            screen.blit(glow, (x, y))
            screen.blit(img, img.get_rect(center=rect.center))


def draw_hint_button(screen, x, y, w, h, text, active=False, disabled=False,
                       hover=False, pressed=False, ticks=0, fontsize=None):
    # Тёмный HUD-стиль + анимации: hover-подсветка, pressed-вдавливание, active-пульс
    import math
    if active:
        base, border, txt_color = (21, 128, 61), (74, 222, 128), (255, 255, 255)
        # пульс активной кнопки (дыхание)
        pulse = (math.sin(ticks / 300.0) + 1) / 2  # 0..1
        glow_a = int(40 + 50 * pulse)
    elif disabled:
        base, border, txt_color = BTN_DIS_BG, BTN_DIS_BORDER, BTN_DIS_FG
        glow_a = 0
    else:
        base, border, txt_color = BTN_BG, GOLD, BTN_FG
        glow_a = 0

    dx, dy, dw, dh = 0, 0, 0, 0
    if not disabled:
        if hover and not pressed:
            # hover: приподнять и подсветить
            dy = -2
            border = GOLD_LIGHT if not active else (134, 239, 172)
            glow_a = 70
        if pressed and hover:
            # pressed: вдавить
            dy = 2
            base = tuple(max(0, c - 25) for c in base)

    rect = pygame.Rect(x + dx, y + dy, w + dw, h + dh)
    if glow_a and not disabled:
        glow = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*border, glow_a),
                         glow.get_rect(), border_radius=14)
        screen.blit(glow, (x - 8, y - 8 + dy))
    pygame.draw.rect(screen, base, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, 3 if hover and not disabled else 2,
                     border_radius=10)
    draw_text_crisp(screen, text, fontsize or FONT_BTN, txt_color, rect.center, center=True, bold=True)
    return pygame.Rect(x, y, w, h)


def draw_refresh_icon(screen, center, radius, color, angle_deg, width=5):
    """Иконка обновления: круговая стрелка. angle_deg — поворот для анимации."""
    import math
    cx, cy = center
    rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    # дуга почти полный круг с разрывом
    a0 = math.radians(angle_deg + 40)
    a1 = math.radians(angle_deg + 320)
    # pygame arc: углы в радианах, 0 = вправо, против часовой
    try:
        pygame.draw.arc(screen, color, rect, a0, a1, width)
    except Exception:
        pass
    # наконечник стрелки — на другом конце дуги (40°), направление перевёрнуто
    tip_ang = math.radians(angle_deg + 40)
    tx = cx + radius * math.cos(tip_ang)
    ty = cy - radius * math.sin(tip_ang)
    # касательное направление — в обратную сторону
    tan_ang = tip_ang - math.pi / 2
    s = radius * 0.45
    p1 = (tx, ty)
    p2 = (tx + s * math.cos(tan_ang + 2.5), ty - s * math.sin(tan_ang + 2.5))
    p3 = (tx + s * math.cos(tan_ang - 2.5), ty - s * math.sin(tan_ang - 2.5))
    pygame.draw.polygon(screen, color, [p1, p2, p3])


def draw_restart_button(screen, board, mouse_pos=(0, 0), mouse_down=False, ticks=0):
    """Новый дизайн кнопки рестарта: круг + иконка refresh + анимации."""
    import math
    cx, cy = WIDTH - 55, 36
    base_r = 27
    if board["game_over"]:
        bg = (21, 128, 61) if board["won"] else (153, 27, 27)
        ring = (74, 222, 128) if board["won"] else (248, 113, 113)
        icon_col = (255, 255, 255)
    else:
        bg = GOLD_LIGHT
        ring = GOLD
        icon_col = (15, 23, 42)

    hit = pygame.Rect(cx - base_r, cy - base_r, base_r * 2, base_r * 2)
    hover = hit.collidepoint(mouse_pos)
    r = base_r + (2 if hover and not mouse_down else 0) - (2 if hover and mouse_down else 0)

    # hover-свечение + пульс после конца игры
    if hover:
        glow = pygame.Surface((r * 2 + 24, r * 2 + 24), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*ring, 80), (r + 12, r + 12), r + 8)
        screen.blit(glow, (cx - r - 12, cy - r - 12))
    if board["game_over"]:
        pulse = (math.sin(ticks / 350.0) + 1) / 2
        pr = int(r + 4 + 4 * pulse)
        pygame.draw.circle(screen, (*ring, ), (cx, cy), pr, 2)

    # тень + тело
    pygame.draw.circle(screen, (0, 0, 0, 90), (cx + 2, cy + 3), r)
    pygame.draw.circle(screen, bg, (cx, cy), r)
    # блик сверху
    hi = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(hi, (255, 255, 255, 55), (r - 6, r - 8), r // 3)
    screen.blit(hi, (cx - r, cy - r))
    pygame.draw.circle(screen, (255, 255, 255) if not board["game_over"] else ring,
                       (cx, cy), r, 2)
    # иконка: крутится при наведении В ОБРАТНУЮ сторону, при победе/поражении — покачивание наоборот
    if hover and not board["game_over"]:
        angle = (-ticks / 8) % 360
    elif board["game_over"]:
        angle = -15 * math.sin(ticks / 400.0)
    else:
        angle = 0
    draw_refresh_icon(screen, (cx, cy), int(r * 0.55), icon_col, angle, width=5)
    return hit


def draw(screen, font, small_font, tiny_font, board, mouse_pos=(0, 0), mouse_down=False, ticks=0):
    screen.fill(HEADER_BG)
    # верхняя HUD-панель + золотая акцентная линия
    pygame.draw.rect(screen, HEADER_BG, (0, 0, WIDTH, HEADER))
    pygame.draw.line(screen, HEADER_BORDER, (0, HEADER - 3), (WIDTH, HEADER - 3), 2)
    pygame.draw.line(screen, GOLD, (0, HEADER - 1), (WIDTH, HEADER - 1), 2)
    flags_left = MINES - count_flags(board)
    if board["start_time"] and not board["game_over"]:
        elapsed = int(time.time() - board["start_time"])
    else:
        elapsed = int(board["elapsed"])

    draw_text_crisp(screen, f"MINES {flags_left:02d}   TIME {elapsed}s",
                    FONT_INFO, FG, (18, 8), bold=True)
    _dk = board.get("difficulty", SETTINGS.get("difficulty", "normal"))
    _dr = DIFFICULTY.get(_dk, DIFFICULTY["normal"])["reward"]
    draw_text_crisp(screen, f"{_dk.upper()} +{_dr}  PTS {SETTINGS.get('points', 0)}",
                    FONT_MSG, GOLD_LIGHT, (18, 44), bold=True)
    # новая круглая кнопка рестарта с иконкой refresh
    face_rect = draw_restart_button(screen, board, mouse_pos, mouse_down, ticks)

    # 3 крупные кнопки подсказок (с hover/press анимацией)
    bw, bh, gap = 196, 52, 12
    y_btn = 78
    safe_txt = f"SAVE {board.get('hints_safe',0)} [1]"
    mine_txt = f"MINE {board.get('hints_mine',0)} [2]"
    if board.get("shield_on"):
        shield_txt = "SHIELD ON [3]"
    else:
        shield_txt = f"SHIELD {board.get('shields_stock',0)} [3]"
    base_safe = pygame.Rect(18, y_btn, bw, bh)
    base_mine = pygame.Rect(18 + bw + gap, y_btn, bw, bh)
    base_shield = pygame.Rect(18 + (bw + gap) * 2, y_btn, bw, bh)
    r_safe = draw_hint_button(screen, 18, y_btn, bw, bh, safe_txt,
                              disabled=board.get("hints_safe", 0) <= 0 or board["game_over"],
                              hover=base_safe.collidepoint(mouse_pos),
                              pressed=mouse_down, ticks=ticks)
    r_mine = draw_hint_button(screen, 18 + bw + gap, y_btn, bw, bh, mine_txt,
                              disabled=board.get("hints_mine", 0) <= 0 or board["game_over"],
                              hover=base_mine.collidepoint(mouse_pos),
                              pressed=mouse_down, ticks=ticks)
    r_shield = draw_hint_button(screen, 18 + (bw + gap) * 2, y_btn, bw, bh, shield_txt,
                                active=board.get("shield_on", False),
                                disabled=not board.get("shield_on") and board.get("shields_stock", 0) <= 0,
                                hover=base_shield.collidepoint(mouse_pos),
                                pressed=mouse_down, ticks=ticks)

    # строка сообщений / победы — крупно и чётко
    msg = get_message(board)
    if board["game_over"]:
        if board["won"]:
            _aw = board.get("award", 0)
            if board.get("hints_used", 0) == 0:
                msg = f"PERFECT! +{_aw}pts ({elapsed}s)! Press R"
            else:
                msg = f"WIN +{_aw}pts ({elapsed}s)! Press R"
        else:
            msg = "BOOM! Press R"
    if msg:
        # убрать эмодзи — они мылят в pygame, только чистый текст
        clean = msg.replace("💡", "").replace("🚩", "").replace("🛡", "").replace("🎁", "").replace("🏆", "").replace("💣", "").replace("⏱", "").strip()
        col = (248, 113, 113) if (board["game_over"] and not board["won"]) else (74, 222, 128)
        draw_text_crisp(screen, clean, FONT_MSG, col, (18, 150), bold=True)
    else:
        draw_text_crisp(screen, "LMB-number=3x3  RMB-flag  R-restart", FONT_MSG, MUTED, (18, 150), bold=True)

    # кнопки входа в магазин и Wi-Fi гонку (справа от сообщений)
    _rr = pygame.Rect(WIDTH - 160, 142, 142, 50)
    skins_rect = draw_hint_button(screen, WIDTH - 160, 142, 142, 50, "SKINS [S]",
                                  hover=_rr.collidepoint(mouse_pos),
                                  pressed=mouse_down, ticks=ticks)
    _rg = pygame.Rect(WIDTH - 312, 142, 142, 50)
    race_rect = draw_hint_button(screen, WIDTH - 312, 142, 142, 50, "RACE [G]",
                                 hover=_rg.collidepoint(mouse_pos),
                                 pressed=mouse_down, ticks=ticks)

    for r in range(ROWS):
        for c in range(COLS):
            draw_cell(screen, font, board, r, c)

    return {"face": face_rect, "safe": r_safe, "mine": r_mine, "shield": r_shield,
            "skins": skins_rect, "race": race_rect}


def draw_skin_card(screen, x, y, w, h, image, name, selected=False,
                   hover=False, pressed=False, ticks=0, locked=False):
    """Карточка скина в меню: превью + название/цена. Выбранная — зелёная."""
    import math
    base = pygame.Rect(x, y, w, h)
    if selected:
        pulse = (math.sin(ticks / 350.0) + 1) / 2
        glow_a = int(40 + 40 * pulse)
        glow = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
        pygame.draw.rect(glow, (74, 222, 128, glow_a), glow.get_rect(), border_radius=14)
        screen.blit(glow, (x - 8, y - 8))
    dy = -2 if (hover and not pressed) else (2 if (hover and pressed) else 0)
    rect = pygame.Rect(x, y + dy, w, h)
    pygame.draw.rect(screen, BTN_BG, rect, border_radius=12)
    if selected:
        border, bw = (74, 222, 128), 3
    elif locked:
        border, bw = (HEADER_BORDER if not hover else MUTED), 2
    else:
        border, bw = (GOLD if hover else HEADER_BORDER), 3 if hover else 2
    pygame.draw.rect(screen, border, rect, bw, border_radius=12)
    screen.blit(image, image.get_rect(center=(rect.centerx, rect.centery - 16)))
    if selected:
        label, col = "* " + name, (74, 222, 128)
    elif locked:
        label, col = name, MUTED
    else:
        label, col = name, BTN_FG
    draw_text_crisp(screen, label, FONT_MSG, col,
                    (rect.centerx, rect.bottom - 26), center=True, bold=True)
    return base


def skin_card_label(kind, skin):
    """Название + цена для закрытого скина."""
    names = BOMB_NAMES if kind == "bomb" else FLAG_NAMES
    owned = SETTINGS.get("owned_bombs" if kind == "bomb" else "owned_flags", [])
    if skin in owned:
        return names[skin]
    return f"LOCK {SKIN_PRICES.get(skin, 0)}"


def draw_skins_menu(screen, mouse_pos=(0, 0), mouse_down=False, ticks=0):
    """Экран магазина: уровень, тема, скины за очки. Возвращает rects для кликов."""
    screen.fill(HEADER_BG)
    pygame.draw.line(screen, GOLD, (0, 0), (WIDTH, 0), 2)
    draw_text_crisp(screen, "SHOP & LEVEL", FONT_INFO, FG, (18, 12), bold=True)
    draw_text_crisp(screen, f"PTS {SETTINGS.get('points', 0)}", FONT_BTN,
                    GOLD_LIGHT, (18, 48), bold=True)
    back = draw_hint_button(screen, WIDTH - 150, 10, 132, 48, "BACK",
                            hover=pygame.Rect(WIDTH - 150, 10, 132, 48).collidepoint(mouse_pos),
                            pressed=mouse_down, ticks=ticks)

    # уровни сложности (размер поля + награда)
    draw_text_crisp(screen, "LEVEL (win pts)", FONT_BTN, MUTED, (18, 84), bold=True)
    level_rects = {}
    lw = (WIDTH - 36 - 24) // 3
    for i, key in enumerate(DIFF_ORDER):
        x = 18 + i * (lw + 12)
        d = DIFFICULTY[key]
        base = pygame.Rect(x, 112, lw, 50)
        btn = draw_hint_button(screen, x, 112, lw, 50, d["label"],
                               active=SETTINGS.get("difficulty") == key,
                               hover=base.collidepoint(mouse_pos),
                               pressed=mouse_down, ticks=ticks, fontsize=18)
        level_rects[key] = btn

    draw_text_crisp(screen, "THEME  [T]", FONT_BTN, MUTED, (18, 176), bold=True)
    td_base = pygame.Rect(18, 204, 304, 50)
    tl_base = pygame.Rect(318, 204, 304, 50)
    td = draw_hint_button(screen, 18, 204, 304, 50, "DARK",
                          active=SETTINGS.get("theme") == "dark",
                          hover=td_base.collidepoint(mouse_pos),
                          pressed=mouse_down, ticks=ticks)
    tl = draw_hint_button(screen, 318, 204, 304, 50, "LIGHT",
                          active=SETTINGS.get("theme") == "light",
                          hover=tl_base.collidepoint(mouse_pos),
                          pressed=mouse_down, ticks=ticks)

    draw_text_crisp(screen, "BOMBS", FONT_BTN, MUTED, (18, 268), bold=True)
    bomb_rects = {}
    for i, sk in enumerate(BOMB_SKINS):
        x = 18 + i * (196 + 12)
        img = get_bomb_image(92, sk)
        owned = sk in SETTINGS.get("owned_bombs", ["fuse"])
        base = draw_skin_card(screen, x, 296, 196, 162, img, skin_card_label("bomb", sk),
                              selected=SETTINGS.get("bomb_skin") == sk,
                              hover=pygame.Rect(x, 296, 196, 162).collidepoint(mouse_pos),
                              pressed=mouse_down, ticks=ticks, locked=not owned)
        bomb_rects[sk] = base

    draw_text_crisp(screen, "FLAGS", FONT_BTN, MUTED, (18, 472), bold=True)
    flag_rects = {}
    for i, sk in enumerate(FLAG_SKINS):
        x = 18 + i * (196 + 12)
        img = get_flag_image(92, sk)
        owned = sk in SETTINGS.get("owned_flags", ["wave"])
        base = draw_skin_card(screen, x, 500, 196, 162, img, skin_card_label("flag", sk),
                              selected=SETTINGS.get("flag_skin") == sk,
                              hover=pygame.Rect(x, 500, 196, 162).collidepoint(mouse_pos),
                              pressed=mouse_down, ticks=ticks, locked=not owned)
        flag_rects[sk] = base

    shop_msg = get_shop_message()
    if shop_msg:
        draw_text_crisp(screen, shop_msg, FONT_MSG, GOLD_LIGHT, (18, 682), bold=True)
    else:
        draw_text_crisp(screen, "Win levels for pts - S / Esc back", FONT_MSG, MUTED, (18, 682), bold=True)
    return {"back": back, "theme_dark": td, "theme_light": tl,
            "levels": level_rects, "bombs": bomb_rects, "flags": flag_rects}


# --- Wi-Fi гонка ---
def race_message(race, text, dur=4.0):
    race["msg"] = text
    race["msg_until"] = time.time() + dur


def get_race_message(race):
    if race.get("msg") and time.time() < race.get("msg_until", 0):
        return race["msg"]
    return ""


def new_race_state():
    import random as _r
    ip = netplay.get_lan_ip() if netplay else "127.0.0.1"
    return {"role": None, "host": None, "client": None, "seed": None,
            "players": [], "table": [], "places": None, "reported": False,
            "connecting": False, "name": f"Player-{_r.randint(100, 999)}",
            "ip": "", "field": None, "msg": "", "msg_until": 0,
            "my_ip": ip, "frame": 0}


def leave_race(race):
    try:
        if race.get("host"):
            race["host"].stop()
    except Exception:
        pass
    try:
        if race.get("client"):
            race["client"].stop()
    except Exception:
        pass
    seed_keep_name, seed_keep_ip = race.get("name"), race.get("ip")
    my_ip = race.get("my_ip", "")
    race.clear()
    race.update(new_race_state())
    race["name"], race["ip"], race["my_ip"] = seed_keep_name, seed_keep_ip, my_ip


def draw_text_field(screen, x, y, w, h, text, active, placeholder=""):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, BTN_BG, rect, border_radius=10)
    pygame.draw.rect(screen, GOLD_LIGHT if active else HEADER_BORDER, rect,
                     3 if active else 2, border_radius=10)
    shown = text if text else placeholder
    col = BTN_FG if text else MUTED
    if shown:
        draw_text_crisp(screen, shown, FONT_BTN, col, (x + 14, rect.centery - 14), bold=True)
    if active and int(time.time() * 2) % 2 == 0:
        cx = x + 14 + get_font(FONT_BTN * 3, True).size(shown)[0] // 3 + 4 if shown else x + 14
        pygame.draw.line(screen, GOLD_LIGHT, (cx, y + 10), (cx, y + h - 10), 2)
    return rect


def draw_race_menu(screen, race, mouse_pos, mouse_down, ticks):
    screen.fill(HEADER_BG)
    pygame.draw.line(screen, GOLD, (0, 0), (WIDTH, 0), 2)
    draw_text_crisp(screen, "WI-FI RACE", FONT_INFO, FG, (18, 12), bold=True)
    draw_text_crisp(screen, "Same map for all - fastest wins!", FONT_MSG, MUTED, (18, 50), bold=True)
    back = draw_hint_button(screen, WIDTH - 150, 10, 132, 48, "BACK",
                            hover=pygame.Rect(WIDTH - 150, 10, 132, 48).collidepoint(mouse_pos),
                            pressed=mouse_down, ticks=ticks)
    draw_text_crisp(screen, f"My IP: {race['my_ip']}", FONT_MSG, GOLD_LIGHT, (18, 84), bold=True)
    draw_text_crisp(screen, "Name:", FONT_BTN, MUTED, (18, 120), bold=True)
    fname = draw_text_field(screen, 18, 148, 300, 50, race["name"],
                            race["field"] == "name")
    draw_text_crisp(screen, "Host IP:", FONT_BTN, MUTED, (330, 120), bold=True)
    fip = draw_text_field(screen, 330, 148, 292, 50, race["ip"],
                          race["field"] == "ip", placeholder="192.168.1.5")
    host_b = pygame.Rect(18, 218, 304, 54)
    join_b = pygame.Rect(318, 218, 304, 54)
    hb = draw_hint_button(screen, 18, 218, 304, 54, "HOST GAME [H]",
                          hover=host_b.collidepoint(mouse_pos),
                          pressed=mouse_down, ticks=ticks)
    jb = draw_hint_button(screen, 318, 218, 304, 54, "JOIN [J]",
                          hover=join_b.collidepoint(mouse_pos),
                          pressed=mouse_down, ticks=ticks)
    msg = get_race_message(race)
    if msg:
        draw_text_crisp(screen, msg, FONT_MSG, (248, 113, 113), (18, 292), bold=True)
    else:
        draw_text_crisp(screen, "Host shares IP - joiners type it. Esc - back",
                        FONT_MSG, MUTED, (18, 292), bold=True)
    return {"back": back, "host": hb, "join": jb, "fname": fname, "fip": fip}


def draw_lobby(screen, race, mouse_pos, mouse_down, ticks):
    screen.fill(HEADER_BG)
    pygame.draw.line(screen, GOLD, (0, 0), (WIDTH, 0), 2)
    draw_text_crisp(screen, "LOBBY", FONT_INFO, FG, (18, 12), bold=True)
    if race["role"] == "host":
        draw_text_crisp(screen, f"Tell friends your IP: {race['my_ip']}", FONT_MSG,
                        GOLD_LIGHT, (18, 50), bold=True)
    else:
        draw_text_crisp(screen, "Waiting for host to press START...", FONT_MSG,
                        GOLD_LIGHT, (18, 50), bold=True)
    y = 96
    for i, nm in enumerate(race.get("players", [])):
        you = " (YOU)" if nm == race["name"] else ""
        draw_text_crisp(screen, f"{i + 1}. {nm}{you}", FONT_BTN, FG, (18, y), bold=True)
        y += 36
    rects = {"players": race.get("players", [])}
    if race["role"] == "host":
        st = pygame.Rect(18, y + 10, 304, 54)
        rects["start"] = draw_hint_button(screen, 18, y + 10, 304, 54, "START [Space]",
                                          hover=st.collidepoint(mouse_pos),
                                          pressed=mouse_down, ticks=ticks)
    qb = pygame.Rect(WIDTH - 150, 10, 132, 48)
    rects["quit"] = draw_hint_button(screen, WIDTH - 150, 10, 132, 48, "QUIT",
                                     hover=qb.collidepoint(mouse_pos),
                                     pressed=mouse_down, ticks=ticks)
    msg = get_race_message(race)
    if msg:
        draw_text_crisp(screen, msg, FONT_MSG, (248, 113, 113), (18, y + 80), bold=True)
    return rects


def race_table_line(race):
    parts = []
    for row in race.get("table", []):
        nm = row["name"] + ("*" if row["name"] == race["name"] else "")
        if row.get("finished"):
            st = f"{row['elapsed']:.1f}s" if row["elapsed"] >= 0 else "DNF"
        else:
            st = f"{row.get('opened', 0)}/{row.get('total', 0)}"
        parts.append(f"{nm} {st}")
    line = "RACE " + " | ".join(parts[:3])
    if len(parts) > 3:
        line += f" +{len(parts) - 3}"
    return line


def draw_race_hud(screen, race):
    pygame.draw.rect(screen, HEADER_BG, (0, 176, WIDTH, 30))
    draw_text_crisp(screen, race_table_line(race), FONT_MSG, GOLD_LIGHT, (18, 181), bold=True)


def draw_race_result(screen, race, mouse_pos, mouse_down, ticks):
    screen.fill(HEADER_BG)
    pygame.draw.line(screen, GOLD, (0, 0), (WIDTH, 0), 2)
    places = race.get("places") or []
    winners = [p for p in places if p["elapsed"] >= 0]
    if winners:
        w = winners[0]
        draw_text_crisp(screen, f"WINNER {w['name']} {w['elapsed']:.1f}s",
                        FONT_INFO, GOLD_LIGHT, (18, 14), bold=True)
    else:
        draw_text_crisp(screen, "Everyone DNF!", FONT_INFO, (248, 113, 113), (18, 14), bold=True)
    y = 70
    medals = ["1st", "2nd", "3rd"]
    for i, p in enumerate(places):
        tag = medals[i] if i < 3 else f"{i + 1}th"
        res = f"{p['elapsed']:.1f}s" if p["elapsed"] >= 0 else "DNF"
        you = " (YOU)" if p["name"] == race["name"] else ""
        col = GOLD_LIGHT if i == 0 and winners else FG
        draw_text_crisp(screen, f"{tag}  {p['name']}{you}  {res}", FONT_BTN, col, (18, y), bold=True)
        y += 38
    qb = pygame.Rect(18, y + 16, 220, 52)
    back = draw_hint_button(screen, 18, y + 16, 220, 52, "QUIT [Esc]",
                            hover=qb.collidepoint(mouse_pos),
                            pressed=mouse_down, ticks=ticks)
    return {"back": back}


def main():
    pygame.init()
    pygame.display.set_caption("Сапёр — уровни, очки и магазин скинов")
    load_settings()  # тема + скины из файла
    # большее окно + сглаживание за счёт крупного CELL
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    # шрифты крупнее; основной текст идёт через draw_text_crisp (суперсэмплинг x3)
    font = pygame.font.SysFont("arial", FONT_CELL, bold=True)
    small_font = pygame.font.SysFont("arial", FONT_INFO, bold=True)
    tiny_font = pygame.font.SysFont("arial", FONT_BTN, bold=True)
    # предсоздаём картинки в высоком качестве
    get_bomb_image()
    get_flag_image()

    board = create_empty_board()
    rects = {"face": None, "safe": None, "mine": None, "shield": None,
             "skins": None, "race": None}
    mode = "game"  # game | skins | race | lobby | race_game | race_result
    cheat_buf = ""  # чит HESOYAM набирается буквами
    race = new_race_state()

    def race_host_game():
        nonlocal board, mode
        if netplay is None:
            race_message(race, "netplay.py missing")
            return
        name = race["name"].strip() or "Player"
        race["name"] = name
        try:
            h = netplay.RaceHost(name, SETTINGS.get("difficulty", "normal"))
            h.serve()
        except OSError:
            race_message(race, "Port busy - close other host")
            return
        race["host"] = h
        race["role"] = "host"
        race["diff"] = SETTINGS.get("difficulty", "normal")
        race["players"] = [name]
        race["table"] = [{"name": name, "opened": 0,
                          "total": ROWS * COLS - MINES,
                          "finished": False, "elapsed": -1}]
        mode = "lobby"

    def race_join_game():
        nonlocal mode
        if netplay is None:
            race_message(race, "netplay.py missing")
            return
        name = race["name"].strip() or "Player"
        race["name"] = name
        ip = race["ip"].strip() or "127.0.0.1"
        c = netplay.RaceClient(ip, name)
        race["client"] = c
        race["role"] = "client"
        race["connecting"] = True
        c.connect()

    def race_start_host():
        nonlocal board, mode, cheat_buf
        apply_difficulty(race.get("diff", SETTINGS.get("difficulty", "normal")))
        race["host"].start_race()
        board = build_race_board(race["host"].seed)
        board["start_time"] = time.time()
        race["reported"] = False
        race["table"] = []
        cheat_buf = ""
        mode = "race_game"

    running = True
    while running:
        # окно подстраивается под уровень (размер поля)
        if screen.get_size() != (WIDTH, HEIGHT):
            screen = pygame.display.set_mode((WIDTH, HEIGHT))
        mouse_pos = pygame.mouse.get_pos()
        mouse_down = pygame.mouse.get_pressed()[0]
        ticks = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                k = event.key
                if mode == "race":
                    # меню гонки: поля ввода или хоткеи
                    if race["field"]:
                        fld = race["field"]
                        if k == pygame.K_ESCAPE:
                            race["field"] = None
                        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if fld == "name":
                                race["field"] = "ip"
                            else:
                                race["field"] = None
                                race_join_game()
                        elif k == pygame.K_BACKSPACE:
                            race[fld] = race[fld][:-1]
                        elif event.unicode and len(event.unicode) == 1:
                            ch = event.unicode
                            if fld == "name" and len(race[fld]) < 12 and (
                                    ch.isalnum() or ch in "_- "):
                                race[fld] += ch
                            elif fld == "ip" and len(race[fld]) < 15 and (
                                    ch.isdigit() or ch == "."):
                                race[fld] += ch
                    else:
                        if k == pygame.K_ESCAPE:
                            mode = "game"
                        elif k == pygame.K_h:
                            race_host_game()
                        elif k == pygame.K_j:
                            race_join_game()
                        elif k == pygame.K_t:
                            toggle_theme()
                elif mode == "lobby":
                    if k == pygame.K_ESCAPE:
                        leave_race(race)
                        mode = "race"
                    elif k == pygame.K_SPACE and race["role"] == "host":
                        race_start_host()
                    elif k == pygame.K_t:
                        toggle_theme()
                elif mode == "race_game":
                    if k == pygame.K_ESCAPE:
                        leave_race(race)
                        mode = "race"
                    elif k == pygame.K_1:
                        use_safe_hint(board)
                    elif k == pygame.K_2:
                        use_mine_hint(board)
                    elif k == pygame.K_3:
                        toggle_shield(board)
                    elif k == pygame.K_t:
                        toggle_theme()
                elif mode == "race_result":
                    if k == pygame.K_ESCAPE:
                        leave_race(race)
                        mode = "race"
                    elif k == pygame.K_t:
                        toggle_theme()
                elif mode == "skins":
                    if k == pygame.K_ESCAPE:
                        mode = "game"
                    elif k == pygame.K_s:
                        mode = "game"
                    elif k == pygame.K_t:
                        toggle_theme()
                elif mode == "game":
                    if k == pygame.K_ESCAPE:
                        pass
                    elif k == pygame.K_s and not (
                            "hesoyam".startswith(cheat_buf + "s")):
                        # S внутри слова HESOYAM — часть чита, а не меню
                        mode = "skins"
                    elif k == pygame.K_g:
                        race["field"] = None
                        mode = "race"
                    elif k == pygame.K_t:
                        toggle_theme()
                    elif k == pygame.K_r:
                        board = create_empty_board()
                        cheat_buf = ""
                    elif k == pygame.K_1:
                        use_safe_hint(board)
                    elif k == pygame.K_2:
                        use_mine_hint(board)
                    elif k == pygame.K_3:
                        toggle_shield(board)
                    # чит HESOYAM: просто набери буквы на клавиатуре
                    if event.unicode and event.unicode.isalpha():
                        cheat_buf = (cheat_buf + event.unicode.lower())[-7:]
                        if cheat_buf == "hesoyam":
                            cheat_win(board)
                            cheat_buf = ""
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if mode == "race":
                    if rects.get("back") and rects["back"].collidepoint(mx, my):
                        race["field"] = None
                        mode = "game"
                        continue
                    if rects.get("fname") and rects["fname"].collidepoint(mx, my):
                        race["field"] = "name"
                        continue
                    if rects.get("fip") and rects["fip"].collidepoint(mx, my):
                        race["field"] = "ip"
                        continue
                    race["field"] = None
                    if rects.get("host") and rects["host"].collidepoint(mx, my):
                        race_host_game()
                        continue
                    if rects.get("join") and rects["join"].collidepoint(mx, my):
                        race_join_game()
                        continue
                    continue
                if mode == "lobby":
                    if rects.get("quit") and rects["quit"].collidepoint(mx, my):
                        leave_race(race)
                        mode = "race"
                        continue
                    if (rects.get("start") and race["role"] == "host"
                            and rects["start"].collidepoint(mx, my)):
                        race_start_host()
                        continue
                    continue
                if mode == "race_result":
                    if rects.get("back") and rects["back"].collidepoint(mx, my):
                        leave_race(race)
                        mode = "race"
                        continue
                    continue
                if mode == "skins":
                    if rects.get("back") and rects["back"].collidepoint(mx, my):
                        mode = "game"
                        continue
                    if rects.get("theme_dark") and rects["theme_dark"].collidepoint(mx, my):
                        apply_theme("dark")
                        save_settings()
                        continue
                    if rects.get("theme_light") and rects["theme_light"].collidepoint(mx, my):
                        apply_theme("light")
                        save_settings()
                        continue
                    _handled = False
                    for key, rc in rects.get("levels", {}).items():
                        if rc.collidepoint(mx, my):
                            if SETTINGS.get("difficulty") != key:
                                apply_difficulty(key)
                                save_settings()
                                board = create_empty_board()
                                cheat_buf = ""
                            mode = "game"
                            _handled = True
                            break
                    if _handled:
                        continue
                    for sk, rc in rects.get("bombs", {}).items():
                        if rc.collidepoint(mx, my):
                            buy_or_select("bomb", sk)
                            break
                    for sk, rc in rects.get("flags", {}).items():
                        if rc.collidepoint(mx, my):
                            buy_or_select("flag", sk)
                            break
                    continue
                if mode == "game" and rects["face"] and rects["face"].collidepoint(mx, my):
                    board = create_empty_board()
                    cheat_buf = ""
                    continue
                # клики по кнопкам подсказок (и в гонке тоже)
                if rects["safe"] and rects["safe"].collidepoint(mx, my):
                    use_safe_hint(board)
                    continue
                if rects["mine"] and rects["mine"].collidepoint(mx, my):
                    use_mine_hint(board)
                    continue
                if rects["shield"] and rects["shield"].collidepoint(mx, my):
                    toggle_shield(board)
                    continue
                if mode == "game" and rects.get("skins") and rects["skins"].collidepoint(mx, my):
                    mode = "skins"
                    continue
                if mode == "game" and rects.get("race") and rects["race"].collidepoint(mx, my):
                    race["field"] = None
                    mode = "race"
                    continue
                if my < HEADER:
                    continue
                c = (mx - BOARD_X) // CELL
                r = (my - HEADER) // CELL
                if 0 <= r < ROWS and 0 <= c < COLS:
                    if event.button == 1:  # левая
                        if board["opened"][r][c]:
                            chord_open(board, r, c)
                        else:
                            open_cell(board, r, c)
                    elif event.button == 2:  # средняя (колесо) — тоже хорд
                        chord_open(board, r, c)
                    elif event.button == 3:  # правая
                        toggle_flag(board, r, c)

        # --- сетевые события гонки ---
        if race["role"] == "host" and race["host"]:
            while True:
                try:
                    ev = race["host"].events.get_nowait()
                except queue.Empty:
                    break
                if ev.get("t") == "table":
                    race["table"] = ev["rows"]
                    race["players"] = [r["name"] for r in ev["rows"]]
                elif ev.get("t") == "result":
                    race["places"] = ev["places"]
                    mode = "race_result"
        elif race["role"] == "client" and race["client"]:
            while True:
                try:
                    ev = race["client"].events.get_nowait()
                except queue.Empty:
                    break
                t = ev.get("t")
                if t == "welcome":
                    apply_difficulty(ev.get("diff", "normal"))
                    save_settings()
                    race["seed"] = ev["seed"]
                    race["players"] = ev.get("players", [])
                    race["connecting"] = False
                    mode = "lobby"
                elif t == "players":
                    race["players"] = ev.get("players", [])
                elif t == "table":
                    race["table"] = ev["rows"]
                    race["players"] = [r["name"] for r in ev["rows"]]
                elif t == "start":
                    board = build_race_board(race["seed"])
                    board["start_time"] = time.time()
                    race["reported"] = False
                    race["table"] = []
                    mode = "race_game"
                elif t == "result":
                    race["places"] = ev["places"]
                    mode = "race_result"
                elif t in ("bye", "disconnected"):
                    race_message(race, "Host left the race")
                    leave_race(race)
                    mode = "race"
                elif t == "conn_fail":
                    race_message(race, "No connection - check IP")
                    race["client"] = None
                    race["role"] = None
                    race["connecting"] = False
                elif t == "join_error":
                    race_message(race, str(ev.get("msg", "join failed")))
                    race["client"] = None
                    race["role"] = None
                    race["connecting"] = False

        # --- прогресс и финиш гонки ---
        if mode == "race_game":
            race["frame"] += 1
            opened = sum(sum(row) for row in board["opened"])
            total = ROWS * COLS - MINES
            if not board["game_over"] and race["frame"] % 30 == 0:
                if race["role"] == "host" and race["host"]:
                    race["host"].report_self(opened, total)
                elif race["role"] == "client" and race["client"]:
                    race["client"].send_progress(opened, total)
            if board["game_over"] and not race["reported"]:
                race["reported"] = True
                el = board["elapsed"] if board["won"] else -1
                if race["role"] == "host" and race["host"]:
                    race["host"].report_self(opened, total, True, el)
                elif race["role"] == "client" and race["client"]:
                    race["client"].send_finish(el)

        if mode == "skins":
            rects = draw_skins_menu(screen, mouse_pos, mouse_down, ticks)
        elif mode == "race":
            rects = draw_race_menu(screen, race, mouse_pos, mouse_down, ticks)
        elif mode == "lobby":
            rects = draw_lobby(screen, race, mouse_pos, mouse_down, ticks)
        elif mode == "race_result":
            rects = draw_race_result(screen, race, mouse_pos, mouse_down, ticks)
        else:
            rects = draw(screen, font, small_font, tiny_font, board,
                         mouse_pos=mouse_pos, mouse_down=mouse_down, ticks=ticks)
            if mode == "race_game":
                draw_race_hud(screen, race)
        pygame.display.flip()
        clock.tick(60)

    if race["role"]:
        leave_race(race)
    pygame.quit()


if __name__ == "__main__":
    main()
