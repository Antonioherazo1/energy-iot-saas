#!/usr/bin/env python3
import sys, json, io, os, mimetypes
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = "https://thinc.site/api/v1"

def _request(method, url, headers=None, data=None, files=None):
    if files:
        boundary = b"----BOUNDARY123"
        body = io.BytesIO()
        for name, (filename, fdata) in files.items():
            body.write(b"--" + boundary + b"\r\n")
            ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            disposition = f'Content-Disposition: form-data; name="{name}"; filename="{os.path.basename(filename)}"\r\n'
            body.write(disposition.encode())
            body.write(f"Content-Type: {ct}\r\n\r\n".encode())
            body.write(fdata)
            body.write(b"\r\n")
        if data:
            for k, v in data.items():
                body.write(b"--" + boundary + b"\r\n")
                body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
                body.write(v.encode() if isinstance(v, str) else v)
                body.write(b"\r\n")
        body.write(b"--" + boundary + b"--\r\n")
        payload = body.getvalue()
        if not headers:
            headers = {}
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary.decode()}"
    elif data:
        payload = json.dumps(data).encode()
        if not headers:
            headers = {}
        headers.setdefault("Content-Type", "application/json")
    else:
        payload = None

    req = Request(url, data=payload, method=method, headers=headers or {})
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        print(f"ERROR {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

def main():
    bin_path = sys.argv[1] if len(sys.argv) > 1 else "Medidor_IOT/build/esp32.esp32.esp32/Medidor_IOT.ino.bin"
    version = sys.argv[2] if len(sys.argv) > 2 else "2.1-test"
    email = sys.argv[3] if len(sys.argv) > 3 else "admin@thinc.site"
    password = sys.argv[4] if len(sys.argv) > 4 else "cambiame"

    print("==> Login...")
    r = _request("POST", f"{API}/auth/login", data={"email": email, "password": password})
    token = r["access_token"]

    print(f"==> Subiendo firmware v{version}...")
    with open(bin_path, "rb") as f:
        r = _request("POST", f"{API}/firmware/upload",
                     headers={"Authorization": f"Bearer {token}"},
                     data={"version": version},
                     files={"file": (bin_path, f.read())})
    fw_id = r["firmware"]["id"]
    print(f"  Firmware ID: {fw_id}")

    print("==> Enviando OTA a TODOS los dispositivos...")
    r = _request("POST", f"{API}/firmware/ota/all",
                 headers={"Authorization": f"Bearer {token}"},
                 data={"firmware_id": fw_id})
    print(f"  {json.dumps(r, indent=2)}")

if __name__ == "__main__":
    main()
