from machine import Pin, SPI
import gc9a01
import time

# Hardware SPI on ESP32-C2 (try SPI(1) or SPI(2) if one doesn't work)
spi = SPI(1, baudrate=40000000, polarity=0, phase=0, sck=Pin(8), mosi=Pin(20))

tft = gc9a01.GC9A01(
    spi,
    240,
    240,
    dc=Pin(9, Pin.OUT),
    reset=Pin(19, Pin.OUT),
    rotation=0)  # Try 0-7 if upside down

tft.init()
tft.fill(gc9a01.BLACK)

# Test: full white screen
tft.fill(gc9a01.WHITE)
time.sleep(5)

# Test: red screen
tft.fill(gc9a01.RED)

while True:
    time.sleep(1)
