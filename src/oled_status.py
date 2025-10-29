#!/usr/bin/env python3
import time, socket, subprocess, re, sys
import board, busio, digitalio
from PIL import Image, ImageDraw, ImageFont
from adafruit_ssd1305 import SSD1305_I2C

WIDTH, HEIGHT = 128, 32        # Adafruit #4567 is 128x32
I2C_ADDR = 0x3C                 # Default SSD1305 I2C address
# Some boards don’t wire reset; use None if D4 isn’t present.
RST_PIN = getattr(board, "D4", None)

def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "raspberrypi"

def get_ipv4() -> str | None:
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
    # Init I2C + display
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        reset = None
        if RST_PIN is not None:
            try:
                reset = digitalio.DigitalInOut(RST_PIN)
            except Exception:
                reset = None
        disp = SSD1305_I2C(WIDTH, HEIGHT, i2c, addr=I2C_ADDR, reset=reset)
    except Exception as e:
        print(f"[oled] failed to init display (is I2C enabled?): {e}", file=sys.stderr)
        time.sleep(2)
        return

    image = Image.new("1", (disp.width, disp.height))
    canvas = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    def render(lines: list[str]) -> None:
        # Clear background
        canvas.rectangle((0, 0, disp.width, disp.height), outline=0, fill=0)
        y = 0
        for line in lines[:3]:  # 3 lines fit comfortably at ~10px spacing
            canvas.text((0, y), line[:21], font=font, fill=255)
            y += 10
        disp.image(image)
        disp.show()

    host = get_hostname()
    last_ip = None

    # Initial screen
    render([host, "IP: (waiting)"])

    while True:
        try:
            ip = get_ipv4()
            line2 = f"IP: {ip}" if ip else "IP: (waiting)"
            if ip != last_ip:
                render([host, line2])
                last_ip = ip
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception:
            # transient error: wait and retry
            time.sleep(5)

if __name__ == "__main__":
    main()
