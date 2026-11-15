# Scrum master, five minutes

You do not need Java, and you do not need a SHAFT checkout. A repository of stories and plans is enough. No developer has to be in the refinement session.

## Refinement

1. Pull one item.
2. If it hides more than one problem, split it or reject it. The ready gate names that failure `mixed-problems`.
3. Tighten acceptance criteria until each one can fail a check. Missing criteria stay `missing-criteria`. Untestable wording stays `untestable-criteria`.
4. Record open questions on the item. Do not invent answers to make it look ready.
5. Exit ready or not ready. There is no third state.

`sdlc_flows.refine` is that exit. `sdlc_flows.role_gates("scrum-master")` names the gates: acceptance criteria, a single problem, the ready gate, and an intent-match review.

## Review floor

Every change, including a typo in a story or a test plan, needs one adversarial intent-match review. Public, irreversible, or outbound work needs two. A green unit-test job cannot waive the floor. `sdlc_flows.review_floor` records `waived` as false.

The [product owner](start-product-owner.md) owns the story text. The [tester](start-tester.md) owns the plan and the executable checks.

## Proof in this repo

```bash
python3 -m unittest tests.scripts.test_sdlc_flows_8059
```
