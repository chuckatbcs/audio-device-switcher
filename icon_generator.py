from PIL import Image, ImageDraw

def generate_speaker_icon(active=True, badge=None):
    """
    Procedurally draws a beautiful, high-contrast, minimalist speaker icon.
    - active=True: Draws glowing blue/violet soundwaves and a vibrant indicator dot.
    - active=False: Draws monochrome gray soundwaves and a neutral gray indicator dot.
    """
    # Create a 64x64 transparent image (RGBA)
    size = 64
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Color scheme
    if active:
        speaker_color = (243, 244, 246, 255)       # Off-white (gray-50)
        wave_color = (99, 102, 241, 255)           # Vibrant Indigo (indigo-500)
        dot_color = (16, 185, 129, 255)            # Emerald Green (emerald-500)
    else:
        speaker_color = (209, 213, 219, 255)       # Light gray (gray-300)
        wave_color = (156, 163, 175, 255)          # Medium gray (gray-400)
        dot_color = (107, 114, 128, 255)           # Darker gray (gray-500)

    # 1. Draw the Speaker Cone (Base + Horn)
    # Speaker base (rectangle): x from 10 to 18, y from 22 to 42
    draw.rectangle([10, 22, 18, 42], fill=speaker_color)
    
    # Speaker horn (polygon): connects base to front edge
    # Front edge is at x=28, extending from y=14 to y=50
    draw.polygon([
        (18, 22),  # Top-right of base
        (28, 14),  # Top of horn front edge
        (28, 50),  # Bottom of horn front edge
        (18, 42)   # Bottom-right of base
    ], fill=speaker_color)

    # 2. Draw Soundwaves (Arcs)
    # Inner Wave (Arc with radius 12, centered around the horn)
    # Bounding box centered at x=20, y=32 with radius 18
    # draw.arc parameters: [x0, y0, x1, y1], start_angle, end_angle
    # In PIL, 0 degrees is East, 90 is South, etc.
    draw.arc([14, 14, 50, 50], start=-45, end=45, fill=wave_color, width=4)
    
    # Outer Wave (Arc with radius 22, centered around the horn)
    draw.arc([4, 4, 60, 60], start=-45, end=45, fill=wave_color, width=4)

    # 3. Draw Status Indicator Dot (glowing/accent circle in top right)
    # Bounding box for dot: center at (48, 16), radius 5
    draw.ellipse([43, 11, 53, 21], fill=dot_color)
    
    # Add a subtle inner white dot for active state to make it look premium
    if active:
        draw.ellipse([46, 14, 50, 18], fill=(255, 255, 255, 255))

    if badge:
        label = str(badge)[:5]
        tw = 8 * len(label) + 8
        tx0, ty0 = max(2, 32 - tw // 2), 48
        draw.rounded_rectangle([tx0, ty0, tx0 + tw, 58], radius=4, fill=(30, 30, 30, 220))
        draw.text((tx0 + 4, ty0 - 1), label, fill=(243, 244, 246, 255))

    return image

if __name__ == '__main__':
    # Save the icons for visual inspection and local verification
    icon_active = generate_speaker_icon(active=True)
    icon_active.save("icon_active.png")
    
    icon_inactive = generate_speaker_icon(active=False)
    icon_inactive.save("icon_inactive.png")
    
    print("Procedural icons generated successfully! Saved 'icon_active.png' and 'icon_inactive.png'.")
