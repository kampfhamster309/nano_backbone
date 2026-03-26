"""
Captive portal provisioning for the Arduino Nano RP2040 Connect.
Uses adafruit_esp32spi to drive the Nina W102 WiFi co-processor.

Required libraries in /lib/:
  adafruit_esp32spi/
  adafruit_bus_device/
"""

import time
import board
import busio
import microcontroller
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi

AP_SSID = "nano-backbone"
AP_PORT = 80
# Nina W102 assigns itself this IP when acting as an AP.
_AP_FALLBACK_IP = "192.168.4.1"

_FORM_HTML = """\
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>nano_backbone Setup</title>
<style>
body{font-family:sans-serif;max-width:420px;margin:40px auto;padding:0 16px}
label{display:block;margin-bottom:12px;font-size:.9em}
input[type=text],input[type=password]{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px;font-size:1em}
input[type=submit]{padding:9px 20px;font-size:1em;margin-top:8px}
</style></head>
<body><h2>nano_backbone Setup</h2>
<form method="POST">
<label>WiFi SSID<input name="ssid" type="text" required></label>
<label>WiFi Password<input name="password" type="password"></label>
<label>Server URL<input name="server_url" type="text" placeholder="http://192.168.1.100:8000" required></label>
<label>API Key<input name="api_key" type="text" required></label>
<input type="submit" value="Save and Reboot">
</form></body></html>"""

_SAVED_HTML = """\
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Saved</title></head>
<body><h2>Saved!</h2><p>Device is rebooting&hellip;</p></body></html>"""

_ERROR_HTML = """\
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Error</title></head>
<body><h2>Missing required fields</h2><p>SSID, Server URL and API Key are required.</p>
<a href="/">Go back</a></body></html>"""


# ── Pure-Python helpers (no CircuitPython dependencies) ───────────────────────

def _url_decode(s):
    s = s.replace("+", " ")
    out = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1 : i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _parse_form(body):
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, _, v = pair.partition("=")
            params[_url_decode(k)] = _url_decode(v)
    return params


def _write_settings(ssid, password, server_url, api_key):
    def _esc(v):
        return v.replace("\\", "\\\\").replace('"', '\\"')

    content = (
        f'WIFI_SSID = "{_esc(ssid)}"\n'
        f'WIFI_PASSWORD = "{_esc(password)}"\n'
        f'SERVER_URL = "{_esc(server_url)}"\n'
        f'DEVICE_API_KEY = "{_esc(api_key)}"\n'
        f'CURRENT_VERSION = "0.0.0"\n'
    )
    with open("/settings.toml", "w") as f:
        f.write(content)


# ── ESP32SPI-backed I/O ────────────────────────────────────────────────────────

def _setup_esp():
    """Initialise the Nina W102 over SPI.

    Pin constants for the Arduino Nano RP2040 Connect. If you get an
    AttributeError here, run `import board; print(dir(board))` in the REPL
    to see what your build exposes.
    """
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs = DigitalInOut(board.CS1)
    ready = DigitalInOut(board.ESP_BUSY)
    reset_pin = DigitalInOut(board.ESP_RESET)
    return adafruit_esp32spi.ESP_SPIcontrol(spi, cs, ready, reset_pin)


def _read_request(esp, sock):
    """Poll the socket until a full HTTP request has arrived.

    Returns (headers_str, body_str).
    """
    raw = b""
    for _ in range(200):
        try:
            chunk = esp.socket_read(sock, 64)
        except Exception:
            break
        if chunk:
            raw += chunk
        if b"\r\n\r\n" in raw:
            header_bytes, _, body_so_far = raw.partition(b"\r\n\r\n")
            headers = header_bytes.decode("utf-8", "replace")
            content_length = 0
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                    break
            body = body_so_far
            for _ in range(100):
                if len(body) >= content_length:
                    break
                try:
                    body += esp.socket_read(sock, content_length - len(body)) or b""
                except Exception:
                    break
            return headers, body.decode("utf-8", "replace")
        time.sleep(0.01)
    return raw.decode("utf-8", "replace"), ""


def _send_response(esp, sock, status, body_html):
    body_bytes = body_html.encode("utf-8")
    header = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("utf-8")
    esp.socket_write(sock, header)
    esp.socket_write(sock, body_bytes)


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    esp = _setup_esp()

    print("[captive] Resetting Nina W102...")
    esp.reset()
    time.sleep(1)

    print("[captive] Starting SoftAP:", AP_SSID)
    esp.create_AP(AP_SSID)

    try:
        ap_ip = esp.pretty_ip(esp.ip_address)
    except Exception:
        ap_ip = _AP_FALLBACK_IP
    print(f"[captive] Connect to '{AP_SSID}' and open http://{ap_ip}/")

    server_sock = esp.get_socket()
    esp.server_socket(server_sock, AP_PORT, adafruit_esp32spi.TCP_MODE)
    print("[captive] Listening on port", AP_PORT)

    while True:
        client_sock = esp.socket_available(server_sock)
        if client_sock is not None and client_sock != 255:
            print("[captive] Client connected, socket:", client_sock)
            try:
                headers, body = _read_request(esp, client_sock)
                first_line = headers.split("\r\n")[0] if headers else ""

                if first_line.startswith("POST"):
                    params = _parse_form(body)
                    ssid = params.get("ssid", "").strip()
                    password = params.get("password", "")
                    server_url = params.get("server_url", "").strip()
                    api_key = params.get("api_key", "").strip()

                    if ssid and server_url and api_key:
                        _write_settings(ssid, password, server_url, api_key)
                        _send_response(esp, client_sock, "200 OK", _SAVED_HTML)
                        esp.socket_close(client_sock)
                        print("[captive] Settings saved. Rebooting...")
                        time.sleep(1)
                        microcontroller.reset()
                    else:
                        _send_response(esp, client_sock, "400 Bad Request", _ERROR_HTML)
                else:
                    _send_response(esp, client_sock, "200 OK", _FORM_HTML)
            except Exception as e:
                print("[captive] Error:", e)
            finally:
                try:
                    esp.socket_close(client_sock)
                except Exception:
                    pass

        time.sleep(0.05)
