"""ai-happy-01 -- "Make the AI judge happy".

The image: a golden-hour meadow. Two little robots meet on a green hill.
The teal robot offers a bright red flower to the orange robot, who throws
both arms up in delight while pink hearts float up between them. Butterflies,
wildflowers, a warm low sun and soft clouds complete the scene.

One specific, joyful moment (a flower offered, a friend delighted) -- not a
stock smiley face or a generic sunny scene -- drawn cleanly as flat
illustration with bold shapes that still read clearly at 300 pixels wide.

Rendering: pure Python 3.13 standard library only. The scene is rasterised
at 2x (2048x2048) with scanline fills, box-downsampled to 1024x1024, and
encoded as a PNG by hand (zlib + CRC). No randomness, no time, no network,
so two runs write identical bytes.
"""

import binascii
import math
import os
import struct
import zlib

# ---------------------------------------------------------------- palette
# Warm golden-hour palette: coral sky, golden sun, green hill, teal + orange
# robots, red flower, pink hearts. High contrast, cheerful, cohesive.
SKY_TOP = (255, 143, 107)      # warm coral
SKY_MID = (255, 184, 92)       # golden
SKY_LOW = (255, 233, 168)      # pale honey at the horizon
SUN_CORE = (255, 246, 216)
SUN_GLOW1 = (255, 211, 77)
SUN_GLOW2 = (255, 190, 60)
CLOUD = (255, 255, 255)
CLOUD_SHADE = (255, 233, 242)
HILL_TOP = (111, 194, 107)
HILL_BOT = (62, 155, 79)
HILL_BAND = (140, 210, 110)
GRASS_DARK = (46, 130, 66)
SHADOW = (52, 133, 63)
OUTLINE = (58, 44, 34)         # warm dark brown, soft outline colour
ROBOT_A = (47, 168, 160)       # teal
ROBOT_A_DARK = (30, 122, 116)
ROBOT_A_BELLY = (216, 243, 239)
ROBOT_B = (255, 138, 61)       # warm orange
ROBOT_B_DARK = (217, 106, 30)
ROBOT_B_BELLY = (255, 232, 210)
EYE_WHITE = (255, 255, 255)
PUPIL = (34, 48, 58)
CHEEK = (255, 158, 158)
FLOWER_RED = (255, 77, 109)
FLOWER_CTR = (255, 210, 63)
STEM = (62, 155, 79)
LEAF = (88, 179, 104)
HEART_PINK = (255, 77, 109)
HEART_SOFT = (255, 123, 169)
GOLD = (255, 201, 60)
BUTTERFLY_O = (255, 159, 28)
BUTTERFLY_P = (155, 93, 229)
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- PNG writer


def _chunk(kind, data):
    out = kind + data
    return struct.pack(">I", len(data)) + out + struct.pack(
        ">I", binascii.crc32(out) & 0xFFFFFFFF)


def write_png(path, w, h, rgb):
    """Encode raw RGB bytes (w*h*3) as a PNG with filter 0 on every row."""
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 6)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", idat)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- canvas
# All drawing coordinates are in 1024-space; the canvas rasterises at S=2
# (2048x2048) and downsamples, which gives smooth edges.

W = 1024
H = 1024
S = 2
PW = W * S
PH = H * S
STRIDE = PW * 3


def _lerp(c0, c1, t):
    return (round(c0[0] + (c1[0] - c0[0]) * t),
            round(c0[1] + (c1[1] - c0[1]) * t),
            round(c0[2] + (c1[2] - c0[2]) * t))


