# Credits for the demo media

The 25 photographs in `assets/media/` come from Pexels and are used under the Pexels License (https://www.pexels.com/license/). Every photo page was opened and read before download, and each one stated "Free" and linked to that licence. No page marked a photo as AI-generated, and none shows a recognisable person, brand or logo as its subject.

## What was changed in every file

The original was downloaded from images.pexels.com at its full size, its orientation applied, scaled down so the long edge is at most 1600 px (never enlarged), and re-encoded as a progressive JPEG at quality 82 in sRGB. The original files carry no camera metadata, so the camera model, focal length, aperture, ISO, shutter speed and capture date that the Pexels photo page published for the photo were written back into the file as EXIF (model, FNumber, ISOSpeedRatings, FocalLength, ExposureTime, DateTimeOriginal) together with the photographer's name as Artist (folded to plain ASCII, as EXIF requires) and as XPAuthor (UTF-16, with the correct spelling). Where a page did not publish a value, the tag is absent.

Pages publish a capture date but no time of day, so DateTimeOriginal carries 00:00:00. Two photos have no published shutter time (autumn-02-birch-light.jpg and city-05-waterfront.jpg). Lens names are not published for any photo, so the demo shows none.

The files are shipped as JavaScript data packs (`assets/media/lakes.js`, `coast.js`, `city.js`, `autumn.js`), which hold the same JPEG bytes as base64 data URIs so the page can decode them from `file://`.

Ratings, flags, colour labels, keywords, collection names and the develop settings already applied to some photos were written for this demo and are not from the photographers or from Pexels.

## Photos

| File in the demo | Title | Photographer | Source page | Licence as stated on the page |
| --- | --- | --- | --- | --- |
| lakes-01-walensee.jpg | Sailing on Walensee Lake with Alpine Background | Paolo Bici | https://www.pexels.com/photo/sailing-on-walensee-lake-with-alpine-background-40090812/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-02-kolsai.jpg | Scenic View of Kolsai Lake in Almaty, Kazakhstan | Necip Duman | https://www.pexels.com/photo/scenic-view-of-kolsai-lake-in-almaty-kazakhstan-39859805/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-03-green-water.jpg | Green Lake Surrounded by Green Trees and Snow Covered Mountains | Markus Spiske | https://www.pexels.com/photo/green-lake-surrounded-by-green-trees-and-snow-covered-mountains-138903/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-04-braies.jpg | Green Trees on Rocky Mountains Near Lake | Sara Rubini | https://www.pexels.com/photo/green-trees-on-rocky-mountains-near-lake-9389047/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-05-lunersee.jpg | Amazing Lunersee in Alps | David Waschbüsch | https://www.pexels.com/photo/amazing-lunersee-in-alps-13308077/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-06-misty-lake.jpg | Green Island Surrounded by Water | Bob Krustev | https://www.pexels.com/photo/green-island-surrounded-by-water-163912/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| lakes-07-cirque.jpg | Stream in a Mountain Valley | Hristofor Stoyanov | https://www.pexels.com/photo/stream-in-a-mountain-valley-17887057/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-01-foggy-beach.jpg | Mountains Near Body of Water | Tiana | https://www.pexels.com/photo/mountains-near-body-of-water-529411/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-02-long-surf.jpg | Aerial View of Pristine Coastline and Ocean Waves | Laszlo Magyar | https://www.pexels.com/photo/aerial-view-of-pristine-coastline-and-ocean-waves-37753980/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-03-blue-rocks.jpg | Scenic Rocky Coastline with Blue Ocean under Clear Sky | Glen Zi | https://www.pexels.com/photo/scenic-rocky-coastline-with-blue-ocean-under-clear-sky-40629359/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-04-cliff-bay.jpg | Cliff and Bay | Cyrill | https://www.pexels.com/photo/cliff-and-bay-15663631/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-05-misty-cliffs.jpg | Misty Coastal Cliffs at Daybreak | Sandra | https://www.pexels.com/photo/misty-coastal-cliffs-at-daybreak-39130477/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| coast-06-sea-cliff.jpg | Cliff, Sea and Clear Sky Landscape | Denis Larose | https://www.pexels.com/photo/cliff-sea-and-clear-sky-landscape-4616317/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-01-roundabout.jpg | Vibrant Urban Roundabout at Night with Light Trails | Oleksiy | https://www.pexels.com/photo/vibrant-urban-roundabout-at-night-with-light-trails-31531448/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-02-hill-town.jpg | A View of a Town at Night | Melike B | https://www.pexels.com/photo/a-view-of-a-town-at-night-8261543/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-03-river-towers.jpg | Skyscrapers by River in Austin at Night | Elsie Soto | https://www.pexels.com/photo/skyscrapers-by-river-in-austin-at-night-20185085/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-04-traffic-streaks.jpg | Blurred Motion of Traffic in the City | Famitsay Tamayo | https://www.pexels.com/photo/blurred-motion-of-traffic-in-the-city-12317907/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-05-waterfront.jpg | City Buildings Near Body of Water | Mack Kamp | https://www.pexels.com/photo/city-buildings-near-body-of-water-1449455/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| city-06-skyline.jpg | Skyline of a Modern City with Illuminated Buildings at Night | Johannes Plenio | https://www.pexels.com/photo/skyline-of-a-modern-city-with-illuminated-buildings-at-night-20208915/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-01-mist-branch.jpg | Misty Autumn Forest with Colorful Foliage | Adrian Limani | https://www.pexels.com/photo/misty-autumn-forest-with-colorful-foliage-34693090/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-02-birch-light.jpg | Trees in Autumn Forest | David Bartus | https://www.pexels.com/photo/trees-in-autumn-forest-1545345/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-03-red-maple.jpg | A View of the Forest During Autumn | Jason Thompson | https://www.pexels.com/photo/a-view-of-the-forest-during-autumn-11420370/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-04-orange-beech.jpg | Vibrant Autumn Forest with Orange Foliage | Mikałaj Prakopčyk | https://www.pexels.com/photo/vibrant-autumn-forest-with-orange-foliage-34574533/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-05-hillside.jpg | Vibrant Autumn Forest Landscape in Daylight | Gabriel Grip | https://www.pexels.com/photo/vibrant-autumn-forest-landscape-in-daylight-34427164/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
| autumn-06-tall-trees.jpg | Vibrant Autumn Forest with Tall Trees | Christina & Peter | https://www.pexels.com/photo/vibrant-autumn-forest-with-tall-trees-34582296/ | Pexels License (page: "Free", linking to https://www.pexels.com/license/) |
