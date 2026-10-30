# CreatorOS — Current Status and Documentation Corrections

Updated 30 October 2026. This page and [EVIDENCE.md](EVIDENCE.md) qualify older
design documents; dated test artifacts retain their original results.

| Area | Current evidence | Still pending |
| --- | --- | --- |
| External users | Owner reports no external users | Discovery interviews and a private beta |
| Product stage | Working prototype described in the repository | Independent end-to-end deployment verification |
| Product name | CreatorOS | Repository slug retained for link compatibility |
| Tests | Headline suite count: **142** | See [verification](evidence/verification.md); no new full passing run claimed |
| AI evaluation | Strategy tests with two synthetic profiles and one judge model | Raw repeated-run outputs, broader dataset, human calibration, AI Coach semantic evals |
| Payments | Stripe checkout simulated; PayPal/Razorpay integration code exists | Credentials, provider-specific validation and deployment verification; no revenue proven |
| Analytics | Allowlist, ingestion and per-user summary implementation | End-to-end emission audit, product KPI queries/dashboard and real cohorts |
| Experiments | Reference designs documented | Assignment framework, rollout, sufficient real users and observed outcomes |

## Metric definitions and numbers

The active proposed north star is **Weekly Active Decisions** from
[metrics.md](../metrics.md): count distinct users per week who complete a plan
task, update/complete a goal or action a recommendation. It is a proposed proxy
for value, not proof of a business outcome. Record each event and deduplicate
users explicitly when implementing the query.

The older **Weekly Actioned Insights** design describes an action count per
user. That is a different metric; it is not interchangeable with a weekly count
of users. Earlier Q3 targets, conversion assumptions, experiment sizes and SLOs
in [the design framework](../04_METRICS_AND_AB.md) are planning examples, not
observed baseline data. The 15–40% quota band and 95% groundedness threshold
are hypotheses/targets, not validated universal benchmarks.

The reported 6/6 and approximately 2/6 synthetic eval outcomes are small-sample,
developer-reported observations. They do not establish population accuracy or
reliability. Using a different judge model does not remove judge bias; human
calibration and repeat runs remain necessary.

## Historical material

- Original JSON/XML reports retain subset counts and timestamps. They are not
  rewritten to the current **142** headline suite count.
- The build log is historical. Current commands and verification live in
  [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
- Combined DOCX/HTML/TXT design exports are legacy snapshots. They are not the
  authoritative source of present implementation status or measured results.
- The README's broad implementation and ownership statements are explained by
  [EVIDENCE.md](EVIDENCE.md); they do not certify independent coding proficiency.
- Live preview availability, configured provider credentials, environment flags
  and deployed version cannot be inferred from repository files.

## Prioritised next work

1. Reproduce semantic evals and preserve redacted per-run outputs; address
   unsupported multi-asset calculations and add AI Coach coverage.
2. Audit emission of events needed for the north-star query; compute a baseline
   only after excluding demo, test and synthetic accounts.
3. Run the [external validation protocol](VALIDATION.md) and document one
   observed issue, one product change and one retest.
4. Verify live provider flows and deployment configuration in an isolated test
   environment before describing any integration as operational.
