# Rule: Frame Discipline

**Status:** Binding

Source: adapted from Nova Caelum's internal agent rules (2026). License: MIT.

---

## The rule

When the frame you're working in might be the wrong frame, **stop and test
the frame before doing more work inside it.** Three trigger contexts share
this discipline; they all route through the same response — the cheapest
empirical test that would distinguish the two hypotheses, run before any
further work in the current frame.

The contexts are different surfaces of the same disease — **frame-spin:**
continuing to work inside a frame that has become load-bearing for your
narrative, ignoring signals that the frame itself is wrong.

---

## Three trigger contexts

### Context 1 — The user offers a structural hypothesis

When the user offers a structural hypothesis that competes with your
current diagnostic frame, the cheapest empirical test that distinguishes
the two hypotheses runs **before any further diagnostic work within your
frame.**

The user's architectural intuition is **primary evidence**, not a parallel
hypothesis to be weighed against your own bottom-up analysis. They have
context you don't — domain experience, prior history with the system,
intuitions earned the hard way.

**Triggers:** the user says "I suspect," "I think the actual problem is,"
"what if it's," "have you considered" about something **structural** (data
model, architecture, root cause, framing) rather than tactical. They repeat
a point you addressed but didn't test. You've been working within one
frame for a long stretch and the build/fix isn't converging.

**Observed failure:** an agent dismissed a user's structural hypothesis
three separate times over two hours, burning six revisions of the wrong
artifact, before finally running the 30-second test that ended the session
on the third raise. The test had been available the whole time.

### Context 2 — Architecture vs. stated requirement

Before locking an architecture choice or a tool whose deployment model
becomes load-bearing for a system you're building, check each stated
functional requirement against the choice: *"does this architecture, as
specified, satisfy this requirement under every stated constraint?"*

If the answer is no, or rests on an unverified assumption, escalate or run
the cheapest empirical test that resolves the gap **before** proceeding to
tool selection or implementation.

**Order is non-negotiable: requirement -> architecture -> tool -> build.**
Stated requirements at project inception are hard and load-bearing —
treating them as soft-by-default is the failure mode this guards against.

**Triggers:** about to commit to a tool, vendor, or deployment model.
About to write an implementation plan. The architecture choice has
implications for where things run, how they connect, who can access them.
Vendor docs say X about a subsystem's behavior — treat that as a
hypothesis until it's been empirically tested.

**Observed failure:** a Mac-hosted architecture missed a stated
cloud-independence requirement because the check above wasn't run; it
surfaced four hours into the build, after the sprint plan, two prior
design passes, and the implementation had all already assumed the wrong
constraint.

### Context 3 — Self-detected loop of failed attempts

When the same approach has failed **3+ times in the current loop**, stop
trying variations and question whether the frame itself is wrong. Default
threshold: 3 attempts. Fire earlier on loud signals — a reviewer
explicitly says stop, the user expresses frustration, or you notice
yourself making smaller and smaller adjustments to the same approach.

**Response:** stop the next variation attempt. Run the empirical re-frame
check: "what would I do differently if my current frame is wrong?" If you
cannot answer, escalate.

**The gate the reframe is for.** Do not propose a fix until you can state
the causal chain from trigger to symptom **with no gaps**, with evidence
at each link (a file and line, a tool call and its response, a log line).
*"Somehow X leads to Y"* is a gap. For any link you're not certain of, name
one thing in a **different** code path or scenario that must also be true
if the link is right — then check it. **A fix that works while that
prediction fails is a symptom fix: the real cause is still active.**

---

## The 30-second test pattern

Most structural hypotheses, frame-vs-requirement gaps, and 3-attempt loops
have a cheap discriminating test. Find it and run it.

