def E(id: str, name: str, group: str, description: str, settings: dict) -> dict:
    return {"id": f"builtin.{id}", "name": name, "group": group, "description": description, "settings": settings}


SRGB_JPEG = {"format": "jpeg", "space": "srgb", "depth": 8}

LIBRARY = [
    E("client-gallery", "Client Gallery (2048 px, signed)", "Client Delivery", "Online gallery size with a small copyright mark bottom right and the copyright in the file.",
      {"file": {**SRGB_JPEG, "quality": 85}, "size": {"resize": True, "mode": "long", "value": 2048}, "sharpen": {"on": True, "for": "screen", "amount": "standard"},
       "metadata": {"include": "copyright"}, "watermark": {"on": True, "kind": "text", "text": "{copyright}", "size": 0.022, "opacity": 0.6, "anchor": "br"}}),
    E("proof", "Proofs (1200 px, centred watermark)", "Client Delivery", "Small proofs for choosing, with a large faint watermark across the middle so they cannot stand in for the finals.",
      {"file": {**SRGB_JPEG, "quality": 70}, "size": {"resize": True, "mode": "long", "value": 1200}, "sharpen": {"on": True, "for": "screen", "amount": "low"},
       "metadata": {"include": "copyright"}, "watermark": {"on": True, "kind": "text", "text": "PROOF {copyright}", "size": 0.06, "opacity": 0.3, "anchor": "c", "shadow": False}}),
    E("print-lab", "Print Lab (sRGB JPEG, 300 ppi)", "Print", "Full size, high-quality sRGB JPEG for consumer and pro labs (Mpix asks for sRGB; Bay Photo and WHCC also take Adobe RGB; WHCC prints most products at 300 dpi, Mpix and Bay Photo size at 250).",
      {"file": {**SRGB_JPEG, "quality": 93}, "size": {"ppi": 300}, "sharpen": {"on": True, "for": "glossy", "amount": "standard"}, "metadata": {"include": "copyright"}}),
    E("stock", "Stock Agency (sRGB JPEG, full size)", "Licensing", "Full-size sRGB JPEG with all metadata; Adobe Stock and Shutterstock both ask for JPEG in sRGB of at least 4 MP, so do not crop below that.",
      {"file": {**SRGB_JPEG, "quality": 95}, "metadata": {"include": "all", "removePerson": False}}),
    E("news", "News Filing (JPEG, full metadata)", "Licensing", "Full-size JPEG that keeps every IPTC field (caption, creator, credit, location) for a picture desk.",
      {"file": {**SRGB_JPEG, "quality": 90}, "metadata": {"include": "all", "removePerson": False, "removeLocation": False}}),
    E("mls", "Real Estate MLS (3000 px, under 6 MB)", "Web and Social", "sRGB JPEG with the long side at 3000 px and each file under 6 MB. MLS rules vary (Canopy MLS caps at 3000 x 3000 and 6 MB; Canopy and Unlock MLS both ask for at least 2048 x 1536), so check yours.",
      {"file": {**SRGB_JPEG, "quality": 85, "limitKB": 6000}, "size": {"resize": True, "mode": "long", "value": 3000}, "sharpen": {"on": True, "for": "screen", "amount": "standard"},
       "metadata": {"include": "copyright"}}),
    E("instagram", "Instagram (1080 px wide)", "Web and Social", "1080 px wide sRGB JPEG; Instagram's help says it keeps photos up to 1080 px across. Crop to 4:5 portrait or 1:1 first if you want them to fill the feed.",
      {"file": {**SRGB_JPEG, "quality": 88}, "size": {"resize": True, "mode": "wh", "w": 1080, "h": 10000}, "sharpen": {"on": True, "for": "screen", "amount": "standard"},
       "metadata": {"include": "copyright"}}),
    E("blog", "Blog and Website (1600 px)", "Web and Social", "1600 px long side, lighter file for web pages.",
      {"file": {**SRGB_JPEG, "quality": 80}, "size": {"resize": True, "mode": "long", "value": 1600}, "sharpen": {"on": True, "for": "screen", "amount": "standard"},
       "metadata": {"include": "copyright"}}),
    E("4k", "4K Display (3840 px)", "Web and Social", "3840 px long side for 4K screens, slideshows and portfolio sites.",
      {"file": {**SRGB_JPEG, "quality": 90}, "size": {"resize": True, "mode": "long", "value": 3840}, "sharpen": {"on": True, "for": "screen", "amount": "low"},
       "metadata": {"include": "copyright"}}),
    E("archive", "Archive Master (16-bit TIFF, Adobe RGB)", "Print", "Lossless 16-bit TIFF in Adobe RGB with all metadata, for a finished master to keep.",
      {"file": {"format": "tiff", "depth": 16, "compression": "zip", "space": "adobergb"}, "metadata": {"include": "all", "removePerson": False}}),
]
