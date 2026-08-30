# CreatorOS — Decision Log

Twelve decisions, four lines each: what I decided, why, what I gave up,
and whether I'd do it again. This exists because "tell me about a hard
product decision" comes up in almost every PM interview, and a decision
log beats a PRD for answering it — a PRD shows what got built, this shows
what got *chosen*, with the trade-off already written down instead of
reconstructed under pressure.

---

### 1. Seeded the demo portfolio on first run instead of an empty state

**Decision:** Copy a demo creator's portfolio into every new account,
labelled and dismissible.

**Why:** A portfolio product with no portfolio cannot demonstrate its
own value. An empty first run is the highest-drop-off moment in a
data-dependent product.

**Trade-off accepted:** Some users find pre-populated data confusing.
Mitigated with a demo badge and one-tap clear.

**Would I do it again:** Yes, but I would have shipped the badge in the
same release rather than after.

---

### 2. Free tier gated on usage, not features — why 10/day

**Decision:** Free tier gets the entire product surface (dashboard,
portfolio, finance, goals), but AI Coach is capped at 10 messages/day and
Strategy Planner at 1 plan/week — nothing is feature-walled.

**Why:** 10/day is roughly two real conversations — enough to feel the
coach actually knows your numbers, not enough to run your whole business
on it for free. Gating the expensive inference calls instead of the core
product means free users still see full value, so the paywall gets hit
by people already convinced, not people who never got to see anything.

**Trade-off accepted:** A curious power user testing edge cases burns
their daily quota on exploration, not real use, and can feel throttled
unfairly. There's no separate "just exploring" allowance yet.

**Would I do it again:** Yes — I'd add a one-time grace nudge (e.g. "5
extra messages, just this once") on a user's *first* quota hit instead of
a hard wall immediately, to soften the first bad moment.

---

### 3. Mock-when-unconfigured integrations

**Decision:** Every third-party integration (YouTube, Instagram, PayPal,
Stripe) returns real API data when credentials are present, and
deterministic mock data derived from the user's handle when not — every
response is explicitly tagged `"mocked": true/false`.

**Why:** A creator tool that only works after configuring five API
accounts fails its own first impression. Mocking-by-default means the
whole product is demoable on day one, and going live later is a config
change, not a rebuild.

**Trade-off accepted:** Deterministic mock data derived from a handle
hash is "too clean" — it doesn't show the noisy, spiky reality of actual
creator revenue, so a reviewer who stays in mock mode too long gets a
slightly rosier picture than production will deliver.

**Would I do it again:** Yes, but I'd inject small realistic noise/variance
into the mock generator so it doesn't look artificially smooth.

---

### 4. In-process rate limiter accepted over Redis, and when it breaks

**Decision:** Burst rate limiting (e.g. 30 chat messages/60s, 5 strategy
plans/hour) is an in-process sliding window — a plain dict of deques —
not Redis.

**Why:** For a single-worker deployment this is zero extra
infrastructure, zero extra latency, and zero extra failure mode. At this
stage, that's the right trade, not an unknown gap.

