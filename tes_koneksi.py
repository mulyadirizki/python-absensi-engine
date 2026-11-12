"""
Tes koneksi ke mesin absensi Revo (protokol ZKTeco) langkah demi langkah.

Contoh:
    python tes_koneksi.py --ip 192.168.1.201                 # langsung ke satu IP
    python tes_koneksi.py --ip 192.168.1.201 --password 123  # jika Comm Key mesin diisi
    python tes_koneksi.py                                    # semua mesin aktif di machines.json
    python tes_koneksi.py --mesin "Kantor Pusat"

Langkah yang dicek per mesin:
    1. Ping                  -> mesin hidup & satu jaringan?
    2. Port TCP (4370)       -> port terbuka / tidak diblok firewall?
    3. Login protokol (TCP)  -> Comm Key benar? jika gagal dicoba juga lewat UDP
    4. Baca info mesin       -> SN, firmware, jam, jumlah user & log

Script ini HANYA membaca; tidak mengubah atau menghapus apa pun di mesin.
"""

import argparse
import json
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    from zk import ZK
except ImportError:
    sys.exit("Modul pyzk belum terpasang. Jalankan: pip install -r requirements.txt")

BASE_DIR = Path(__file__).resolve().parent


def ok(msg):
    print(f"   [OK]    {msg}")


def gagal(msg):
    print(f"   [GAGAL] {msg}")


def info(msg):
    print(f"   [INFO]  {msg}")


def tes_ping(ip):
    flag = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        r = subprocess.run(["ping", flag, "2", ip], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None  # ping tidak tersedia / macet -> tidak bisa disimpulkan
    # Windows bisa exit 0 untuk "Destination host unreachable", jadi cek juga ada "TTL="
    return r.returncode == 0 and "ttl=" in r.stdout.lower()


def tes_port(ip, port, timeout=3):
    mulai = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True, (time.perf_counter() - mulai) * 1000, None
    except OSError as e:
        return False, None, str(e)


def coba_login(ip, port, password, timeout, udp):
    zk = ZK(ip, port=port, timeout=timeout, password=password, force_udp=udp, ommit_ping=True)
    return zk.connect()


def baca_info(conn):
    hasil = {}
    for label, fungsi in [
        ("Serial number", conn.get_serialnumber),
        ("Nama device", conn.get_device_name),
        ("Firmware", conn.get_firmware_version),
        ("Platform", conn.get_platform),
        ("MAC", conn.get_mac),
        ("Jam mesin", conn.get_time),
    ]:
        try:
            hasil[label] = fungsi()
        except Exception as e:
            hasil[label] = f"(tidak terbaca: {e})"
    try:
        conn.read_sizes()  # baca kapasitas tanpa menarik seluruh data
        hasil["Jumlah user"] = conn.users
        hasil["Jumlah log"] = conn.records
        hasil["Jumlah sidik jari"] = conn.fingers
    except Exception as e:
        hasil["Kapasitas"] = f"(tidak terbaca: {e})"
    return hasil


def tes_mesin(m):
    nama = m.get("nama", m["ip"])
    ip = m["ip"]
    port = int(m.get("port", 4370))
    password = int(m.get("password", 0))
    timeout = int(m.get("timeout", 10))
    force_udp = bool(m.get("force_udp", False))

    print(f"\n=== {nama} ({ip}:{port}) ===")

    # 1. Ping
    print("1) Ping")
    hasil_ping = tes_ping(ip)
    if hasil_ping is True:
        ok("mesin membalas ping")
    elif hasil_ping is False:
        gagal("tidak membalas ping (bisa jadi ping diblok, lanjut cek port)")
    else:
        info("perintah ping tidak tersedia, dilewati")

    # 2. Port TCP
    print(f"2) Port TCP {port}")
    terbuka, ms, err = tes_port(ip, port)
    if terbuka:
        ok(f"port terbuka ({ms:.0f} ms)")
    else:
        gagal(f"port tidak bisa dibuka: {err}")
        if not force_udp:
            info("akan tetap dicoba lewat UDP")

    # 3. Login protokol ZK (TCP lalu UDP, atau UDP saja jika force_udp)
    print("3) Login protokol ZKTeco")
    urutan = [True] if force_udp else ([False, True] if terbuka else [True])
    conn, mode_ok, errors = None, None, []
    for udp in urutan:
        mode = "UDP" if udp else "TCP"
        try:
            conn = coba_login(ip, port, password, timeout, udp)
            mode_ok = mode
            ok(f"login berhasil via {mode}")
            break
        except Exception as e:
            errors.append(f"{mode}: {e}")
            gagal(f"login via {mode}: {e}")

    if conn is None:
        print("\n   Saran:")
        teks = " ".join(errors).lower()
        if "unauth" in teks:
            print("   - Comm Key salah. Cek menu mesin: Comm/Koneksi > Comm Key, lalu isi --password / 'password'.")
        if not terbuka and hasil_ping is not True:
            print("   - Mesin tidak terjangkau: cek kabel LAN, IP mesin, dan apakah PC satu subnet dengan mesin.")
        elif not terbuka:
            print("   - Mesin hidup tapi port tertutup: cek port di menu mesin dan firewall/router di antaranya.")
        print("   - Pastikan tidak ada aplikasi lain (mis. software absensi bawaan) yang sedang terhubung ke mesin.")
        print("   - Coba naikkan timeout (--timeout 30).")
        return False

    # 4. Info mesin
    print("4) Info mesin")
    try:
        for k, v in baca_info(conn).items():
            print(f"   {k:<18}: {v}")
        if mode_ok == "UDP" and not force_udp:
            info("mesin hanya tersambung via UDP -> set \"force_udp\": true di machines.json")
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass
    return True


def muat_mesin(path, filter_nama=None):
    if not path.exists():
        sys.exit(
            f"File {path.name} tidak ada. Pakai --ip <alamat>, atau salin machines.example.json menjadi {path.name}."
        )
    with path.open(encoding="utf-8") as f:
        daftar = [m for m in json.load(f) if m.get("aktif", True)]
    if filter_nama:
        dicari = {n.lower() for n in filter_nama}
        daftar = [m for m in daftar if m.get("nama", "").lower() in dicari or m["ip"] in dicari]
    if not daftar:
        sys.exit("Tidak ada mesin yang cocok/aktif.")
    return daftar


def main():
    p = argparse.ArgumentParser(description="Tes koneksi ke mesin absensi Revo/ZKTeco")
    p.add_argument("--ip", help="IP mesin (tanpa perlu machines.json)")
    p.add_argument("--port", type=int, default=4370)
    p.add_argument("--password", type=int, default=0, help="Comm Key mesin, default 0")
    p.add_argument("--timeout", type=int, default=10, help="detik")
    p.add_argument("--udp", action="store_true", help="paksa pakai UDP")
    p.add_argument("--config", default=str(BASE_DIR / "machines.json"))
    p.add_argument("--mesin", nargs="*", help="nama atau IP mesin di machines.json")
    args = p.parse_args()

    if args.ip:
        daftar = [{
            "ip": args.ip, "port": args.port, "password": args.password,
            "timeout": args.timeout, "force_udp": args.udp,
        }]
    else:
        daftar = muat_mesin(Path(args.config), args.mesin)

    hasil = [(m.get("nama", m["ip"]), tes_mesin(m)) for m in daftar]

    print("\n=== Ringkasan ===")
    for nama, sukses in hasil:
        print(f"  {'[OK]   ' if sukses else '[GAGAL]'} {nama}")
    sys.exit(0 if all(s for _, s in hasil) else 1)


if __name__ == "__main__":
    main()