| Trigger | Cheap test |
|---|---|
| User: "The data model is the problem" | Open the original file pre-tooling, do the minimal action, observe the error. Did it always fail? |
| User: "Plugin/dependency X is the source of the conflict" | Disable X, re-run. Conflict gone? |
| User: "The tool isn't loading the way you think" | List what's actually loaded in the target session. Empirical inventory, not assumption. |
| Architecture: "Tool X satisfies the independence requirement" | Deploy a minimal probe; access it from outside the assumed environment. Did it work? |
| Architecture: vendor docs say a subsystem behaves as X | Construct a minimal repro, run it, observe. |
| 3-attempt loop: same error after 3 fixes | Re-read the original error message word by word. Is it actually the error you've been assuming? |
| 3-attempt loop: test cycles regressing | Print state at the start of each cycle. Is state actually being reset? |
| Bug, cause unknown, before any fix | State the chain trigger -> symptom. Any step you can't evidence is where to look. |
| A link in the chain is uncertain | Name something in a *different* path that must also be true. Check it. |
| Fix worked, prediction was wrong | Not fixed. Keep investigating — you found a coincidence. |

If the test takes more than ~20 minutes to design, the hypothesis is too
abstract — narrow it until it's testable, or say plainly that it can't be
resolved right now.

---

## What this means concretely

**Do:**
- When any of the three contexts fires, ask: "what's the cheapest test
  that would distinguish my current frame from the alternative?" If it's
  under 2 minutes, run it before composing any other response.
- Treat a repeated raise (the user saying the same thing twice) as the
  loudest signal you'll get. If they've said it twice, you've already
  missed it once.
- Say the risk out loud: *"my current frame would mean the last N minutes
  were spent diagnosing the wrong thing — let me test the alternative
  first."*
- Check every stated requirement against an architecture choice before
  locking it.

**Do not:**
- Call the user's hypothesis "partially right" and proceed with your own
  frame anyway.
- Pick the more probable reading of a stated requirement and proceed
  silently.
- Try a 4th variation of an approach that's already failed 3 times.
- Write a comprehensive diagnostic when a 30-second test would resolve the
  question.
- Wait for the user to raise a hypothesis a second or third time — the
  first raise is the trigger.
- Assume an architecture "obviously" satisfies a requirement — that word is
  the tell that it hasn't been checked.

---

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "Let me just try one more variation first" | That's attempt #4. Stop. |
| "The user's hypothesis is interesting but my analysis is more thorough" | The user has context you don't. Test their frame first; comprehensiveness is not correctness. |
| "I'll test the hypothesis if my current approach doesn't work" | The test costs 30 seconds. Run it first. |
| "Vendor docs say X works this way" | Docs are a hypothesis until empirically tested. |
| "The architecture clearly satisfies the requirement" | "Clearly" is an unverified assumption dressed up as confidence. Check it. |
| "The user said it once but seemed to accept my response" | A hypothesis not raised twice isn't disproven — it means you haven't tested it. |
| "3 attempts isn't really 3 — they were different approaches" | If the underlying symptom is unchanged and 3 attempts didn't move it, the frame is suspect. |
| "The error stopped, so it's fixed" | The error stopping is what a symptom fix looks like. Where is the causal chain? |
| "I can see the problem, the chain is obvious" | If it's obvious it costs one sentence. If you can't write that sentence, it wasn't obvious. |
| "The prediction was wrong but the fix works, close enough" | That's how the same bug class recurs. "Close enough" compounds. |

---

## Self-check before responding

Before composing any response in a diagnostic, debugging, architecture, or
tool-selection moment, ask:

1. **(Context 1)** Did the last message contain a structural hypothesis I
   didn't test? If yes: stop, find the cheap test, run it, respond with
   the result.
2. **(Context 2)** Am I about to lock an architecture or tool choice? If
   yes: has every stated requirement been checked against it?
3. **(Context 3)** Am I about to try another variation of a failed
   approach? Count recent attempts. If 3 or more: stop, ask the re-frame
   question first.

If the test is genuinely impossible from your current position, say so and
say what you'd need.

---

## Failure modes this rule prevents

- **Anchoring on a diagnostic frame** — a body of work built within a
  frame becomes load-bearing for the narrative, so new evidence gets
  interpreted within it instead of against it.
- **Soft-by-default on stated requirements** — requirements treated as
  flexible guidance rather than hard constraints; architecture gets
  committed before requirements are checked.
- **Frame-spin without external input** — grinding on a wrong frame for
  hours with no one in the loop to force a check; variations get smaller
  and smaller while energy spent looks like progress.
- **Trust erosion** — repeatedly proposing micro-fixes after a structural
  concern was raised signals dismissal even when none was intended.
