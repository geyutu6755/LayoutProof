# Security Policy

## Scope

LayoutProof is a local command-line tool that reads `.pptx` files and reports layout, readability and integrity problems. This document describes the security model it is designed around, and how to report a vulnerability.

## Security model

### Fully offline

- LayoutProof makes **no network requests**. It does not phone home, upload decks, download rule packs, or call out to any analytics service.
- There is no telemetry, no update check, and no remote configuration. Everything runs in-process on your machine.

### Safe handling of untrusted `.pptx` archives

A `.pptx` is a zip of XML and binary parts. Untrusted decks are treated as hostile input:

- **Never extracted to disk.** Archives are read in memory through Python's `zipfile`; entries are opened by name and consumed as bytes, so there is no on-disk extraction step for an attacker to influence.
- **Zip-slip and path traversal rejected.** Entry names must be relative POSIX paths. Absolute paths, drive letters, backslashes, and any `..` segment are flagged as anomalies and skipped.
- **Duplicate entries rejected** as package anomalies.
- **Resource bombs capped.** Default hard limits: source file ≤ 100 MB (configurable via `max_file_size_mb`), ≤ 5000 zip entries, ≤ 2 GB total uncompressed size.
- **Required parts validated.** A package missing `[Content_Types].xml` or a `ppt/presentation*.xml` main part is reported as a `structure_anomaly`, not trusted blindly.

### Safe XML parsing

- XML parts are parsed with `lxml` using `resolve_entities=False`, `no_network=True`, `huge_tree=False`, and DTD loading/validation disabled.
- This blocks external entity expansion (XXE), billion-laughs/entity-expansion bombs, and any attempt by a malicious deck to reach the network while being parsed.

### Source files are read-only

- `layoutproof scan` **never modifies, moves or deletes** the `.pptx` you point it at. It opens the archive read-only and closes it.
- The `fix` subcommand (alpha) writes only to an explicitly requested `--output` path (default `<name>.fixed.pptx`) and, unless `--no-backup` is passed, keeps a backup; it never overwrites the source in place.
- The `--output/-o` flag for `scan` writes a *report* (text or JSON) to a path you choose; it does not rewrite the deck.

### No traversal beyond the target

- When given a directory, LayoutProof lists `*.pptx` (or `**/*.pptx` with `-r`) directly under that directory. It does not follow symlinks, does not walk hidden or system directories implicitly, and does not read any file outside the target you supplied.
- It operates only on files whose suffix is `.pptx`.

### What is out of scope

- LayoutProof does not open slides in PowerPoint/LibreOffice and does not render macros, ActiveX, embedded OLE objects or media players. It inspects OOXML structure only.
- It is not a malware scanner: a deck may contain malicious embedded media that LayoutProof simply cannot execute. Treat untrusted attachments as untrusted regardless.

## Supported versions

Only the latest released minor version receives security fixes. As of the `0.1.0a1` alpha, security fixes land on `main` and are included in the next release.

## Reporting a vulnerability

Please report security issues privately rather than opening a public GitHub issue:

- Open a confidential report through the repository's **Security → Report a vulnerability** advisory (GitHub Private Vulnerability Reporting).
- Include: the version/commit, your OS and Python version, the smallest `.pptx` or input that reproduces the issue, the exact command run, and what went wrong.

We aim to acknowledge reports promptly and will keep you informed through the fix. Because decks can be sensitive, you may redact or scrub content before sharing; a synthetic reproducer is preferred.

## Hardening expectations for integrators

- Run LayoutProof with the least-privilege account available; it needs only read access to the decks and write access to wherever you point `--output`.
- In CI, do not mount secrets into the job that runs `layoutproof scan` — the tool itself does not need them, and it should never have a reason to read them.
- Keep the default `max_file_size_mb` cap for untrusted input.
