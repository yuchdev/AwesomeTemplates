# 0002 - Configuration values are owned by the component that uses them

> **Status:** Accepted
>
> **Date:** 2026-07-08
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context

Several components each declared their own identity and behavior as
class-level attributes (name, category, and similar). One piece of
per-component policy was left behind in an external, ops-curated config
file instead: each component's relative priority/weight, used when
combining their outputs.

That external file hardcoded the full component roster and had to be kept
in sync by hand. Adding a new component meant remembering to also edit the
config file; forgetting to do so left the new component silently
under-weighted rather than failing visibly.

## Decision

**Weight becomes an intrinsic, self-declared property of each component
class**, and the external config-file concept for it is eliminated.

1. Add a `default_weight` class attribute that every concrete component
   must declare - the same way it already declares its name/category.
2. Weight resolution collapses to two tiers: (1) an explicit per-run
   override when one is passed in, else (2) the component's own
   `default_weight`. There is no longer a third tier that reads an
   external file.
3. A component that omits `default_weight` now fails loudly (an
   `AttributeError`) at resolution time, rather than silently defaulting to
   some fallback value.

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| Keep the external file, document it better | No code churn | Leaves weight as external, hand-synced policy; the roster can still drift from the config | Rejected - doesn't fix the root cause |
| Make `default_weight` optional with a fallback default | Tolerates a component that forgets to declare a weight | Reintroduces silent misconfiguration - a forgotten weight gets a plausible-but-wrong value instead of failing | Rejected - a missing weight should fail like a missing name, not be papered over |
| Self-declared scalar weight, no external file (chosen) | Fully self-declared; no external file; loud on misconfiguration | Loses any per-scenario weight differentiation the old file allowed (see Negative) | **Accepted** |

## Consequences

### Positive

- Weight is now co-located with the component it describes; adding a
  component means declaring one more attribute, with nothing to edit in an
  external file.
- The component registry is the single source of truth; weight can no
  longer drift from it.
- A component that omits `default_weight` fails loudly instead of being
  silently mis-weighted.

### Negative

- Any previous per-scenario weight differentiation is lost - every
  scenario now uses the same flat weight per component. If that turns out
  to matter, it needs a deliberate follow-up design, not a quiet
  reintroduction of the external file.
- An operator can no longer retune weights without a code change and
  redeploy; explicit per-run overrides remain available for one-off cases.

## Validation / Rollout

- Unit tests: the two-tier precedence (explicit override beats
  `default_weight`; `default_weight` used otherwise); each component's
  declared weight is present.
- Integration test: default (no-override) behavior is unchanged from
  before the migration.
- Full test suite + lint after implementation.

## Links

- **Roadmap task:** _(link to the task that introduced this, once you have one)_
- **Supporting specs:** _(none)_
- **Diagrams:** _(none)_
