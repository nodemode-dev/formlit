import numpy as np
import pytest


class FakeInput:
    def __init__(self, name):
        self.name = name


class FakeSession:
    def __init__(self, file, fn):
        self.file = file
        self.fn = fn
        self.calls = []

    def get_inputs(self):
        return [FakeInput("input")]

    def run(self, names, feeds):
        self.calls.append({k: np.asarray(v).shape for k, v in feeds.items()})
        return self.fn(feeds)


def disc(n):
    yy, xx = np.mgrid[0:n, 0:n]
    return ((xx - n / 2) ** 2 + (yy - n / 2) ** 2 < (n / 4) ** 2).astype(np.float32)


def fake_model(feeds):
    if "pixel_values" in feeds:
        return [np.zeros((1, 32, 256, 256), np.float32), np.zeros((1, 64, 128, 128), np.float32), np.zeros((1, 256, 64, 64), np.float32)]
    if "input_points" in feeds:
        masks = np.stack([disc(256) * 16.0 - 8.0] * 3)[None, None]
        return [np.array([[[0.2, 0.9, 0.4]]], np.float32), masks, np.zeros((1, 1, 1), np.float32)]
    side = feeds["input"].shape[-1]
    if side == 1024:
        return [disc(1024)[None, None] * 16.0 - 8.0]
    return [disc(side)[None, None]]


@pytest.fixture
def installed(monkeypatch):
    from app.ai import models

    have: set[str] = set()
    opened: list[str] = []

    def session(key, file, model=None):
        opened.append(file)
        return FakeSession(file, fake_model)

    monkeypatch.setattr(models, "ready", lambda m: m in have)
    monkeypatch.setattr(models, "session", session)
    return have, opened


@pytest.fixture
def image():
    rng = np.random.default_rng(3)
    return rng.integers(0, 255, (300, 450, 3), dtype=np.uint8)


def test_every_choice_is_pinned_like_the_other_models():
    from app.ai import models

    for family, choices in models.CHOICES.items():
        assert len(choices) == 2 and all(c in models.MODELS for c in choices)
        for c in choices:
            for name, (url, sha) in models.MODELS[c]["files"].items():
                assert url.startswith("https://") and len(sha) == 64 and int(sha, 16) >= 0, (c, name)
    assert models.MODELS["subjectHq"]["license"] == "MIT" and models.MODELS["objectsHq"]["license"] == "Apache-2.0"
    assert models.MODELS["subjectHq"]["files"][models.BIREFNET_FILE][0].startswith("https://github.com/ZhengPeng7/BiRefNet/releases/download/")


