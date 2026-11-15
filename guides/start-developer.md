# Developer, five minutes

Frontend and backend use the same loop. You do not need Java, and you do not need a SHAFT checkout. Specs, stories, and test plans are in scope, not only source diffs.

## Loop

1. Start from a ready story: one problem, testable acceptance criteria. The [product owner](start-product-owner.md) and [scrum master](start-scrum-master.md) gates are the same ones you should refuse to skip.
2. Read the [tester](start-tester.md) plan. Executable checks exist before implementation details get baked into the proof.
3. Implement only what the criteria ask. An intent-match review rejects a check that passes but contradicts the story.
4. One adversarial review is the floor, including a typo-sized edit. Public, irreversible, or outbound work needs two. A green unit-test job does not waive the review.

Host setup is one page per tool under [tools/](tools/). Install steps are in [INSTALL.md](../INSTALL.md).

## Proof in this repo

```bash
python3 -m unittest tests.scripts.test_sdlc_flows_8059
```
