"""Generate a professional screenshot for Gatekeeper HA repo.

Usage: python scripts/generate_screenshot.py [output_path]
Default output: <repo>/docs/screenshot.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = 1280
H = 800

img = Image.new("RGB", (W, H), (17, 17, 17))
draw = ImageDraw.Draw(img)

# Try to load a nice font
font_paths = [
    # macOS
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    # Windows
    "C:\\Windows\\Fonts\\arial.ttf",
]
title_font = None
body_font = None
small_font = None
for fp in font_paths:
    if os.path.exists(fp):
        title_font = ImageFont.truetype(fp, 28)
        body_font = ImageFont.truetype(fp, 18)
        small_font = ImageFont.truetype(fp, 14)
        break
if not title_font:
    title_font = body_font = small_font = ImageFont.load_default()

# Card background
card_x, card_y = 240, 60
card_w, card_h = 560, 680
draw.rounded_rectangle(
    [card_x, card_y, card_x + card_w, card_y + card_h],
    radius=16, fill=(26, 26, 26), outline=(40, 40, 40)
)

# Header
draw.text((card_x + 28, card_y + 28), "🏠  Guest Access", font=title_font, fill=(238, 238, 238))

# Guest Mode toggle label + switch
mode_text = "Guest Mode"
mode_switch_x = card_x + card_w - 100
mode_switch_y = card_y + 30
draw.text((mode_switch_x - 90, mode_switch_y), mode_text, font=small_font, fill=(150, 150, 150))
draw.rounded_rectangle([mode_switch_x, mode_switch_y - 2, mode_switch_x + 44, mode_switch_y + 22], radius=12, fill=(46, 125, 50))
draw.ellipse([mode_switch_x + 22, mode_switch_y, mode_switch_x + 42, mode_switch_y + 20], fill=(165, 214, 167))

# Mode banner
banner_y = card_y + 80
draw.rounded_rectangle(
    [card_x + 28, banner_y, card_x + card_w - 28, banner_y + 40],
    radius=10, fill=(27, 94, 32)
)
draw.text((card_x + 44, banner_y + 10), "Guest mode active", font=body_font, fill=(165, 214, 167))
draw.text((card_x + card_w - 160, banner_y + 10), "47h 22m remaining", font=body_font, fill=(165, 214, 167))

# Section header
section_y = banner_y + 60
draw.text((card_x + 28, section_y), "Active Tokens (2)", font=body_font, fill=(238, 238, 238))

# New Token button
btn_x = card_x + card_w - 148
btn_y = section_y - 4
draw.rounded_rectangle([btn_x, btn_y, btn_x + 120, btn_y + 32], radius=8, fill=(108, 92, 231))
draw.text((btn_x + 16, btn_y + 6), "+ New Token", font=small_font, fill=(255, 255, 255))

# Token items
token_y = section_y + 36
tokens = [
    ("Plumber Wed", "Expires 3h 15m · 0 uses", (76, 175, 80)),
    ("Uncle Bob weekend", "Expires 26h 40m · 5 uses", (255, 152, 0)),
]

for label, meta, color in tokens:
    draw.rounded_rectangle(
        [card_x + 28, token_y, card_x + card_w - 28, token_y + 52],
        radius=10, fill=(34, 34, 34)
    )
    # Left border color
    draw.rectangle([card_x + 31, token_y + 6, card_x + 34, token_y + 46], fill=color)

    draw.text((card_x + 48, token_y + 8), label, font=body_font, fill=(238, 238, 238))
    draw.text((card_x + 48, token_y + 28), meta, font=small_font, fill=(136, 136, 136))

    # Revoke button
    rev_x = card_x + card_w - 100
    draw.rounded_rectangle([rev_x, token_y + 10, rev_x + 64, token_y + 42], radius=6, fill=(58, 58, 58))
    draw.text((rev_x + 12, token_y + 14), "Revoke", font=small_font, fill=(204, 204, 204))

    token_y += 60

# QR Section
qr_y = token_y + 10
draw.line([card_x + 28, qr_y, card_x + card_w - 28, qr_y], fill=(42, 42, 42), width=1)

qr_text_y = qr_y + 24
draw.text((card_x + card_w // 2 - 100, qr_text_y), "Share this QR for guest access", font=small_font, fill=(136, 136, 136))

# QR placeholder
qr_center_x = card_x + card_w // 2
qr_center_y = qr_text_y + 80
qr_size = 100
qr_x1 = qr_center_x - qr_size // 2
qr_y1 = qr_center_y - qr_size // 2
draw.rounded_rectangle([qr_x1, qr_y1, qr_x1 + qr_size, qr_y1 + qr_size], radius=8, fill=(255, 255, 255))

# Draw a QR-like pattern inside
for i in range(0, qr_size, 6):
    for j in range(0, qr_size, 6):
        if (i + j) % 7 < 3:
            draw.rectangle([qr_x1 + i, qr_y1 + j, qr_x1 + i + 4, qr_y1 + j + 4], fill=(0, 0, 0))

# Top left position indicator
draw.rectangle([qr_x1 + 6, qr_y1 + 6, qr_x1 + 24, qr_y1 + 24], fill=(0, 0, 0))
draw.rectangle([qr_x1 + 10, qr_y1 + 10, qr_x1 + 20, qr_y1 + 20], fill=(255, 255, 255))
# Top right
draw.rectangle([qr_x1 + qr_size - 24, qr_y1 + 6, qr_x1 + qr_size - 6, qr_y1 + 24], fill=(0, 0, 0))
draw.rectangle([qr_x1 + qr_size - 20, qr_y1 + 10, qr_x1 + qr_size - 10, qr_y1 + 20], fill=(255, 255, 255))
# Bottom left
draw.rectangle([qr_x1 + 6, qr_y1 + qr_size - 24, qr_x1 + 24, qr_y1 + qr_size - 6], fill=(0, 0, 0))
draw.rectangle([qr_x1 + 10, qr_y1 + qr_size - 20, qr_x1 + 20, qr_y1 + qr_size - 10], fill=(255, 255, 255))

# Browser frame chrome
draw.rectangle([0, 0, W, 30], fill=(30, 30, 30))
draw.ellipse([10, 10, 20, 20], fill=(255, 95, 87))  # red
draw.ellipse([24, 10, 34, 20], fill=(255, 189, 46))   # yellow
draw.ellipse([38, 10, 48, 20], fill=(39, 202, 78))     # green

# Save
# Default to <repo>/docs/screenshot.png relative to this script so the script
# works regardless of who runs it or where they cloned the repo.
repo_root = Path(__file__).resolve().parent.parent
default_out = repo_root / "docs" / "screenshot.png"
out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
out_path.parent.mkdir(parents=True, exist_ok=True)
img.save(out_path)
print(f"Saved: {out_path}")
print(f"Size: {img.size}")
