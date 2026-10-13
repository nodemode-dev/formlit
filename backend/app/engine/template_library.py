def T(id: str, name: str, value, description: str, tags: str = "", **extra) -> dict:
    return {"id": id, "name": name, "value": value, "description": description, "tags": tags.split(), **extra}


FILENAME = [
    T("filename", "Filename (unchanged)", "{name}", "Keeps the camera's file name.", "keep original"),
    T("custom-seq", "Custom Name - Sequence", "{custom}-{seq:3}", "Shoot or client name plus a three-digit count; the usual delivery naming.", "client delivery"),
    T("custom-num", "Custom Name - Original File Number", "{custom}-{num}", "Custom name plus the camera's own frame number, so names still trace back to the card.", "client card"),
    T("date-filename", "Date - Filename", "{date:%Y%m%d}-{name}", "Capture date in front of the camera name; sorts by day in any file browser.", "date"),
    T("date-seq", "Date - Sequence", "{date:%Y-%m-%d}-{seq:4}", "Capture date and a four-digit count.", "date"),
    T("datetime-num", "Date and Time - Original Number", "{date:%Y%m%d_%H%M%S}_{num}", "Capture time to the second plus the frame number; unique even for bursts.", "time burst"),
    T("shoot-filename", "Shoot Name - Filename", "{custom}-{name}", "Shoot name in front of the camera name.", "shoot"),
    T("client-date-seq", "Client_Date_Sequence", "{custom}_{date:%Y%m%d}_{seq:4}", "Client or job, capture date and count; a common studio delivery pattern.", "client studio delivery"),
    T("creator-date-seq", "Creator_Date_Sequence", "{creator}_{date:%Y%m%d}_{seq:4}", "Photographer, date and count; needs a creator in the metadata (a metadata template at import sets it).", "creator agency"),
    T("multicam", "Time-sorted Multi-camera", "{date:%Y%m%d-%H%M%S}-{camera}-{num}", "Capture time first, then body and frame: files from several cameras interleave in shooting order. Set every camera's clock to the same time before the shoot.", "wedding event second shooter"),
    T("wire", "Wire: Date_Creator_Sequence", "{date:%Y%m%d}_{creator}_{seq:3}", "Date, photographer and count for news and sports filing; needs a creator in the metadata.", "news sports editorial"),
    T("listing-seq", "Listing - Sequence", "{custom}-{seq:2}", "Property address or listing id as the custom text and a two-digit order, the order the listing shows them.", "real estate mls"),
    T("product-sku", "SKU - Sequence", "{custom}_{seq:2}", "Product SKU as the custom text and a view number (01 front, 02 back and so on).", "product ecommerce"),
    T("city-date-seq", "City_Date_Sequence", "{city}_{date:%Y%m%d}_{seq:3}", "City from the metadata, date and count; for travel work.", "travel location"),
    T("title-seq", "Title - Sequence", "{title}-{seq:2}", "Title from the metadata and a count; for portfolio and print files.", "portfolio fine art"),
    T("folder-seq", "Folder - Sequence", "{folder}-{seq:4}", "The folder's name and a count.", "folder"),
    T("rating-filename", "Rating - Filename", "{rating}star-{name}", "Star rating in front of the name, so selects sort to the top.", "rating selects"),
]

FOLDER = [
    T("year-day", "By date: 2026/2026-10-07", "{date:%Y}/{date:%Y-%m-%d}", "Year, then one folder per day.", "date"),
    T("year-month", "By date: 2026/10", "{date:%Y}/{date:%m}", "Year, then month.", "date"),
    T("day", "By date: 2026-10-07", "{date:%Y-%m-%d}", "One folder per day.", "date"),
    T("year-day-shoot", "Year / Date Shoot Name", "{date:%Y}/{date:%Y-%m-%d} {custom}", "Year, then a job folder that starts with the date so jobs sort in order (the custom text is the shoot name).", "shoot job client"),
    T("year-shoot", "Year / Shoot Name", "{date:%Y}/{custom}", "Year, then the shoot name.", "shoot job"),
    T("clients", "Clients / Client / Date", "Clients/{custom}/{date:%Y-%m-%d}", "A folder per client (the custom text), then per day.", "client studio"),
    T("camera-day", "By camera: Camera / Date", "{camera}/{date:%Y-%m-%d}", "One folder per body, then per day; keeps a second shooter's cards apart.", "camera second shooter"),
    T("one", "Into one folder", "", "Everything into the destination folder.", "flat"),
]


