# secondary.py - Minimal display test: init TFT and show "Worked!"
import time
from st7735 import TFT
import machine

# TFT pins
sck_pin = machine.Pin(8)
mosi_pin = machine.Pin(20)
dc_pin = machine.Pin(9)
rst_pin = machine.Pin(19)

spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0,
                  sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)
tft.rotation(1)
tft.fill(TFT.BLACK)

# Show success message (large, centered)
tft.draw_small_text((20, 30), "Worked!", TFT.GREEN)
tft.draw_small_text((10, 60), "Secondary running", TFT.CYAN)

while True:
    time.sleep(1)
