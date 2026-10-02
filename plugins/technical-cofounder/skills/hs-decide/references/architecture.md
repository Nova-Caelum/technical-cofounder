# Architecture: Decision.md, `## Architecture`

Decomposes the chosen option into named components a stranger could build and test on their own. The names written here are the keys of `mapping.json`; the descoping step cuts against this list and the draft stage plans tasks from it.

Append `## Architecture` to `Decision.md`:

1. **Name the components.** One `### <component name>` per unit: a name a search finds (`greet command`, not `the script`), stable for the rest of the run. One clear purpose per unit. If you can't say its purpose in one sentence, split it; if two units share a purpose, merge them.
2. **Four lines per component.**
   - **Does:** what it does.
   - **Used by:** its interface: who calls it and how (a command, a function, a file it writes).
   - **Depends on:** the components, files or tools it needs.
   - **Passes:** the `T<n>` ids it exists to pass, or `none`. Write `none` honestly; descoping decides what it means.
3. **`### Data flow`.** From the entry action to the terminal effect, the path the `WHOLE-PATH:` criterion walks, naming each component in order. A component that appears in no step is a finding: say so beside it.
4. **`### Error handling` and `### Testing`.** What fails loudly, what never fails open. For each `T<n>`, which component's test discharges it and where that test lives.
5. **Isolation check.** For every component: can someone understand it without reading its internals? Can the internals change without breaking its callers? If either answer is no, move the boundary before handing back.

Keep it proportional: bounded is about one screen; architectural as long as the components need.

## Self-review

- [ ] Every `###` name is unique and I would recognize it in `mapping.json` a week from now.
- [ ] No `Does` line needs "and" to join two purposes.
- [ ] `### Data flow` walks the `WHOLE-PATH:` criterion, and `### Testing` names the component whose test fails when the path breaks.
- [ ] No `TBD`, no `Used by: various`, no blank `Passes`.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "One component per criterion; the tests give me the decomposition." | Components come from the problem's shape. `Passes` lists the tests each one serves, often several. |
| "I'll leave the components vague; the plan will firm them up." | Build hands each task to a fresh implementer with a brief. A component that can't be briefed from its four lines gets redesigned at build, in the most expensive context. |
| "Every component has its own test, so testing is covered." | Observed failure: a worker's unit tests passed while it sat unwired. The data flow walks the whole path. |

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `brainstorming` (MIT).
