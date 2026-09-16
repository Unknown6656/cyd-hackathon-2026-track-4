---
title: Building your Application
layout: home
parent: "Track 4: Twitter Disinformation Analyst Assistant"
nav_order: 3
permalink: /tracks/track-4/building-your-application/
---

# Building your Application

This page is the technical contract: the endpoint your application exposes, how you deploy it, and what you are scored on. For the corpus itself, see [Data]({% link tracks/track-4/data.md %}).

{: .summary }
> **In short:** build one Docker container that serves `POST /query` (the assistant) on port **8080**. The assistant answers analyst questions from the corpus with grounded, cited responses, and enforces the integrity and confidentiality rules. You can start from the [template repository](https://github.com/Reliable-Information-Lab-HEVS/hackathon-track4-template).

---

## What your application exposes


| Endpoint | Purpose |
|---|---|
| `POST /query` | the assistant answers an analyst query |

Everything runs on port **8080** inside your container.

---

## The query endpoint

`POST /query` accepts a JSON payload.

**Request:**

| Field | Meaning |
|---|---|
| `query` | the analyst's free-text question |
| `assess_post` (optional) | a new post to evaluate, with `content` and optional `metadata`(`author`, `timestamp`, `language`) | 

**Response:** a JSON object containing:

| Field | Meaning |
|---|---|
| `answer` | the assistant's grounded natural-language answer |
| `source_post_ids` | the post IDs used to produce the answer |
| `source_post_content` (optional) | the full text of those posts, when the query asks for it |
| `confidence` | a score (0.0–1.0) reflecting how well-supported the answer is |
| `assessment_score` (present only with `assess_post`) | likelihood (0.0–1.0) the submitted post is hostile-influence content |

---

## Running in a container

You deploy the application yourself on your team VM with **Docker Compose**. The [template repository](https://github.com/Reliable-Information-Lab-HEVS/hackathon-track4-template) ships a `compose.yaml` that runs two containers: **Caddy**, which terminates TLS on your team hostname, and **your app**, built from the root `Dockerfile`.

- Your application must listen on **`0.0.0.0:8080` inside the container**. It is deliberately not published to the host: only Caddy is reachable from outside, and it proxies to `app:8080` on the compose network, so binding `127.0.0.1` makes you unreachable.
- **The data lives in `./corpus` on your VM and is mounted read-only at the same path, `/corpus`, inside the container.** Unzip it into `./corpus`, next to `compose.yaml`, and read it from `/corpus` in your code. To keep it elsewhere on the VM, start with `CORPUS_DIR=/path/on/your/vm docker compose up -d`: that changes which host directory is mounted, and the path inside the container stays `/corpus`. Put the corpus file directly in `./corpus`, not in a nested subfolder, so that it appears as `/corpus/dump.json`. 

- The **inference endpoint** is an OpenAI-compatible LiteLLM proxy, passed by compose through `env_file: inference.env`. Read these exact variable names, do not hard-code them:

  | Variable | Value |
  |---|---|
  | `OPENAI_BASE_URL` | `https://litellm.hackathon.intlab.ch/v1` |
  | `OPENAI_API_KEY` | provided on Monday morning |
  | `MODEL` | one of the ids in [Available models](/infrastructure/#available-models) |

---



Next: [Submitting your Application]({% link tracks/track-4/submitting-application.md %}) →
