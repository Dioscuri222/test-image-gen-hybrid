"""
Hugging Face Space Web UI - Hybrid Cloud-to-Local Architecture
Frontend interface deployed on Hugging Face Spaces (Free CPU Tier)
Communicates via Secure Tunnel (Cloudflare/Ngrok) with Local GPU Workstation
"""
import os
import io
import time
import base64
import requests
from PIL import Image
import gradio as gr

# Default configuration from environment variables if present
DEFAULT_TUNNEL_URL = os.getenv("TUNNEL_URL", "")
DEFAULT_API_KEY = os.getenv("API_KEY", "sk-local-gpu-hybrid-2026")

def check_connection(tunnel_url: str, api_key: str):
    """
    Test konektivitas ke backend GPU lokal melalui Secure Tunnel.
    Memeriksa kesehatan server, nama GPU, dan autentikasi.
    """
    if not tunnel_url or not tunnel_url.strip():
        return (
            "⚠️ **Status:** URL Tunnel belum diisi!\n"
            "Masukkan URL Cloudflare Tunnel (misal: `https://xxxx.trycloudflare.com`) atau Ngrok."
        )

    clean_url = tunnel_url.strip().rstrip("/")
    status_endpoint = f"{clean_url}/api/status"

    headers = {}
    if api_key and api_key.strip():
        headers["X-API-Key"] = api_key.strip()

    t0 = time.time()
    try:
        response = requests.get(status_endpoint, headers=headers, timeout=10)
        roundtrip = round((time.time() - t0) * 1000, 1)

        if response.status_code == 200:
            data = response.json()
            gpu_name = data.get("gpu_name", "Unknown Device")
            model_status = data.get("model_status", "unknown")
            device = data.get("device", "unknown")
            vram = data.get("vram", {})
            vram_str = f" | VRAM Total: {vram.get('total_gb', 'N/A')} GB" if vram else ""

            return (
                f"✅ **Terhubung ke Node GPU Lokal!**\n\n"
                f"- **Device:** `{gpu_name}` ({device.upper()})\n"
                f"- **Model Status:** `{model_status}`\n"
                f"- **Latency Ping:** `{roundtrip} ms`{vram_str}\n"
                f"- **Backend URL:** `{clean_url}`"
            )
        elif response.status_code == 401:
            return (
                f"❌ **401 Unauthorized:** API Key tidak valid atau ditolak oleh server backend lokal.\n"
                f"Periksa kembali Custom API Key yang dimasukkan."
            )
        else:
            return f"⚠️ **Backend Respon HTTP {response.status_code}:** {response.text}"

    except requests.exceptions.Timeout:
        return (
            "❌ **Connection Timeout:** Waktu permintaan habis (10s).\n"
            "Server GPU lokal tidak merespon. Pastikan backend `server.py` dan tunnel Cloudflare/Ngrok aktif."
        )
    except requests.exceptions.ConnectionError:
        return (
            "❌ **Connection Error:** Tidak dapat menjangkau URL Tunnel.\n"
            "Pastikan URL benar dan tunnel publik masih aktif di komputer workstation lokal."
        )
    except Exception as e:
        return f"❌ **Error:** {str(e)}"

