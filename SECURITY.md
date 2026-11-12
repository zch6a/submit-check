# Security

submit-check reads LaTeX and PDFs that may come from anyone (a co-author, a template, a downloaded paper).

## What it does

- **Sends nothing.** No network access at all: the rules ship with the tool.
- **Runs nothing from the paper.** It reads `.tex` files as text (through paper-proof's reader, which only follows
  `\input` / `\include` inside the project folder and rejects absolute, drive and network paths before any file
  access) and reads the PDF with pypdf. It never runs LaTeX or anything in the project.
- **Hostile text stays text.** Titles and messages are shown with control characters made visible; the Markdown
  report renders no links, images, HTML or mentions.
- **The GitHub Action** needs only `contents: read`, runs the tool at the action's own ref, and passes inputs through
  environment variables.

## What it does not protect against

- **Leaks it has no pattern for.** It checks what it knows (names, acknowledgements, links, self-citation, metadata);
  a paper it says nothing about is not proven anonymous.
- **Rules that changed.** The rules are as the official pages said on the date each file records.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Report a vulnerability) rather than a public issue.
