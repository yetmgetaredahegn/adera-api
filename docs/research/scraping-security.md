Your notes are a good start, but a few points need clarification to make them more accurate and legally cautious.

## Corrected Version

### When scraping public tender websites is generally acceptable

Scraping information that is **publicly available without requiring an account, password, or other access controls** is often legally permissible in many jurisdictions. However, the legal rules vary by country and by the website's terms, so being public does **not automatically** mean scraping is always allowed.

---

## Situations that can create legal or contractual problems

### 1. Ignoring the website's Terms of Service

If a website's Terms of Service prohibit automated scraping or require permission, scraping may violate the agreement you accepted (or otherwise create legal issues depending on the jurisdiction).

---

### 2. Accessing restricted areas

Do **not** attempt to bypass authentication or technical protections, including:

* Logging in without authorization
* Circumventing CAPTCHAs
* Bypassing rate limits
* Exploiting security vulnerabilities
* Accessing private endpoints

These actions can cross into unauthorized access.

---

### 3. Excessive request rates

Sending too many requests can overload a server.

Examples:

* Hundreds or thousands of requests per second
* Many concurrent connections
* Ignoring server errors or retry limits

Consequences may include:

* IP blocking
* Temporary bans
* Service disruption
* In serious cases, legal action if the traffic intentionally harms the service

---

### 4. Collecting personal information

Avoid collecting unnecessary personal information such as:

* Personal phone numbers
* Private email addresses
* National IDs
* Home addresses

For a tender website, you usually only need business information such as:

* Tender title
* Organization
* Tender number
* Deadline
* Category
* Tender documents

---

### 5. Official API available

If the organization provides an official API, it is usually preferable to use it because it is more stable and often intended for automated access. Some websites may also restrict scraping in favor of their API.

---

### 6. Copyright

Even if you can scrape information, the content itself (especially documents, images, or reports) may still be protected by copyright. Republishing or redistributing content may require permission depending on the applicable law and license.

---

## Best Practices

### Check `robots.txt`

Example:

```
https://example.com/robots.txt
```

`robots.txt` tells automated agents which paths the site owner prefers bots not to crawl.

Important:

* It is **not a law**.
* It is **not always legally binding**.
* It is a good practice to respect it unless you have another authorization to access the data.

---

### Read the Terms of Service

Search for keywords such as:

* scraping
* crawler
* robot
* automated access
* bot
* API

Understand whether automated collection is permitted.

---

### Use an API when available

An API is usually:

* More reliable
* Faster
* Easier to maintain
* Less likely to break when the website changes

---

### Be polite

Instead of:

```
100 requests/second
```

Use something like:

```
1 request every few seconds
```

Also:

* Retry politely
* Stop on repeated errors
* Respect rate limits if published

---

### Collect only what you need

For a tender portal, store only relevant business information.

Good examples:

* Tender title
* Organization
* Deadline
* Category
* Tender document link
* Procurement method

Avoid collecting unrelated personal information.

---

### Build resilient scrapers

Websites change frequently.

Instead of hard-coding everything:

* Handle missing elements gracefully.
* Detect layout changes.
* Log failures.
* Update selectors when necessary.

---

## For your Ethiopian tender project

For a site that aggregates Ethiopian public tenders, a responsible workflow would be:

1. Identify official public tender sources.
2. Check whether they provide an API.
3. Review the Terms of Service and `robots.txt`.
4. Collect only publicly available tender information.
5. Rate-limit your requests.
6. Store the data in your database.
7. Link users back to the original tender notice whenever possible.
8. Regularly synchronize updates rather than repeatedly downloading the same pages.

Following these practices helps you build a reliable tender aggregation service while reducing technical and legal risks.
