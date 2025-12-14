# secondary.py - ESP32-C2 Christmas Gift LED Animation (Test Version)
# Loops festive LED patterns; prints status. Runs until reset.

import machine
import time
import uos

# Built-in LED on GPIO 2 (adjust for your board)
led = machine.Pin(2, machine.Pin.OUT)

def blink_fast(count=10, delay=0.1):
    """Twinkling lights pattern."""
    for _ in range(count):
        led.on()
        time.sleep(delay)
        led.off()
        time.sleep(delay)

def blink_slow(count=3, delay=0.5):
    """Gift reveal pulse."""
    for _ in range(count):
        led.on()
        time.sleep(delay)
        led.off()
        time.sleep(delay * 2)

def christmas_cycle():
    """One full holiday cycle."""
    print("🎄 Merry Christmas! Starting gift animation... Also Willoh Shoutout! 🎁")
    blink_fast(20, 0.05)  # Fast twinkles
    blink_slow(5, 0.3)    # Slow reveal
    print("Animation complete. Uptime: {}s".format(time.ticks_ms() // 1000))
    led.off()  # Idle low

print("secondary.py loaded. Starting Christmas gift loop...")
cycle_count = 0
while True:
    cycle_count += 1
    christmas_cycle()
    print(f"Cycle {cycle_count} done. Waiting for next reset...")
    time.sleep(5)  # Short pause between cycles
