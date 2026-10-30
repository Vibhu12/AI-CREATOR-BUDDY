# CreatorOS — Evidence and Contribution Map

## Evidence labels

- **Implemented:** inspectable code; does not imply successful production use.
- **Historical report:** saved results or developer notes from an earlier run.
- **Verified this revision:** a check actually performed, with its scope stated.
- **Proposed:** design, target or experiment that has not been demonstrated.
- **Owner-reported:** personal contribution stated by the owner, not independently attributable from generated commits.

## Claims and supporting material

| Claim | Evidence | Status / permissible interpretation |
| --- | --- | --- |
| CreatorOS combines portfolio, finance, goals and AI guidance | [Application source](../../frontend/app), [backend](../../backend) | Implemented; not a claim of market demand |
| Tier limits and burst controls exist | [quotas.py](../../backend/quotas.py), [tests](../../backend/tests/test_v13_security_fixes.py) | Implemented; limiter is process-local |
| Analytics has an event allowlist and ingestion endpoint | [analytics.py](../../backend/analytics.py) | Implemented; accepting an event name does not prove that every client flow emits it |
| Pricing/payment flows are represented | [billing.py](../../backend/billing.py), [provider status](STATUS.md) | Mix of implementation, mock fallback and test-mode paths; no paying-customer claim |
| Functional tests exist | [test source](../../backend/tests), [saved reports](../../test_reports/pytest) | Headline suite: **142 tests**; old subset counts remain historical, not current totals |
| AI quality is evaluated separately from schema correctness | [eval source and explanation](../../backend/evals) | Implemented starter suite; limited synthetic coverage |
| Simple and complex portfolios behaved differently | [historical eval notes](../../backend/evals/README.md) | Developer-reported small-sample result; raw per-run evidence not committed |
| The product has users, retained customers or revenue | None established | Not claimed; external validation pending |
| Production latency/cost/groundedness targets are achieved | [metrics targets](../metrics.md) | Proposed thresholds, not achieved service levels |

## Contribution boundaries

| Area | Owner contribution reported in existing documents | AI-assisted implementation / review evidence | What remains to establish |
| --- | --- | --- | --- |
| Product framing and MVP | Selected a creator portfolio/business view | [README build disclosure](../../README.md), [decision log](../decisions.md) | Interview findings and demand validation |
| Pricing and quotas | Chose tiers and usage gating | [billing](../../backend/billing.py), [quotas](../../backend/quotas.py) | Willingness to pay and actual unit economics |
| Measurement | Defined an event vocabulary and success framework | [analytics](../../backend/analytics.py), [metrics](../metrics.md) | Emission audit, queries and observed cohorts |
| AI quality | Reported identifying persona mismatch and requesting eval coverage | [strategy](../../backend/strategy.py), [evals](../../backend/evals) | Reproducible runs, human review and broader cases |
| Security review | Reported reviewing demo/payment defaults | [security tests](../../backend/tests/test_v13_security_fixes.py), [decision 8](../decisions.md) | Current deployment configuration and security assessment |
| Code production | Directed iterative builds and reviewed behaviour | Emergent-assisted source and history, disclosed in README | A personal technical walkthrough; no inference that every line was manually authored |

## Resume claim boundaries

Supported themes: independently directed an AI-assisted prototype; defined
product scope and quota/pricing choices; documented measurement targets;
investigated personalisation failures and introduced evaluation coverage.

Use measured numbers only with their denominator, date, environment and source.
Do not turn synthetic eval percentages into customer success rates, targets into
achievements, test collection into passing tests, or an implementation into a
completed live customer deployment. Role suitability remains an interview
assessment, not something repository presence alone certifies.
