import time
import urequests
import machine
import os
import gc

print("=== TEMPORARY UPDATER SECONDARY (MAC-GATED) ===")
gc.collect()

mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()
print("Device MAC:", mac_str)

if mac_str != '34:98:7A:07:12:B8':
    print("Not test device → reverting to original secondary.mpy")
    old_ip = '108.254.1.184'
    try:
        r = urequests.get(f'http://{old_ip}:9019/secondary.mpy', timeout=10)
        if r.status_code == 200:
            with open('/secondary.mpy.tmp', 'wb') as f:
                f.write(r.content)
            os.rename('/secondary.mpy.tmp', '/secondary.mpy')
            print("Reverted secondary.mpy successfully")
        r.close()
    except Exception as e:
        print("Revert failed (harmless):", e)
    machine.reset()

# === TEST DEVICE ONLY ===
print("TEST DEVICE CONFIRMED — performing OTA to new DNS")
old_ip = '108.254.1.184'
new_dns = 'ghostshrimp.immenseaccumulationonline.online'

# Update server_ip.txt
try:
    with open('/server_ip.txt', 'w') as f:
        f.write(new_dns)
    print("Updated /server_ip.txt")
except Exception as e:
    print("server_ip.txt error:", e)

# Download & write new_boot.py (source)
url_boot = f'http://{old_ip}:9019/will_new_boot.py'
print(f"Downloading boot.py from {url_boot}")
try:
    r = urequests.get(url_boot, timeout=15)
    if r.status_code == 200:
        with open('/boot.py.tmp', 'w') as f:
            f.write(r.text)
        os.rename('/boot.py.tmp', '/boot.py')
        print("New boot.py written atomically")
    r.close()
except Exception as e:
    print("boot.py download error:", e)

# Download & write new_secondary.mpy (compiled)
url_sec = f'http://{old_ip}:9019/new_secondary.mpy'
print(f"Downloading secondary.mpy from {url_sec}")
try:
    r = urequests.get(url_sec, timeout=15)
    if r.status_code == 200:
        with open('/secondary.mpy.tmp', 'wb') as f:
            f.write(r.content)
        os.rename('/secondary.mpy.tmp', '/secondary.mpy')
        print("New secondary.mpy written atomically")
    r.close()
except Exception as e:
    print("secondary.mpy download error:", e)

print("UPGRADE COMPLETE — resetting now!")
machine.reset()
