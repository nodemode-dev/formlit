# Credits for the develop demo media

The nine photographs in `assets/media/develop.js` come from Pexels and are used under the Pexels License (https://www.pexels.com/license/). They are the same files, with the same EXIF, as nine of the photographs in `demo/assets/media/` (see `demo/CREDITS.md`, where each source page was opened and read before download: each stated "Free" and linked to that licence). No page marked a photo as AI-generated, and none shows a recognisable person, brand or logo as its subject.

## What was changed

Nothing beyond what `demo/CREDITS.md` records (long edge at most 1600 px, orientation applied, progressive JPEG at quality 82 in sRGB, camera model, focal length, aperture, ISO, shutter speed and capture date written back as EXIF from the values the Pexels photo page published, the photographer as Artist and XPAuthor). The nine files were repacked unchanged into one JavaScript data pack (`develop.js`) so the page can decode them from `file://`.

Ratings, flags, colour labels, keywords, the three shoot names, and every develop setting, mask and preset already applied were written for this demo and are not from the photographers or from Pexels.

## Photos

| File in the demo | Title | Photographer | Source page | Licence as stated on the page |
| --- | --- | --- | --- | --- |
| lakes-01-walensee.jpg | Sailing on Walensee Lake with Alpine Background | Paolo Bici | https://www.pexels.com/photo/sailing-on-walensee-lake-with-alpine-background-40090812/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-05-lunersee.jpg | Amazing Lunersee in Alps | David Waschbüsch | https://www.pexels.com/photo/amazing-lunersee-in-alps-13308077/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-02-kolsai.jpg | Scenic View of Kolsai Lake in Almaty, Kazakhstan | Necip Duman | https://www.pexels.com/photo/scenic-view-of-kolsai-lake-in-almaty-kazakhstan-39859805/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-01-foggy-beach.jpg | Mountains Near Body of Water | Tiana | https://www.pexels.com/photo/mountains-near-body-of-water-529411/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-03-blue-rocks.jpg | Scenic Rocky Coastline with Blue Ocean under Clear Sky | Glen Zi | https://www.pexels.com/photo/scenic-rocky-coastline-with-blue-ocean-under-clear-sky-40629359/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-06-sea-cliff.jpg | Cliff, Sea and Clear Sky Landscape | Denis Larose | https://www.pexels.com/photo/cliff-sea-and-clear-sky-landscape-4616317/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-03-red-maple.jpg | A View of the Forest During Autumn | Jason Thompson | https://www.pexels.com/photo/a-view-of-the-forest-during-autumn-11420370/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-02-birch-light.jpg | Trees in Autumn Forest | David Bartus | https://www.pexels.com/photo/trees-in-autumn-forest-1545345/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-01-mist-branch.jpg | Misty Autumn Forest with Colorful Foliage | Adrian Limani | https://www.pexels.com/photo/misty-autumn-forest-with-colorful-foliage-34693090/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |

## Selection bitmaps

`assets/media/masks.js` holds six 800 px grey-scale PNG bitmaps (five sky selections and one subject selection) that Select Sky and Select Subject use on the photos above. They were made for this demo from those photographs with OpenCV (GrabCut seeded from colour and position, then a guided filter), and carry the licence of the photographs they derive from (Pexels License). They contain no other third-party material.

| Bitmap key | Derived from | Selects |
| --- | --- | --- |
| lakes-01-walensee_sky | lakes-01-walensee.jpg | sky |
| lakes-05-lunersee_sky | lakes-05-lunersee.jpg | sky |
| coast-01-foggy-beach_sky | coast-01-foggy-beach.jpg | sky |
| coast-03-blue-rocks_sky | coast-03-blue-rocks.jpg | sky |
| coast-06-sea-cliff_sky | coast-06-sea-cliff.jpg | sky |
| autumn-03-red-maple_subject | autumn-03-red-maple.jpg | the red maple |

## Other assets

The interface, icons, fonts (Inter and JetBrains Mono, listed in `NOTICE.md`) and the favicon are the app's own and are bundled by the build. The demo uses no other third-party files.
