from PIL import Image, ImageDraw, ImageFont

# Farben (Bootstrap Primary Blue + Dark Background)
BG_COLOR = (13, 110, 253)  # Bootstrap Primary
TEXT_COLOR = (255, 255, 255)

def create_icon(size, maskable=False):
    """Erstellt ein einfaches App-Icon"""
    # Größeres Canvas für maskable (safe zone)
    if maskable:
        canvas_size = int(size * 1.25)
        img = Image.new('RGB', (canvas_size, canvas_size), BG_COLOR)
    else:
        img = Image.new('RGB', (size, size), BG_COLOR)
    
    draw = ImageDraw.Draw(img)
    
    # Zeichne "HG" Text in der Mitte
    try:
        font_size = size // 2
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    text = "HG"
    
    # Text zentrieren
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    if maskable:
        x = (canvas_size - text_width) // 2
        y = (canvas_size - text_height) // 2
    else:
        x = (size - text_width) // 2
        y = (size - text_height) // 2
    
    # Text zeichnen
    draw.text((x, y), text, fill=TEXT_COLOR, font=font)
    
    # Für maskable: auf richtige Größe zuschneiden (zentriert)
    if maskable:
        left = (canvas_size - size) // 2
        top = (canvas_size - size) // 2
        img = img.crop((left, top, left + size, top + size))
    
    return img

# Icons erstellen
print("Erstelle PWA Icons...")

# Standard Icons
icon_192 = create_icon(192)
icon_192.save('core/static/core/images/icon-192x192.png')
print("✓ icon-192x192.png")

icon_512 = create_icon(512)
icon_512.save('core/static/core/images/icon-512x512.png')
print("✓ icon-512x512.png")

# Maskable Icons (für Android adaptive icons)
icon_maskable_192 = create_icon(192, maskable=True)
icon_maskable_192.save('core/static/core/images/icon-maskable-192x192.png')
print("✓ icon-maskable-192x192.png")

icon_maskable_512 = create_icon(512, maskable=True)
icon_maskable_512.save('core/static/core/images/icon-maskable-512x512.png')
print("✓ icon-maskable-512x512.png")

print("\n✅ Alle Icons erfolgreich erstellt!")
print("📁 Speicherort: core/static/core/images/")
