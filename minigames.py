#!/usr/bin/env python3
"""Точка входа для будущего набора мини-игр. Пока доступна игра Tic-Tac-Toe."""
import subprocess
import sys
import pygame

W, H = 640, 500
BG, PANEL, BTN, BORDER, FG, MUTED, GOLD = (25,33,52), (15,23,42), (36,49,73), (71,85,105), (255,255,255), (148,163,184), (245,158,11)
def draw_text(screen, value, size, color, pos, center=False):
    image=pygame.font.SysFont("arial",size,bold=True).render(value,True,color); screen.blit(image,image.get_rect(center=pos) if center else image.get_rect(topleft=pos))
def main():
    pygame.init(); screen=pygame.display.set_mode((W,H)); pygame.display.set_caption("Mini Games"); clock=pygame.time.Clock(); running=True
    cards=[("TIC-TAC-TOE", "Local and Wi-Fi multiplayer", True), ("MINESWEEPER", "Coming when modules are combined", False), ("MORE GAMES", "Reserved slot for a future mini-game", False)]
    while running:
        mouse=pygame.mouse.get_pos(); click=False
        for event in pygame.event.get():
            if event.type==pygame.QUIT: running=False
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1: click=True
        screen.fill(BG); pygame.draw.rect(screen,PANEL,(0,0,W,95)); pygame.draw.line(screen,GOLD,(0,93),(W,93),2); draw_text(screen,"MINI GAMES",32,FG,(24,22)); draw_text(screen,"Choose a game",18,MUTED,(25,59))
        for i,(title,subtitle,enabled) in enumerate(cards):
            rect=pygame.Rect(70,120+i*112,500,88); hover=rect.collidepoint(mouse) and enabled
            pygame.draw.rect(screen,(48,63,91) if hover else BTN,rect,border_radius=12); pygame.draw.rect(screen,GOLD if hover else BORDER,rect,3 if hover else 2,border_radius=12)
            draw_text(screen,title,24,FG if enabled else MUTED,(92,138)); draw_text(screen,subtitle,16,MUTED,(92,171)); draw_text(screen,"PLAY" if enabled else "SOON",18,GOLD if enabled else MUTED,(520,164),True)
            if click and enabled and rect.collidepoint(mouse): pygame.quit(); subprocess.call([sys.executable,"tictactoe.py"]); return
        pygame.display.flip(); clock.tick(60)
    pygame.quit()
if __name__ == "__main__": main()