def _cc(id: str, name: str, code: str, path: str) -> dict:
    return T(f"cc-{id}", f"Creative Commons {code}", {
        "creator": "{creator}", "copyright": "© {year} {creator}. Licensed under " + code + ".", "copyrightStatus": "Copyrighted",
        "rightsUsage": f"Creative Commons {name} ({code})", "copyrightUrl": f"https://creativecommons.org/licenses/{path}/4.0/",
    }, f"Marks the photos as licensed under {code} and links the licence deed.", "license creative commons cc")


METADATA = [
    T("all-rights", "Copyright: All Rights Reserved", {"creator": "{creator}", "copyright": "© {year} {creator}. All rights reserved.", "copyrightStatus": "Copyrighted",
                                                       "rightsUsage": "No use without written permission from {creator}.", "creatorEmail": "{email}", "creatorUrl": "{url}"},
      "Creator, copyright notice, status and usage terms; the default for anything that leaves the studio.", "copyright rights"),
    _cc("by", "Attribution 4.0 International", "CC BY 4.0", "by"),
    _cc("by-sa", "Attribution-ShareAlike 4.0 International", "CC BY-SA 4.0", "by-sa"),
    _cc("by-nd", "Attribution-NoDerivatives 4.0 International", "CC BY-ND 4.0", "by-nd"),
    _cc("by-nc", "Attribution-NonCommercial 4.0 International", "CC BY-NC 4.0", "by-nc"),
    _cc("by-nc-sa", "Attribution-NonCommercial-ShareAlike 4.0 International", "CC BY-NC-SA 4.0", "by-nc-sa"),
    _cc("by-nc-nd", "Attribution-NonCommercial-NoDerivatives 4.0 International", "CC BY-NC-ND 4.0", "by-nc-nd"),
    T("cc0", "Public Domain (CC0 1.0)", {"creator": "{creator}", "copyrightStatus": "Public Domain", "rightsUsage": "CC0 1.0 Universal: no rights reserved.",
                                          "copyrightUrl": "https://creativecommons.org/publicdomain/zero/1.0/"}, "Dedicates the photos to the public domain under CC0 1.0.", "license public domain cc0"),
    T("editorial", "Editorial and News", {"creator": "{creator}", "creatorJob": "Photographer", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted",
                                          "credit": "{creator}", "source": "{creator}", "instructions": "Editorial use only.", "jobId": "{job}"},
      "IPTC fields a picture desk reads: creator, job title, credit line, source, instructions and job id. Write the caption per photo.", "news sports editorial iptc"),
    T("wedding-client", "Wedding Client Delivery", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted", "event": "{event}",
                                                    "rightsUsage": "Personal use licence: prints and personal social media with credit to {creator}. No commercial use.", "creatorUrl": "{url}"},
      "Copyright with a personal-use licence for a couple's gallery, and the event name.", "wedding client personal"),
    T("commercial", "Commercial Client Licence", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted",
                                                  "rightsUsage": "Licensed to {client} for the usage agreed in the contract.", "instructions": "Contact {creator} for additional licensing.",
                                                  "creatorEmail": "{email}"}, "Copyright with usage limited to the client's contract.", "commercial client product"),
    T("real-estate", "Real Estate Listing", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted", "credit": "{creator}",
                                             "rightsUsage": "Licensed to {client} to market the listed property only, for the duration of the listing."},
      "Copyright with usage limited to marketing the listing.", "real estate mls listing"),
    T("event", "Event Coverage", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted", "event": "{event}", "credit": "{creator}"},
      "Creator, copyright, credit line and the event name.", "event conference corporate"),
    T("portfolio", "Portfolio and Web", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted", "creatorUrl": "{url}",
                                         "rightsUsage": "Portfolio display. No reuse without permission."}, "Copyright and a link back for photos posted online.", "web portfolio social"),
    T("stock", "Stock Submission", {"creator": "{creator}", "copyright": "© {year} {creator}", "copyrightStatus": "Copyrighted"},
      "Creator and copyright only; agencies take title, description and keywords from their own upload form or the photo's Title, Caption and Keywords.", "stock agency"),
    T("clear-rights", "Clear Rights Fields", {"copyright": "", "copyrightStatus": "", "rightsUsage": "", "copyrightUrl": ""},
      "Empties copyright, status, usage terms and the licence link.", "clear reset"),
]

