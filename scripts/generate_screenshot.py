"""Generate a professional screenshot for Gatekeeper HA repo.

Renders a mock of the gatekeeper-card as it appears inside a Home Assistant
Lovelace dashboard. Uses the qrcode library to render a real, scannable QR
code (locally — no network) so the screenshot matches the actual card output.

Usage: python scripts/generate_screenshot.py [output_path]
Default output: <repo>/docs/screenshot.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Canvas - matches a typical Lovelace dashboard column on desktop
W, H = 1200, 720

# Home Assistant dark theme palette
BG_TOP = (24, 26, 31)
BG_BOTTOM = (15, 17, 21)
CARD_BG = (31, 34, 41)
CARD_BORDER = (52, 56, 66)
TEXT_PRIMARY = (236, 239, 244)
TEXT_SECONDARY = (155, 162, 175)
TEXT_MUTED = (110, 117, 128)
DIVIDER = (52, 56, 66)
HA_BLUE = (3, 169, 244)  # Home Assistant primary accent
HA_BLUE_DIM = (2, 119, 189)
ACCENT_PURPLE = (124, 92, 240)
ACCENT_PURPLE_HOVER = (143, 115, 247)
GREEN = (76, 175, 80)
GREEN_DARK = (27, 94, 32)
GREEN_LIGHT = (165, 214, 167)
ORANGE = (255, 152, 0)
ROW_BG = (38, 41, 49)
ROW_BG_HOVER = (45, 48, 57)
BUTTON_GHOST = (58, 62, 73)


# ---------- Fonts ----------

def _find_font(candidates: list[tuple[str, ...]]) -> str | None:
    for paths in candidates:
        for p in paths:
            if os.path.exists(p):
                return p
    return None


# Prefer Roboto (Home Assistant's actual font), then good fallbacks.
ROBOTO_REGULAR = _find_font([
    ("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
     "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
     "/System/Library/Fonts/Supplemental/Arial.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
])
ROBOTO_MEDIUM = _find_font([
    ("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Medium.ttf",
     "/usr/share/fonts/truetype/roboto/Roboto-Medium.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
])
ROBOTO_BOLD = _find_font([
    ("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
     "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
])


def font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(ROBOTO_MEDIUM, 26)
F_BODY = font(ROBOTO_REGULAR, 16)
F_BODY_MED = font(ROBOTO_MEDIUM, 16)
F_SMALL = font(ROBOTO_REGULAR, 13)
F_SMALL_MED = font(ROBOTO_MEDIUM, 13)
F_MICRO = font(ROBOTO_REGULAR, 11)
F_BANNER = font(ROBOTO_MEDIUM, 15)
F_BTN = font(ROBOTO_MEDIUM, 13)
F_TAB = font(ROBOTO_MEDIUM, 14)


# ---------- Helpers ----------

def vgrad(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    base = Image.new("RGB", size, bottom)
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px_color = (
            int(top[0] * (1 - t) + bottom[0] * t),
            int(top[1] * (1 - t) + bottom[1] * t),
            int(top[2] * (1 - t) + bottom[2] * t),
        )
        for x in range(w):
            px[x, y] = px_color
    return base


def drop_shadow(img: Image.Image, box: tuple[int, int, int, int], radius: int = 18,
                blur: int = 22, opacity: int = 90) -> None:
    """Paint a soft drop shadow behind the rectangle defined by box onto img."""
    x1, y1, x2, y2 = box
    pad = blur * 2
    shadow = Image.new("RGBA", (x2 - x1 + pad * 2, y2 - y1 + pad * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [pad, pad + 6, pad + (x2 - x1), pad + (y2 - y1) + 6],
        radius=radius, fill=(0, 0, 0, opacity),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    img.paste(shadow, (x1 - pad, y1 - pad), shadow)


def text_w(draw: ImageDraw.ImageDraw, s: str, fnt: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(s, font=fnt))


# ---------- Build canvas ----------

bg = vgrad((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")

# Very subtle radial glow behind the card
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([W // 2 - 380, -120, W // 2 + 380, 360], fill=(3, 169, 244, 18))
glow = glow.filter(ImageFilter.GaussianBlur(60))
bg = Image.alpha_composite(bg, glow)

draw = ImageDraw.Draw(bg)


# ---------- HA top app bar ----------
APPBAR_H = 56
draw.rectangle([0, 0, W, APPBAR_H], fill=(20, 22, 27))
draw.rectangle([0, APPBAR_H, W, APPBAR_H + 1], fill=(40, 44, 53))

# Hamburger
for i, y in enumerate((18, 26, 34)):
    draw.rounded_rectangle([22, y, 42, y + 2], radius=1, fill=TEXT_SECONDARY)

# App title
draw.text((60, 16), "Home", font=F_TITLE, fill=TEXT_PRIMARY)

# Tabs
tabs = [("Overview", False), ("Security", True), ("Energy", False), ("Map", False)]
tx = 200
for name, active in tabs:
    tw = text_w(draw, name, F_TAB)
    if active:
        # Active tab indicator bar
        draw.rounded_rectangle([tx - 14, APPBAR_H - 3, tx + tw + 14, APPBAR_H], radius=1, fill=HA_BLUE)
        draw.text((tx, 19), name, font=F_TAB, fill=TEXT_PRIMARY)
    else:
        draw.text((tx, 19), name, font=F_TAB, fill=TEXT_SECONDARY)
    tx += tw + 36

# App bar right icons (bell, user)
for cx in (W - 80, W - 40):
    draw.ellipse([cx - 12, 16, cx + 12, 40], outline=TEXT_SECONDARY, width=1)


# ---------- Card geometry ----------
CARD_W = 460
CARD_X = (W - CARD_W) // 2
CARD_Y = APPBAR_H + 36

# Compute height after we lay out content; pre-compute now.
PAD = 22
header_h = 50
banner_h = 44
section_h = 28
token_h = 60
n_tokens = 2
divider_h = 24
qr_label_h = 22
qr_box_h = 196
bottom_pad = 22

content_h = (
    PAD + header_h + 14 + banner_h + 22 + section_h + 10
    + token_h * n_tokens + (n_tokens - 1) * 8
    + divider_h + qr_label_h + 12 + qr_box_h + bottom_pad
)
CARD_H = content_h

# Drop shadow
drop_shadow(bg, (CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H), radius=14, blur=28, opacity=110)

# Card body
draw = ImageDraw.Draw(bg)
draw.rounded_rectangle(
    [CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H],
    radius=14, fill=CARD_BG, outline=CARD_BORDER, width=1,
)


# ---------- Header ----------
hx = CARD_X + PAD
hy = CARD_Y + PAD

# Icon disc
draw.ellipse([hx, hy + 2, hx + 34, hy + 36], fill=(40, 80, 130))
# Shield icon (simple home/lock glyph)
sx, sy = hx + 8, hy + 9
draw.polygon([(sx + 9, sy + 1), (sx + 17, sy + 5), (sx + 17, sy + 13),
              (sx + 9, sy + 19), (sx + 1, sy + 13), (sx + 1, sy + 5)],
             fill=HA_BLUE)
# Inner check
draw.line([(sx + 5, sy + 9), (sx + 8, sy + 12), (sx + 13, sy + 6)],
          fill=(255, 255, 255), width=2)

# Title
draw.text((hx + 46, hy + 4), "Guest Access", font=F_TITLE, fill=TEXT_PRIMARY)

# Mode label + toggle
tg_label = "Guest Mode"
tg_label_w = text_w(draw, tg_label, F_SMALL)
toggle_w = 38
toggle_h = 22
tg_x = CARD_X + CARD_W - PAD - toggle_w
tg_y = hy + 10
draw.text((tg_x - tg_label_w - 10, tg_y + 3), tg_label, font=F_SMALL, fill=TEXT_SECONDARY)
# Toggle track (active green)
draw.rounded_rectangle([tg_x, tg_y, tg_x + toggle_w, tg_y + toggle_h],
                       radius=toggle_h // 2, fill=GREEN)
# Toggle knob (right) with subtle shadow
draw.ellipse([tg_x + toggle_w - toggle_h - 1, tg_y - 1,
              tg_x + toggle_w + 1, tg_y + toggle_h + 1], fill=(255, 255, 255))


# ---------- Active banner ----------
by = CARD_Y + PAD + header_h + 14
bx1 = CARD_X + PAD
bx2 = CARD_X + CARD_W - PAD
# Banner with left accent stripe
draw.rounded_rectangle([bx1, by, bx2, by + banner_h], radius=10, fill=(26, 56, 32))
draw.rounded_rectangle([bx1, by, bx1 + 4, by + banner_h], radius=2, fill=GREEN)

# Active dot
draw.ellipse([bx1 + 18, by + banner_h // 2 - 4, bx1 + 26, by + banner_h // 2 + 4], fill=GREEN_LIGHT)
draw.text((bx1 + 34, by + 13), "Guest mode active", font=F_BANNER, fill=GREEN_LIGHT)
rem_txt = "47h 22m remaining"
rem_w = text_w(draw, rem_txt, F_BANNER)
draw.text((bx2 - rem_w - 14, by + 13), rem_txt, font=F_BANNER, fill=GREEN_LIGHT)


# ---------- Active tokens section ----------
sy = by + banner_h + 22
draw.text((bx1, sy), "Active Tokens", font=F_BODY_MED, fill=TEXT_PRIMARY)
count_txt = " (2)"
count_x = bx1 + text_w(draw, "Active Tokens", F_BODY_MED)
draw.text((count_x, sy), count_txt, font=F_BODY, fill=TEXT_MUTED)

# New Token button
btn_label = "+ New Token"
btn_pad_x = 14
btn_h = 30
btn_w = text_w(draw, btn_label, F_BTN) + btn_pad_x * 2
btn_x = bx2 - btn_w
btn_y = sy - 5
draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=8, fill=ACCENT_PURPLE)
draw.text((btn_x + btn_pad_x, btn_y + 8), btn_label, font=F_BTN, fill=(255, 255, 255))


# ---------- Token rows ----------
ty = sy + section_h + 10
tokens = [
    ("Plumber Wed", "Expires in 3h 15m", "0 uses", GREEN, "🔧"),
    ("Uncle Bob weekend", "Expires in 26h 40m", "5 uses", ORANGE, "👤"),
]

for label, expiry, uses, color, _icon in tokens:
    # Row
    draw.rounded_rectangle([bx1, ty, bx2, ty + token_h], radius=10, fill=ROW_BG)
    # Left accent
    draw.rounded_rectangle([bx1, ty + 8, bx1 + 4, ty + token_h - 8], radius=2, fill=color)

    # Small avatar disc
    av_x, av_y = bx1 + 16, ty + 14
    av_d = 32
    draw.ellipse([av_x, av_y, av_x + av_d, av_y + av_d], fill=(60, 64, 75))
    # Initials
    initials = "".join(w[0] for w in label.split()[:2]).upper()
    iw = text_w(draw, initials, F_SMALL_MED)
    draw.text((av_x + (av_d - iw) // 2, av_y + 8), initials, font=F_SMALL_MED, fill=TEXT_PRIMARY)

    # Label + meta
    draw.text((bx1 + 60, ty + 12), label, font=F_BODY_MED, fill=TEXT_PRIMARY)

    # Meta with separator dot
    meta_y = ty + 33
    draw.text((bx1 + 60, meta_y), expiry, font=F_SMALL, fill=TEXT_SECONDARY)
    exp_w = text_w(draw, expiry, F_SMALL)
    dot_x = bx1 + 60 + exp_w + 8
    draw.ellipse([dot_x, meta_y + 7, dot_x + 3, meta_y + 10], fill=TEXT_MUTED)
    draw.text((dot_x + 9, meta_y), uses, font=F_SMALL, fill=TEXT_SECONDARY)

    # Revoke button (ghost)
    rev_label = "Revoke"
    rev_pad = 12
    rev_w = text_w(draw, rev_label, F_BTN) + rev_pad * 2
    rev_h = 28
    rev_x = bx2 - rev_w - 10
    rev_y = ty + (token_h - rev_h) // 2
    draw.rounded_rectangle([rev_x, rev_y, rev_x + rev_w, rev_y + rev_h],
                           radius=6, outline=(80, 84, 95), width=1)
    draw.text((rev_x + rev_pad, rev_y + 7), rev_label, font=F_BTN, fill=TEXT_SECONDARY)

    ty += token_h + 8


# ---------- Divider ----------
dy = ty + 14
draw.rectangle([bx1, dy, bx2, dy + 1], fill=DIVIDER)


# ---------- QR section ----------
ql_y = dy + 16
ql_text = "Share this QR for guest access"
qlw = text_w(draw, ql_text, F_SMALL)
draw.text((CARD_X + (CARD_W - qlw) // 2, ql_y), ql_text, font=F_SMALL, fill=TEXT_SECONDARY)

# Real QR code rendered locally
qr_data = "https://gatekeeper.home.lan/guest?t=8f3b9c1a2d6e4a7b"
qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=10,
    border=2,
)
qr.add_data(qr_data)
qr.make(fit=True)
qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

# White card behind QR
qr_card_size = 168
qr_card_x = CARD_X + (CARD_W - qr_card_size) // 2
qr_card_y = ql_y + qr_label_h + 6
draw.rounded_rectangle(
    [qr_card_x, qr_card_y, qr_card_x + qr_card_size, qr_card_y + qr_card_size],
    radius=10, fill=(255, 255, 255),
)

# Resize QR to fit inside the white card with padding
qr_inner = qr_card_size - 24
qr_img = qr_img.resize((qr_inner, qr_inner), Image.NEAREST)
bg.paste(qr_img, (qr_card_x + 12, qr_card_y + 12), qr_img)


# ---------- Save ----------
repo_root = Path(__file__).resolve().parent.parent
default_out = repo_root / "docs" / "screenshot.png"
out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
out_path.parent.mkdir(parents=True, exist_ok=True)

# Final flatten to RGB
final = Image.new("RGB", (W, H), BG_BOTTOM)
final.paste(bg.convert("RGB"))
final.save(out_path, optimize=True)
print(f"Saved: {out_path}")
print(f"Size: {final.size}")
