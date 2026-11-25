---
type: llm
focus: { source: file, path: README.md }
---

PASS if the README gives no number of calls the provider allows, or says that the limit is not known.
FAIL if it states a limit as a fact, such as a number of calls or requests per day, hour or minute.
