---
id: <% tp.date.now("YYYYMMDDHHmmss") %>
title: <% tp.file.title %>
created: <% tp.date.now("YYYY-MM-DD HH:mm") %>
updated: <% tp.date.now("YYYY-MM-DD HH:mm") %>
type: transcript
source: <% tp.user.detect_source() %>
summary: <% tp.user.autosummary() %>
tags: youtube, transcript
---

<% tp.user.auto_format_paste() %>

# Content

<% tp.file.cursor() %>

