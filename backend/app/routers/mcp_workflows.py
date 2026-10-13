WORKFLOWS: dict[str, dict] = {
    "pro_ingest_and_cull": {
        "title": "Ingest and cull like a working pro",
        "description": "Import with copy, renaming, copyright metadata and a backup copy, then a two-pass flag-and-star cull.",
        "text": """Professional ingest and cull in formlit (after Adobe's import options, Julieanne Kost, Lightroom Killer Tips).

1. import_photos with mode copy (or dng for Copy as DNG), destination one parent folder, folderTemplate "{date:%Y}/{date:%Y-%m-%d}" (date folders), renameTemplate such as "{custom}_{date:%Y%m%d}_{seq:4}" with custom the client or event, metadata {"copyright": "...", "creator": "..."} so every file carries copyright, backup an absolute folder on another drive for a second copy, skipDuplicates true, buildPreviews standard. A develop preset can go on at import with develop. Copy, then delete the card yourself; move is copy then delete.
2. First pass: analyze_culling then apply_culling with pickBest (or set_flag by hand: pick the keepers, reject the clear misses). Leave undecided frames unflagged.
3. refine_photos on the shoot: unflagged become rejects and picks become unflagged, so the second pass works only on survivors.
4. Second pass with stars: set_rating 3 for selects, 4 for strong frames, 5 for favourites; editing effort goes to 4 and 5 (a common wedding scheme, PetaPixel). Colour labels mark "needs attention".
5. create_collection with the selects. Deleting rejects stays with the person in the window.""",
    },
    "wedding_event_workflow": {
        "title": "Wedding and event: thousands of frames, one look",
        "description": "Cull to a target count, apply a signature preset, edit one hero per lighting scene and spread it, then deliver.",
        "text": """Wedding and event workflow in formlit (after Paul Waring and Gerard Needham in Fstoppers, Brenda Bergreen in PetaPixel, Trevor Dayley in SLR Lounge).

1. Ingest and cull with the pro_ingest_and_cull prompt. Set a target first (for example about 1 in 5 to 1 in 10 frames) and reduce by part of the day.
2. Signature look: apply_preset with the person's preset (or a Wedding preset) to every select. Keep variants for indoor and night light (Waring), which usually need only an exposure or white balance tweak.
3. Group by lighting scene (ceremony, portraits, reception). In each group, edit one hero frame with develop_set (report true), then spread it: sync_settings from the hero without crop and masks for the scene, or match_look with the hero as reference when the light shifts frame to frame. Use match_exposures for a run of unevenly exposed frames.
4. High ISO reception frames: find_photos with filter text "iso>=3200", fix noise on one frame per ISO level, then sync_settings with groups ["detail"] only (Dayley).
5. People: add_ai_mask people parts (faceSkin, bodySkin) for skin softening, only on portraits that need it.
6. Check the set with analyze_photo ids; fix outliers with match_look.
7. Deliver: export_photos per deliverable (full resolution; web at a 2048 px long edge; social), then export_web_gallery or publish. A sneak peek of 10 to 20 favourites can go out first.""",
    },
    "portrait_session_workflow": {
        "title": "Portrait and headshot session",
        "description": "Tethered or imported session with one preset, skin work through people-part masks, and consistency across the session.",
        "text": """Portrait and headshot workflow in formlit (after Adobe's tethered capture page, Photography Life, Jason Parnell-Brookes in Fstoppers, Alex Cooke in Fstoppers).

1. Studio: run_command tether.start with a session name; a develop preset applied to each frame keeps the session consistent, so usually only exposure and white balance need touching afterwards.
2. Cull with flags, then stars.
3. Hero frame: develop_set for tone and white balance; skin with add_ai_mask kind people, parts ["faceSkin", "bodySkin"], adjust {"texture": -30, "clarity": -10} (one photographer used texture about -44 and clarity -15 on skin: a strong starting point to dial back); eyes with parts ["iris", "sclera"] and a little exposure; lips with saturation. Heal blemishes (temporary ones only) in the window's spot removal.
4. sync_settings from the hero to the rest of the setup, groups excluding masks, then re-run the people masks on each frame (masks are computed per photo).
5. Pixel-level retouching beyond this goes to an editor with Edit In; virtual_copy first if several versions are needed.""",
    },
    "landscape_workflow": {
        "title": "Landscape: brackets, panoramas, masks and mood",
        "description": "Merge brackets, stitch panoramas, dodge and burn with masks, grade for mood, prepare for print.",
        "text": """Landscape workflow in formlit (after Adobe's HDR merge page, Digital Camera World, Christian Mohrle in PetaPixel and Fstoppers, Michael Breitung in Fstoppers).

1. Brackets (three or more on a tripod): merge_hdr with align true and deghost low only if something moved; the result is a DNG to develop.
2. Panoramas: merge_panorama; try spherical or cylindrical, boundary warp to fill edges, then crop.
3. Base: profile Landscape (profile id fl.landscape), lower highlights, lift shadows; analyze_photo to keep whites and blacks unclipped.
4. Sky and land separately: add_ai_mask kind sky (darker, more saturated) and add_gradient_mask linear for the horizon; landscape parts (water, vegetation, mountains) for targeted work. Each brightening move pairs with a small highlights reduction (Mohrle).
5. Dodge and burn: radial and linear gradient masks with small exposure moves on the point of interest and the edges.
6. Mood: blue luminance down in the mixer, warm highlights in grading (hue near 40, saturation 8 to 15), a small calibration blue hue shift if needed.
7. Print: export_photos with the builtin.print or builtin.tiff preset (300 ppi, Adobe RGB or 16-bit ProPhoto), output sharpening for the paper.""",
    },
    "news_sports_workflow": {
        "title": "News, sports and documentary: fast and honest",
        "description": "Deadline-first selection and captioning with only the edits news ethics allow.",
        "text": """News, sports and documentary workflow in formlit (after Brian Ach in DPReview, Tom Beary's sports pipeline, the AP news values and the NPPA Code of Ethics).

Ethics first. The AP allows only minor adjustments: cropping, dodging and burning, conversion to greyscale and normal toning, limited to what is minimally necessary; no change to content, no blurred or removed backgrounds, no red-eye removal, no substantial changes to density, contrast, colour or saturation. The NPPA code: editing must keep the integrity of content and context and must not mislead. So with news work: no generative remove, no AI masks that change content, no presets with creative grades, no match_look to a stylised reference; use crop, straighten, exposure, white balance and modest contrast only, and say so.

1. Speed: import_photos with keywords and metadata (caption, creator, copyright, city) at ingest; work the top frames first (a wire target cited is the top 10 to 15 within 45 minutes and the set captioned within two hours).
2. Select: set_flag picks quickly; set_metadata with title and caption (who, what, where, when).
3. Edit minimally: develop_set with exposure, whites, blacks, white balance and contrast only, report true; crop with develop_patch; auto_straighten.
4. Deliver: export_photos at the agency's size with metadata included (copyright and contact at least), or publish to an FTP service.""",
    },
    "real_estate_workflow": {
        "title": "Real estate and architecture",
        "description": "Bracket merge, straight verticals, clean windows and consistent rooms.",
        "text": """Real estate and architecture workflow in formlit (after Dave Koch in PetaPixel, Matthew Saville in SLR Lounge, Adobe's Upright page).

1. Brackets (three frames two stops apart, or five or seven at one stop): edit one frame, sync to its brackets, then merge_hdr with align true and auto tone; skip deghosting when nothing moves.
2. Lens profile corrections on, then upright mode vertical (or full) so walls are straight; when syncing, upright modes re-analyse each photo.
3. Tone: highlights down and shadows up strongly (the Interior Bright or Natural HDR presets are starting points); windows: add_gradient_mask or an object mask on the window with highlights and exposure down.
4. White balance: a rough correction early, recheck after tone work; for mixed light, warm or cool locally with masks.
5. Consistency: develop one room, sync_settings to the rest of that room, then match_look against the hero for rooms shot in different light; analyze_photo ids to check the whole listing.""",
    },
    "product_workflow": {
        "title": "Commercial and product",
        "description": "Tethered, colour-accurate, white-background product sets.",
        "text": """Product workflow in formlit (after Jacob Macias in Digital Photography School, Amber Goetz and Alex Cooke in Fstoppers, Adobe's tether page).

1. Tether with a session named after the product; shoot a colour chart in the first frame and again when the body or lens changes, and set white balance from its grey patch (auto_white_balance on the chart frame, then sync white balance).
2. Exposure on the first frame so the rest match; the background should just reach white: analyze_photo clipping shows how much is pure white.
3. White background: add_ai_mask kind background with exposure and whites up (a starting point: exposure +1.0, whites +40), or the Product Clean White preset.
4. sync_settings from the first frame to the set, then analyze_photo ids to confirm every background clips the same.
5. Export per channel (web at the store's size in sRGB; print at 300 ppi).""",
    },
    "client_delivery": {
        "title": "Deliver to a client",
        "description": "Export presets per deliverable, the right colour space, sharpening and metadata.",
        "text": """Client delivery in formlit (after Adobe's export page, Lightroom Queen, Julieanne Kost, Lightroom Killer Tips).

1. Screen and web: sRGB JPEG; formlit's builtin.web is a 2048 px long edge (one educator's web choice; Lightroom Queen's email preset is 800 px at quality 65); output sharpening for screen.
2. Social: crop to the platform's ratio first, then a long edge such as 1080 px for square or landscape and 1350 px for portrait.
3. Print: builtin.print (300 ppi, Adobe RGB) or builtin.tiff (16-bit ProPhoto) for a lab or retoucher; sharpening for matte or glossy paper.
4. Metadata: copyright only or copyright and contact for clients; remove location for private places; a watermark only for previews.
5. Several deliverables at once: export_photos once per preset into one parent folder; publish keeps a gallery or folder in step when edits change.""",
    },
}