KEYWORDS = [
    T("landscape", "Outdoor Photography", ["Landscape", "Wildlife", "Macro", "Sunset", "Mountains", "Forest", "Water", "Sky", "Snow"], "Places, light and nature outdoors.", "landscape outdoor nature"),
    T("portrait", "Portrait Photography", ["Portrait", "Headshot", "Family", "Couple", "Children", "Group", "Studio", "Natural Light", "Black and White"], "Kinds of portrait.", "portrait headshot"),
    T("wedding", "Wedding Photography", ["Ceremony", "Reception", "Getting Ready", "Details", "Bride", "Groom", "Family", "First Dance", "Candid"], "Moments and parts of a wedding day.", "wedding"),
    T("event", "Event Photography", ["Stage", "Speaker", "Audience", "Venue", "Candid", "Group", "Details", "Food", "Signage"], "Parts of a conference or corporate event.", "event conference"),
    T("sports", "Sports Photography", ["Sports", "Action", "Celebration", "Team", "Coach", "Fans", "Warm-up", "Podium", "Venue"], "Sports coverage beats.", "sports action"),
    T("real-estate", "Real Estate Photography", ["Exterior", "Front", "Kitchen", "Living Room", "Bedroom", "Bathroom", "Backyard", "Twilight", "Aerial"], "Rooms and views of a listing.", "real estate interior"),
    T("product", "Product Photography", ["Product", "Hero", "Front", "Back", "Detail", "Lifestyle", "White Background", "Packaging", "Scale"], "Views an online shop asks for.", "product ecommerce"),
    T("food", "Food Photography", ["Food", "Dish", "Overhead", "Drinks", "Dessert", "Ingredients", "Kitchen", "Restaurant", "Table"], "Food and drink coverage.", "food restaurant"),
    T("travel", "Travel Photography", ["Travel", "City", "Street", "Architecture", "Market", "People", "Landmark", "Food", "Transport"], "Travel story beats.", "travel city"),
    T("street", "Street Photography", ["Street", "Documentary", "People", "Night", "Shadows", "Reflections", "Crowd", "Signs", "Black and White"], "Street and documentary subjects.", "street documentary"),
    T("wildlife", "Wildlife Photography", ["Wildlife", "Birds", "Mammals", "In Flight", "Behaviour", "Habitat", "Portrait", "Feeding", "Young"], "Animals and behaviour.", "wildlife birds nature"),
    T("family", "Family Photography", ["Family", "Newborn", "Kids", "Parents", "Siblings", "Home", "Lifestyle", "Milestone", "Pets"], "Family and newborn session subjects.", "family newborn"),
    T("concert", "Concert Photography", ["Concert", "Live Music", "Stage", "Singer", "Guitar", "Drums", "Crowd", "Lights", "Backstage"], "Live music coverage.", "concert music"),
    T("architecture", "Architecture Photography", ["Architecture", "Exterior", "Interior", "Facade", "Detail", "Stairs", "Lines", "Night", "Skyline"], "Buildings and spaces.", "architecture interior"),
    T("astro", "Night Sky Photography", ["Night Sky", "Milky Way", "Stars", "Star Trails", "Aurora", "Moon", "Long Exposure", "Dark Sky", "Nightscape"], "Night and astro subjects.", "astro night"),
]


def R(field: str, op: str, value=None) -> dict:
    return {"field": field, "op": op, "value": value}


