# secondary.py - Tracking ping + display "h" on TFT
import machine
import time
from st7735 import TFT

# Pins/SPI
sck_pin = machine.Pin(8)   # SCL
mosi_pin = machine.Pin(20) # SDA
dc_pin = machine.Pin(9)    # DC
rst_pin = machine.Pin(19)  # RES

# Safe low baudrate to prevent fuzz
spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0, sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)

# Your working settings
tft.rotation(1)
mirror_text = False

# Simple LCG for pseudo-random numbers
seed = 12345
def rand():
    global seed
    seed = (1103515245 * seed + 12345) & 0x7fffffff
    return seed

# Helper to generate random 16-bit color (bright-ish)
def random_color():
    r = (rand() % 31) << 11  # 5 bits red
    g = (rand() % 63) << 5   # 6 bits green
    b = (rand() % 31)        # 5 bits blue
    return r | g | b

# Helper for random int in range
def rand_range(min_val, max_val):
    return min_val + (rand() % (max_val - min_val + 1))

# Gaussian approximation for dollar value (mean $2.00, std $0.10)
def gaussian_random():
    u1 = rand() / 0x7fffffff
    u2 = rand() / 0x7fffffff
    z = (-2.0 * u1 ** 0.5) * (u2 * 6.283185307179586)  # approx cos
    value = 2.0 + z * 0.1
    if value < 1.5:
        value = 1.5
    if value > 2.5:
        value = 2.5
    return value

# Main infinite loop (removed the range(2) so it runs forever)
for i in range(1):
    tft.fill(TFT.BLACK)  # White background

    # Draw 8 random filled circles in the background
    for _ in range(8):
        cx = rand_range(10, tft.size()[0] - 10)
        cy = rand_range(10, tft.size()[1] - 10)
        radius = rand_range(10, 25)
        color = random_color()
        tft.fillcircle((cx, cy), radius, color)

    # Generate and display PEPE value on top
    dollar_amount = gaussian_random()
    text = "PEPE: ${:.2f}".format(dollar_amount)

    w, h = tft.size()
    text_width = len(text) * 6
    x = (w - text_width) // 2
    y = (h - 8) // 2

    tft.draw_small_text((x, y), text, TFT.WHITE, mirror=mirror_text)

    time.sleep(5)  # Update every 5 seconds

