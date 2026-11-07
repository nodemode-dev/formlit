# Credits for the share demo media

## Photographs

The nineteen photographs in `assets/media/alps.js`, `world.js` and `more.js` come from Pexels and are used under the Pexels License (https://www.pexels.com/license/). Each source page was opened and read before use: each stated "Free" and linked to that licence. No page marked a photo as AI-generated, and none shows a recognisable person, brand or logo as its subject. Thirteen are the same files as in `demo/assets/media/` (see `demo/CREDITS.md`); six were added for this demo.

### What was changed

Long edge at most 1600 px, orientation applied, progressive JPEG at quality 80 in sRGB. Camera model, focal length, aperture, ISO, shutter speed and capture date are written back as EXIF from the values the Pexels photo page published (a photo whose page published none carries none). The photographer is written as Artist and as XPAuthor, and a copyright line reads "(c) Name, Pexels License". Thirteen photos carry a GPS position that was chosen for this demo from the place the photo title or page names (a lake, a village, a city); it is not the photographer's own location data, and the other six carry none so you can place them on the map. Ratings, flags, titles used as captions, the book, slideshow, print and web arrangements and the saved locations were written for this demo and are not from the photographers or from Pexels.

### Photos

| File in the demo | Title | Photographer | Source page |
| --- | --- | --- | --- |
| alps-01-walensee.jpg | Sailing on Walensee Lake with Alpine Background | Paolo Bici | https://www.pexels.com/photo/40090812/ |
| alps-02-lunersee.jpg | Amazing Lunersee in Alps | David Waschbüsch | https://www.pexels.com/photo/13308077/ |
| alps-03-braies.jpg | Green Trees on Rocky Mountains Near Lake | Sara Rubini | https://www.pexels.com/photo/9389047/ |
| alps-04-hallstatt.jpg | Idyllic Lakeside Village of Hallstatt, Austria | Ahmet Yüksek | https://www.pexels.com/photo/33467274/ |
| alps-05-bled.jpg | Aerial View of Lake Bled with Island Church | Jon Eliya | https://www.pexels.com/photo/32562800/ |
| world-01-reine.jpg | Reine, Lofoten | op23 | https://www.pexels.com/photo/12166189/ |
| world-02-kirkjufell.jpg | Majestic Kirkjufell and Waterfall in Iceland | Lorenzo Castellino | https://www.pexels.com/photo/39103198/ |
| world-03-santorini.jpg | Blue Sky over White Houses in Santorini, Greece | Ayoub SOUSSI | https://www.pexels.com/photo/23928841/ |
| world-04-rila.jpg | Green Island Surrounded by Water | Bob Krustev | https://www.pexels.com/photo/163912/ |
| world-05-kolsai.jpg | Scenic View of Kolsai Lake in Almaty, Kazakhstan | Necip Duman | https://www.pexels.com/photo/39859805/ |
| world-06-milford.jpg | Stunning Waterfalls in Milford Sound, New Zealand | Ling Xu | https://www.pexels.com/photo/33045304/ |
| world-07-austin.jpg | Skyscrapers by River in Austin at Night | Elsie Soto | https://www.pexels.com/photo/20185085/ |
| world-08-mexico-city.jpg | Blurred Motion of Traffic in the City | Famitsay Tamayo | https://www.pexels.com/photo/12317907/ |
| more-01-boats.jpg | Green Lake Surrounded by Green Trees and Snow Covered Mountains | Markus Spiske | https://www.pexels.com/photo/138903/ |
| more-02-tarn.jpg | Stream in a Mountain Valley | Hristofor Stoyanov | https://www.pexels.com/photo/17887057/ |
| more-03-surf.jpg | Aerial View of Pristine Coastline and Ocean Waves | Laszlo Magyar | https://www.pexels.com/photo/37753980/ |
| more-04-misty-cliffs.jpg | Misty Coastal Cliffs at Daybreak | Sandra | https://www.pexels.com/photo/39130477/ |
| more-05-autumn-mist.jpg | Misty Autumn Forest with Colorful Foliage | Adrian Limani | https://www.pexels.com/photo/34693090/ |
| more-06-roundabout.jpg | Vibrant Urban Roundabout at Night with Light Trails | Oleksiy | https://www.pexels.com/photo/31531448/ |

## Music

`assets/media/music.js` holds "Piano Fantasia No. 1" by Peter Bille Larsen, released under CC0 1.0 Universal (public domain dedication) on the Internet Archive: https://archive.org/details/3PeterbillelarsenCreativepatriot (the page states "CC0 1.0 Universal"). The slideshow uses a 64 second excerpt of the recording with a short fade in and a fade out, re-encoded as Ogg Opus at 64 kbit/s. The excerpt is the only change. CC0 needs no credit; it is given here anyway.

## Map

The map tiles are cut in the page from "Blue Marble: Next Generation w/ Topography and Bathymetry" (July), a NASA Earth Observatory image: https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-topography-bathymetry (file `world.topo.bathy.200407.3x5400x2700.jpg` from assets.science.nasa.gov). NASA's media usage guidelines state that NASA imagery is generally not subject to copyright in the United States and may be used for non-commercial, factual purposes with NASA credited as the source (https://www.nasa.gov/nasa-brand-center/images-and-media/); the demo does not use the NASA insignia or logotype and does not imply endorsement. The only change is the reduction from 5400 by 2700 to 3600 by 1800 pixels (`assets/media/map.js`); the page then re-samples it per tile, tints it for the road, topo, light and dark styles, and draws the graticule and labels. The place names in `src/gazetteer.ts` are common geographic names typed for this demo; no map data from OpenStreetMap or another provider is used.

## Other assets

The interface, icons, fonts (Inter and JetBrains Mono, listed in `NOTICE.md`) and the favicon are the app's own and are bundled by the build. The demo uses no other third-party files.
