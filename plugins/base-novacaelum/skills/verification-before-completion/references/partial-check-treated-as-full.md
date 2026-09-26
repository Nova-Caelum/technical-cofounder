# Pattern: Partial Check Treated As Full

## Claim
"Linter passed — ready to ship."

## Skipped
The build, compile, integration test, or runtime check that the linter doesn't cover.

## Damage
- Code that lints clean but doesn't compile
- Types that pass but crash at runtime (common in TypeScript)
- Formatting-clean but semantically broken output
- Reviewer/user has to catch what the tooling missed — trust in the "I checked" signal erodes

## Why It Happens
Layered verification tools each cover a slice. The temptation is to run the cheapest one and extrapolate. Extrapolation is not verification — it's assumption.

## Antidote
Name the specific layer your verification covers, and assert nothing beyond it:
- ✅ *"Linter passes"* — accurate
- ❌ *"Linter passes, so build should work"* — extrapolation

If the claim requires the full stack, run the full stack. Every layer skipped is an assumption you're asking someone else to catch.

## Related
Observed failure: a deploy tool's green status check was treated as full deploy verification. That check covers the service binding; the field that actually mattered, the upload path, sat in a different layer and wasn't checked. Cost: a silent upload to the wrong place.
