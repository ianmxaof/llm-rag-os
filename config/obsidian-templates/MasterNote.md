---
id: <% tp.date.now("YYYYMMDDHHmmss") %>
title: <% tp.file.title %>
created: <% tp.date.now("YYYY-MM-DD HH:mm") %>
updated: <% tp.date.now("YYYY-MM-DD HH:mm") %>
type: "manual"
tags: []
aliases: []
source: ""
summary: ""
confidence: ""
origin_file: ""
relationships: []
---

<%* 
// Run smart router to include appropriate skeleton if desired
// But MasterNote is the full master template; avoid nested includes here.
// Optionally, call semantic summary after editing:
// await tp.user.semantic_summary();
%>

# <% tp.file.title %>

## TL;DR

- <% tp.cursor() %>

## Key points

- 

## Full Content (paste / paste & clean)

<%* 
// simple normalization examples (line breaks)
// let content = tp.file.selection() || "";
// tR += content;
%>

## References

- 

## Actions / Tasks

- [ ] review
- [ ] refine summary
- [ ] add tags (`AI Tagger`)

## Related (Dataview)

```dataview
LIST FROM "Manual" OR "Auto"
WHERE contains(file.tags, this.file.name) OR contains(file.content, this.title)
SORT file.mtime DESC
LIMIT 12
```