**Trade-off accepted:** It breaks the moment there's more than one
uvicorn worker — each process keeps its own counters, so a user could get
roughly `limit × worker_count` requests through before any single process
blocks them. This is called out directly in the code comment ("swap for
Redis if you scale horizontally"), not a silent landmine.

**Would I do it again:** Yes for now. I'd swap to Redis the same week a
second worker gets added — not before, since premature infrastructure has
its own cost.

---

### 5. Curated archetype competitors rather than scraping real creators

**Decision:** The Competitor Benchmark radar compares a user against
three curated, explicitly-synthetic "top 1%" and "top 10%" archetype
profiles, not real scraped creator accounts.

**Why:** Scraping and displaying a real creator's performance data next
to a stranger's dashboard is a privacy/ToS problem, and most platform
APIs don't expose competitor data anyway (Instagram's Graph API, for
example, only returns the token owner's own account — never anyone
else's). Archetypes sidestep both problems while still giving a
directionally useful benchmark.

**Trade-off accepted:** The benchmark is illustrative, not literal — it's
not "here's exactly what CreatorBigName123 did this month." A
sophisticated user could notice the numbers don't map to any specific
real account.

**Would I do it again:** Yes. I'd make the archetype framing more visible
in the UI itself — right now it's implicit — so no user mistakes it for
live competitive intelligence.

---

### 6. Event allowlist over free-form names

**Decision:** Analytics events are validated against a fixed ~30-name
allowlist grouped by lifecycle stage (auth, onboarding, AI, payments,
monetization...), rather than accepting arbitrary event strings from the
client.

**Why:** Free-form event names are how analytics tables die — typos,
one-off debug events, and near-duplicate variants of the same event all
live forever as separate rows, and six months in nobody can write a clean
funnel query. A closed vocabulary, decided once, keeps every future query
answerable.

**Trade-off accepted:** Adding a genuinely new event type requires a
backend code change (adding it to `ALLOWED_EVENTS`), not just a
client-side tweak — slower to iterate on new instrumentation ideas.

**Would I do it again:** Yes, without hesitation — that friction is
cheaper than a cardinality-exploded events table.

---

### 7. Server-authoritative pricing

**Decision:** The client only ever sends a tier *name* ("pro", "studio")
when starting checkout. The actual price, feature list, and quota limits
are looked up server-side from a single `TIERS` dict — never trusted from
the client payload.

**Why:** If the client could send its own price, "checkout the $99 tier
for $0.01" is one intercepted request away. Treating price as server
state instead of client input closes that entire bug class by
construction, not by validation.

**Trade-off accepted:** None real — this is close to free correctness,
just discipline about where the source of truth lives.

**Would I do it again:** Yes, and I'd apply the rule earlier next time:
never trust the client for anything that costs money, as a day-one rule,
not something to remember to check.

---

### 8. DEMO_MODE default flipped after the security review

**Decision:** `DEMO_MODE` — the flag allowing mock checkout confirmations
to actually flip a user's paid tier — originally defaulted to `true` when
unset. After a review, I flipped the default to `false`, so an
unconfigured deployment is locked down by default instead of open by
default.

**Why:** A fresh deploy that forgets to set an env var should fail safe,
not fail open. The original code even logged a startup warning when
DEMO_MODE was on — meaning the risk had already been correctly identified
— and shipped the unsafe default anyway. A warning that fires *after*
the unsafe thing is already true isn't a guard.

**Trade-off accepted:** Local/demo environments now need one explicit
line (`DEMO_MODE=true`) instead of working with zero config — a small
one-time cost.

**Would I do it again:** Yes, immediately — and I'd generalize the
lesson: any flag whose unsafe value is "on" defaults to "off," full stop,
no exception for developer convenience.

---

### 9. The strategy personalisation bug — what happened, how I found it, what I built

**Decision:** Found that the Strategy Planner's AI system prompt
hardcoded a fixed demo persona ("Maya," 184k YouTube subscribers, $56k
MTD revenue) for *every* user, regardless of who was signed in or what
their real portfolio contained. Rewrote it to build a per-user context
block from the user's actual assets — mirroring the pattern the AI Coach
already used correctly — and built a small eval suite (`backend/evals/`)
specifically to catch this class of bug going forward.

**Why:** It passed every functional test because the tests only checked
that valid, schema-conformant JSON came back — never whether the JSON
was *about the right business*. Fluent and structured isn't the same as
true. Fixing the bug without adding an eval would leave the same blind
spot for the next regression.

**Trade-off accepted:** The eval suite makes real, non-free LLM calls and
isn't fully deterministic, so it's intentionally excluded from the main
pytest gate and run on demand — meaning it can't yet catch a regression
automatically on every commit.

**Would I do it again:** Yes — and next time I'd write the groundedness
eval *before* shipping any AI feature that's supposed to be personalized,
not after finding the bug by inspection.

---

### 10. Streaming the coach instead of waiting for full completion

**Decision:** AI Coach responses stream token-by-token over SSE rather
than waiting for the full Claude response and returning it in one shot.

**Why:** For a multi-second LLM call, streaming is the difference between
"the app feels broken" and "the app feels alive" — the user sees progress
immediately instead of staring at a spinner, and it's the UX pattern
users now expect from any AI chat surface.

**Trade-off accepted:** Streaming makes auth and error-handling
meaningfully more fiddly than a normal request/response call — this
actually caused a real 401 bug earlier in the build, where the raw SSE
`fetch` call bypassed the app's standard authenticated-fetch wrapper and
forgot to attach the bearer token.

**Would I do it again:** Yes, the UX win is worth it — but I'd centralize
authenticated-SSE fetching into one reusable helper from the start
instead of writing a one-off raw `fetch` for it.

---

### 11. Expo over native, one codebase for three platforms

**Decision:** Built on Expo/React Native with a single codebase
targeting iOS, Android, and web, rather than separate native apps.

**Why:** As a solo builder validating a product idea, shipping the same
feature three times isn't a good use of the scarce resource — my time.
One codebase means every fix and every new screen lands on all three
platforms at once.

**Trade-off accepted:** A few platform-specific rough edges (deep-link
handling for the OAuth redirect behaves differently between native
builds and web) need explicit platform-specific handling rather than
"just working" identically everywhere.

**Would I do it again:** Yes without hesitation at this stage — I'd only
reconsider native if a specific feature genuinely needed something Expo
can't do (e.g. deep OS-level background processing).

---

### 12. Studio tier shipped with three features marked "coming"

**Decision:** The $99/mo Studio tier's feature list includes "Multi-brand
workspaces (coming)," "White-label PDF reports (coming)," and "1:1 human
review of Q&A plans (coming)" — three of its headline features are
explicitly not built yet.

**Why:** This was a demand test, not aspirational filler: I wanted to see
whether anyone would commit money to a tier priced around *specific,
named* future capabilities before spending time building any of them. If
nobody upgrades to Studio, that's a cheap, honest signal not to build
those three features next.

**Trade-off accepted:** Selling something explicitly labeled "(coming)"
only stays honest — not deceptive — because of that visible label, and it
means Studio's actually-delivered value today is thinner than Pro's,
priced higher. That's a real tension I'm accepting deliberately, not
accidentally.

**Would I do it again:** Yes, but I'd attach a real target date or a
"notify me" mechanism to each "(coming)" feature rather than leaving it
open-ended, and I'd want at least a few real Studio signups — not zero —
before treating the demand signal as validated either way.
