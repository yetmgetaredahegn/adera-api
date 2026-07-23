# Security Policy

ADERA takes security reports seriously, including reports about how our
ingestion touches infrastructure we don't own. Please report privately before
disclosing publicly.

## Reporting a vulnerability

Email **[founder to fill in: a security contact address]** with:
- What you found and why it matters
- Steps to reproduce, if applicable
- Any suggested fix

We will acknowledge your report within **[founder to fill in: e.g. 3 business
days]** and aim to resolve confirmed issues promptly. We will credit you (if you
want that) once a fix ships, unless you ask us not to.

## Scope

In scope: this repository (`adera-api`) and the sibling client repositories
(`adera-web`, `adera-mobile`). Also in scope: concerns about how our data
collection affects a third-party system (rate, load, access method) — we take
those exactly as seriously as a bug in our own code.

Out of scope: social engineering, physical access, and denial-of-service testing
against our own infrastructure (ask first — we'll set up a safe window).

## Our commitment

No legal action against good-faith security research conducted under this
policy. We will not disclose your identity without permission.

## Details

The full technical threat model, including honestly-listed open gaps, is
public: [`docs/SECURITY.md`](docs/SECURITY.md).
