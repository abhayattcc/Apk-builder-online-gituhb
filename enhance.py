"""
Enhance low-quality photos (denoise, fix colour, restore faces, upscale 2x).
Reads  : input/*.jpg|jpeg|png|webp
Writes : output/<name>_enhanced.png
Skips images that already have an output file.
"""
import os
import sys
import glob
import urllib.request

import cv2
import numpy as np
import torch
from basicsr.archs.rrdbnet_arch import RRDBNet
from gfpgan import GFPGANer
from realesrgan import RealESRGANer

INPUT_DIR = "input"
OUTPUT_DIR = "output"
WEIGHTS_DIR = "weights"
MAX_SIDE = 1600       # shrink huge inputs so CPU runners finish quickly
UPSCALE = 2
FACE_WEIGHT = 0.6     # 0 = max quality/changes face, 1 = stay closer to original

MODELS = {
    "GFPGANv1.4.pth": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
    "RealESRGAN_x2plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
}


def download_weights():
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    for name, url in MODELS.items():
        path = os.path.join(WEIGHTS_DIR, name)
        if not os.path.exists(path):
            print(f"Downloading {name} ...")
            urllib.request.urlretrieve(url, path)


def preprocess(img):
    """Gentle cleanup before the AI models: resize, denoise, fix colour cast, contrast."""
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # remove compression noise / halos
    img = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)

    # simple gray-world white balance (blended so it never looks harsh)
    f = img.astype(np.float32)
    means = f.reshape(-1, 3).mean(axis=0)
    gain = means.mean() / np.maximum(means, 1e-6)
    balanced = np.clip(f * gain, 0, 255)
    img = (0.5 * f + 0.5 * balanced).astype(np.uint8)

    # mild local contrast on the lightness channel
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def build_restorer():
    use_gpu = torch.cuda.is_available()
    bg_model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                       num_block=23, num_grow_ch=32, scale=2)
    bg_upsampler = RealESRGANer(
        scale=2,
        model_path=os.path.join(WEIGHTS_DIR, "RealESRGAN_x2plus.pth"),
        model=bg_model,
        tile=400, tile_pad=10, pre_pad=0,
        half=use_gpu,
    )
    return GFPGANer(
        model_path=os.path.join(WEIGHTS_DIR, "GFPGANv1.4.pth"),
        upscale=UPSCALE,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=bg_upsampler,
    )


def main():
    exts = ("jpg", "jpeg", "png", "webp", "bmp")
    files = sorted(f for e in exts for f in
                   glob.glob(os.path.join(INPUT_DIR, f"*.{e}")) +
                   glob.glob(os.path.join(INPUT_DIR, f"*.{e.upper()}")))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    todo = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(OUTPUT_DIR, f"{stem}_enhanced.png")
        if not os.path.exists(out):
            todo.append((f, out))

    if not todo:
        print("Nothing new to enhance.")
        return

    download_weights()
    restorer = build_restorer()

    for src, dst in todo:
        print(f"Enhancing {src} ...")
        img = cv2.imread(src, cv2.IMREAD_COLOR)
        if img is None:
            print(f"  could not read {src}, skipping")
            continue
        img = preprocess(img)
        _, _, result = restorer.enhance(
            img, has_aligned=False, only_center_face=False,
            paste_back=True, weight=FACE_WEIGHT,
        )
        cv2.imwrite(dst, result)
        print(f"  saved {dst}")


if __name__ == "__main__":
    sys.exit(main())
