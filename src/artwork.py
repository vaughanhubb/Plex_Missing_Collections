"""Poster artwork rendering with Pillow: library cards, hover overlays and placeholders."""
import textwrap
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

CARD_SIZE = (160, 240)
DETAIL_SIZE = (200, 300)

COLORS = {
    "missing": (231, 76, 60),
    "partial": (243, 156, 18),
    "complete": (0, 188, 140),
    "error": (108, 117, 125),
    "placeholder": (48, 48, 48),
    "text": (255, 255, 255),
    "muted": (190, 190, 190),
}
_FONT_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf")


@lru_cache(maxsize=None)
def font(size):
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def load_poster(data, title):
    """Decode poster bytes to a DETAIL_SIZE image, or build a placeholder."""
    if data:
        try:
            image = Image.open(BytesIO(data)).convert("RGB")
            return ImageOps.fit(image, DETAIL_SIZE, Image.LANCZOS)
        except Exception:
            pass
    return placeholder(title)


def placeholder(title, size=DETAIL_SIZE):
    image = Image.new("RGB", size, COLORS["placeholder"])
    draw = ImageDraw.Draw(image)
    text = "\n".join(textwrap.wrap(title, width=16)[:5])
    draw.multiline_text((size[0] / 2, size[1] / 2), text, font=font(16),
                        fill=COLORS["muted"], anchor="mm", align="center")
    return image


SCALE = 4         # Overlays are drawn supersampled then downscaled for anti-aliased edges
BADGE_ALPHA = 225  # Slight translucency so badges sit softly on the artwork


class _Overlay:
    """Transparent drawing layer in card coordinates, rendered at SCALE x resolution."""

    def __init__(self, size=CARD_SIZE):
        self.size = size
        self.image = Image.new("RGBA", (size[0] * SCALE, size[1] * SCALE), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

    @staticmethod
    def _s(*values):
        return [v * SCALE for v in values]

    def text(self, xy, text, size, fill, **kwargs):
        method = self.draw.multiline_text if "\n" in text else self.draw.text
        method(tuple(self._s(*xy)), text, font=font(size * SCALE), fill=fill, **kwargs)

    def text_width(self, text, size):
        return self.draw.textlength(text, font=font(size * SCALE)) / SCALE

    def pill_width(self, text, size=11):
        return int(self.text_width(text, size)) + 12

    def pill(self, x, y, text, color, size=11):
        """Draw a rounded badge with its top-left at (x, y). Returns its (width, height)."""
        width, height = self.pill_width(text, size), size + 9
        self.draw.rounded_rectangle(self._s(x, y, x + width, y + height),
                                    radius=height * SCALE // 2, fill=(*color, BADGE_ALPHA))
        self.text((x + width / 2, y + height / 2), text, size, COLORS["text"], anchor="mm")
        return width, height

    def check_mark(self, cx, cy, color):
        self.draw.ellipse(self._s(cx - 22, cy - 22, cx + 22, cy + 22), outline=color, width=3 * SCALE)
        self.draw.line([tuple(self._s(cx - 10, cy)), tuple(self._s(cx - 3, cy + 8)),
                        tuple(self._s(cx + 11, cy - 8))], fill=color, width=4 * SCALE, joint="curve")

    def composite(self, base):
        layer = self.image.resize(self.size, Image.LANCZOS)
        return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def _badges(result):
    """Status badges shown in the corner of a card."""
    if result.error:
        return [("Unmatched", COLORS["error"])]
    badges = []
    if result.missing_seasons:
        n = len(result.missing_seasons)
        badges.append((f"{n} season{'s' if n > 1 else ''}", COLORS["missing"]))
    if result.incomplete_seasons:
        n = result.missing_episode_count
        badges.append((f"{n} ep{'s' if n > 1 else ''}", COLORS["partial"]))
    return badges or [("Complete", COLORS["complete"])]


def render_card(poster, result):
    overlay = _Overlay()
    x = CARD_SIZE[0] - 6
    for text, color in reversed(_badges(result)):
        x -= overlay.pill_width(text)
        overlay.pill(x, CARD_SIZE[1] - 26, text, color)
        x -= 4
    return overlay.composite(poster.resize(CARD_SIZE, Image.LANCZOS))


def _flow_badges(overlay, items, y, color, max_y, margin=10):
    """Lay badges out left-to-right, wrapping lines; collapse overflow into '+N'."""
    x, line_height = margin, 0
    for i, text in enumerate(items):
        width = overlay.pill_width(text)
        if x + width > CARD_SIZE[0] - margin:
            x, y = margin, y + line_height + 5
        if y + 20 > max_y:
            overlay.pill(x, y - line_height - 5, f"+{len(items) - i}", COLORS["error"])
            return y
        _, line_height = overlay.pill(x, y, text, color)
        x += width + 5
    return y + line_height + 10


def render_hover(poster, result):
    """Darkened poster with a badge for every missing season and incomplete season."""
    base = ImageEnhance.Brightness(poster.resize(CARD_SIZE, Image.LANCZOS)).enhance(0.25)
    overlay = _Overlay()
    cx, cy = CARD_SIZE[0] / 2, CARD_SIZE[1] / 2
    max_y = CARD_SIZE[1] - 30
    y = 10

    if result.error:
        overlay.text((cx, cy), "\n".join(textwrap.wrap(result.error, 18)), 12,
                     COLORS["muted"], anchor="mm", align="center")
    elif result.status == "complete":
        overlay.check_mark(cx, cy - 10, COLORS["complete"])
        overlay.text((cx, cy + 25), "All seasons complete", 11, COLORS["text"], anchor="mm")
    else:
        if result.missing_seasons:
            overlay.text((10, y), "MISSING SEASONS", 10, COLORS["muted"])
            y = _flow_badges(overlay, [f"S{s.number}" for s in result.missing_seasons],
                             y + 16, COLORS["missing"], max_y)
        if result.incomplete_seasons and y < max_y - 36:
            overlay.text((10, y), "MISSING EPISODES", 10, COLORS["muted"])
            y = _flow_badges(overlay, [f"S{s.number} · {len(s.missing_episodes)}"
                                       for s in result.incomplete_seasons],
                             y + 16, COLORS["partial"], max_y)

    overlay.text((cx, CARD_SIZE[1] - 14), "Click for details", 10, COLORS["muted"], anchor="mm")
    return overlay.composite(base)
