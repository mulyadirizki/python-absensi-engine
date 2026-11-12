"""
Tarik log absensi dari mesin Hikvision / Fingerspot.io DS-11MK lewat ISAPI (lokal, tanpa cloud).

Contoh:
    python tarik_log_hik.py                                   # hari ini, semua mesin aktif
    python tarik_log_hik.py --dari 2026-11-01 --sampai 2026-11-12
    python tarik_log_hik.py --mesin "Kantor Pusat" --format json
    python tarik_log_hik.py --semua-event                     # termasuk event tanpa ID pegawai

Daftar mesin dibaca dari mesin_hik.json (salin dari mesin_hik.example.json).
HANYA membaca log; tidak ada yang dihapus/diubah di mesin.
"""

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

from hik_isapi import NAMA_MINOR, buat_klien, format_waktu, muat_mesin

BASE_DIR = Path(__file__).resolve().parent
KOLOM = ["mesin", "host", "serial_number", "employee_no", "nama", "timestamp",
         "attendance_status", "label", "verifikasi", "minor", "serial_no"]


def tanggal(teks):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(teks, fmt), fmt == "%Y-%m-%d"
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"Format tanggal tidak dikenal: {teks}")


def tarik(m, mulai, akhir, tz, semua_event):
    nama = m.get("nama", m["host"])
    hasil = {"mesin": nama, "host": m["host"], "sukses": False, "logs": []}
    try:
        k = buat_klien(m)
        sn = k.device_info().get("serialNumber", "")
        for e in k.events(mulai, akhir, tz, int(m.get("per_halaman", 30))):
            emp = e.get("employeeNoString") or str(e.get("employeeNo") or "")
            if not emp and not semua_event:
                continue  # event pintu/orang asing tanpa ID pegawai
            minor = e.get("minor")
            hasil["logs"].append({
                "mesin": nama,
                "host": m["host"],
                "serial_number": sn,
                "employee_no": emp,
                "nama": e.get("name", ""),
                "timestamp": format_waktu(e.get("time")),
                "attendance_status": e.get("attendanceStatus", ""),
                "label": e.get("label", ""),
                # cara scan dibaca dari kode minor; currentVerifyMode hanya mode yang disetel di mesin
                "verifikasi": NAMA_MINOR.get(minor) or f"kode {minor}",
                "minor": minor,
                "serial_no": e.get("serialNo", ""),
            })
        hasil["sukses"] = True
    except Exception as ex:
        hasil["error"] = str(ex)
    return hasil


def simpan(logs, folder, fmt):
    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logs = sorted(logs, key=lambda r: (r["timestamp"], r["mesin"], r["employee_no"]))
    if fmt == "json":
        path = folder / f"log_absensi_hik_{stamp}.json"
        path.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path = folder / f"log_absensi_hik_{stamp}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig agar rapi di Excel
            w = csv.DictWriter(f, fieldnames=KOLOM)
            w.writeheader()
            w.writerows(logs)
    return path


def main():
    p = argparse.ArgumentParser(description="Tarik log absensi Hikvision/Fingerspot DS-11MK (ISAPI)")
    p.add_argument("--config", default=str(BASE_DIR / "mesin_hik.json"))
    p.add_argument("--mesin", nargs="*", help="nama atau IP mesin tertentu")
    p.add_argument("--dari", type=tanggal, help="YYYY-MM-DD [HH:MM:SS], default hari ini 00:00")
    p.add_argument("--sampai", type=tanggal, help="YYYY-MM-DD [HH:MM:SS] (inklusif), default sekarang")
    p.add_argument("--tz", default="+07:00", help="zona waktu mesin, default +07:00 (WIB)")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.add_argument("--output", default=str(BASE_DIR / "output"))
    p.add_argument("--semua-event", action="store_true", help="ikutkan event tanpa ID pegawai")
    args = p.parse_args()

    sekarang = dt.datetime.now().replace(microsecond=0)
    mulai = args.dari[0] if args.dari else sekarang.replace(hour=0, minute=0, second=0)
    if args.sampai:
        akhir, hanya_tanggal = args.sampai
        if hanya_tanggal:
            akhir = akhir.replace(hour=23, minute=59, second=59)
    else:
        akhir = sekarang

    daftar = muat_mesin(args.config, args.mesin)
    print(f"Menarik log {mulai} s.d. {akhir} dari {len(daftar)} mesin...")

    semua, gagal = [], 0
    for m in daftar:
        h = tarik(m, mulai, akhir, args.tz, args.semua_event)
        label = f"{h['mesin']} ({h['host']})"
        if h["sukses"]:
            print(f"  [OK]    {label}: {len(h['logs'])} log")
            semua.extend(h["logs"])
        else:
            gagal += 1
            print(f"  [GAGAL] {label}: {h.get('error')}")

    if semua:
        print(f"Total {len(semua)} log disimpan ke {simpan(semua, Path(args.output), args.format)}")
    else:
        print("Tidak ada log pada rentang tersebut.")
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
