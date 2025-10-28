from __future__ import annotations
from typing import Any, Dict, List
from .config import initialize_config, load_cfg, save_cfg
import logging
import threading

# --- GPIO (real or mock)
try:
    import RPi.GPIO as _GPIO
    GPIO = _GPIO
    REAL_GPIO = True
except Exception:  # Mock
    REAL_GPIO = False
    class _Mock:
        BCM = "BCM"; OUT = "OUT"; IN = "IN"; HIGH = 1; LOW = 0
        _vals: Dict[int,int] = {}
        def setwarnings(self, *_): pass
        def setmode(self, *_): pass
        def setup(self, pin, mode, initial=0): self._vals[int(pin)] = 1 if initial else 0
        def output(self, pin, val): self._vals[int(pin)] = 1 if val else 0
        def input(self, pin): return self._vals.get(int(pin), 0)
        def cleanup(self, pin=None):
            if pin is None:
                self._vals.clear()
            else:
                self._vals.pop(int(pin), None)
    GPIO = _Mock()

def _coerce_mode(mode: str | None) -> str:
    return "output" if (mode or "output").lower() not in ("input","in") else "input"

class GpioManager:
    """Single source of truth for GPIO state and config persistence."""
    def __init__(self, socketio):
        self.socketio = socketio
        self.lock = threading.RLock()
        self.log = logging.getLogger(__name__)
        initialize_config()
        self.cfg = load_cfg()
        self._last_inputs: Dict[int, int] = {} # Remembers the last state
        self._setup_hw()

    # ---- hardware helpers
    def _setup_hw(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.log.info("gpio_init_start count=%d", len(self.cfg.get("gpio", [])))
        for item in self.cfg.get("gpio", []):
            pin = int(item["pin"])
            mode = _coerce_mode(item.get("mode"))
            val  = int(item.get("value", 0))
            self._setup_pin(pin, mode, val)
        self.log.info("gpio_init_done")

    def _setup_pin(self, pin: int, mode: str, value: int = 0) -> None:
        try:
            if mode == "output":
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH if value else GPIO.LOW)
                self.log.info("gpio_setup pin=%d mode=output initial=%d ok=1", pin, value)
            else:
                GPIO.setup(pin, GPIO.IN)
                # prime last_inputs with current value so first poll can detect an edge cleanly
                try:
                    self._last_inputs[pin] = 1 if GPIO.input(pin) else 0
                except Exception:
                    self._last_inputs[pin] = 0
                self.log.info("gpio_setup pin=%d mode=input ok=1", pin)
        except Exception as e:
            # don't crash the server; record failure
            self.log.exception("gpio_setup pin=%d mode=%s ok=0 err=%r", pin, mode, e)

    def _cleanup_pin(self, pin: int) -> None:
        try:
            GPIO.cleanup(pin)
            self.log.info("gpio_cleanup pin=%d ok=1", pin)
        except Exception as e:
            self.log.exception("gpio_cleanup pin=%d ok=0 err=%r", pin, e)

    # ---- public API
    def state(self) -> List[Dict[str,Any]]:
        out = []
        items = self.cfg.get("gpio", [])
        for it in items:
            pin  = int(it["pin"])
            mode = _coerce_mode(it.get("mode"))
            val  = int(it.get("value", 0))
            if mode != "output":
                try:
                    new_val = 1 if GPIO.input(pin) else 0
                except Exception:
                    new_val = 0
                # log only on input edge
                prev = self._last_inputs.get(pin)
                if prev is None:
                    self._last_inputs[pin] = new_val
                elif new_val != prev:
                    self._last_inputs[pin] = new_val
                    self.log.info("gpio_read_change pin=%d from=%d to=%d", pin, prev, new_val)
                val = new_val
            out.append({
                "pin": pin,
                "name": it.get("name", f"Pin {pin}"),
                "mode": mode,
                "value": int(val),
            })
        return out

    def set_value(self, pin: int, value: int) -> Dict[str,Any]:
        with self.lock:
            value = 1 if value else 0
            for it in self.cfg.get("gpio", []):
                if int(it["pin"]) == pin:
                    if _coerce_mode(it.get("mode")) != "output":
                        self.log.warning("gpio_set_denied pin=%d reason=input-pin", pin)
                        raise ValueError("Cannot set value on input pin")
                    old = int(it.get("value", 0))
                    try:
                        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)
                    except Exception as e:
                        # still persist; record hardware error
                        self.log.exception("gpio_write pin=%d from=%d to=%d hw_ok=0 err=%r", pin, old, value, e)
                    else:
                        self.log.info("gpio_write pin=%d from=%d to=%d hw_ok=1", pin, old, value)
                    it["value"] = value
                    save_cfg(self.cfg)
                    self.socketio.emit("gpio_update", {"pin": pin, "value": value})
                    return {"pin": pin, "name": it.get("name", f"Pin {pin}"),
                            "mode": _coerce_mode(it.get("mode")), "value": value}
            self.log.warning("gpio_set_missing pin=%d", pin)
            raise KeyError(f"Pin {pin} not in config")

    def add_pin(self, pin: int, name: str, mode: str = "output", value: int = 0) -> Dict[str,Any]:
        with self.lock:
            pin = int(pin); value = 1 if value else 0; mode = _coerce_mode(mode)
            if any(int(it["pin"]) == pin for it in self.cfg.get("gpio", [])):
                self.log.warning("gpio_add_denied pin=%d reason=duplicate", pin)
                raise ValueError(f"Pin {pin} already exists")
            self._setup_pin(pin, mode, value)
            item = {"pin": pin, "name": name or f"Pin {pin}", "mode": mode, "value": value}
            self.cfg.setdefault("gpio", []).append(item)
            save_cfg(self.cfg)
            self.socketio.emit("gpio_added", item)
            self.log.info("gpio_add pin=%d name=%s mode=%s initial=%d", pin, item["name"], mode, value)
            return item

    def remove_pin(self, pin: int) -> None:
        with self.lock:
            pin = int(pin)
            items = self.cfg.get("gpio", [])
            idx = next((i for i, it in enumerate(items) if int(it["pin"]) == pin), None)
            if idx is None:
                self.log.warning("gpio_remove_missing pin=%d", pin)
                raise KeyError(f"Pin {pin} not in config")
            self._cleanup_pin(pin)
            removed = items.pop(idx)
            save_cfg(self.cfg)
            self.socketio.emit("gpio_removed", {"pin": pin})
            self.log.info("gpio_remove pin=%d name=%s", pin, removed.get("name"))

    def rename_pin(self, pin: int, new_name: str) -> Dict[str,Any]:
        with self.lock:
            pin = int(pin)
            for it in self.cfg.get("gpio", []):
                if int(it["pin"]) == pin:
                    old = it.get("name", f"Pin {pin}")
                    it["name"] = new_name or old
                    save_cfg(self.cfg)
                    payload = {"pin": pin, "name": it["name"]}
                    self.socketio.emit("gpio_renamed", payload)
                    self.log.info("gpio_rename pin=%d from=%s to=%s", pin, old, it["name"])
                    return {"pin": pin, "name": it["name"], "mode": _coerce_mode(it.get("mode")), "value": int(it.get("value", 0))}
            self.log.warning("gpio_rename_missing pin=%d", pin)
            raise KeyError(f"Pin {pin} not in config")
