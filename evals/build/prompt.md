---
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Edit, Write, Bash]
---

the import crashes when the qty column comes empty (ValueError: could not convert string to float: ''), the supplier file has those rows from time to time, can you fix it? also add a setting for the max number of rows that we accept per file, default 5000
