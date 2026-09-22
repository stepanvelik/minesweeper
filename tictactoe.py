#!/usr/bin/env python3
"""Крестики-нолики: локальный матч или матч с другом по Wi-Fi."""
import queue
import time
import pygame
import tictactoe_netplay as network

W, H, FPS = 640, 720, 60
BG, PANEL, BTN, BORDER = (25, 33, 52), (15, 23, 42), (36, 49, 73), (71, 85, 105)
FG, MUTED, GOLD, GREEN, RED, BLUE = (255, 255, 255), (148, 163, 184), (245, 158, 11), (74, 222, 128), (248, 113, 113), (96, 165, 250)


def font(size, bold=True): return pygame.font.SysFont("arial", size, bold=bold)
def text(s, value, size, color, pos, center=False):
    image = font(size).render(value, True, color); rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos); s.blit(image, rect)

def button(s, rect, label, mouse, disabled=False):
    hover = rect.collidepoint(mouse) and not disabled
    pygame.draw.rect(s, (30, 41, 59) if disabled else (48, 63, 91) if hover else BTN, rect, border_radius=11)
    pygame.draw.rect(s, BORDER if disabled else GOLD if hover else BORDER, rect, 3 if hover else 2, border_radius=11)
    text(s, label, 20, MUTED if disabled else FG, rect.center, True)
    return hover

def check(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] and board[a] == board[b] == board[c]: return board[a], (a,b,c)
    return ("DRAW", ()) if all(board) else (None, ())

def valid_ip(value):
    if value.lower() == "localhost": return "127.0.0.1"
    parts = value.split(".")
    return value if len(parts) == 4 and all(x.isdigit() and 0 <= int(x) <= 255 for x in parts) else None

