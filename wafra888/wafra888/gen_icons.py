"""يولّد أيقونات PWA (192, 512, و maskable 512) بنفس شعار النموذج الأولي —
خمس دوائر ذهبية متداخلة على خلفية داكنة. يستخدم Pillow فقط (متوفرة أصلاً)."""
from PIL import Image, ImageDraw

GOLD = (201, 162, 39, 255)
BG_DEEP = (14, 13, 10, 255)


def draw_brandmark(size: int, bg_margin_ratio: float = 0.0):
    img = Image.new("RGBA", (size, size), BG_DEEP)
    draw = ImageDraw.Draw(img)

    # نفس نسب الشعار الأصلي (viewBox 0..100)، مع هامش أمان للأيقونات maskable
    usable = size * (1 - 2 * bg_margin_ratio)
    offset = size * bg_margin_ratio
    scale = usable / 100.0

    def circle(cx, cy, r, fill=None, outline=GOLD, width=None):
        x0 = offset + (cx - r) * scale
        y0 = offset + (cy - r) * scale
        x1 = offset + (cx + r) * scale
        y1 = offset + (cy + r) * scale
        w = width or max(1, round(scale * 1.0))
        if fill:
            draw.ellipse([x0, y0, x1, y1], fill=fill)
        else:
            draw.ellipse([x0, y0, x1, y1], outline=outline, width=w)

    circle(50, 50, 46)
    circle(50, 30, 20)
    circle(50, 70, 20)
    circle(32, 50, 20)
    circle(68, 50, 20)
    circle(50, 50, 8, fill=GOLD)
    return img


def main():
    draw_brandmark(192).save("static/icons/icon-192.png")
    draw_brandmark(512).save("static/icons/icon-512.png")
    # maskable: هامش أمان أكبر عشان القص الدائري/المربّع المدوّر على أندرويد
    draw_brandmark(512, bg_margin_ratio=0.12).save("static/icons/icon-maskable-512.png")
    print("icons generated")


if __name__ == "__main__":
    main()
