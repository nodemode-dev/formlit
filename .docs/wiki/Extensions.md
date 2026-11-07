# Extensions

Extensions add features to formlit without changing formlit: a small web page that runs in a sandboxed frame and works on the catalog through formlit's own commands. They follow the Form Extension Contract (API 1), the same in every Form app. They are not the same thing as [Publish Plug-ins](Publish-Plug-ins), which are Python inside the engine.

## Getting extensions

- **FormPortal** installs extensions from the catalogue or from a `.formpkg` file and turns them on for formlit. Extensions, Manage in FormPortal opens it on formlit's page.
- **form.ext** makes extensions; its Run in App loads the folder you are working on into formlit straight away (source Development).

formlit notices a change within two seconds while its window has focus. Extensions, Reload Extensions reads everything again at once.

## In the window

- **Extensions menu** (between Window and Help): each command an extension adds, as `Name: Title`, then Extensions Panel, Reload Extensions and Manage in FormPortal.
- **Extensions panel**: opens in the right column of every module, over that module's panels; the close button or Extensions Panel again brings them back. Each row shows the name, version, where it came from (Catalogue, File or Development), what it may do (permission chips) and its state: Ready, Needs Permission, or Refused with the reason (made for another app, needs a newer formlit, a broken manifest). Open shows the extension's panel; a development extension shows its folder.
- **Extension panels** open under the list, titled with the extension's name, or as a dialog when the extension asks for one.

## Permissions

The first time a version of an extension runs, formlit asks, listing what it wants: read and change the open document (the catalog, the selection), open files you choose, save files where you choose. Allow is remembered for that version; a new version that asks for more asks again. Not Now refuses this time only. Extensions cannot delete files, switch catalogs, use the terminal or reach the internet through formlit, and every change one makes is a single step in Edit, Undo.

## Agents

With the formlit MCP server, `extensions_list` lists the extensions and their commands and `extension_command` runs one in the window, with the same permission prompt. From a terminal: `./formlit cli extensions.list` and `./formlit cli extensions.run id=<id> command=<command>`. The window has to be open.

## Making one

The API page is `docs/EXTENSIONS.md` in the repository: what `document.read` returns, the commands `document.apply` takes, the events formlit sends and how to run a folder in development.
