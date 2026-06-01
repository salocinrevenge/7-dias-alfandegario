"""Reusable tagged-text layout & drawing for text baked onto 3D quads.

A line may begin with a single <tag> that selects its font size from SIZES.
Untagged lines fall back to DEFAULT_TAG. Tags intentionally only control size
to keep parsing trivial — the same layout drives both baking and hit-testing
so on-screen text and clickable rects always agree.

Used by the inspect paper today; meant to be shared by other quads later.
"""
import pyray as rl


# Named font sizes, in texture pixels.
SIZES = {
    "title": 48,
    "h1":    34,
    "h2":    36,
    "body":  33,
    "small": 22,
}
DEFAULT_TAG = "body"
LINE_GAP    = 8          # extra vertical pixels between lines


def parse_tag(line: bytes) -> tuple[int, bytes]:
    """Strip a leading <tag>; return (font_size, remaining_text)."""
    size = SIZES[DEFAULT_TAG]
    if line[:1] == b"<":
        end = line.find(b">")
        if end != -1:
            tag = line[1:end].decode("ascii", "ignore")
            if tag in SIZES:
                size = SIZES[tag]
                line = line[end + 1:]
    return size, line


def measure(font: rl.Font, text: bytes, size: int) -> int:
    return int(rl.measure_text_ex(font, text, float(size), 1.0).x)


def layout_lines(lines, font: rl.Font, mx: int, my: int) -> list[dict]:
    """Lay tagged lines top-to-bottom. Returns spans with absolute texture coords.

    span = {"text": bytes, "size": int, "x": int, "y": int, "w": int, "h": int}
    """
    spans = []
    y = my
    for raw in lines:
        size, text = parse_tag(raw)
        w = measure(font, text, size) if text else 0
        spans.append({"text": text, "size": size, "x": mx, "y": y, "w": w, "h": size})
        y += size + LINE_GAP
    return spans


def draw_text(font: rl.Font, text: bytes, x: int, y: int, size: int, color):
    rl.draw_text_ex(font, text, rl.Vector2(float(x), float(y)), float(size), 1.0, color)


def draw_span(font: rl.Font, span: dict, color):
    draw_text(font, span["text"], span["x"], span["y"], span["size"], color)
