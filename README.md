# Python Absensi Engine

Script Python untuk menarik log absensi langsung dari mesin absensi lewat **jaringan lokal**, tanpa cloud, lalu menyimpannya ke CSV/JSON. Script hanya **membaca** log; tidak ada data yang diubah atau dihapus di mesin.

Mesin yang didukung:

| Mesin | Protokol | Script |
|---|---|---|
| **Fingerspot.io DS-11MK** dan terminal **Hikvision** lain | Hikvision ISAPI (HTTP/HTTPS port 80/443) | `tes_koneksi_hik.py`, `tarik_log_hik.py` |
| Revo / ZKTeco | Protokol ZKTeco (port 4370) | `tes_koneksi.py`, `tarik_log.py` (lihat [bagian bawah](#mesin-revo--zkteco)) |

> Fingerspot.io DS-11MK adalah perangkat buatan Hikvision. Data bisa ditarik langsung dari mesin lewat ISAPI tanpa berlangganan cloud Fingerspot.io, jadi tetap bisa dipakai walaupun cloud diblok di firewall.

## 1. Cek Python

Jalankan di terminal (Linux) atau Command Prompt (Windows: `Win + R`, ketik `cmd`, Enter):

```bash
python3 --version     # Linux
python --version      # Windows
```

- Muncul `Python 3.8` atau lebih baru → Python sudah ada, lanjut ke langkah 2.
- Muncul `command not found` / `'python' is not recognized...` / Microsoft Store terbuka → Python belum terpasang, ikuti langkah 1a.

### 1a. Install Python (jika belum ada)

**Linux (Ubuntu/Debian)**

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

**Windows**

1. Buka https://www.python.org/downloads/ lalu klik **Download Python 3.x**.
2. Jalankan installer. Di layar pertama **centang "Add python.exe to PATH"** (penting), lalu klik **Install Now**.
3. **Tutup lalu buka lagi** Command Prompt, cek ulang dengan `python --version`.

Alternatif lewat terminal (Windows 10/11): `winget install -e --id Python.Python.3.12`

> Jika `python` masih membuka Microsoft Store: *Settings → Apps → Advanced app settings → App execution aliases*, matikan alias `python.exe` dan `python3.exe`, lalu buka ulang Command Prompt.

## 2. Install script

Jalankan di komputer yang **satu jaringan dengan mesin** (bisa menjangkau IP mesin).

**Linux**

```bash
git clone https://github.com/mulyadirizki/python-absensi-engine.git
cd python-absensi-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows** (atau download lewat **Code → Download ZIP** di GitHub lalu ekstrak)

```bat
cd C:\path\ke\python-absensi-engine
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Setiap membuka terminal baru, aktifkan lagi venv-nya (`source .venv/bin/activate` atau `.venv\Scripts\activate`) sebelum menjalankan script. Tanda aktif: muncul `(.venv)` di awal baris.

## 3. Tes koneksi ke mesin (Hikvision / DS-11MK)

Butuh **IP mesin** dan **username/password admin** mesin (yang dipakai saat aktivasi mesin / login web mesin).

```bash
python tes_koneksi_hik.py --host 10.1.36.20 --user admin            # password ditanya, tidak tampil di layar
python tes_koneksi_hik.py --host 10.1.36.20 --user admin --https    # jika HTTP ditutup, pakai HTTPS
```

Yang dicek berurutan:

1. **Port** 80/443 terbuka?
2. **ISAPI** terdeteksi? (mesin membalas `401 Digest` tanpa login)
3. **Login** → model, serial number, firmware, MAC
4. **Data** → jam mesin, jumlah user, jumlah log 7 hari terakhir

> **Hati-hati password:** mesin Hikvision mengunci akun sementara setelah beberapa kali salah password. Script tidak mengulang login yang gagal; cek password dulu sebelum mencoba lagi.

## 4. Konfigurasi mesin

```bash
cp mesin_hik.example.json mesin_hik.json      # Windows: copy mesin_hik.example.json mesin_hik.json
```

Lalu isi `mesin_hik.json` (boleh lebih dari satu mesin):

| Field         | Keterangan                                                    |
|---------------|---------------------------------------------------------------|
| `nama`        | Nama mesin (bebas, dipakai di hasil & filter `--mesin`)       |
| `host`        | IP mesin                                                      |
| `username`    | Username admin mesin, biasanya `admin`                        |
| `password`    | Password admin mesin                                          |
| `https`       | `true` untuk HTTPS (port 443), `false` untuk HTTP (port 80)   |
| `port`        | Opsional, jika port bukan 80/443                              |
| `timeout`     | Detik, default `15`                                           |
| `aktif`       | `false` untuk melewati mesin                                  |

`mesin_hik.json` sudah masuk `.gitignore` karena berisi password. Di Linux, batasi aksesnya: `chmod 600 mesin_hik.json`.

Setelah diisi, tes semua mesin sekaligus: `python tes_koneksi_hik.py`

## 5. Tarik log absensi

```bash
# hari ini (00:00 s.d. sekarang), semua mesin aktif -> output/log_absensi_hik_YYYYMMDD_HHMMSS.csv
python tarik_log_hik.py

# rentang tanggal (sampai = inklusif s.d. 23:59:59)
python tarik_log_hik.py --dari 2026-11-01 --sampai 2026-11-12

# mesin tertentu, format JSON
python tarik_log_hik.py --mesin "Kantor Pusat" --format json

# ikutkan event tanpa ID pegawai (wajah tidak dikenal, event pintu, dll.)
python tarik_log_hik.py --semua-event
```

Kolom hasil:

| Kolom | Isi |
|---|---|
| `mesin`, `host`, `serial_number` | Asal mesin |
| `employee_no` | ID pegawai di mesin |
| `nama` | Nama pegawai di mesin |
| `timestamp` | Waktu scan (jam mesin), `YYYY-MM-DD HH:MM:SS` |
| `attendance_status` | `checkIn` / `checkOut` / `breakOut` / ... jika mode absensi di mesin diaktifkan |
| `verifikasi` | Cara verifikasi: wajah, kartu, sidik jari, dll. |
| `minor`, `serial_no` | Kode event dan nomor urut event di mesin |

Zona waktu default `+07:00` (WIB). Untuk WITA/WIT pakai `--tz +08:00` / `--tz +09:00`.

Exit code `1` jika ada mesin yang gagal, jadi bisa dipantau dari cron/Task Scheduler.

## Jadwal otomatis

**Linux (cron)**, contoh tiap jam menarik log hari ini (`crontab -e`):

```cron
0 * * * * cd /home/USER/python-absensi-engine && .venv/bin/python tarik_log_hik.py >> tarik_log.log 2>&1
```

**Windows (Task Scheduler)**
Program: `C:\path\ke\repo\.venv\Scripts\python.exe` · Argumen: `tarik_log_hik.py` · Start in: `C:\path\ke\repo`

## Kendala umum

| Pesan | Penyebab & solusi |
|---|---|
| `port 80 tidak bisa dibuka` | Komputer tidak satu jaringan dengan mesin, IP salah, atau HTTP dimatikan → coba `--https` |
| `401` / `username/password salah` | Password salah. Tunggu beberapa menit jika akun terkunci, lalu coba lagi dengan password yang benar |
| `404` saat ambil log | Firmware mesin tidak mendukung endpoint ISAPI tersebut, kirim output `tes_koneksi_hik.py` ke developer |
| Log kosong padahal ada scan | Cek jam mesin di hasil tes koneksi, dan cek `--tz` |

---

## Mesin Revo / ZKTeco

Untuk mesin yang memakai protokol ZKTeco (port 4370). Salin `machines.example.json` menjadi `machines.json`, isi `ip` dan `password` (Comm Key di menu mesin, default `0`), lalu:

```bash
python tes_koneksi.py --ip 192.168.1.201          # tes koneksi bertahap: ping, port, login TCP/UDP, info mesin
python tarik_log.py --dari 2026-11-01 --sampai 2026-11-12
```

Jika port 4370 tidak terlihat di scan TCP, coba `python tes_koneksi.py --ip <IP> --udp` (banyak mesin ZKTeco hanya memakai UDP). Kolom hasil: `mesin, ip, serial_number, uid, user_id, timestamp, status, punch`.
