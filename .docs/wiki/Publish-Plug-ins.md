# Publish Plug-ins

Publish services keep a destination in step with a published collection: new and edited photos are exported and sent, photos removed from the collection are deleted at the destination. Hard Drive and FTP are part of the engine; every other service is a plug-in. WebDAV and Nextcloud (`webdav`) and S3-compatible storage (`s3`) ship built in, written against the same interface as yours.

## Installing

Put a plug-in in the `Plugins` folder of the data folder (`~/Formlit/Plugins` by default): a single `.py` file, or a folder with an `__init__.py`. Open File > Plug-in Manager and press Reload Plug-ins. The manager lists every plug-in that loaded, with its version, author and whether it takes comments, and every file that failed with the reason. Plug-ins are Python running inside the engine with your permissions, so install only plug-ins you trust.

## The interface (API 1)

A plug-in module defines `SERVICE` and `connect`:

```python
SERVICE = {
    "kind": "my-service",          # unique, not folder or ftp
    "label": "My Service",
    "version": "1.0.0",
    "author": "you",
    "description": "One sentence for the Plug-in Manager.",
    "help": "Shown in the service dialog above the fields.",
    "comments": False,             # True when the client has comments() and comment()
    "api": 1,
    "fields": [                    # the service dialog's fields, saved into the service settings
        {"path": "url", "label": "Address", "kind": "text", "placeholder": "https://..."},
        {"path": "password", "label": "Password", "kind": "password"},
    ],
}


def connect(settings: dict):
    return Client(settings)
```

Field kinds are `text`, `password`, `number`, `check`, `select` and `seg` (with `options` as `[["value", "Label"], ...]`). Fields named `password`, `secret`, `secretKey`, `token` or `apiKey` are kept out of everything the engine sends back, and an empty value on edit keeps the stored one.

The client returned by `connect` is used for one publish run:

| Method | Called with | Returns |
| --- | --- | --- |
| `upload(path, folders, photo, old)` | the exported file, the collection set path as a list of names, `{"id", "fileName", "captureTime", "title", "caption", "keywords"}`, and the remote id from the last publish (or `""`) | the remote id to store (a URL, key or path) |
| `delete(remote)` | a stored remote id | nothing |
| `comments(remote)` (optional) | a stored remote id | a list of `{"author", "text", "time"}` |
| `comment(remote, text)` (optional) | a stored remote id and the text | nothing |
| `close()` (optional) | nothing | nothing |

Raise an exception with a readable message when something fails; the publish task reports it per photo and carries on with the rest.

## Example

`docs/plugins/journal_folder.py` in the repository is a complete plug-in: it copies photos into a folder, keeps an `index.json` of titles and keywords, and stores comments beside it, so the Library's Comments panel can read and post them.
