# SKILLS.md — recipes for {{PROJECT_NAME}}'s recurring tasks

Follow a recipe **exactly** when one fits. Every recipe ends with *Verify* (real
commands) and *DoD*. No recipe for your task? Larger models: do the work, then add
the recipe here. Smaller models: write a plan and stop for review.

Start with 2–3 recipes for your most common tasks; add one every time a task type
recurs a third time. A recipe that skips Verify teaches the model that done=written;
done=proven.

---

## R1 — {{Most common task, e.g. "Add a <domain object>"}}

**When:** {{trigger}} ({{requirement ids}}).

1. {{Step with exact path/file}}:

   ```{{lang}}
   {{minimal skeleton the model copies — skeletons beat prose for small models}}
   ```
2. {{Step — include the project's known trap here if one applies, e.g. "register X
   in Y or Z silently no-ops"}}
3. {{Run it for real}}: `{{command}}` — {{what correct output looks like}}.

**Verify:** `{{static gate command}}` green; `{{behavior proof command}}` → {{expected}}.
**DoD:** {{bullet list — including "nothing outside files A/B/C was touched"}}.

---

## R2 — {{Second recipe, e.g. "Change the schema"}}

**When:** {{trigger}}.

1. …
2. **Human-review-mandatory if** {{condition, e.g. it alters existing tables}}:
   stop after generating, show the diff, wait.

**Verify:** … **DoD:** …

---

## R3 — Run & inspect {{the app/pipeline}} (ops/debugging)

```bash
{{the 4–6 commands that bring it up, exercise it, and read ground truth}}
```

Debug order when something is wrong: {{observability surface}} → {{verbose mode}} →
{{ground-truth check, e.g. psql \d}} → {{the fixture test}}.
