# Security policy

## Supported versions

Security fixes go into the newest release. Please update before reporting, and
check whether the problem is still there.

| Version | Supported |
| --- | --- |
| 0.47.x (latest release) | Yes |
| Anything older | No |

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Use GitHub's private
reporting instead: on the repository's **Security** tab, choose **Report a
vulnerability**. Include what you found, the steps to reproduce it, the version and
platform, and what an attacker could do with it.

You can expect an acknowledgement within a week. We will keep you informed while it
is fixed and credit you in the release notes, unless you would rather not be named.

## What counts

FormLit runs on your own machine, so the things that matter most are the ways
something outside it could get in:

- **The engine** listens on loopback (port 8390). Anything that makes it reachable
  from another machine, or lets a web page on another origin drive it.
- **Agents and the MCP server**: an outside agent acting before the person has
  allowed it in Preferences, AI agents, or while it is blocked.
- **The terminal dock and Chat**: an outside agent or a web page opening, reading or
  typing into them.
- **Publish services**: anything that leaks the FTP, WebDAV, Nextcloud or
  S3-compatible credentials given to them, or sends photos somewhere the person
  did not choose.
- **Files and downloads**: importing photos or catalogs, or reading a client's
  selections file, in a way that writes outside where it should; a model or ffmpeg
  download getting past its SHA-256 check.
- **Private locations**: an export carrying map locations the person marked private.

Bugs that need someone to already control your machine, or to run a modified build
of FormLit, are ordinary bugs: please open an issue for those.
