from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size, path):
    img = Image.new("RGB", (size, size), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill="#0F6E56")

    font = None
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            font = ImageFont.truetype(c, int(size * 0.52))
            break
    if font is None:
        font = ImageFont.load_default()

    text = "T"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill="#FFFFFF")

    img.save(path, "PNG")
    print("wrote", path, size)

base = os.path.dirname(os.path.abspath(__file__))
make_icon(192, os.path.join(base, "icons", "icon-192.png"))
make_icon(512, os.path.join(base, "icons", "icon-512.png"))
