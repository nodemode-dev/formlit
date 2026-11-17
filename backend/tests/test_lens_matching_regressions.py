"""Wrong lens profiles seen in the Windows run of 0.51.2. The Exif below is copied from the review kit's CC0 raws
(raw.pixls.us); the raws themselves are not in the repository.

Canon_EOS_R5_RAW_fullframe_nodual.CR3 (and the CRAW and dual-pixel files): Make "Canon", Model "Canon EOS R5",
LensModel "50mm F1.4 DG HSM | Art 014", FocalLength 50, exiftool LensID "Sigma 50mm f/1.4 DG HSM | A", LensInfo "50mm f/0".
0.51.2 matched it to "Sigma 105mm F1.4 DG HSM | Art 018".

Canon_EOS_R5m2_RAW_RF135mm.CR3: Make "Canon", Model "Canon EOS R5m2", LensModel "RF135mm F1.8 L IS USM", FocalLength 135,
exiftool LensID "Canon RF 135mm F1.8 L IS USM", LensInfo "135mm f/0". 0.51.2 matched it to "Canon RF 14-35mm F4 L IS USM".

LensInfo's "f/0" means the aperture is not recorded, so it is never used as an aperture."""
import pytest

R5 = ("Canon", "Canon EOS R5")
R5M2 = ("Canon", "Canon EOS R5m2")
SIGMA_ART = "50mm F1.4 DG HSM | Art 014"
RF135 = "RF135mm F1.8 L IS USM"


def match(lens, cam, focal):
    from app.services import lensdb

    best, _ = lensdb.match(lens, cam[0], cam[1], focal)
    return best["model"] if best else None


@pytest.fixture
def bundled(client, monkeypatch):
    from app.services import lensdb

    lensdb.reload()
    assert lensdb.source()["source"] == "bundled"
    return lensdb


def test_the_r5_sigma_50_art_matches_the_art_profile(bundled):
    assert match(SIGMA_ART, R5, 50.0) == "Sigma 50mm f/1.4 DG HSM [A]"


def test_the_r5_mark_ii_rf135_matches_the_rf135(bundled):
    assert match(RF135, R5M2, 135.0) == "Canon RF 135mm F1.8L IS USM"


@pytest.mark.parametrize("lens,focal", [(SIGMA_ART, 85.0), (SIGMA_ART, 105.0), ("50mm F1.2 DG HSM | Art 014", 50.0), (RF135, 35.0), ("RF135mm F2 L IS USM", 135.0)])
def test_a_focal_length_or_aperture_that_conflicts_with_the_exif_matches_nothing(bundled, lens, focal):
    assert match(lens, R5, focal) is None


def fake_index(monkeypatch, *models):
    from app.services import lensdb

    def entry(model, fmin, fmax=None):
        return {"maker": model.split()[0], "model": model, "mounts": ["Canon EF"], "crop": 1.0, "aspect": 1.5, "fmin": fmin, "fmax": fmax or fmin,
                "dist": [], "tca": [], "vig": []}

    lenses = [entry(*m) for m in models]
    monkeypatch.setattr(lensdb, "index", lambda: {"cameras": [{"maker": "Canon", "model": "Canon EOS R5", "mount": "Canon RF", "crop": 1.0}],
                                                  "lenses": lenses, "mounts": {"Canon RF": ["Canon EF"]}})


def test_the_sigma_line_must_agree_and_the_old_ex_lens_is_not_an_art(client, monkeypatch):
    fake_index(monkeypatch, ("Sigma 50mm f/1.4 EX DG HSM", 50.0))
    assert match(SIGMA_ART, R5, 50.0) is None
    fake_index(monkeypatch, ("Sigma 50mm f/1.4 EX DG HSM", 50.0), ("Sigma 50mm f/1.4 DG HSM | A", 50.0))
    assert match(SIGMA_ART, R5, 50.0) == "Sigma 50mm f/1.4 DG HSM | A"
    assert match("50mm F1.4 EX DG HSM", R5, 50.0) == "Sigma 50mm f/1.4 EX DG HSM"


def test_the_sigma_version_code_tells_lenses_apart(client, monkeypatch):
    fake_index(monkeypatch, ("Sigma 105mm F1.4 DG HSM | Art 018", 105.0), ("Sigma 70mm f/2.8 DG Macro | Art 018", 70.0), ("Sigma 70mm f/2.8 DG Macro | Art 006", 70.0))
    assert match(SIGMA_ART, R5, 50.0) is None
    assert match("70mm F2.8 DG MACRO | Art 018", R5, 70.0) == "Sigma 70mm f/2.8 DG Macro | Art 018"
    assert match("70mm F2.8 DG MACRO | Art 006", R5, 70.0) == "Sigma 70mm f/2.8 DG Macro | Art 006"
    assert match("70mm F2.8 DG MACRO | Art 021", R5, 70.0) is None


def test_two_different_lenses_scoring_alike_match_neither(client, monkeypatch):
    fake_index(monkeypatch, ("Canon RF 50mm F1.8 STM", 50.0), ("Canon RF 50mm F1.8 IS STM", 50.0))
    assert match("RF50mm F1.8", R5, 50.0) is None


def test_duplicates_of_one_lens_still_match(bundled):
    assert match("16mm F1.4 DC DN | Contemporary 017", ("Canon", "Canon EOS R7"), 16.0) in ("Sigma 16mm f/1.4 DC DN | Contemporary 017",
                                                                                         "Sigma 16mm f/1.4 DC DN | Contemporary C 017")


def set_optics(pid, lens, camera, focal, make):
    import json

    from app.engine import catalog as catalog_mod

    cat = catalog_mod.get()
    with cat.lock:
        cat.db.execute("UPDATE photos SET lens=?, camera=?, focal=?, exif=? WHERE id=?", (lens, camera, focal, json.dumps({"make": make, "focal": focal}), pid))


def test_an_unmatched_lens_gets_no_profile_and_says_so(client, commands, photo):
    set_optics(photo["id"], "50mm F1.4 DG HSM | Art 014", "Canon EOS R5", 85.0, "Canon")
    info = commands("develop.lensProfileInfo", {"id": photo["id"]})
    assert info["guess"] is None and info["available"] is False
    res = commands("develop.lensProfile", {"ids": [photo["id"]], "enable": True})
    assert res["noProfile"] == [photo["id"]] and res["ids"] == []
    assert not (commands("develop.get", {"id": photo["id"]}).get("settings", {}).get("optics") or {}).get("profile")


def test_the_r5_sigma_art_profile_applies_and_auto_ca_defers_to_its_tca(client, commands, photo):
    set_optics(photo["id"], SIGMA_ART, "Canon EOS R5", 50.0, "Canon")
    info = commands("develop.lensProfileInfo", {"id": photo["id"]})
    assert info["guess"]["model"] == "Sigma 50mm f/1.4 DG HSM [A]"
    res = commands("develop.lensProfile", {"ids": [photo["id"]], "enable": True})
    assert res["ids"] == [photo["id"]]
    ca = commands("develop.autoCa", {"id": photo["id"]})
    assert ca == {"autoCaRed": 0.0, "autoCaBlue": 0.0, "fromProfile": True}
