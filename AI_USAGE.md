# AI Usage

## Tools used

- **GitHub Copilot in VS Code (AI):** design discussion, code drafts,
  explanations, and test ideas. I reviewed the code and made design decisions.
- **Python and pytest:** running unit and integration tests and checking CLI
  output.
- **Git:** reviewing changes and checking diffs.

## Prompts to the AI (summarized)

- I first requested a design-only plan focused on architecture.
  I checked tradeoffs, algorithms, pseudocode,  and alternatives libraries before implementation.
- I asked to build the reader and CSV writer first, then proceed one part
  at a time.
- I requested tests preparation and generation with instructions from my side.
- I requested a final audit of cleanup, tests, assignment requirements,
  and missing work.

## AI mistakes and how they were found

1. **Incorrect variable-mask advice.** 
   The AI said that the mapping involving `all_names` was unnecessary and treated its removal as
   correct. I explained that only relevant names should be used and
   explicitly marked the advice as wrong. I rejected the change; the AI
   should not repeat it without first checking the intended behavior.

2. **Quoted punctuation treated as Liberty structure.** The AI ran a focused
   parser probe with a quoted cell
   name containing `")"`. It returned zero parsed cells because the parser
   matched delimiter text without checking the token kind. I asked the AI to
   explain the parser changes and reviewed the cause and fix. The AI changed
   delimiter matching to require `SYMBOL` tokens and added
   `test_quoted_delimiter_names_are_not_treated_as_structure` in
   `tests/test_liberty_tokenizer.py`. The probe was run by the AI; I reviewed
   the example and requested an explanation rather than running that probe
   myself.

3. **Test coverage was described too broadly.**
   During the assignment review, I checked the actual test files rather than
   relying on a summary of what the tests covered. I found that sequential-cell
   output and nested-group exclusion did not yet have active coverage,
   and I asked the AI to add such tests. Coverage now includes
   `test_library_analyzer_reports_cell_and_pin_edge_cases` in
   `tests/test_library_analyzer.py`. 
   Those tests check sequential output and
   that fake pins inside nested groups do not become output rows.

## My design and review

I chose the pure-Python approach and directed the staged implementation. I
reviewed the code and diffs, compared the implementation with the assignment
and design plans, and gave the AI corrections and follow-up questions. I asked
for explanations when an algorithm or code change was unclear.

## Verification

- I reviewed code changes and checked them against the design plans and
  assignment requirements.
- I ran the unit and integration tests with `python -m pytest -q`.
- I compared CLI output with the provided expected sample rows.
- I checked the public sky130 HD and Nangate45 runs and stored their CSV output
  under `pdk_results/`.
