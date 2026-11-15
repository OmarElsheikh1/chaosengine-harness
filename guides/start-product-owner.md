# Product owner, five minutes

You do not need Java, and you do not need a SHAFT checkout. Stories and acceptance criteria are the artefact.

## Start

1. Install ChaosEngine into the repository that holds the stories. Follow [INSTALL.md](../INSTALL.md). Any supported host is enough.
2. Write one story. State the user-visible intent and the bounds. One problem only.
3. Add acceptance criteria. Each criterion is a check someone can fail. "Make it nice" is not a criterion.
4. Leave the item not ready until those criteria exist. Open questions stay open questions. Do not hide a second problem in the same item. Split it or reject it.

## Gates

The ready gate fails with a named reason when criteria are missing (`missing-criteria`), a criterion is not testable (`untestable-criteria`), or the item mixes problems (`mixed-problems`). The check is `sdlc_flows.ready_gate` and `sdlc_flows.refine`.

An intent-match review is still required after criteria exist, including a typo-sized edit. A green test job cannot waive it. High-stakes work (public contract, irreversible, or outbound) needs two reviews.

Hand the ready story to a [tester](start-tester.md). Flow and status sit with the [scrum master](start-scrum-master.md).

## Proof in this repo

```bash
python3 -m unittest tests.scripts.test_sdlc_flows_8059
```
