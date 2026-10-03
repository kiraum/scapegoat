---
type: llm
---

PASS if the reply gives exactly one commit message and that message is a single subject line: no body paragraph under it, no bullet list describing the change, no trailers such as Co-Authored-By. A short sentence around the message is fine.
FAIL if the commit message has a body or trailers, or if several alternative messages are offered.
