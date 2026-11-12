# Tarik Log Mesin Absensi Revo

Script Python untuk menarik log absensi dari mesin fingerprint Revo (protokol ZKTeco, port 4370) dan menyimpannya ke CSV/JSON. Script hanya membaca log; tidak ada data yang dihapus dari mesin.

Isi folder:

| File                    | Fungsi                                                   |
|-------------------------|----------------------------------------------------------|
| `tes_koneksi.py`        | Cek koneksi ke mesin langkah demi langkah (jalankan dulu) |
| `tarik_log.py`          | Tarik log absensi ke CSV/JSON                            |
| `machines.example.json` | Contoh daftar mesin                                      |
| `requirements.txt`      | Library yang dibutuhkan (`pyzk`)                         |

## 1. Cek Python

Buka **Command Prompt** (tekan `Win + R`, ketik `cmd`, Enter), lalu jalankan:

```bat
python --version
```

- Muncul `Python 3.8` atau lebih baru (mis. `Python 3.10.6`) → Python sudah ada, lanjut ke langkah 2.
- Muncul `'python' is not recognized...` atau Microsoft Store terbuka → Python belum terpasang, ikuti langkah 1a.

Cek juga `pip`:

```bat
python -m pip --version
```

### 1a. Install Python (jika belum ada)

**Windows**

1. Buka https://www.python.org/downloads/ lalu klik **Download Python 3.x**.
2. Jalankan installer. Di layar pertama **centang "Add python.exe to PATH"** (penting), lalu klik **Install Now**.
3. Setelah selesai, **tutup lalu buka lagi** Command Prompt dan cek ulang dengan `python --version`.

Alternatif lewat terminal (Windows 10/11):

```bat
winget install -e --id Python.Python.3.12
```

> Jika `python` masih membuka Microsoft Store: buka *Settings → Apps → Advanced app settings → App execution aliases*, matikan alias `python.exe` dan `python3.exe`, lalu buka ulang Command Prompt.

**Linux (Ubuntu/Debian)**

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
```

Di Linux/Mac gunakan `python3` sebagai pengganti `python`.

## 2. Install script

Download repo ini (tombol **Code → Download ZIP** di GitHub lalu ekstrak, atau `git clone`), lalu masuk ke foldernya:

```bat
cd C:\path\ke\folder-repo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux/Mac: `source .venv/bin/activate` sebagai pengganti baris aktivasi.

Setiap kali membuka Command Prompt baru, aktifkan lagi venv-nya dengan `.venv\Scripts\activate` (muncul `(.venv)` di awal baris) sebelum menjalankan script.

## 3. Konfigurasi mesin

Salin `machines.example.json` menjadi `machines.json`, lalu isi data mesin:

| Field       | Keterangan                                                        |
|-------------|-------------------------------------------------------------------|
| `nama`      | Nama mesin (bebas, dipakai di hasil & filter `--mesin`)           |
| `ip`        | IP mesin                                                          |
| `port`      | Default `4370`                                                    |
| `password`  | Comm Key di menu mesin (Comm/Koneksi), default `0`                |
| `timeout`   | Detik, default `15`                                               |
| `force_udp` | `true` jika mesin hanya menerima UDP                              |
| `aktif`     | `false` untuk melewati mesin                                      |

`machines.json` sudah masuk `.gitignore` karena berisi IP dan comm key.

Windows: `copy machines.example.json machines.json`, lalu buka `machines.json` dengan Notepad. IP mesin bisa dilihat di menu mesin: *Comm / Koneksi → Ethernet*.

## 4. Tes koneksi dulu

```bash
# langsung ke satu IP, tanpa machines.json
python tes_koneksi.py --ip 192.168.1.201
python tes_koneksi.py --ip 192.168.1.201 --password 123   # jika Comm Key diisi

# semua mesin aktif di machines.json
python tes_koneksi.py
```

Dicek bertahap: ping → port TCP 4370 → login protokol (TCP, lalu UDP jika TCP gagal) → info mesin (SN, firmware, jam, jumlah user/log). Jika gagal, script menampilkan saran perbaikannya.

## 5. Tarik log absensi

```bash
# tes koneksi + info mesin (firmware, jam mesin, jumlah user)
python tarik_log.py --tes

# tarik semua log dari semua mesin aktif -> output/log_absensi_YYYYMMDD_HHMMSS.csv
python tarik_log.py

# rentang tanggal (sampai = inklusif)
python tarik_log.py --dari 2026-11-01 --sampai 2026-11-12

# mesin tertentu, format JSON
python tarik_log.py --mesin "Kantor Pusat" 192.168.1.202 --format json
```

Kolom hasil: `mesin, ip, serial_number, uid, user_id, timestamp, status, punch`.
`user_id` adalah ID/badge pegawai di mesin; `punch` biasanya 0 = masuk, 1 = pulang (tergantung setelan mesin).

Exit code `1` jika ada mesin yang gagal ditarik, jadi bisa dipantau dari Task Scheduler/cron.

## Jadwal otomatis (Windows Task Scheduler)

Program: `C:\path\ke\repo\.venv\Scripts\python.exe`
Argumen: `tarik_log.py --dari <tanggal>`
Start in: `C:\path\ke\repo`

## Kendala umum

- **tidak bisa dihubungi**: cek IP/port, mesin dan PC satu jaringan, firewall.
- **Unauthenticated**: Comm Key di `machines.json` tidak sama dengan di mesin.
- **Timeout saat log banyak**: naikkan `timeout`, atau coba `force_udp: true`.