def generate_hybrid(
    tunnel_url: str,
    api_key: str,
    prompt: str,
    negative_prompt: str,
    steps: int,
    cfg_scale: float,
    dimensions: str,
    seed: int,
    randomize_seed: bool,
    progress=gr.Progress(track_tqdm=True)
):
    """
    Mengirim permintaan inferensi ke server GPU lokal dan menerima gambar Base64.
    """
    if not tunnel_url or not tunnel_url.strip():
        raise gr.Error("URL Tunnel wajib diisi! Masukkan URL Cloudflare / Ngrok workstation Anda.")
    
    if not prompt or not prompt.strip():
        raise gr.Error("Prompt tidak boleh kosong!")

    clean_url = tunnel_url.strip().rstrip("/")
    generate_endpoint = f"{clean_url}/api/generate"

    # Parse dimensions
    try:
        width_str, height_str = dimensions.split("x")
        width = int(width_str)
        height = int(height_str)
    except Exception:
        width, height = 512, 512

    actual_seed = None if randomize_seed or seed < 0 else int(seed)

    payload = {
        "prompt": prompt.strip(),
        "negative_prompt": negative_prompt.strip() if negative_prompt else "",
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
        "width": width,
        "height": height,
        "seed": actual_seed
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key.strip() if api_key else ""
    }

    progress(0.1, desc="Mengirim task ke workstation GPU lokal...")
    t0 = time.time()

    try:
        progress(0.3, desc="Menjalankan inferensi Stable Diffusion pada GPU lokal...")
        response = requests.post(generate_endpoint, json=payload, headers=headers, timeout=180)
        total_time = round(time.time() - t0, 2)

        if response.status_code == 200:
            progress(0.9, desc="Mengunduh & memproses hasil gambar...")
            data = response.json()
            img_b64 = data.get("image_base64")
            latency = data.get("latency_seconds", total_time)
            device = data.get("device", "GPU").upper()

            if not img_b64:
                raise gr.Error("Format respon backend tidak valid: 'image_base64' hilang.")

            # Decode Base64 PNG ke PIL Image
            img_bytes = base64.b64decode(img_b64)
            image = Image.open(io.BytesIO(img_bytes))

            info_text = (
                f"✨ **Berhasil Dibuat!**\n"
                f"- **Render Hardware:** `{device}` (Workstation Lokal)\n"
                f"- **Waktu Inferensi:** `{latency} detik` (Total request: `{total_time}s`)\n"
                f"- **Resolusi:** `{width}x{height}` | Steps: `{steps}` | CFG: `{cfg_scale}`\n"
                f"- **Seed:** `{actual_seed if actual_seed is not None else 'Random'}`"
            )
            return image, info_text

        elif response.status_code == 401:
            raise gr.Error("❌ 401 Unauthorized: API Key salah atau tidak terdaftar di backend GPU lokal!")
        elif response.status_code == 503:
            raise gr.Error("⏳ 503 Service Unavailable: Model di server lokal masih dalam proses loading. Coba sesaat lagi.")
        else:
            try:
                err_detail = response.json().get("detail", response.text)
            except Exception:
                err_detail = response.text
            raise gr.Error(f"Backend Error ({response.status_code}): {err_detail}")

    except requests.exceptions.Timeout:
        raise gr.Error("❌ Connection Timeout: Permintaan melebihi batas waktu (180 detik). Periksa beban GPU lokal.")
    except requests.exceptions.ConnectionError:
        raise gr.Error("❌ Connection Error: Gagal menghubungi server melalui tunnel. Pastikan URL tunnel benar dan aktif.")
    except Exception as e:
        raise gr.Error(f"Terjadi kesalahan: {str(e)}")

# Gradio Interface
custom_css = """
.main-header {
    text-align: center;
    padding: 1.5rem 1rem;
    background: linear-gradient(135deg, #1e1e2f 0%, #2d2b55 100%);
    color: white;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}
.main-header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    color: #ffffff;
}
.main-header p {
    font-size: 0.95rem;
    color: #b4b8d0;
    margin: 0;
}
.connection-box {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
}
"""

