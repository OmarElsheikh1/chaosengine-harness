# Backend developer, five minutes

You do not need Java, and you do not need a SHAFT checkout. A contract, a fixture, and a failing check are enough to start.

## Loop

1. Take one story with acceptance criteria a caller can observe: status, payload, and the failure you refuse to hide. The [product owner](start-product-owner.md) page is the source of that story.
2. Agree the check with the [tester](start-tester.md) before changing the service. A check that only imports the module is not done.
3. Change only the criteria. An intent-match review rejects a green check that contradicts the story.
4. One adversarial review is the floor. Public, irreversible, or outbound work needs two.

Host setup is one page per tool under [tools/](tools/). Install steps are in [INSTALL.md](../INSTALL.md). The [frontend start](start-frontend-developer.md) uses the same review floor.
