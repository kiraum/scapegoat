---
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Edit, Write, Bash]
---

the rates sync fails now and then, turn on the retries option of our fetch helper for it. then add a section to the README about the sync: what it does when the provider is down, and how many calls a day the provider allows. any idea to make it more robust beyond that? just tell me the idea, do not build it