with gr.Blocks(title="Hybrid Image Generation WebUI") as demo:
    with gr.Column(elem_classes=["main-header"]):
        gr.Markdown(
            "# 🎨 IMAGE GENERATION HUGGING FACE WEB UI\n"
            "### Arsitektur Hybrid Cloud-to-Local Hardware (Workstation GPU)"
        )
        gr.Markdown(
            "Frontend ringan di **Hugging Face Spaces** yang meneruskan task ke **GPU Workstation Lokal** melalui Secure Tunnel & Custom API Key."
        )

    with gr.Accordion("⚙️ Konfigurasi Koneksi Node Lokal (Secure Tunnel & API Key)", open=True):
        with gr.Row():
            tunnel_url = gr.Textbox(
                label="🌐 URL Tunnel Backend Lokal",
                placeholder="https://xxxx.trycloudflare.com atau https://xxxx.ngrok-free.app",
                value=DEFAULT_TUNNEL_URL,
                info="URL publik dari Cloudflare Tunnel / Ngrok yang mengarah ke port 8000 workstation lokal.",
                scale=3
            )
            api_key = gr.Textbox(
                label="🔑 Custom API Key",
                placeholder="sk-local-gpu-hybrid-2026",
                value=DEFAULT_API_KEY,
                type="password",
                info="API key untuk autentikasi keamanan akses GPU lokal.",
                scale=2
            )
            btn_check = gr.Button("🔍 Test Koneksi", variant="secondary", scale=1)
        
        status_output = gr.Markdown("Tekan **Test Koneksi** untuk memverifikasi kesiapan GPU lokal.")

    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown("### 📝 Parameter Pembuatan Gambar")
            prompt = gr.Textbox(
                label="Prompt",
                lines=3,
                placeholder="Contoh: A high-tech cyberpunk laboratory with glowing neon lights, futuristic computer screens, ultra realistic 8k photography",
                value="A futuristic cybernetic cat sitting on a neon rooftop, cyberpunk city in the background, highly detailed, 8k resolution, cinematic lighting"
            )
            negative_prompt = gr.Textbox(
                label="Negative Prompt",
                lines=2,
                placeholder="Elemen yang ingin dihindari...",
                value="blurry, distorted, low quality, bad anatomy, out of frame, watermark"
            )

            with gr.Row():
                steps = gr.Slider(
                    minimum=10,
                    maximum=50,
                    value=20,
                    step=1,
                    label="Inference Steps",
                    info="20 steps optimal untuk DPMSolver scheduler"
                )
                cfg_scale = gr.Slider(
                    minimum=1.0,
                    maximum=15.0,
                    value=7.5,
                    step=0.5,
                    label="CFG Guidance Scale",
                    info="Tingkat kepatuhan terhadap prompt"
                )

            with gr.Row():
                dimensions = gr.Dropdown(
                    choices=["512x512", "512x768", "768x512"],
                    value="512x512",
                    label="Resolusi Gambar",
                    info="512x512 optimal untuk VRAM 4GB (RTX 2050)"
                )
                seed = gr.Number(
                    value=-1,
                    label="Seed",
                    info="-1 untuk acak (random)"
                )
                randomize_seed = gr.Checkbox(
                    value=True,
                    label="Randomize Seed",
                    info="Gunakan seed baru tiap generasi"
                )

            btn_generate = gr.Button("🚀 Generate Image (Kirim ke GPU Lokal)", variant="primary", size="lg")

        with gr.Column(scale=5):
            gr.Markdown("### 🖼️ Hasil Gambar (Dari GPU Lokal)")
            output_image = gr.Image(
                label="Generated Output",
                type="pil",
                interactive=False
            )
            output_info = gr.Markdown("Hasil generasi dan metrik latensi akan ditampilkan di sini.")

    # Event Handlers
    btn_check.click(
        fn=check_connection,
        inputs=[tunnel_url, api_key],
        outputs=[status_output]
    )

    btn_generate.click(
        fn=generate_hybrid,
        inputs=[
            tunnel_url,
            api_key,
            prompt,
            negative_prompt,
            steps,
            cfg_scale,
            dimensions,
            seed,
            randomize_seed
        ],
        outputs=[output_image, output_info]
    )

    gr.Examples(
        examples=[
            [
                "A serene Japanese garden in autumn with vibrant red maple leaves, stone lanterns, koi pond, cinematic morning light",
                "blurry, ugly, distorted, lowres",
                20,
                7.5,
                "512x512"
            ],
            [
                "Detailed digital painting of an astronaut exploring an ancient alien ruin on Mars, atmospheric dust, dramatic lighting",
                "bad quality, oversaturated, deformed",
                25,
                8.0,
                "512x512"
            ]
        ],
        inputs=[prompt, negative_prompt, steps, cfg_scale, dimensions]
    )

if __name__ == "__main__":
    try:
        demo.launch(theme=gr.themes.Soft(), css=custom_css)
    except TypeError:
        demo.launch()