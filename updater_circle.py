import time
import urequests
import machine
import os
import gc

print("=== CIRCLE UPDATER (DNS-only for 5 MACs) ===")
gc.collect()

mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()
print("Device MAC:", mac_str)

target_circle_macs = {
    '34:98:7A:07:12:B8',
    '34:98:7A:07:11:7C',
    '34:98:7A:06:FD:74',
    '34:98:7A:07:13:40',
    '34:98:7A:07:09:68'
}

if mac_str not in target_circle_macs:
    print("Not a target circle device → reverting")
    try:
        r = urequests.get(f'http://108.254.1.184:9019/secondary.mpy', timeout=10)
        if r.status_code == 200:
            with open('/secondary.mpy.tmp', 'wb') as f:
                f.write(r.content)
            os.rename('/secondary.mpy.tmp', '/secondary.mpy')
        r.close()
    except:
        pass
    machine.reset()

# === TARGET CIRCLE DEVICE ONLY ===
print("TARGET CIRCLE DEVICE CONFIRMED — performing DNS OTA")
old_ip = '108.254.1.184'

# Update server_ip.txt (DNS only)
with open('/server_ip.txt', 'w') as f:
    f.write('mosquitofish.immenseaccumulationonline.online')
print("Updated /server_ip.txt to DNS")

# Download new_boot.py (already served by server)
url_boot = f'http://{old_ip}:9019/new_boot.py'
try:
    r = urequests.get(url_boot, timeout=15)
    if r.status_code == 200:
        with open('/boot.py.tmp', 'w') as f:
            f.write(r.text)
        os.rename('/boot.py.tmp', '/boot.py')
        print("New boot.py written")
    r.close()
except Exception as e:
    print("boot.py error:", e)

# Download new_tertiary.mpy
url_ter = f'http://{old_ip}:9019/new_tertiary.mpy'
try:
    r = urequests.get(url_ter, timeout=15)
    if r.status_code == 200:
        with open('/tertiary.mpy.tmp', 'wb') as f:
            f.write(r.content)
        os.rename('/tertiary.mpy.tmp', '/tertiary.mpy')
        print("New tertiary.mpy written")
    r.close()
except Exception as e:
    print("tertiary.mpy error:", e)

print("CIRCLE UPGRADE COMPLETE — resetting!")
machine.reset()
