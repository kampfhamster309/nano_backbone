import time
import wifi
import socketpool
import microcontroller

AP_SSID = "nano-backbone"
AP_PORT = 80

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


def _read_request(conn):
    """Read a full HTTP request. Returns (headers_str, body_str)."""
    buf = b""
    conn.settimeout(5.0)
    try:
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv(64)
            if not chunk:
                break
            buf += chunk
    except OSError:
        pass

    if b"\r\n\r\n" not in buf:
        return buf.decode("utf-8", "replace"), ""

    header_bytes, _, body_so_far = buf.partition(b"\r\n\r\n")
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
    try:
        while len(body) < content_length:
            chunk = conn.recv(content_length - len(body))
            if not chunk:
                break
            body += chunk
    except OSError:
        pass

    return headers, body.decode("utf-8", "replace")


def _send_response(conn, status, body_html):
    body_bytes = body_html.encode("utf-8")
    header = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8")
    conn.send(header + body_bytes)


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


def run():
    print("[captive] Starting SoftAP:", AP_SSID)
    wifi.radio.start_ap(AP_SSID)
    ap_ip = wifi.radio.ipv4_address_ap
    print(f"[captive] AP IP: {ap_ip}")
    print(f"[captive] Connect to '{AP_SSID}' and open http://{ap_ip}/")

    pool = socketpool.SocketPool(wifi.radio)
    server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", AP_PORT))
    server.listen(1)
    server.settimeout(None)

    print("[captive] Listening on port", AP_PORT)

    while True:
        conn, addr = server.accept()
        print("[captive] Connection from", addr)
        try:
            headers, body = _read_request(conn)
            first_line = headers.split("\r\n")[0] if headers else ""

            if first_line.startswith("POST"):
                params = _parse_form(body)
                ssid = params.get("ssid", "").strip()
                password = params.get("password", "")
                server_url = params.get("server_url", "").strip()
                api_key = params.get("api_key", "").strip()

                if ssid and server_url and api_key:
                    _write_settings(ssid, password, server_url, api_key)
                    _send_response(conn, "200 OK", _SAVED_HTML)
                    conn.close()
                    print("[captive] Settings saved. Rebooting...")
                    time.sleep(1)
                    microcontroller.reset()
                else:
                    _send_response(conn, "400 Bad Request", _ERROR_HTML)
            else:
                _send_response(conn, "200 OK", _FORM_HTML)
        except Exception as e:
            print("[captive] Error:", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
