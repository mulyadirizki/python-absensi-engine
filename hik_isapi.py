"""
Klien kecil Hikvision ISAPI untuk terminal absensi/akses (termasuk Fingerspot.io DS-11MK
yang berbasis Hikvision). Hanya fungsi BACA yang dipakai; tidak ada yang mengubah mesin.
"""

import datetime as dt
import json
import socket
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPDigestAuth
except ImportError:
    raise SystemExit("Modul requests belum terpasang. Jalankan: pip install -r requirements.txt")

# Kode minor event (major 5 = event akses) yang umum di terminal Hikvision
NAMA_MINOR = {
    1: "kartu",
    38: "sidik jari",
    75: "wajah",
    76: "wajah gagal",
    104: "wajah+kartu",
    105: "wajah+sidik jari",
    112: "wajah+password",
}


class GagalLogin(Exception):
    pass


class HikISAPI:
    def __init__(self, host, username, password, port=None, https=False, timeout=15, verify_ssl=False):
        self.host = host
        self.https = https
        self.port = int(port or (443 if https else 80))
        skema = "https" if https else "http"
        self.base = f"{skema}://{host}:{self.port}"
        self.timeout = timeout
        self.s = requests.Session()
        self.s.auth = HTTPDigestAuth(username, password)
        self.s.verify = verify_ssl
        if not verify_ssl:
            requests.packages.urllib3.disable_warnings()  # sertifikat mesin self-signed

    # ---------- HTTP dasar ----------
    def _cek(self, r):
        if r.status_code == 401:
            raise GagalLogin("username/password salah (401). Hati-hati: mesin bisa mengunci akun setelah beberapa kali gagal.")
        r.raise_for_status()
        return r

    def get(self, path):
        return self._cek(self.s.get(self.base + path, timeout=self.timeout))

    def post_json(self, path, body):
        r = self._cek(self.s.post(self.base + path, data=json.dumps(body), timeout=self.timeout,
                                  headers={"Content-Type": "application/json"}))
        return r.json()

    # ---------- Info ----------
    def port_terbuka(self, timeout=3):
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def tanpa_login(self):
        """Request tanpa kredensial: mesin ISAPI membalas 401 + header Digest."""
        r = requests.get(self.base + "/ISAPI/System/deviceInfo", timeout=self.timeout, verify=self.s.verify)
        return r.status_code, r.headers.get("WWW-Authenticate", "")

    def device_info(self):
        return _xml_ke_dict(self.get("/ISAPI/System/deviceInfo").text)

    def waktu(self):
        return _xml_ke_dict(self.get("/ISAPI/System/time").text)

    def jumlah_user(self):
        data = self.get("/ISAPI/AccessControl/UserInfo/Count?format=json").json()
        return data.get("UserInfoCount", {}).get("userNumber")

    def jumlah_event(self, mulai, akhir, tz):
        body = {"AcsEventTotalNumCond": {"major": 5, "minor": 0,
                                         "startTime": _iso(mulai, tz), "endTime": _iso(akhir, tz)}}
        return self.post_json("/ISAPI/AccessControl/AcsEventTotalNum?format=json", body) \
            .get("AcsEventTotalNum", {}).get("totalNum")

    # ---------- Log absensi ----------
    def events(self, mulai, akhir, tz, per_halaman=30):
        """Generator semua event akses (major 5) pada rentang waktu, dengan paging."""
        search_id = uuid.uuid4().hex
        posisi = 0
        while True:
            body = {"AcsEventCond": {
                "searchID": search_id,
                "searchResultPosition": posisi,
                "maxResults": per_halaman,
                "major": 5,
                "minor": 0,
                "startTime": _iso(mulai, tz),
                "endTime": _iso(akhir, tz),
            }}
            data = self.post_json("/ISAPI/AccessControl/AcsEvent?format=json", body).get("AcsEvent", {})
            daftar = data.get("InfoList") or []
            yield from daftar
            posisi += len(daftar)
            if data.get("responseStatusStrg") != "MORE" or not daftar:
                break


def _iso(waktu, tz):
    return waktu.strftime("%Y-%m-%dT%H:%M:%S") + tz


def _xml_ke_dict(teks):
    akar = ET.fromstring(teks)
    return {el.tag.split("}")[-1]: (el.text or "").strip() for el in akar.iter() if len(el) == 0}


def format_waktu(teks):
    """'2026-11-12T08:01:02+07:00' -> '2026-11-12 08:01:02' (jam lokal mesin)."""
    try:
        return dt.datetime.fromisoformat(teks).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return teks


def muat_mesin(path, filter_nama=None):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"File {path.name} tidak ada. Salin mesin_hik.example.json menjadi {path.name} lalu isi datanya.")
    with path.open(encoding="utf-8") as f:
        daftar = [m for m in json.load(f) if m.get("aktif", True)]
    if filter_nama:
        dicari = {n.lower() for n in filter_nama}
        daftar = [m for m in daftar if m.get("nama", "").lower() in dicari or m["host"] in dicari]
    if not daftar:
        raise SystemExit("Tidak ada mesin yang cocok/aktif.")
    return daftar


def buat_klien(m):
    return HikISAPI(
        host=m["host"],
        username=m.get("username", "admin"),
        password=m["password"],
        port=m.get("port"),
        https=bool(m.get("https", False)),
        timeout=int(m.get("timeout", 15)),
    )