def test_the_recommended_models_run_on_the_cpu_provider_only(monkeypatch):
    import onnxruntime as ort

    from app.ai import models

    seen = {}

    def fake(path, opts, providers):
        seen[str(path).split("Models", 1)[-1]] = providers
        return object()

    monkeypatch.setattr(ort, "InferenceSession", fake)
    monkeypatch.setattr(models, "providers", lambda: ["CoreMLExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setattr(models, "_sessions", {})
    models.session("subjectHq", models.BIREFNET_FILE)
    models.session("sam-enc-objectsHq", "sam2.1-hiera-base-plus/vision_encoder.onnx", "objectsHq")
    models.session("sam-enc-objects", "sam2.1-hiera-tiny/vision_encoder.onnx", "objects")
    by_file = {k.rsplit("/", 2)[-2] + "/" + k.rsplit("/", 1)[-1]: v for k, v in seen.items()}
    assert by_file[models.BIREFNET_FILE] == ["CPUExecutionProvider"]
    assert by_file["sam2.1-hiera-base-plus/vision_encoder.onnx"] == ["CPUExecutionProvider"]
    assert by_file["sam2.1-hiera-tiny/vision_encoder.onnx"] == ["CoreMLExecutionProvider", "CPUExecutionProvider"]


@pytest.mark.parametrize("have,subject,objects", [
    (set(), None, None),
    ({"subject", "objects"}, "subject", "objects"),
    ({"subjectHq", "objectsHq"}, "subjectHq", "objectsHq"),
    ({"subject", "subjectHq", "objects", "objectsHq"}, "subjectHq", "objectsHq"),
])
def test_the_best_installed_model_is_chosen(installed, have, subject, objects):
    from app.ai import models

    installed[0].update(have)
    assert models.best("subject") == subject
    assert models.best("objects") == objects
    assert models.usable("subject") is (subject is not None)


def test_nothing_installed_names_the_recommended_model_and_the_small_one(installed):
    from app.ai import models

    with pytest.raises(models.ModelMissing) as e:
        models.require("subject")
    assert e.value.model == "subjectHq" and e.value.choices == ["subjectHq", "subject"]
    assert "U2-Net" in str(e.value) and "BiRefNet" in str(e.value)


def test_a_model_outside_the_choices_keeps_its_own_name(installed):
    from app.ai import models

    with pytest.raises(models.ModelMissing) as e:
        models.require("sky")
    assert e.value.model == "sky" and e.value.choices == ["sky"]


def test_catalogue_marks_recommended_and_small():
    from app.ai import models

    rows = {m["id"]: m for m in models.catalogue()}
    assert rows["subjectHq"]["recommended"] is True and rows["subject"]["recommended"] is False
    assert rows["objectsHq"]["for"] == rows["objects"]["for"] == "objects"
    assert "for" not in rows["sky"]


def check_mask(a, image):
    assert a.shape == image.shape[:2] and a.dtype == np.float32
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0
    h, w = a.shape
    assert a[h // 2, w // 2] > 0.9 and a[2, 2] < 0.1


def test_subject_uses_birefnet_when_it_is_installed(installed, image):
    from app.ai import models, nets

    installed[0].update({"subject", "subjectHq"})
    a = nets.subject(image)
    check_mask(a, image)
    assert installed[1] == [models.BIREFNET_FILE]


def test_subject_falls_back_to_u2net_when_only_the_small_model_is_installed(installed, image):
    from app.ai import nets

    installed[0].add("subject")
    a = nets.subject(image)
    check_mask(a, image)
    assert installed[1] == ["u2net.onnx"]


def test_birefnet_turns_logits_into_a_zero_to_one_mask(installed, image):
    from app.ai import nets

    installed[0].add("subjectHq")
    a = nets.birefnet(image)
    check_mask(a, image)
    assert float(a.max()) > 0.99 and float(a.min()) < 0.01


@pytest.mark.parametrize("have,folder", [({"objects"}, "sam2.1-hiera-tiny"), ({"objects", "objectsHq"}, "sam2.1-hiera-base-plus"), ({"objectsHq"}, "sam2.1-hiera-base-plus")])
def test_objects_use_the_best_installed_sam(installed, image, have, folder):
    from app.ai import nets

    installed[0].update(have)
    a = nets.sam_box(image, [0.25, 0.25, 0.75, 0.75])
    check_mask(a, image)
    assert installed[1] == [f"{folder}/vision_encoder.onnx", f"{folder}/prompt_encoder_mask_decoder.onnx"]


def test_u2net_alone_does_not_run_on_birefnet(installed, image):
    from app.ai import models, nets

    installed[0].add("subjectHq")
    with pytest.raises(models.ModelMissing):
        nets.u2net(image, "subject")


def test_the_mask_command_runs_on_the_small_model(client, photo, installed):
    installed[0].add("subject")
    r = client.post("/api/commands/develop.aiMask", json={"id": photo["id"], "kind": "subject"})
    assert r.status_code == 200, r.text
    shape = r.json()["result"]["shape"]
    assert shape["kind"] == "subject" and 0.0 < shape["coverage"] < 1.0
    assert installed[1] == ["u2net.onnx"]
