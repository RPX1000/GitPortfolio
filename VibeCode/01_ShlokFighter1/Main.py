"""Shlok Fighter 1 - The Game.

Run this file to play:  python Main.py
The game code lives in the shlok_fighter package. It needs pygame (see requirements.txt).
"""

import pygame

from shlok_fighter.config import WIDTH, HEIGHT, FPS
from shlok_fighter.game import Game


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
    pygame.display.set_caption("Shlok Fighter 1 - The Game")
    clock = pygame.time.Clock()
    game = Game(screen)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                game.on_key(event.key)
        if game.wants_quit:
            running = False
        game.update(pygame.key.get_pressed())
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
