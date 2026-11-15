# Agent notes

## Project

This repository is a software project. Read the files that are already here before adding new ones. Prefer the stack and layout the repository already uses.

## Setup, build, and test

- Install the language toolchain the project declares.
- If the project has a `pom.xml`, build and test with Maven: `mvn test`.
- If the project has a `package.json`, build and test with npm: `npm test`.
- If the project has a `pyproject.toml` or `requirements.txt`, use the runner that file names.
- Do not download tools the project does not ask for.

## Code style

- Match the style already in the repository.
- Use clear names. Keep functions small. Add a comment only when the code would otherwise hide a constraint.
- Do not leave generated output, secrets, or local machine paths in source.

## Testing

- Tests must be deterministic. Do not depend on the clock, on a random order, or on any network beyond the system under test.
- Assert the outcome a user would care about.
- Keep test data out of the test logic when the project has a data file or a configuration file for it.

## Pull requests and commits

- One change per commit. The message names the behavior.
- Do not commit secrets, caches, or build output.

## When you are unsure

Ask a short question before guessing. If you are told to decide, pick the simplest option that still meets the request and continue.
