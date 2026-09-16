---
title: Extensions
parent: "Track 4: Twitter Disinformation Analyst Assistant"
nav_order: 6
layout: home
permalink: /tracks/track-4/extensions/
---


# Extensions

{: .summary }
> **Optional.** Once your core assistant works, these are directions to take it
> further. They are pointers, not requirements: pick any, all, or none, and feel
> free to go your own way.

Your baseline is the assistant from [Building your Application]({% link tracks/track-4/building-application.md %}). Everything here is on top of that.

---

## 1. Add a user interface

Your assistant is an HTTP endpoint, which is enough for grading but not much to look at. A chat UI makes it easy to demo and to test by hand.

{: .tip }
> [Open WebUI](https://openwebui.com) is an open-source chat interface you can point at your assistant. It speaks the OpenAI chat format, so you will likely add a thin adapter between it and your `/query` endpoint, or expose an OpenAI-compatible route alongside it.

---

## 2. Extend to larger dataset

You can ask organisers for a much larger dataset if you want to stress-test your retrieval and grounding at a larger scale.

The graded questions are about the provided corpus, so this is about robustness and higher-scale implementation. 
---

## 3. Your own extension

Free choice. If you have an idea that makes the assistant more useful, safer, or more interesting, build it. A few directions to spark ideas:

- other questions that may be useful for OSINT agency analyzing misinformation campaign,
- make the assistant work in form of chat instead of query (so that it also has memory of previous queries)
- given the larger dataset, automatize detection of different nicknames corresponding to the same person/event( e.g. "Donald Trump", "Drumpf", “45 and 47”, "DJT").

{: .tip }
> Surprise us. The pointers above are starting points, not a menu.
