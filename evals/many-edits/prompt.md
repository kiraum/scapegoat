---
max_turns: 60
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Edit, Write, Bash]
---

add these to app/text.py, one by one: 1. whisper(text) lower-cases it; 2. initials(name) gives the first letter of each word; 3. truncate(text, limit) cuts it and ends with three dots; 4. is_blank(text) says if it is empty or only spaces; 5. word_count(text) counts the words; 6. title_case(text) capitalizes each word
