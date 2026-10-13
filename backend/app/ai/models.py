import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Callable

from app.core import config

MODELS: dict[str, dict] = {
    "subject": {"name": "U2-Net (subject and background)", "license": "Apache-2.0", "size": 176,
                "files": {"u2net.onnx": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
                                         "8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491")}},
    "people": {"name": "U2-Net human segmentation (people)", "license": "Apache-2.0", "size": 176,
               "files": {"u2net_human_seg.onnx": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx",
                                                  "01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c")}},
    "sky": {"name": "Sky segmenter (U-2-Net, xiongzhu666)", "license": "MIT", "size": 176,
            "files": {"skyseg/skyseg.onnx": ("https://huggingface.co/JianyuanWang/skyseg/resolve/3ba8c6df1d9ba9ff26f637c7ba9568ac11a9aa7f/skyseg.onnx",
                                             "ab9c34c64c3d821220a2886a4a06da4642ffa14d5b30e8d5339056a089aa1d39")}},
    "depth": {"name": "Depth Anything V2 Small", "license": "Apache-2.0", "size": 99,
              "files": {"depth-anything-v2-small/model.onnx": ("https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/413ce838e669ab7dfc01a6a396bf3d4397286d7f/onnx/model.onnx",
                                                               "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c")}},
    "objects": {"name": "SAM 2.1 tiny (objects)", "license": "Apache-2.0", "size": 155,
                "files": {
                    "sam2.1-hiera-tiny/vision_encoder.onnx": ("https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/814a066640debee5a91e70aa401fb8e17e030503/onnx/vision_encoder.onnx",
                                                              "4f30aacd3aaefbca81a0b7fe4c1fc96345570ea0a6f80ced599493d1b3be2e8c"),
                    "sam2.1-hiera-tiny/vision_encoder.onnx_data": ("https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/814a066640debee5a91e70aa401fb8e17e030503/onnx/vision_encoder.onnx_data",
                                                                   "e83df9866a5afe68ea7f0f721f18f65137fc3acbf0da1c74e946d363e09c69cc"),
                    "sam2.1-hiera-tiny/prompt_encoder_mask_decoder.onnx": ("https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/814a066640debee5a91e70aa401fb8e17e030503/onnx/prompt_encoder_mask_decoder.onnx",
                                                                           "874414704c5d686db7d206a35f6e15d26563d50c8c4468fccc6739bd7e491dcf"),
                    "sam2.1-hiera-tiny/prompt_encoder_mask_decoder.onnx_data": ("https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/814a066640debee5a91e70aa401fb8e17e030503/onnx/prompt_encoder_mask_decoder.onnx_data",
                                                                                "e9874d900dd4134ed60eab1e97910327c2419e0b2954485d8fd6e7f1a1470f47"),
                }},
    "remove": {"name": "LaMa inpainting (generative remove)", "license": "Apache-2.0", "size": 208,
               "files": {"lama_fp32.onnx": ("https://huggingface.co/Carve/LaMa-ONNX/resolve/c3c0c9e468934d62e79c329e35d82dd09ff8c444/lama_fp32.onnx",
                                            "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6")}},
    "upscale": {"name": "Real-ESRGAN x4plus (super resolution)", "license": "BSD-3-Clause", "size": 67,
                "files": {"realesrgan-x4plus.onnx": ("https://huggingface.co/skillsafe-ai/realesrgan-x4plus/resolve/107475e49b7d46412cc966481efccc3500955801/model.onnx",
                                                     "4851ec156207d271f5328605d0582eeb851e656227da8aca093ced9e60789291")}},
    "faces": {"name": "YuNet face detector and SFace recognizer (OpenCV Zoo)", "license": "MIT and Apache-2.0", "size": 39,
              "files": {
                  "yunet-face/face_detection_yunet_2023mar.onnx": ("https://huggingface.co/opencv/face_detection_yunet/resolve/3cc26e7f1014a5ee5d74a42acee58bafc9d0a310/face_detection_yunet_2023mar.onnx",
                                                                    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
                  "sface/face_recognition_sface_2021dec.onnx": ("https://huggingface.co/opencv/face_recognition_sface/resolve/3d7082438a6e4551e840c9b2bb60b71e8da4b524/face_recognition_sface_2021dec.onnx",
                                                                "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
              }},
}

_lock = threading.RLock()
_sessions: dict[str, Any] = {}
_downloading: set[str] = set()
PROVIDERS = ("CoreMLExecutionProvider", "DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider")


class ModelMissing(Exception):
    def __init__(self, model: str):
        spec = MODELS[model]
        super().__init__(f"{spec['name']} is not installed yet ({spec['size']} MB, {spec['license']}). Install it in Preferences, or call run_command with {{\"command\": \"ai.download\", \"params\": {{\"model\": \"{model}\", \"wait\": true}}}} once; if that fails, do the edit without this mask (the colour mixer or a gradient mask) rather than retrying.")
        self.model = model


def path(name: str) -> Path:
    return config.models_dir() / name


def ready(model: str) -> bool:
    spec = MODELS.get(model)
    if not spec:
        return False
    return all(path(n).is_file() and path(n).stat().st_size > 1024 for n in spec["files"])


def require(model: str) -> None:
    if not ready(model):
        raise ModelMissing(model)


def catalogue() -> list[dict]:
    return [{"id": k, "name": v["name"], "license": v["license"], "sizeMB": v["size"], "ready": ready(k), "downloading": k in _downloading} for k, v in MODELS.items()]


def download(model: str, progress: Callable | None = None) -> dict:
    import httpx
    spec = MODELS[model]
    files = list(spec["files"].items())
    _downloading.add(model)
    try:
        for i, (name, (url, sha)) in enumerate(files):
            target = path(name)
            if target.is_file() and target.stat().st_size > 1024:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".download")
            digest = hashlib.sha256()
            try:
                with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0))
                    got = 0
                    with tmp.open("wb") as out:
                        for chunk in r.iter_bytes(1 << 20):
                            if progress is not None and getattr(progress, "cancelled", False):
                                raise InterruptedError("Cancelled")
                            out.write(chunk)
                            digest.update(chunk)
                            got += len(chunk)
                            if progress is not None and total:
                                progress(i * 1000 + int(1000 * got / total), len(files) * 1000, f"Downloading {spec['name']}")
                if digest.hexdigest() != sha:
                    raise ValueError(f"Checksum mismatch for {name}: the download was discarded")
                tmp.replace(target)
                target.with_suffix(target.suffix + ".json").write_text(json.dumps({"url": url, "sha256": sha, "license": spec["license"]}))
            finally:
                tmp.unlink(missing_ok=True)
    finally:
        _downloading.discard(model)
    return {"model": model, "ready": ready(model)}


def providers() -> list[str]:
    import onnxruntime as ort
    have = ort.get_available_providers()
    return [p for p in PROVIDERS if p in have] or ["CPUExecutionProvider"]


def session(key: str, file: str):
    with _lock:
        s = _sessions.get(key)
        if s is None:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.enable_cpu_mem_arena = False
            s = ort.InferenceSession(str(path(file)), opts, providers=providers())
            _sessions[key] = s
            while len(_sessions) > 3:
                _sessions.pop(next(iter(_sessions)))
        return s