def main():
    pygame.init(); screen = pygame.display.set_mode((W, H)); pygame.display.set_caption("Крестики-нолики — Wi-Fi")
    clock = pygame.time.Clock(); board = [None] * 9; scene = "menu"; turn = "X"; winner, line = None, ()
    role = peer = None; player, opponent = "Player", "Opponent"; name, ip, editing = "Player", "", None; status = ""; status_until = 0
    rects = {}
    def message(value, seconds=3):
        nonlocal status, status_until
        status, status_until = value, time.time() + seconds
    def reset(first="X"):
        nonlocal board, turn, winner, line
        board, turn, winner, line = [None]*9, first, None, ()
    def send(value):
        if peer: peer.send(value)
    def leave():
        nonlocal peer, role
        if peer: peer.stop()
        peer, role = None, None
    running = True
    while running:
        mouse = pygame.mouse.get_pos(); click = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if scene == "game": leave(); scene = "menu"
                    elif scene != "menu": scene = "menu"
                    editing = None
                elif editing:
                    if event.key == pygame.K_BACKSPACE:
                        if editing == "name": name = name[:-1]
                        else: ip = ip[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): editing = None
                    elif event.unicode and len(event.unicode) == 1:
                        if editing == "name" and len(name) < 16 and (event.unicode.isalnum() or event.unicode in "_-"): name += event.unicode
                        elif editing == "ip" and len(ip) < 15 and (event.unicode.isdigit() or event.unicode == "."): ip += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: click = True
        if peer:
            while True:
                try: event = peer.events.get_nowait()
                except queue.Empty: break
                kind = event.get("t")
                if kind == "joined": opponent = event["name"]; reset("X"); scene = "game"; message(f"{opponent} joined. You are X")
                elif kind == "welcome": opponent = event.get("host", "Host"); player = name or "Player"; reset("X"); scene = "game"; message(f"Connected to {opponent}. You are O")
                elif kind == "move":
                    cell, mark = event.get("cell"), event.get("mark")
                    if isinstance(cell, int) and 0 <= cell < 9 and not board[cell]:
                        board[cell] = mark; winner, line = check(board); turn = "O" if mark == "X" else "X"
                elif kind == "rematch": reset(event.get("first", "X")); message("Rematch started")
                elif kind == "error": message(event.get("msg", "Network error")); leave(); scene = "wifi"
                elif kind == "left":
                    if scene == "game": message("Opponent left"); leave(); scene = "wifi"
        screen.fill(BG); pygame.draw.rect(screen, PANEL, (0, 0, W, 74)); pygame.draw.line(screen, GOLD, (0, 72), (W, 72), 2)
        text(screen, "MINI GAMES", 26, FG, (20, 20)); text(screen, "TIC-TAC-TOE", 16, GOLD, (20, 49))
        if scene == "menu":
            text(screen, "TIC-TAC-TOE", 42, FG, (W//2, 150), True); text(screen, "Play on one screen or challenge a friend on Wi-Fi", 19, MUTED, (W//2, 190), True)
            rects = {"local": pygame.Rect(110,250,420,64), "wifi": pygame.Rect(110,330,420,64)}
            button(screen, rects["local"], "LOCAL MATCH", mouse); button(screen, rects["wifi"], "WI-FI MATCH", mouse)
            text(screen, "X goes first. Three in a row wins.", 18, MUTED, (W//2, 440), True)
        elif scene == "wifi":
            text(screen, "WI-FI MATCH", 34, FG, (W//2, 130), True); text(screen, f"Your IP: {network.lan_ip()}  •  port {network.PORT}", 18, GOLD, (W//2, 172), True)
            rects = {"name":pygame.Rect(110,220,420,52), "ip":pygame.Rect(110,294,420,52), "host":pygame.Rect(110,380,202,58), "join":pygame.Rect(328,380,202,58), "back":pygame.Rect(110,466,420,50)}
            for key, label, value in (("name","Name",name),("ip","Host IP",ip)):
                r=rects[key]; pygame.draw.rect(screen, BTN, r, border_radius=10); pygame.draw.rect(screen, GOLD if editing==key else BORDER, r, 3 if editing==key else 2, border_radius=10); text(screen, value or label, 20, FG if value else MUTED, (r.x+15,r.y+15))
            button(screen, rects["host"], "HOST GAME", mouse); button(screen, rects["join"], "JOIN", mouse); button(screen, rects["back"], "BACK", mouse)
            text(screen, "Host tells the shown IP to one friend. Both players need the same Wi-Fi.", 16, MUTED, (W//2, 548), True)
        else:
            me = "X" if role == "host" else "O" if role == "client" else None
            headline = f"{winner} WINS!" if winner and winner != "DRAW" else "DRAW!" if winner else (f"YOUR TURN ({turn})" if not me or turn == me else f"{opponent}'S TURN ({turn})")
            text(screen, headline, 28, GREEN if winner else GOLD, (W//2, 110), True)
            origin, size = (95, 150), 150
            for i in range(9):
                r=pygame.Rect(origin[0]+(i%3)*size,origin[1]+(i//3)*size,size,size); pygame.draw.rect(screen, BTN, r); pygame.draw.rect(screen, GREEN if i in line else BORDER, r, 4)
                if board[i]: text(screen, board[i], 78, BLUE if board[i]=="X" else RED, r.center, True)
            rects={"again":pygame.Rect(110,620,202,54),"exit":pygame.Rect(328,620,202,54)}; button(screen,rects["again"],"REMATCH",mouse,not bool(winner)); button(screen,rects["exit"],"EXIT",mouse)
        if status and time.time() < status_until: text(screen, status, 18, RED if "error" in status.lower() or "cannot" in status.lower() else GREEN, (W//2, H-25), True)
        if click:
            if scene == "menu":
                if rects["local"].collidepoint(mouse): role=None; player="X"; opponent="O"; reset(); scene="game"
                elif rects["wifi"].collidepoint(mouse): scene="wifi"
            elif scene == "wifi":
                if rects["name"].collidepoint(mouse): editing="name"
                elif rects["ip"].collidepoint(mouse): editing="ip"
                elif rects["back"].collidepoint(mouse): scene="menu"
                elif rects["host"].collidepoint(mouse):
                    try: peer=network.Host(name or "Player"); peer.start(); role="host"; player=name or "Player"; message("Waiting for a friend to join…", 10)
                    except OSError: message("Port is busy")
                elif rects["join"].collidepoint(mouse):
                    address=valid_ip(ip)
                    if not address: message("Enter a valid IPv4 address")
                    else: peer=network.Client(address,name or "Player"); peer.start(); role="client"; message("Connecting…", 8)
            else:
                if rects["exit"].collidepoint(mouse): leave(); scene="menu"
                elif winner and rects["again"].collidepoint(mouse):
                    first = "O" if turn == "X" else "X"; reset(first); send({"t":"rematch","first":first})
                elif not winner:
                    ox,oy=95,150
                    if ox <= mouse[0] < ox+450 and oy <= mouse[1] < oy+450:
                        cell=(mouse[0]-ox)//150 + 3*((mouse[1]-oy)//150)
                        if not board[cell] and (not me or turn == me):
                            board[cell]=turn; mark=turn; winner,line=check(board); turn="O" if turn=="X" else "X"; send({"t":"move","cell":cell,"mark":mark})
        pygame.display.flip(); clock.tick(FPS)
    leave(); pygame.quit()

if __name__ == "__main__": main()
