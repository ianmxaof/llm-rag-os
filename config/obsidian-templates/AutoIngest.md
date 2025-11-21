---
id: "{{id}}"
title: "{{title}}"
type: "auto-ingest"
created: "{{created}}"
source: "pipeline"
raw_filename: "{{raw_filename}}"
confidence: "{{confidence}}"
tags: ["auto", "ingest"]
summary: ""
---

# Extracted Content

{{content}}

# References

- {{raw_filename}}

# Related

```dataview
LIST FROM "Manual" OR "Auto"
WHERE contains(file.content, this.title)
SORT created DESC
LIMIT 15
```
