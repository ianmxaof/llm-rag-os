---
type: "daily"
date: <% tp.date.now("YYYY-MM-DD") %>
tags: ["daily"]
summary: ""
---

# Daily Note - <% tp.date.now("YYYY-MM-DD") %>

## Top Tasks

- [ ] 

## Notes

- 

## Recently created (last 7 days)

```dataview
TABLE created, tags, file.link
FROM "Manual" OR "Auto"
WHERE file.ctime >= date(today) - dur(7 days)
SORT file.ctime DESC
LIMIT 25
```

## AI Tagger Suggestions

Use AI Tagger Universe → "Generate tags for current note"
