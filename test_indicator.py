import time
from PIL import Image, ImageDraw
import pystray

def create_image():
    # Generate a simple 64x64 blue circle image
    image = Image.new('RGB', (64, 64), color='black')
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill='blue')
    return image

print("Imported pystray and PIL successfully.")

try:
    icon = pystray.Icon("test_icon", create_image(), "Test Indicator")
    print("Created icon instance successfully:", icon)
except Exception as e:
    print("Failed to create icon:", e)
