import re
import time
from functools import lru_cache
from pathlib import Path

from app.core import config

FACES = {"sans": ("LiberationSans-Regular", "LiberationSans-Bold", "LiberationSans-Italic", "LiberationSans-BoldItalic"),
         "serif": ("LiberationSerif-Regular", "LiberationSerif-Bold", "LiberationSerif-Italic", "LiberationSerif-BoldItalic"),
         "mono": ("LiberationMono-Regular", "LiberationMono-Bold", "LiberationMono-Italic", "LiberationMono-BoldItalic")}
VERSION = "PDF/X-1a:2001"
PDFX_KEY = "PDF/X-1:2001"


@lru_cache(maxsize=1)
def register() -> bool:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    folder = config.shared_dir() / "fonts" / "liberation"
    for faces in FACES.values():
        for name in faces:
            pdfmetrics.registerFont(TTFont(name, str(folder / f"{name}.ttf")))
    return True


def font(family: str, bold: bool, italic: bool) -> str:
    register()
    return FACES.get(family, FACES["sans"])[(1 if bold else 0) + (2 if italic else 0)]


def finish(path: Path, profile: str, boxes: list[tuple[float, float, float, float]], title: str) -> None:
    import pikepdf
    from PIL import ImageCms
    desc = ImageCms.getProfileDescription(ImageCms.getOpenProfile(profile)).strip() or Path(profile).stem
    with pikepdf.open(str(path), allow_overwriting_input=True) as pdf:
        icc = pikepdf.Stream(pdf, Path(profile).read_bytes())
        icc.N = 4
        pdf.Root.OutputIntents = pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX, OutputConditionIdentifier=pikepdf.String(desc),
            OutputCondition=pikepdf.String(desc), RegistryName=pikepdf.String("http://www.color.org"), Info=pikepdf.String(desc),
            DestOutputProfile=pdf.make_indirect(icc)))])
        for page, box in zip(pdf.pages, boxes):
            media = [float(v) for v in page.MediaBox]
            page.obj.TrimBox = pikepdf.Array([round(v, 3) for v in box])
            page.obj.BleedBox = pikepdf.Array(media)
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["dc:title"] = title
            meta["pdfx:GTS_PDFXVersion"] = PDFX_KEY
        info = pdf.docinfo
        stamp = pikepdf.String(time.strftime("D:%Y%m%d%H%M%S"))
        info["/Title"] = title
        info["/CreationDate"] = info.get("/CreationDate", stamp)
        info["/ModDate"] = stamp
        info["/GTS_PDFXVersion"] = PDFX_KEY
        info["/GTS_PDFXConformance"] = VERSION
        info["/Trapped"] = pikepdf.Name("/False")
        pdf.save(str(path), force_version="1.3", object_stream_mode=pikepdf.ObjectStreamMode.disable, static_id=False)


def check(path: Path) -> list[str]:
    import pikepdf
    issues: list[str] = []
    with pikepdf.open(str(path)) as pdf:
        if pdf.pdf_version > "1.3":
            issues.append(f"PDF version {pdf.pdf_version} (X-1a:2001 needs 1.3 or lower)")
        info = pdf.docinfo
        if str(info.get("/GTS_PDFXVersion", "")) != PDFX_KEY or str(info.get("/GTS_PDFXConformance", "")) != VERSION:
            issues.append("GTS_PDFXVersion or GTS_PDFXConformance missing")
        for key in ("/CreationDate", "/ModDate"):
            if key not in info:
                issues.append(f"{key[1:]} missing")
        if "/ID" not in pdf.trailer:
            issues.append("document ID missing")
        if str(info.get("/Trapped", "")) not in ("/True", "/False"):
            issues.append("Trapped key missing")
        if not str(info.get("/Title", "")).strip():
            issues.append("Title missing")
        intents = pdf.Root.get("/OutputIntents") or []
        if not any(str(i.get("/S")) == "/GTS_PDFX" and "/DestOutputProfile" in i for i in intents):
            issues.append("no GTS_PDFX output intent with an embedded profile")
        for n, page in enumerate(pdf.pages, 1):
            if "/TrimBox" not in page.obj and "/ArtBox" not in page.obj:
                issues.append(f"page {n}: no TrimBox")
            res = page.obj.get("/Resources") or {}
            for name, f in (res.get("/Font") or {}).items():
                desc = f.get("/FontDescriptor") or next((d.get("/FontDescriptor") for d in (f.get("/DescendantFonts") or [])), None)
                if desc is None or not any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                    issues.append(f"page {n}: font {f.get('/BaseFont')} not embedded")
            for name, x in (res.get("/XObject") or {}).items():
                if x.get("/Subtype") == "/Image" and str(x.get("/ColorSpace")) not in ("/DeviceCMYK", "/DeviceGray"):
                    issues.append(f"page {n}: image {name} in {x.get('/ColorSpace')}")
                if "/SMask" in x:
                    issues.append(f"page {n}: image {name} has transparency")
            if "/Group" in page.obj:
                issues.append(f"page {n}: transparency group")
            data = b"".join(c.read_bytes() for c in (page.obj.Contents if isinstance(page.obj.Contents, pikepdf.Array) else [page.obj.Contents]))
            if re.search(rb"(^|\s)(rg|RG)(\s|$)", data):
                issues.append(f"page {n}: RGB colour in the page content")
    return sorted(set(issues))
