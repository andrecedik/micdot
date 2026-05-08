#!/usr/bin/env python3
"""Generate MicDot.icns from scratch using Pillow."""
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Install Pillow first:  pip install Pillow")

SIZES = [16, 32, 64, 128, 256, 512, 1024]


def make_icon(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Background: dark rounded square ──────────────────────────────────
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=s * 0.22, fill=(28, 28, 32, 255))

    lw = max(1, int(s * 0.055))
    white = (230, 230, 235, 255)
    cx = s / 2

    # ── Mic capsule (tall rounded rect) ──────────────────────────────────
    cap_w = s * 0.26
    cap_h = s * 0.38
    cap_x0 = cx - cap_w / 2
    cap_y0 = s * 0.09
    cap_x1 = cx + cap_w / 2
    cap_y1 = cap_y0 + cap_h
    draw.rounded_rectangle([cap_x0, cap_y0, cap_x1, cap_y1], radius=cap_w / 2, fill=white)

    # ── Stand collar arc (wraps around bottom of capsule) ─────────────────
    # Arc goes from 0° to 180° = bottom half of ellipse = U / bowl shape
    # Positioned so the top of the arc aligns with the bottom third of capsule
    arc_pad = s * 0.14
    arc_top = cap_y1 - s * 0.08      # slightly overlap capsule base
    arc_bot = arc_top + s * 0.28
    draw.arc(
        [arc_pad, arc_top, s - arc_pad, arc_bot],
        start=0,
        end=180,
        fill=white,
        width=lw,
    )

    # ── Vertical post: from arc nadir to base ─────────────────────────────
    post_top = (arc_top + arc_bot) / 2   # vertical center of the arc bounding box
    post_bot = s * 0.81
    draw.line([(cx, post_top), (cx, post_bot)], fill=white, width=lw)

    # ── Rounded base ──────────────────────────────────────────────────────
    base_w = s * 0.40
    base_h = lw * 1.4
    draw.rounded_rectangle(
        [cx - base_w / 2, post_bot - base_h / 2, cx + base_w / 2, post_bot + base_h / 2],
        radius=base_h / 2,
        fill=white,
    )

    # ── Status dot badge (lower-right) ────────────────────────────────────
    dot_r = s * 0.155
    dot_cx = s * 0.74
    dot_cy = s * 0.75
    draw.ellipse(                               # drop shadow
        [dot_cx - dot_r - 2, dot_cy - dot_r - 2, dot_cx + dot_r + 2, dot_cy + dot_r + 2],
        fill=(0, 0, 0, 80),
    )
    draw.ellipse(                               # white border
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=(255, 255, 255, 255),
    )
    inner = dot_r * 0.76
    draw.ellipse(                               # green fill
        [dot_cx - inner, dot_cy - inner, dot_cx + inner, dot_cy + inner],
        fill=(0, 210, 100, 255),
    )

    return img


def build_iconset(out_dir: Path) -> None:
    iconset = out_dir / "MicDot.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    for sz in SIZES:
        img = make_icon(sz)
        img.save(iconset / f"icon_{sz}x{sz}.png")
        if sz <= 512:
            img2 = make_icon(sz * 2)
            img2.save(iconset / f"icon_{sz}x{sz}@2x.png")

    icns_path = out_dir / "MicDot.icns"
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"iconutil failed:\n{result.stderr}")

    print(f"Created {icns_path}")


if __name__ == "__main__":
    build_iconset(Path(__file__).parent)
