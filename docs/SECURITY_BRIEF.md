# ADERA — Security & Data Practices

*A one-page summary for institutions and partners evaluating ADERA. Drafted by
the founder; every claim below should be true and checkable — the security
engineer's job includes verifying that (see `docs/SECURITY.md` §8).*

**ADERA** is a tender-intelligence platform that helps Ethiopian businesses find
and act on public procurement opportunities they'd otherwise miss.

## Where our data comes from

We collect only from sources that are either:
- **Public, unauthenticated pages and APIs** — information already open to
  anyone, without a login.
- **Data shared with us directly**, under an agreement.

**We do not log in to any platform in order to collect data, and we do not
scrape services that restrict automated access.** This is a firm rule, not a
convenience — recorded as an architecture decision in our codebase
(`docs/ADRs/027-source-access-legality.md`).

## We do not touch your infrastructure

Every request we make identifies itself (a named, contactable User-Agent
string), runs at a conservative rate, and respects any crawling restrictions a
site publishes. We cache what we fetch rather than re-requesting it. We are not
a load risk to any system we read from.

## We link out, we don't replace you

ADERA sends bidders *to* the official procurement platform to complete their
process. We are a discovery layer, not a competing channel.

## How supplier data is protected

Company profile data is stored with the minimum fields the product needs,
never committed to source code, and can be exported or deleted on request.

## Report a problem

If you believe ADERA is affecting your systems or have a security concern,
contact **[founder to fill in: an email address]**. We commit to acknowledging
reports within [founder to fill in: e.g. 3 business days].

## What we'd welcome from you

Official, sanctioned access to procurement data — an API, a data-sharing
agreement, or a listed integration — would let us serve your transparency goals
better than any public-page reading ever could. We'd welcome that conversation.

---
*This summary is deliberately non-technical. The full technical threat model is
available on request: `docs/SECURITY.md`.*
