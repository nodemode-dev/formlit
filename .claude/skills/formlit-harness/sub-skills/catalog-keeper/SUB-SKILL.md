---
name: catalog-keeper
description: "Owns getting photos into formlit's catalog and keeping them findable over MCP: import, folders, sources and filters, collections, keywords, IPTC metadata, people and faces, GPS and saved locations. Load when photos need adding, finding, organizing, tagging, naming or placing on the map."
---

# Catalog Keeper

## Purpose

Make the right photos addressable by id, and keep their organization (collections, keywords, metadata, people, locations) correct. Hands back the ids the next specialist works on, and the organization changes made.

## Preconditions

The formlit MCP tools are connected (`get_catalog` answers). When they are not: inside the formlit repository the project's `.mcp.json` needs approving in the client; anywhere else the person runs `./formlit agents install` in the formlit folder and restarts the client.

## Procedure

1. `get_catalog` for the folder, collection and keyword ids. Never guess an id.
2. New photos: `import_photos` with absolute paths. `mode: "add"` references files where they are; `copy` and `move` need a `destination`. Pass `keywords` to tag the whole import. The result lists the new ids; `find_photos` with `{"kind": "previousImport"}` finds them again later.
3. Finding: `find_photos` with a source and a filter from `references/sources-and-filters.md`. Large sets come back capped by `limit`; the `total` tells you how many matched.
4. Organizing:
   - `create_collection` with ids to keep a set together; `add_to_collection` to grow it.
   - `add_keywords` with `Parent|Child` paths for hierarchy (`Places|Portugal|Lisbon`).
   - `set_metadata` with IPTC fields (title, caption, creator, copyright, city, country and the rest).
   - `stack_photos` for brackets or sequences, best frame first.
5. People: `find_faces` (installs nothing; when the faces model is missing it says so), then `list_people`; `name_person` with the face ids of an unnamed group. Named people become `People|Name` keywords, and the rest of the catalog's faces are suggested against them.
6. Places: `set_location` with decimal degrees; `run_command` with `gps.tracklog`, `path` of a GPX file and `offsetMinutes` (camera clock minus UTC) tags a whole trip; `run_command` with `location.save` keeps a named place with a radius, `private: true` to strip it from exports.
7. Show the person what changed with `show_in_window` (module `library`, the collection as `source`).

## Gate

Done when every id handed on came from `find_photos` or an import result, and each organizing change was read back once (`get_photo` on one photo shows the keyword, metadata or location).

## Hands back

The ids for the next step, and a one-line summary per organizing change.

## Owned resources

- `references/sources-and-filters.md` every source kind, filter key and metadata field the tools accept
