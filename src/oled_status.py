#!/usr/bin/env python3
import time, socket, subprocess, re
import board, busio, digitalio
from adafruit_ssd1305 import SSD1305_I2C

WIDTH, HEIGHT = 128, 32        # Product 4567 is 128x32
I2C_ADDR = 0x3C                 # Default SSD1305 I2C address
RST_PIN = board.D4              # Bonnet reset pin

def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "raspberrypi"

def get_ipv4():
    # 1) Prefer `hostname -I` (first IPv4)
    try:
        txt = subprocess.check_output(["hostname", "-I"], text=True).strip()
        parts = [p for p in txt.split() if re.match(r"\d+\.\d+\.\d+\.\d+$", p)]
        if parts:
            return parts[0]
    except Exception:
        pass
    # 2) UDP “no-send” trick: asks kernel for default outbound IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def main():
    # Init display
    i2c = busio.I2C(board.SCL, board.SDA)
    reset = digitalio.DigitalInOut(RST_PIN)
    disp = SSD1305_I2C(WIDTH, HEIGHT, i2c, addr=I2C_ADDR, reset=reset)

    # Draw helper
    def draw(lines):
        disp.fill(0)
        y = 0
        for line in lines[: (HEIGHT // 8)]:  # 8px text rows
            disp.text(line[:21], 0, y, 1)    # ~21 chars across at 6x8/8x8 font
            y += 16                          # 16px spacing for readability
        disp.show()

    host = get_hostname()
    last_ip = None

    # Initial screen
    draw([host, "IP: (waiting)"])

    while True:
        try:
            ip = get_ipv4()
            if ip != last_ip:
                draw([host, ip or "IP: (waiting)"])
                last_ip = ip
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception:
            # Keep trying if anything transient fails
            time.sleep(5)

if __name__ == "__main__":
    main()
