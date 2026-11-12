"""
Tes koneksi ke mesin absensi Hikvision / Fingerspot.io DS-11MK lewat ISAPI (jaringan lokal, tanpa cloud).

Contoh:
    python tes_koneksi_hik.py --host 10.1.36.20 --user admin          # password ditanya (tidak tampil)
    python tes_koneksi_hik.py --host 10.1.36.20 --user admin --https
    python tes_koneksi_hik.py                                         # semua mesin aktif di mesin_hik.json

Langkah:
    1. Port HTTP/HTTPS terbuka?
    2. Tanpa login -> mesin membalas 401 Digest? (memastikan ini ISAPI)
    3. Login -> info device (model, SN, firmware)
    4. Jam mesin, jumlah user, jumlah log 7 hari terakhir

HANYA membaca. Login yang gagal tidak diulang, karena mesin bisa mengunci akun
setelah beberapa kali salah password.
"""

import argparse
import datetime as dt
import getpass
import sys
from pathlib import Path

from hik_isapi import GagalLogin, buat_klien, muat_mesin


def tes(m, tz):
    k = buat_klien(m)
    print(f"\n=== {m.get('nama', m['host'])} ({k.base}) ===")

    print("1) Port")
    if not k.port_terbuka():
        print(f"   [GAGAL] port {k.port} tidak bisa dibuka. Cek IP, jaringan, firewall, atau coba --https.")
        return False
    print(f"   [OK]    port {k.port} terbuka")

    print("2) Cek ISAPI (tanpa login)")
    try:
        kode, auth = k.tanpa_login()
    except Exception as e:
        print(f"   [GAGAL] {e}")
        return False
    if kode == 401 and "digest" in auth.lower():
        print(f"   [OK]    ISAPI terdeteksi ({auth.split(',')[0]})")
    else:
        print(f"   [INFO]  respons tak terduga: HTTP {kode} {auth}. Tetap dicoba login.")

    print("3) Login + info device")
    try:
        info = k.device_info()
    except GagalLogin as e:
        print(f"   [GAGAL] {e}")
        return False
    except Exception as e:
        print(f"   [GAGAL] {e}")
        return False
    print("   [OK]    login berhasil")
    for kunci in ("deviceName", "model", "serialNumber", "firmwareVersion", "firmwareReleasedDate", "macAddress"):
        if info.get(kunci):
            print(f"   {kunci:<20}: {info[kunci]}")

    print("4) Data")
    try:
        w = k.waktu()
        print(f"   {'jam mesin':<20}: {w.get('localTime')}  (timeZone {w.get('timeZone')})")
    except Exception as e:
        print(f"   [INFO]  jam mesin tidak terbaca: {e}")
    try:
        print(f"   {'jumlah user':<20}: {k.jumlah_user()}")
    except Exception as e:
        print(f"   [INFO]  jumlah user tidak terbaca: {e}")
    akhir = dt.datetime.now().replace(microsecond=0)
    mulai = (akhir - dt.timedelta(days=7)).replace(hour=0, minute=0, second=0)
    try:
        print(f"   {'log 7 hari terakhir':<20}: {k.jumlah_event(mulai, akhir, tz)} event")
    except Exception as e:
        print(f"   [INFO]  jumlah log tidak terbaca ({e}); dicoba ambil 1 halaman...")
        try:
            n = sum(1 for _ in zip(range(30), k.events(mulai, akhir, tz)))
            print(f"   {'contoh log':<20}: {n} event terbaca")
        except Exception as e2:
            print(f"   [GAGAL] log tidak terbaca: {e2}")
            return False
    return True


def main():
    p = argparse.ArgumentParser(description="Tes koneksi mesin Hikvision/Fingerspot DS-11MK (ISAPI)")
    p.add_argument("--host", help="IP mesin (tanpa perlu mesin_hik.json)")
    p.add_argument("--user", default="admin")
    p.add_argument("--port", type=int, help="default 80 (http) / 443 (https)")
    p.add_argument("--https", action="store_true")
    p.add_argument("--tz", default="+07:00", help="zona waktu mesin, default +07:00 (WIB)")
    p.add_argument("--config", default=str(Path(__file__).resolve().parent / "mesin_hik.json"))
    p.add_argument("--mesin", nargs="*", help="nama atau IP mesin di mesin_hik.json")
    args = p.parse_args()

    if args.host:
        daftar = [{"host": args.host, "username": args.user, "port": args.port, "https": args.https,
                   "password": getpass.getpass(f"Password {args.user}@{args.host}: ")}]
    else:
        daftar = muat_mesin(args.config, args.mesin)

    hasil = [(m.get("nama", m["host"]), tes(m, args.tz)) for m in daftar]
    print("\n=== Ringkasan ===")
    for nama, ok in hasil:
        print(f"  {'[OK]   ' if ok else '[GAGAL]'} {nama}")
    sys.exit(0 if all(ok for _, ok in hasil) else 1)


if __name__ == "__main__":
    main()
