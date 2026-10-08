# IMAGE GENERATION HUGGING FACE WEB UI DENGAN ARSITEKTUR HYBRID CLOUD-TO-LOCAL HARDWARE

Proyek implementasi arsitektur **Hybrid Cloud-to-Local Hardware** untuk Text-to-Image Generation (Stable Diffusion). 

Arsitektur ini memisahkan **antarmuka web publik (Frontend)** yang di-deploy secara ringan di **Hugging Face Spaces** (Free CPU Tier) dengan **mesin inferensi (Backend)** yang dieksekusi di workstation GPU lokal (misalnya NVIDIA GeForce RTX 2050). Komunikasi antar-node diamankan melalui **Secure Tunneling (Cloudflare Tunnel / Ngrok)** dan autentikasi berbasis **Custom API Key**.

---

## 🏗️ Diagram Arsitektur

```
┌─────────────────────────────────┐
│   User Browser (Klien / Publik) │
└────────────────┬────────────────┘
                 │ HTTP (Web UI)
                 ▼
┌────────────────────────────────────────────────────────┐
│ Hugging Face Spaces (Frontend - Free CPU Tier)        │
│ - Gradio Web UI                                        │
│ - Input: Prompt, Negative Prompt, Steps, CFG, Seed     │
│ - Konfigurasi: URL Tunnel & Custom API Key             │
│ - Ringan (tanpa PyTorch GPU / tanpa kuota ZeroGPU)     │
└────────────────┬───────────────────────────────────────┘
                 │ HTTPS (Rest API + Header X-API-Key)
                 ▼
┌────────────────────────────────────────────────────────┐
│ Secure Tunnel (Cloudflare Tunnel / Ngrok)              │
│ - Public URL (misal: https://xxxx.trycloudflare.com)   │
│ - Menembus NAT/Firewall lokal tanpa port-forwarding    │
└────────────────┬───────────────────────────────────────┘
                 │ Reverse Proxy ke http://127.0.0.1:8000
                 ▼
┌────────────────────────────────────────────────────────┐
│ Workstation GPU Lokal (Backend - FastAPI Server)       │
│ - Framework: FastAPI + Uvicorn                         │
│ - Engine: PyTorch + Diffusers (Stable Diffusion v1.5)  │
│ - Akselerasi: NVIDIA GPU (RTX 2050 4GB VRAM)           │
│ - Optimasi: FP16 + Attention Slicing + VAE Slicing     │
│ - Autentikasi: Custom API Key Verification Middleware  │
│ - Respon: Base64 Encoded PNG Image + Latency Metrics   │
└────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Repositori

```
image-gen-hybrid/
├── backend/
│   ├── server.py              # Server inferensi FastAPI dengan Stable Diffusion
│   └── requirements.txt       # Dependensi backend (FastAPI, PyTorch, Diffusers, dll)
├── frontend/                  # Folder salinan pengembangan lokal WebUI
│   ├── app.py
│   └── requirements.txt
├── TestImage/                 # Repositori Git Hugging Face Space (dihubungkan ke Spaces)
│   ├── app.py                 # Antarmuka Gradio klien ringan (bebas ZeroGPU)
│   ├── requirements.txt       # gradio, requests, pillow (sangat ringan)
│   └── README.md              # Space metadata (Gradio CPU basic)
├── check_cuda.py              # Script diagnostik GPU lokal & PyTorch CUDA
├── test_local.py              # Script pengujian endpoint backend lokal & keamanan
├── test_structure.py          # Validasi struktur proyek sesuai proposal PDF
├── run_backend.bat            # Launcher 1-klik backend lokal (Windows)
├── run_tunnel.bat             # Launcher 1-klik Cloudflare Tunnel (Windows)
└── README.md                  # Dokumentasi proyek
```

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Persiapan Akselerasi GPU Lokal (NVIDIA RTX 2050)

Jalankan script diagnostik terlebih dahulu:
```powershell
python check_cuda.py
```

Jika terdeteksi `PyTorch version: ...+cpu` dan `CUDA Available: False`, aktifkan CUDA untuk GPU NVIDIA Anda dengan menjalankan:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

### 2. Menjalankan Backend Inferensi Lokal

Jalankan server backend:
- **Cara 1 (Double click / Terminal):**
  ```powershell
  .\run_backend.bat
  ```
- **Cara 2 (Manual Python):**
  ```powershell
  python backend/server.py
  ```

Server akan aktif pada `http://127.0.0.1:8000`.
- API Key Default: `sk-local-gpu-hybrid-2026`
- Status endpoint: `http://127.0.0.1:8000/api/status`

### 3. Mengaktifkan Secure Tunnel (Cloudflare Tunnel)

Gunakan Cloudflare Tunnel untuk menghubungkan server lokal ke internet tanpa perlu membuka port router/IP publik:
- **Cara 1:**
  ```powershell
  .\run_tunnel.bat
  ```
- **Cara 2 (Manual):**
  ```powershell
  cloudflared tunnel --url http://127.0.0.1:8000
  ```

Salin URL HTTPS publik yang muncul di terminal, contoh:
`https://example-random-subdomain.trycloudflare.com`

### 4. Menggunakan Hugging Face Spaces Frontend

1. Buka antarmuka Hugging Face Space Anda: [https://huggingface.co/spaces/Dioscuri222/TestImage](https://huggingface.co/spaces/Dioscuri222/TestImage)
2. Buka panel **⚙️ Konfigurasi Koneksi Node Lokal**:
   - **URL Tunnel Backend Lokal:** Tempelkan URL Cloudflare Tunnel dari Langkah 3 (misal: `https://xxxx.trycloudflare.com`).
   - **Custom API Key:** Masukkan `sk-local-gpu-hybrid-2026` (atau kunci kustom Anda).
   - Klik **🔍 Test Koneksi** hingga muncul status hijau terhubung dengan nama GPU Anda (`NVIDIA GeForce RTX 2050`).
3. Masukkan prompt gambar dan klik **🚀 Generate Image (Kirim ke GPU Lokal)**. Gambar akan diinferensi oleh GPU laptop Anda dan langsung tampil di browser!

---

## 🔒 Keamanan & Penanganan Kesalahan (Sesuai PDF)

1. **401 Unauthorized:**
   Jika permintaan tidak menyertakan `X-API-Key` yang cocok dengan backend lokal, server akan menolak akses dengan status 401 dan frontend akan menampilkan pesan peringatan yang jelas.
2. **Connection Timeout:**
   Jika backend lokal mati atau tunnel terputus, frontend Gradio akan menangani `requests.exceptions.Timeout` / `ConnectionError` dan memberikan instruksi perbaikan kepada pengguna.
3. **Optimasi VRAM 4GB (RTX 2050):**
   - Menggunakan presisi `FP16` (`torch.float16`).
   - Mengaktifkan `enable_attention_slicing()` dan `enable_vae_slicing()`.
   - Scheduler `DPMSolverMultistepScheduler` menghasilkan gambar berkualitas tinggi hanya dalam 20 langkah inferensi, menjaga penggunaan VRAM di bawah ~2.5 GB.

---

## 🔄 Deployment ke Hugging Face Spaces

Untuk memperbarui Hugging Face Space:
```bash
cd TestImage
git add .
git commit -m "Update Hybrid Architecture: lightweight frontend client with tunnel support"
git push origin main
```