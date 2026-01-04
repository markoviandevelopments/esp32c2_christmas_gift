import pygame
import requests
import time
import sys

# Configuration — match your hardware
SERVER_IP = "108.254.1.184"  # Change if needed
PORT = 9025
SRC_SIZE = 64          # Source image resolution
SCALE = 3              # Each source pixel becomes 3x3 on display
DISPLAY_SIZE = 240     # TFT size
TOTAL_PIXELS = SRC_SIZE * SRC_SIZE
CHUNKS = TOTAL_PIXELS // 16  # 256 chunks of 16 pixels → 32 bytes each

# Colors (RGB565 → RGB888 conversion helper)
def rgb565_to_rgb(high, low):
    value = (high << 8) | low
    r = (value >> 11) & 0x1F
    g = (value >> 5) & 0x3F
    b = value & 0x1F
    return (r << 3, g << 2, b << 3)

# Simple bitmap font (5x8) matching your MicroPython font
FONT = {
    ' ': [0x00,0x00,0x00,0x00,0x00],
    '0': [0x7C,0xA2,0x92,0x8A,0x7C],
    '1': [0x00,0x42,0xFE,0x02,0x00],
    '2': [0x42,0x86,0x8A,0x92,0x62],
    '3': [0x84,0x82,0xA2,0xD2,0x8C],
    '4': [0x18,0x28,0x48,0xFE,0x08],
    '5': [0xE4,0xA2,0xA2,0xA2,0x9C],
    '6': [0x3C,0x52,0x92,0x92,0x0C],
    '7': [0x80,0x8E,0x90,0xA0,0xC0],
    '8': [0x6C,0x92,0x92,0x92,0x6C],
    '9': [0x60,0x92,0x92,0x94,0x78],
    ':': [0x00,0x36,0x36,0x00,0x00],
    '.': [0x00,0x00,0x00,0x06,0x06],
    '$': [0x24,0x54,0xFE,0x54,0x48],
    '-': [0x08,0x08,0x08,0x08,0x08],
    'A': [0x3E,0x48,0x48,0x48,0x3E],
    'B': [0xFE,0x92,0x92,0x92,0x6C],
    'C': [0x7C,0x82,0x82,0x82,0x44],
    'D': [0xFE,0x82,0x82,0x82,0x7C],
    'E': [0xFE,0x92,0x92,0x92,0x82],
    'F': [0xFE,0x90,0x90,0x90,0x80],
    'G': [0x7C,0x82,0x92,0x92,0x5C],
    'H': [0xFE,0x10,0x10,0x10,0xFE],
    'I': [0x00,0x82,0xFE,0x82,0x00],
    'J': [0x04,0x02,0x82,0xFC,0x80],
    'K': [0xFE,0x10,0x28,0x44,0x82],
    'L': [0xFE,0x02,0x02,0x02,0x02],
    'M': [0xFE,0x40,0x30,0x40,0xFE],
    'N': [0xFE,0x20,0x10,0x08,0xFE],
    'O': [0x7C,0x82,0x82,0x82,0x7C],
    'P': [0xFE,0x90,0x90,0x90,0x60],
    'Q': [0x7C,0x82,0x8A,0x84,0x7A],
    'R': [0xFE,0x90,0x98,0x94,0x62],
    'S': [0x62,0x92,0x92,0x92,0x8C],
    'T': [0x80,0x80,0xFE,0x80,0x80],
    'U': [0xFC,0x02,0x02,0x02,0xFC],
    'V': [0xF8,0x04,0x02,0x04,0xF8],
    'W': [0xFC,0x02,0x1C,0x02,0xFC],
    'X': [0xC6,0x28,0x10,0x28,0xC6],
    'Y': [0xE0,0x10,0x0E,0x10,0xE0],
    'Z': [0x86,0x8A,0x92,0xA2,0xC2],
    '!': [0x00,0x00,0xBE,0x00,0x00],
}

def draw_text(surface, x, y, text, color=(255, 255, 255)):
    cx = x
    for char in text.upper():
        if char not in FONT:
            char = ' '
        bitmap = FONT[char]
        for col in range(5):
            bits = bitmap[col]
            for row in range(8):
                if bits & (1 << (7 - row)):
                    surface.set_at((cx + col, y + row), color)
        cx += 6  # 5 pixels + 1 space

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((DISPLAY_SIZE, DISPLAY_SIZE))
pygame.display.set_caption("Circle Display Simulator - Preston & Willoh's Gift")
clock = pygame.time.Clock()

# Main loop
running = True
last_success = False
show_success_message = False
message_start_time = 0

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Clear screen
    screen.fill((0, 0, 0))

    # Draw "Loading..." initially or on failure
    if not last_success:
        draw_text(screen, 80, 110, "Loading...", (200, 200, 200))

    success = True
    base_url = f"http://{SERVER_IP}:{PORT}"

    offset_x = (DISPLAY_SIZE - SRC_SIZE * SCALE) // 2
    offset_y = (DISPLAY_SIZE - SRC_SIZE * SCALE) // 2

    pixel_index = 0
    for chunk_n in range(CHUNKS):
        try:
            url = f"{base_url}/pixel?n={chunk_n}"
            # Add headers to prevent gzip compression
            headers = {'Accept-Encoding': 'identity'}
            r = requests.get(url, timeout=10, headers=headers)
            
            if r.status_code == 200:
                data = r.content
                expected_len = 32
                if len(data) != expected_len:
                    print(f"Warning: chunk {chunk_n} got {len(data)} bytes (expected {expected_len}). Padding with zeros.")
                    data += b'\x00' * (expected_len - len(data))  # Pad short chunks (common for black areas)
                
                for i in range(0, len(data), 2):
                    if i + 1 >= len(data):
                        break  # Safety if odd length
                    high = data[i]
                    low = data[i + 1]
                    color = rgb565_to_rgb(high, low)
    
                    sx = pixel_index % SRC_SIZE
                    sy = pixel_index // SRC_SIZE
                    x = offset_x + sx * SCALE
                    y = offset_y + sy * SCALE
    
                    pygame.draw.rect(screen, color, (x, y, SCALE, SCALE))
    
                    pixel_index += 1
            else:
                print(f"Bad status for chunk {chunk_n}: {r.status_code}")
                success = False
                break
        except Exception as e:
            print(f"Error fetching chunk {chunk_n}: {e}")
            success = False
            # Optional: break here or continue trying next chunks
            break
    last_success = success

    if success:
        # Show birthday message for 8 seconds
        draw_text(screen, 60, 100, "Happy Birthday!!!", (255, 255, 255))
        draw_text(screen, 60, 120, "Mom", (255, 200, 200))
        draw_text(screen, 60, 140, "-Preston & Willoh", (200, 200, 255))
        show_success_message = True
        message_start_time = time.time()
    else:
        draw_text(screen, 40, 100, "No Photo", (255, 100, 100))
        draw_text(screen, 20, 130, "Check Server", (200, 200, 200))

    pygame.display.flip()
    clock.tick(10)  # Limit to ~10 FPS to reduce server load

pygame.quit()
sys.exit()