SMART = [
    T("colored-red", "Colored Red", {"match": "all", "rules": [R("label", "=", "red")]}, "Photos with the red label.", "label"),
    T("five-stars", "Five Stars", {"match": "all", "rules": [R("rating", "=", 5)]}, "Five-star photos.", "rating best"),
    T("four-plus", "Four Stars and Up", {"match": "all", "rules": [R("rating", ">=", 4)]}, "Four and five stars: portfolio candidates.", "rating portfolio"),
    T("past-month", "Past Month", {"match": "all", "rules": [R("captureTime", "inLast", 30)]}, "Taken in the last 30 days.", "date recent"),
    T("recently-modified", "Recently Modified", {"match": "all", "rules": [R("editTime", "inLast", 2)]}, "Edited in the last two days.", "date edited"),
    T("imported-week", "Imported This Week", {"match": "all", "rules": [R("importTime", "inLast", 7)]}, "Imported in the last 7 days.", "import recent"),
    T("without-keywords", "Without Keywords", {"match": "all", "rules": [R("keyword", "notContains", "")]}, "Photos with no keywords yet.", "keywords todo"),
    T("no-copyright", "Without Copyright", {"match": "all", "rules": [R("copyright", "isEmpty")]}, "Photos missing a copyright notice; apply a metadata template before delivery.", "copyright todo"),
    T("missing-gps", "Without GPS", {"match": "all", "rules": [R("hasGps", "=", False)]}, "Photos with no location.", "gps todo"),
    T("picks-to-edit", "Picks to Edit", {"match": "all", "rules": [R("flag", "=", "pick"), R("edited", "=", False)]}, "Picked but not developed yet.", "cull edit todo"),
    T("ready", "Ready to Deliver", {"match": "all", "rules": [R("flag", "=", "pick"), R("edited", "=", True)]}, "Picked and developed.", "deliver"),
    T("unrated-picks", "Unrated Picks", {"match": "all", "rules": [R("flag", "=", "pick"), R("rating", "=", 0)]}, "Picks that still need stars.", "cull rating"),
    T("rejects", "Rejects", {"match": "all", "rules": [R("flag", "=", "reject")]}, "Rejected photos, to review before removing.", "cull reject"),
    T("soft", "Possibly Soft", {"match": "all", "rules": [R("sharpness", "<", 35)]}, "Sharpness score under 35 after analyze culling.", "cull sharpness"),
    T("best-of-group", "Best of Each Group", {"match": "all", "rules": [R("bestOfGroup", "=", True)]}, "The sharpest frame of each group of near-duplicates, after analyze culling.", "cull duplicates"),
    T("high-iso", "High ISO (3200+)", {"match": "all", "rules": [R("iso", ">=", 3200)]}, "ISO 3200 and up: candidates for noise reduction by ISO or Denoise.", "iso noise"),
    T("long-exposure", "Long Exposures (1 s+)", {"match": "all", "rules": [R("shutter", ">=", 1)]}, "Shutter of a second or longer.", "night tripod"),
    T("telephoto", "Telephoto (200 mm+)", {"match": "all", "rules": [R("focal", ">=", 200)]}, "Focal length 200 mm and longer.", "lens wildlife sports"),
    T("wide", "Wide Angle (24 mm and wider)", {"match": "all", "rules": [R("focal", "<=", 24)]}, "Focal length 24 mm or wider.", "lens landscape interior"),
    T("raw-unedited", "Raw, Not Edited", {"match": "all", "rules": [R("kind", "=", "raw"), R("edited", "=", False)]}, "Raw files with no develop settings yet.", "raw todo"),
    T("videos", "Video Files", {"match": "all", "rules": [R("kind", "=", "video")]}, "Every video clip.", "video"),
    T("virtual-copies", "Virtual Copies", {"match": "all", "rules": [R("virtualCopy", "=", True)]}, "Versions made as virtual copies.", "versions"),
    T("missing-files", "Missing Files", {"match": "all", "rules": [R("missing", "=", True)]}, "Photos whose original cannot be found.", "maintenance"),
]

STAGES = [
    ("Picks", [R("flag", "=", "pick")]),
    ("To Edit", [R("flag", "=", "pick"), R("edited", "=", False)]),
    ("Edited", [R("flag", "=", "pick"), R("edited", "=", True)]),
    ("Portfolio (4 stars and up)", [R("rating", ">=", 4)]),
    ("Rejects", [R("flag", "=", "reject")]),
]


def S(id: str, name: str, description: str, *, folder: str, rename: str, metadata: str, keywords: str, exports: list[str], workflow: str,
      develop: str = "", iso: bool = False, previews: str = "standard", smart: bool = False, tags: str = "") -> dict:
    return T(id, name, {"folder": folder, "rename": rename, "metadata": metadata, "keywords": keywords, "exports": exports, "workflow": workflow,
                        "develop": develop, "isoNoise": iso, "previews": previews, "smartPreviews": smart}, description, tags)


