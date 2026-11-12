"""
Tarik log absensi dari mesin Revo (protokol ZKTeco) memakai pyzk.

Contoh:
    python tarik_log.py                                  # semua mesin, semua log
    python tarik_log.py --dari 2026-11-01 --sampai 2026-11-12
    python tarik_log.py --mesin "Kantor Pusat" --format json
    python tarik_log.py --tes                            # hanya cek koneksi + info mesin

Daftar mesin dibaca dari machines.json (salin dari machines.example.json).
Script ini HANYA membaca log; log di mesin tidak dihapus.
"""

import argparse
import csv
import datetime as dt
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from zk import ZK
except ImportError:
    sys.exit("Modul pyzk belum terpasang. Jalankan: pip install -r requirements.txt")

BASE_DIR = Path(__file__).resolve().parent
KOLOM = ["mesin", "ip", "serial_number", "uid", "user_id", "timestamp", "status", "punch"]


def bisa_dihubungi(ip, port, timeout=3):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_tanggal(teks, akhir=False):
    """'YYYY-MM-DD' atau 'YYYY-MM-DD HH:MM:SS'. Tanggal saja untuk --sampai berarti s.d. akhir hari itu."""
    if not teks:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            nilai = dt.datetime.strptime(teks, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d" and akhir:
            nilai += dt.timedelta(days=1)
        return nilai
    raise argparse.ArgumentTypeError(f"Format tanggal tidak dikenal: {teks}")


def buat_koneksi(m):
    return ZK(
        m["ip"],
        port=int(m.get("port", 4370)),
        timeout=int(m.get("timeout", 15)),
        password=int(m.get("password", 0)),  # Comm Key di menu mesin, default 0
        force_udp=bool(m.get("force_udp", False)),
        ommit_ping=True,
    )


def tarik_dari_mesin(m, dari=None, sampai=None, hanya_tes=False):
    nama, ip, port = m.get("nama", m["ip"]), m["ip"], int(m.get("port", 4370))
    hasil = {"mesin": nama, "ip": ip, "sukses": False, "jumlah": 0, "logs": []}

    if not bisa_dihubungi(ip, port):
        hasil["error"] = f"tidak bisa dihubungi di {ip}:{port}"
        return hasil

    conn = None
    try:
        conn = buat_koneksi(m).connect()
        sn = conn.get_serialnumber()
        hasil["serial_number"] = sn

        if hanya_tes:
            hasil.update(
                sukses=True,
                info={
                    "firmware": conn.get_firmware_version(),
                    "platform": conn.get_platform(),
                    "jam_mesin": str(conn.get_time()),
                    "jumlah_user": len(conn.get_users() or []),
                },
            )
            return hasil

        conn.disable_device()  # kunci mesin sebentar supaya data konsisten saat dibaca
        for att in conn.get_attendance() or []:
            ts = att.timestamp
            if dari and ts < dari:
                continue
            if sampai and ts >= sampai:
                continue
            hasil["logs"].append({
                "mesin": nama,
                "ip": ip,
                "serial_number": sn,
                "uid": att.uid,
                "user_id": str(att.user_id),
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "status": att.status,
                "punch": att.punch,
            })
        hasil["sukses"] = True
        hasil["jumlah"] = len(hasil["logs"])
    except Exception as e:  # pyzk melempar banyak jenis exception
        hasil["error"] = str(e)
    finally:
        if conn:
            try:
                conn.enable_device()
            except Exception:
                pass
            try:
                conn.disconnect()
            except Exception:
                pass
    return hasil


def muat_mesin(path, filter_nama=None):
    if not path.exists():
        sys.exit(f"File {path.name} tidak ada. Salin machines.example.json menjadi {path.name} lalu isi IP mesin.")
    with path.open(encoding="utf-8") as f:
        daftar = json.load(f)
    daftar = [m for m in daftar if m.get("aktif", True)]
    if filter_nama:
        dicari = {n.lower() for n in filter_nama}
        daftar = [m for m in daftar if m.get("nama", "").lower() in dicari or m["ip"] in dicari]
    if not daftar:
        sys.exit("Tidak ada mesin yang cocok/aktif.")
    return daftar


def simpan(logs, folder, fmt):
    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logs = sorted(logs, key=lambda r: (r["timestamp"], r["mesin"], r["user_id"]))
    if fmt == "json":
        path = folder / f"log_absensi_{stamp}.json"
        path.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path = folder / f"log_absensi_{stamp}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig agar rapi dibuka di Excel
            w = csv.DictWriter(f, fieldnames=KOLOM)
            w.writeheader()
            w.writerows(logs)
    return path


def main():
    p = argparse.ArgumentParser(description="Tarik log absensi mesin Revo/ZKTeco")
    p.add_argument("--config", default=str(BASE_DIR / "machines.json"), help="file daftar mesin")
    p.add_argument("--mesin", nargs="*", help="nama atau IP mesin tertentu (default: semua yang aktif)")
    p.add_argument("--dari", type=parse_tanggal, help="tanggal awal, YYYY-MM-DD [HH:MM:SS]")
    p.add_argument("--sampai", type=lambda s: parse_tanggal(s, akhir=True), help="tanggal akhir (inklusif), YYYY-MM-DD [HH:MM:SS]")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.add_argument("--output", default=str(BASE_DIR / "output"), help="folder hasil")
    p.add_argument("--workers", type=int, default=5, help="jumlah mesin yang ditarik bersamaan")
    p.add_argument("--tes", action="store_true", help="hanya tes koneksi dan tampilkan info mesin")
    args = p.parse_args()

    daftar = muat_mesin(Path(args.config), args.mesin)
    print(f"Menarik dari {len(daftar)} mesin...")

    semua_log, gagal = [], 0
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(daftar)))) as ex:
        futures = [ex.submit(tarik_dari_mesin, m, args.dari, args.sampai, args.tes) for m in daftar]
        for fut in as_completed(futures):
            h = fut.result()
            label = f"{h['mesin']} ({h['ip']})"
            if not h["sukses"]:
                gagal += 1
                print(f"  [GAGAL] {label}: {h.get('error')}")
            elif args.tes:
                print(f"  [OK] {label} SN={h.get('serial_number')} {h['info']}")
            else:
                print(f"  [OK] {label} SN={h.get('serial_number')}: {h['jumlah']} log")
                semua_log.extend(h["logs"])

    if not args.tes:
        if semua_log:
            path = simpan(semua_log, Path(args.output), args.format)
            print(f"Total {len(semua_log)} log disimpan ke {path}")
        else:
            print("Tidak ada log pada rentang tersebut.")

    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