class Canvas:
    def __init__(self):
        self.buf = bytearray(PW * PH * 3)

    # -- low level -----------------------------------------------------
    def _span(self, y, x0, x1, rgb):
        """Fill pixels [x0, x1) on row y (pixel coords) with one colour."""
        if y < 0 or y >= PH:
            return
        x0 = max(0, x0)
        x1 = min(PW, x1)
        if x1 <= x0:
            return
        n = x1 - x0
        i = (y * PW + x0) * 3
        self.buf[i:i + n * 3] = bytes(rgb) * n

    def _rect(self, x0, y0, x1, y1, rgb):
        for y in range(y0, y1):
            self._span(y, x0, x1, rgb)

    # -- shapes (1024-space coords) -----------------------------------
    def rect(self, x0, y0, x1, y1, rgb):
        self._rect(int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S), rgb)

    def circle(self, cx, cy, r, rgb):
        cx, cy, r = int(cx * S), int(cy * S), int(r * S)
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            d2 = r2 - dy * dy
            if d2 < 0:
                continue
            dx = int(math.sqrt(d2))
            self._span(y, cx - dx, cx + dx + 1, rgb)

    def ellipse(self, cx, cy, rx, ry, rgb):
        cx, cy = int(cx * S), int(cy * S)
        rx, ry = int(rx * S), int(ry * S)
        if rx <= 0 or ry <= 0:
            return
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            d2 = 1.0 - dy * dy
            if d2 < 0:
                continue
            dx = int(rx * math.sqrt(d2))
            self._span(y, cx - dx, cx + dx + 1, rgb)

    def round_rect(self, x0, y0, x1, y1, r, rgb):
        x0, y0, x1, y1, r = (int(x0 * S), int(y0 * S), int(x1 * S),
                            int(y1 * S), int(r * S))
        if r <= 0:
            self._rect(x0, y0, x1, y1, rgb)
            return
        self._rect(x0 + r, y0, x1 - r, y1, rgb)
        self._rect(x0, y0 + r, x0 + r, y1 - r, rgb)
        self._rect(x1 - r, y0 + r, x1, y1 - r, rgb)
        for ccx, ccy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                         (x0 + r, y1 - r), (x1 - r, y1 - r)):
            r2 = r * r
            for y in range(ccy - r, ccy + r + 1):
                dy = y - ccy
                d2 = r2 - dy * dy
                if d2 < 0:
                    continue
                dx = int(math.sqrt(d2))
                self._span(y, ccx - dx, ccx + dx + 1, rgb)

    def poly(self, pts, rgb):
        """Scanline-fill a polygon given in 1024-space (x, y) points."""
        pts = [(int(x * S), int(y * S)) for x, y in pts]
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(PH - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x_a, y_a = pts[i]
                x_b, y_b = pts[(i + 1) % n]
                if (y_a <= y < y_b) or (y_b <= y < y_a):
                    t = (y - y_a) / (y_b - y_a)
                    xs.append(int(x_a + t * (x_b - x_a)))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self._span(y, xs[k], xs[k + 1] + 1, rgb)

    def thick_line(self, x0, y0, x1, y1, w, rgb):
        x0, y0, x1, y1 = int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S)
        w = max(2, int(w * S))
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            self._disc(x0, y0, w // 2, rgb)
            return
        nx = -dy / length * w / 2
        ny = dx / length * w / 2
        self._poly_px([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                       (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], rgb)
        self._disc(x0, y0, w // 2, rgb)
        self._disc(x1, y1, w // 2, rgb)

    def _disc(self, cx, cy, r, rgb):
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            d2 = r2 - dy * dy
            if d2 < 0:
                continue
            dx = int(math.sqrt(d2))
            self._span(y, cx - dx, cx + dx + 1, rgb)

    def _poly_px(self, pts, rgb):
        pts = [(int(x), int(y)) for x, y in pts]
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(PH - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x_a, y_a = pts[i]
                x_b, y_b = pts[(i + 1) % n]
                if (y_a <= y < y_b) or (y_b <= y < y_a):
                    t = (y - y_a) / (y_b - y_a)
                    xs.append(int(x_a + t * (x_b - x_a)))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self._span(y, xs[k], xs[k + 1] + 1, rgb)

    def arc(self, cx, cy, r, a0_deg, a1_deg, w, rgb):
        """Draw an arc (angles in degrees, 0 = +x, 90 = +y i.e. down)."""
        a0 = math.radians(a0_deg)
        a1 = math.radians(a1_deg)
        steps = max(6, int(abs(a1 - a0) * r / 5) + 1)
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            self.circle(x, y, max(1.0, w / 2.0), rgb)

    def heart(self, cx, cy, s, rgb):
        self.circle(cx - s * 0.48, cy - s * 0.18, s * 0.52, rgb)
        self.circle(cx + s * 0.48, cy - s * 0.18, s * 0.52, rgb)
        self.poly([(cx - s * 0.95, cy - s * 0.05),
                   (cx + s * 0.95, cy - s * 0.05),
                   (cx, cy + s * 0.95)], rgb)

    def star(self, cx, cy, r_out, r_in, rgb):
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = r_out if i % 2 == 0 else r_in
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, rgb)

    def flower(self, cx, cy, r, petal, center):
        for i in range(5):
            a = -math.pi / 2 + i * 2 * math.pi / 5
            px = cx + r * 0.62 * math.cos(a)
            py = cy + r * 0.62 * math.sin(a)
            self.circle(px, py, r * 0.5, petal)
        self.circle(cx, cy, r * 0.42, center)
        self.circle(cx - r * 0.12, cy - r * 0.12, r * 0.12, WHITE)

    def butterfly(self, cx, cy, s, wing, outline):
        self.ellipse(cx - s, cy - s * 0.35, s * 1.05, s * 0.75, outline)
        self.ellipse(cx + s, cy - s * 0.35, s * 1.05, s * 0.75, outline)
        self.ellipse(cx - s * 0.85, cy + s * 0.55, s * 0.7, s * 0.5, outline)
        self.ellipse(cx + s * 0.85, cy + s * 0.55, s * 0.7, s * 0.5, outline)
        self.ellipse(cx - s, cy - s * 0.35, s * 0.9, s * 0.62, wing)
        self.ellipse(cx + s, cy - s * 0.35, s * 0.9, s * 0.62, wing)
        self.ellipse(cx - s * 0.85, cy + s * 0.55, s * 0.58, s * 0.4, wing)
        self.ellipse(cx + s * 0.85, cy + s * 0.55, s * 0.58, s * 0.4, wing)
        self.thick_line(cx, cy - s * 0.9, cx, cy + s * 0.9, s * 0.28, OUTLINE)
        self.circle(cx - s * 0.35, cy - s * 1.15, s * 0.14, OUTLINE)
        self.circle(cx + s * 0.35, cy - s * 1.15, s * 0.14, OUTLINE)

    # -- gradients ------------------------------------------------------
    def vgrad(self, y0, y1, c_top, c_mid, c_bot):
        """Vertical gradient over rows y0..y1 (1024-space), full width."""
        y0p, y1p = int(y0 * S), int(y1 * S)
        span = max(1, y1p - y0p)
        for y in range(y0p, y1p):
            t = (y - y0p) / span
            if t < 0.5:
                c = _lerp(c_top, c_mid, t * 2)
            else:
                c = _lerp(c_mid, c_bot, (t - 0.5) * 2)
            self._span(y, 0, PW, c)

    def hill(self, cx, cy, rx, ry):
        """Green hill: ellipse filled with a vertical green gradient."""
        cxp, cyp = int(cx * S), int(cy * S)
        rxp, ryp = int(rx * S), int(ry * S)
        for y in range(cyp - ryp, PH):
            dy = (y - cyp) / ryp
            d2 = 1.0 - dy * dy
            if d2 < 0:
                continue
            dx = int(rxp * math.sqrt(d2))
            t = (y - (cyp - ryp)) / (2 * ryp)
            c = _lerp(HILL_TOP, HILL_BOT, min(1.0, max(0.0, t)))
            self._span(y, cxp - dx, cxp + dx + 1, c)

    # -- downsample ------------------------------------------------------
    def downsample(self):
        """Box-average the 2x buffer to 1024x1024 RGB bytes."""
        out = bytearray(W * H * 3)
        buf = self.buf
        for oy in range(H):
            sy = oy * 2
            r0 = sy * STRIDE
            r1 = (sy + 1) * STRIDE
            oo = oy * W * 3
            for ox in range(W):
                sx = ox * 2
                i0 = r0 + sx * 3
                i1 = r1 + sx * 3
                o = oo + ox * 3
                out[o] = (buf[i0] + buf[i0 + 3] + buf[i1] + buf[i1 + 3]) >> 2
                out[o + 1] = (buf[i0 + 1] + buf[i0 + 4] + buf[i1 + 1]
                              + buf[i1 + 4]) >> 2
                out[o + 2] = (buf[i0 + 2] + buf[i0 + 5] + buf[i1 + 2]
                              + buf[i1 + 5]) >> 2
        return bytes(out)


# ---------------------------------------------------------------- scene

def _cloud(c, cx, cy, s):
    c.ellipse(cx, cy + s * 0.18, s * 1.15, s * 0.42, CLOUD_SHADE)
    c.ellipse(cx - s * 0.62, cy + s * 0.08, s * 0.62, s * 0.38, CLOUD)
    c.ellipse(cx + s * 0.62, cy + s * 0.08, s * 0.62, s * 0.38, CLOUD)
    c.ellipse(cx, cy - s * 0.14, s * 0.85, s * 0.5, CLOUD)


def _robot_legs(c, x_left, x_right, feet_y, dark):
    c.round_rect(x_left, feet_y - 62, x_left + 34, feet_y - 4, 10, dark)
    c.round_rect(x_right, feet_y - 62, x_right + 34, feet_y - 4, 10, dark)
    c.ellipse(x_left + 17, feet_y - 2, 28, 13, dark)
    c.ellipse(x_right + 17, feet_y - 2, 28, 13, dark)


def _arm(c, x0, y0, x1, y1, w, fill):
    c.thick_line(x0, y0, x1, y1, w + 9, OUTLINE)
    c.thick_line(x0, y0, x1, y1, w, fill)
    c.circle(x1, y1, w * 0.72, OUTLINE)
    c.circle(x1, y1, w * 0.72 - 3, fill)


def draw_scene(c):
    # --- sky ---
    c.vgrad(0, 660, SKY_TOP, SKY_MID, SKY_LOW)
    # pale honey below the gradient so no unpainted gap shows at the
    # hill's edges, where the hilltop sits lower than at the centre
    c.rect(0, 660, 1024, 1024, SKY_LOW)

    # --- sun (upper right) with soft stepped glow and short rays ---
    sx, sy = 770, 200
    c.circle(sx, sy, 195, SUN_GLOW2)
    c.circle(sx, sy, 165, SUN_GLOW1)
    for ang in (-160, -120, -80, -40, 0):
        a = math.radians(ang)
        x0 = sx + 132 * math.cos(a)
        y0 = sy + 132 * math.sin(a)
        x1 = sx + 168 * math.cos(a)
        y1 = sy + 168 * math.sin(a)
        c.thick_line(x0, y0, x1, y1, 11, SUN_GLOW1)
    c.circle(sx, sy, 118, SUN_CORE)
    c.circle(sx - 30, sy - 30, 24, WHITE)

    # --- clouds ---
    _cloud(c, 200, 150, 78)
    _cloud(c, 430, 92, 58)
    _cloud(c, 880, 340, 66)

    # --- hill ---
    c.hill(512, 1180, 1000, 540)
    c.ellipse(512, 1080, 700, 120, HILL_BAND)

    # --- wildflowers and grass on the hill ---
    for fx, fy, r, petal, ctr in (
            (120, 920, 12, WHITE, FLOWER_CTR),
            (240, 962, 10, HEART_SOFT, FLOWER_CTR),
            (900, 940, 12, FLOWER_CTR, FLOWER_RED),
            (820, 982, 10, WHITE, FLOWER_CTR),
            (480, 942, 9, HEART_SOFT, FLOWER_CTR),
            (60, 880, 10, FLOWER_CTR, FLOWER_RED),
            (960, 880, 9, WHITE, FLOWER_CTR)):
        c.thick_line(fx, fy + r, fx, fy + r + 20, 4, STEM)
        c.flower(fx, fy, r, petal, ctr)
    for gx, gy in ((150, 905), (350, 952), (650, 932), (950, 905),
                   (760, 972), (420, 985), (180, 985)):
        c.thick_line(gx - 8, gy, gx - 12, gy - 18, 4, GRASS_DARK)
        c.thick_line(gx, gy, gx, gy - 22, 4, GRASS_DARK)
        c.thick_line(gx + 8, gy, gx + 12, gy - 18, 4, GRASS_DARK)

    # --- soft shadows under the robots ---
    c.ellipse(330, 868, 118, 18, SHADOW)
    c.ellipse(700, 868, 118, 18, SHADOW)

    # --- butterflies ---
    c.butterfly(180, 300, 15, BUTTERFLY_O, OUTLINE)
    c.butterfly(862, 430, 13, BUTTERFLY_P, OUTLINE)

    # --- hearts rising between the robots ---
    c.heart(560, 380, 24, HEART_PINK)
    c.heart(640, 300, 18, HEART_SOFT)
    c.heart(470, 310, 15, HEART_PINK)

    # --- sparkles ---
    c.star(560, 470, 15, 5, GOLD)
    c.star(602, 428, 11, 4, WHITE)
    c.star(448, 420, 10, 3.5, GOLD)

    # --- robot A (teal, left): offering the flower ---
    _robot_legs(c, 285, 350, 862, ROBOT_A_DARK)
    c.round_rect(248, 560, 412, 830, 42, OUTLINE)
    c.round_rect(254, 566, 406, 824, 38, ROBOT_A)
    c.round_rect(278, 640, 382, 800, 28, ROBOT_A_BELLY)
    for by in (680, 720, 760):
        c.circle(330, by, 7, ROBOT_A_DARK)
    # left arm, down and out
    _arm(c, 256, 660, 196, 730, 22, ROBOT_A)
    # right arm, extended toward the flower
    _arm(c, 404, 650, 498, 618, 22, ROBOT_A)
    # head
    c.round_rect(262, 428, 398, 566, 36, OUTLINE)
    c.round_rect(268, 434, 392, 560, 32, ROBOT_A)
    # antenna with a gold star
    c.thick_line(330, 428, 330, 382, 8, ROBOT_A_DARK)
    c.star(330, 366, 22, 9, OUTLINE)
    c.star(330, 366, 19, 8, GOLD)
    # big friendly eyes
    for ex in (306, 360):
        c.circle(ex, 494, 29, OUTLINE)
        c.circle(ex, 494, 26, EYE_WHITE)
        c.circle(ex, 496, 12, PUPIL)
        c.circle(ex - 4, 490, 5, WHITE)
    # smile and cheeks
    c.arc(333, 512, 22, 25, 155, 7, OUTLINE)
    c.circle(284, 536, 13, CHEEK)
    c.circle(382, 536, 13, CHEEK)

    # --- the flower, held out by robot A ---
    c.thick_line(500, 622, 520, 572, 7, STEM)
    c.ellipse(508, 600, 12, 6, LEAF)
    c.ellipse(532, 596, 12, 6, LEAF)
    c.flower(520, 550, 27, FLOWER_RED, FLOWER_CTR)

    # --- robot B (orange, right): arms up in delight ---
    _robot_legs(c, 640, 705, 862, ROBOT_B_DARK)
    c.round_rect(618, 580, 782, 830, 42, OUTLINE)
    c.round_rect(624, 586, 776, 824, 38, ROBOT_B)
    c.round_rect(648, 660, 752, 800, 28, ROBOT_B_BELLY)
    for by in (700, 740, 780):
        c.circle(700, by, 7, ROBOT_B_DARK)
    # both arms raised
    _arm(c, 626, 668, 556, 566, 22, ROBOT_B)
    _arm(c, 774, 668, 844, 566, 22, ROBOT_B)
    # head
    c.round_rect(632, 448, 768, 586, 36, OUTLINE)
    c.round_rect(638, 454, 762, 580, 32, ROBOT_B)
    # antenna with a heart
    c.thick_line(700, 448, 700, 402, 8, ROBOT_B_DARK)
    c.heart(700, 386, 20, HEART_PINK)
    # happy closed eyes (upward curves) and a wide smile
    c.arc(664, 514, 16, 200, 340, 7, OUTLINE)
    c.arc(736, 514, 16, 200, 340, 7, OUTLINE)
    c.arc(700, 520, 30, 20, 160, 8, OUTLINE)
    c.circle(648, 556, 13, CHEEK)
    c.circle(752, 556, 13, CHEEK)


# ---------------------------------------------------------------- main

def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    canvas = Canvas()
    draw_scene(canvas)
    rgb = canvas.downsample()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(path, W, H, rgb)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()