SHOOTS = [
    S("wedding", "Wedding", "Time-sorted names across bodies, personal-use licence, the wedding keyword set, noise by ISO for the reception, and gallery plus print exports.",
      folder="year-day-shoot", rename="multicam", metadata="wedding-client", keywords="wedding", exports=["builtin.client-gallery", "builtin.print-lab", "builtin.proof"],
      workflow="wedding_event_workflow", iso=True, smart=True, tags="wedding event"),
    S("portrait", "Portrait Session", "Client naming, all-rights copyright, the portrait keyword set and proof plus print exports.",
      folder="year-day-shoot", rename="client-date-seq", metadata="all-rights", keywords="portrait", exports=["builtin.proof", "builtin.client-gallery", "builtin.print-lab"],
      workflow="portrait_session_workflow", tags="portrait headshot family"),
    S("headshots", "Corporate Headshots", "Client naming, commercial licence and web plus full-size exports for a company's people pages.",
      folder="clients", rename="client-date-seq", metadata="commercial", keywords="portrait", exports=["builtin.client-gallery", "builtin.full"],
      workflow="portrait_session_workflow", tags="headshot corporate"),
    S("event", "Event and Conference", "Time-sorted multi-camera names, event metadata, the event keyword set and fast web delivery.",
      folder="year-day-shoot", rename="multicam", metadata="event", keywords="event", exports=["builtin.web", "builtin.client-gallery"],
      workflow="wedding_event_workflow", iso=True, tags="event conference corporate"),
    S("news-sports", "News and Sports", "Wire naming, editorial IPTC, embedded previews for speed and full-size filing with all metadata. Only standard toning and cropping are allowed.",
      folder="day", rename="wire", metadata="editorial", keywords="sports", exports=["builtin.news"], workflow="news_sports_workflow", iso=True, previews="", tags="news sports editorial"),
    S("landscape", "Landscape and Travel", "Date and shoot folders, all-rights copyright, the landscape keyword set, portfolio and print exports.",
      folder="year-day-shoot", rename="date-seq", metadata="all-rights", keywords="landscape", exports=["builtin.web", "builtin.4k", "builtin.print-lab"],
      workflow="landscape_workflow", smart=True, tags="landscape travel outdoor"),
    S("real-estate", "Real Estate Listing", "Listing-order names, a listing licence, the real estate keyword set and MLS plus web exports.",
      folder="clients", rename="listing-seq", metadata="real-estate", keywords="real-estate", exports=["builtin.mls", "builtin.web"],
      workflow="real_estate_workflow", tags="real estate interior architecture"),
    S("product", "Product and E-commerce", "SKU naming, commercial licence, the product keyword set and shop plus full-size exports.",
      folder="clients", rename="product-sku", metadata="commercial", keywords="product", exports=["builtin.web", "builtin.full"],
      workflow="product_workflow", tags="product ecommerce"),
    S("concert", "Concert and Low Light", "Time-sorted names, event metadata, the concert keyword set, noise by ISO and web delivery.",
      folder="year-day-shoot", rename="multicam", metadata="event", keywords="concert", exports=["builtin.web", "builtin.client-gallery"],
      workflow="concert_workflow", iso=True, tags="concert music night"),
    S("stock", "Stock Submission", "Date naming, stock metadata and a full-size sRGB JPEG export that meets the agencies' 4 MP minimum.",
      folder="year-day-shoot", rename="date-seq", metadata="stock", keywords="travel", exports=["builtin.stock"], workflow="stock_workflow", tags="stock agency"),
    S("family", "Family and Newborn", "Client naming, personal-use licence, the family keyword set and gallery plus print exports.",
      folder="year-day-shoot", rename="client-date-seq", metadata="wedding-client", keywords="family", exports=["builtin.client-gallery", "builtin.print-lab"],
      workflow="portrait_session_workflow", tags="family newborn"),
    S("astro", "Night Sky", "Date and shoot folders, the night sky keyword set, noise by ISO and 4K plus print exports.",
      folder="year-day-shoot", rename="datetime-num", metadata="all-rights", keywords="astro", exports=["builtin.4k", "builtin.print-lab"],
      workflow="astro_workflow", iso=True, tags="astro night"),
]
