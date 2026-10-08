import os
from PIL import Image, ImageDraw

def create_gastronomy_icon(output_path="app_icon.ico"):
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle - elegant deep navy blue with gradient effect
    # Outer circle
    draw.ellipse([8, 8, 248, 248], fill=(24, 32, 54, 255), outline=(212, 175, 55, 255), width=6)
    # Inner border gold ring
    draw.ellipse([18, 18, 238, 238], outline=(230, 195, 80, 200), width=2)
    
    # Food Cloche / Plate dome in Gold
    # Plate base
    draw.rounded_rectangle([50, 180, 206, 194], radius=6, fill=(230, 180, 40, 255), outline=(255, 215, 0, 255), width=2)
    # Cloche Dome
    draw.pieslice([60, 85, 196, 215], start=180, end=0, fill=(240, 190, 50, 255), outline=(255, 220, 70, 255), width=3)
    # Cloche Handle (top knob)
    draw.ellipse([118, 70, 138, 90], fill=(255, 215, 0, 255), outline=(220, 160, 20, 255), width=2)
    
    # Fork & Knife accents or Star Rating on dome
    # 3 golden stars above cloche
    def draw_star(cx, cy, r):
        draw.polygon([
            (cx, cy - r),
            (cx + r*0.3, cy - r*0.3),
            (cx + r, cy - r*0.2),
            (cx + r*0.4, cy + r*0.3),
            (cx + r*0.6, cy + r),
            (cx, cy + r*0.5),
            (cx - r*0.6, cy + r),
            (cx - r*0.4, cy + r*0.3),
            (cx - r, cy - r*0.2),
            (cx - r*0.3, cy - r*0.3)
        ], fill=(255, 235, 120, 255))

    draw_star(128, 48, 12)
    draw_star(95, 55, 8)
    draw_star(161, 55, 8)
    
    # Fork on left inside cloche or decoration
    # Steam swirls or gourmet emblem
    # Soft shine on the cloche
    draw.arc([75, 100, 150, 170], start=200, end=260, fill=(255, 255, 220, 200), width=4)

    # Save multi-size icon
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    
    img.save("app_icon.png")
    icon_images[0].save(
        output_path,
        format="ICO",
        sizes=sizes,
        append_images=icon_images[1:]
    )
    print(f"Icon generated successfully at {output_path} and app_icon.png")

if __name__ == "__main__":
    create_gastronomy_icon()
