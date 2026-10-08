"""
Local Inference Server for Hybrid Image Generation Architecture
Runs locally on workstation with GPU acceleration (e.g., NVIDIA RTX)
Exposes FastAPI endpoints for Hugging Face Spaces via Secure Tunnel (Cloudflare/Ngrok)
"""
import os
import io
import sys
import time
import base64
import secrets

# Set utf-8 encoding for Windows console compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Security, Header, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

# Environment configuration
DEFAULT_API_KEY = os.getenv("LOCAL_API_KEY", "sk-local-gpu-hybrid-2026")
PORT = int(os.getenv("PORT", 8000))
MODEL_ID = os.getenv("MODEL_ID", "runwayml/stable-diffusion-v1-5")

# Registered API Keys store
VALID_API_KEYS: Dict[str, Dict[str, Any]] = {
    DEFAULT_API_KEY: {
        "device_name": "default-local-key",
        "created_at": datetime.now().isoformat()
    }
}

app = FastAPI(
    title="Hybrid Image Generation Local GPU API",
    description="Backend inferensi lokal berbasis GPU untuk WebUI Hugging Face Spaces",
    version="1.0.0"
)

# CORS configuration (allows requests from Hugging Face Spaces)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> str:
    """Verifikasi Custom API Key dari Header X-API-Key atau Authorization Bearer"""
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token or token not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="401 Unauthorized: Invalid or missing API Key"
        )
    return token

class GenerationRequest(BaseModel):
    prompt: str = Field(..., description="Prompt teks untuk pembuatan gambar")
    negative_prompt: str = Field("", description="Teks negatif prompt")
    steps: int = Field(20, ge=1, le=50, description="Jumlah langkah inferensi")
    cfg_scale: float = Field(7.0, ge=1.0, le=20.0, description="Guidance scale")
    width: int = Field(512, ge=256, le=1024, description="Lebar gambar")
    height: int = Field(512, ge=256, le=1024, description="Tinggi gambar")
    seed: Optional[int] = Field(None, description="Random seed untuk reproduksibilitas")

class ApiKeyRequest(BaseModel):
    device_name: str = "remote-client"

# Global pipeline instance
pipe = None
startup_time = time.time()

@app.on_event("startup")
def load_pipeline():
    """Load model Stable Diffusion ke GPU lokal saat startup"""
    global pipe
    print("=" * 60)
    print("🚀 Initializing Local Inference Engine...")
    
    cuda_available = torch.cuda.is_available()
    device = "cuda" if cuda_available else "cpu"
    dtype = torch.float16 if cuda_available else torch.float32

    print(f"🖥️ Hardware Detection: {'CUDA GPU Available' if cuda_available else 'CPU Mode (Warning: GPU not active)'}")
    if cuda_available:
        gpu_name = torch.cuda.get_device_name(0)
        total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"🎮 Target GPU: {gpu_name} ({total_vram:.2f} GB VRAM)")
    else:
        print("⚠️ Catatan: PyTorch saat ini berjalan dalam mode CPU.")
        print("   Untuk mengaktifkan GPU NVIDIA, jalankan: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126")

    print(f"📦 Loading pre-trained model: {MODEL_ID}...")
    try:
        pipe = StableDiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            safety_checker=None,
            requires_safety_checker=False
        )
        
        # Scheduler DPMSolverMultistepScheduler untuk inferensi cepat (20 steps sudah berkualitas tinggi)
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
        
        if cuda_available:
            pipe = pipe.to("cuda")
            # Optimasi VRAM khusus untuk GPU workstation/laptop (misal RTX 2050 4GB)
            pipe.enable_attention_slicing()
            try:
                pipe.enable_vae_slicing()
            except Exception:
                pass
        
        print(f"✅ Model loaded successfully on {device}!")
        print(f"🔑 Default API Key aktif: {DEFAULT_API_KEY}")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        pipe = None
    print("=" * 60)

@app.get("/")
def root():
    return {
        "service": "Hybrid Image Generation - Local GPU Backend",
        "status": "online",
        "uptime_seconds": round(time.time() - startup_time, 2),
        "docs_url": "/docs"
    }

@app.get("/api/status")
def get_status(api_key: Optional[str] = None):
    """Cek kesehatan backend, ketersediaan GPU, status model, dan VRAM"""
    global pipe
    cuda_available = torch.cuda.is_available()
    
    vram_info = {}
    if cuda_available:
        try:
            allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            vram_info = {
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "total_gb": round(total, 2)
            }
        except Exception:
            pass

    return {
        "status": "healthy",
        "model_status": "ready" if pipe is not None else "initializing",
        "model_id": MODEL_ID,
        "device": "cuda" if cuda_available else "cpu",
        "gpu_available": cuda_available,
        "gpu_name": torch.cuda.get_device_name(0) if cuda_available else "CPU (No CUDA)",
        "vram": vram_info,
        "active_api_keys": len(VALID_API_KEYS)
    }

@app.post("/api/key")
def generate_api_key(request: ApiKeyRequest):
    """Menghasilkan Custom API Key baru untuk client"""
    new_key = f"sk-local-{secrets.token_urlsafe(16)}"
    VALID_API_KEYS[new_key] = {
        "device_name": request.device_name,
        "created_at": datetime.now().isoformat()
    }
    return {
        "success": True,
        "api_key": new_key,
        "message": f"API Key created for {request.device_name}"
    }

@app.post("/api/generate")
def generate_image(
    request: GenerationRequest,
    api_key: str = Security(verify_api_key)
):
    """
    Endpoint utama inferensi gambar dengan GPU lokal.
    Mengembalikan gambar dalam format Base64 PNG beserta metrik latensi.
    """
    global pipe
    if pipe is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is still loading or failed to initialize."
        )

    # Validasi dimensi (harus kelipatan 8)
    if request.width % 8 != 0 or request.height % 8 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Width and Height must be multiples of 8."
        )

    t0 = time.time()
    try:
        # Penanganan seed
        generator = None
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
        if request.seed is not None and request.seed >= 0:
            generator = torch.Generator(device_str).manual_seed(request.seed)

        # Proses inferensi pada GPU
        with torch.inference_mode():
            result = pipe(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt if request.negative_prompt else None,
                num_inference_steps=request.steps,
                guidance_scale=request.cfg_scale,
                width=request.width,
                height=request.height,
                generator=generator
            )
            image = result.images[0]

        # Konversi output gambar ke Base64 PNG
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        latency = round(time.time() - t0, 3)
        print(f"✨ Image generated in {latency}s [{request.width}x{request.height}, steps={request.steps}] on {device_str}")

        return JSONResponse({
            "success": True,
            "image_base64": img_str,
            "latency_seconds": latency,
            "device": device_str,
            "resolution": f"{request.width}x{request.height}",
            "timestamp": datetime.now().isoformat()
        })

    except torch.cuda.OutOfMemoryError:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CUDA Out of Memory! Kurangi resolusi gambar (misal 512x512) atau jumlah steps."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    print(f"Starting server on http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)