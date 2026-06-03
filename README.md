# Imagecb

Conversational multimodal retrieval over an image corpus that mixes
standalone image files with images embedded inside PowerPoint (`.pptx`)
and PDF documents.

Every image is:

- Embedded into a joint vision-language space with **Amazon Titan
  Multimodal Embeddings** on Bedrock (`amazon.titan-embed-image-v1`).
- Captioned by a **VLM** into a structured JSON document. Default is
  **AWS Bedrock** Claude Haiku 4.5
  (`us.anthropic.claude-haiku-4-5-20251001-v1:0`); OpenAI and Anthropic
  are also supported as drop-in providers.
- Indexed in **ChromaDB** (dense), **rank-bm25** (sparse over caption +
  OCR + slide context), and **SQLite** (provenance + filters).

User turns are parsed by an LLM into a structured `QuerySpec`
(semantic phrase, time window, source/author filters, must-have /
must-avoid keywords, refinement flag). The system fuses dense + sparse
hits with Reciprocal Rank Fusion, reranks with **Cohere Rerank 3.5**
on Bedrock (`cohere.rerank-v3-5:0`), and renders results with
full provenance (e.g. `Slide 7 of Q3_Review.pptx, modified 2026-05-08`).

## Architecture at a glance

```
ingest:  files -> extractor (pptx/pdf/image) -> OCR + VLM caption + Titan image emb
                                              -> SQLite + Chroma + BM25

query:   text + history -> LLM QuerySpec
                        -> metadata filter
                        -> dense (Titan text -> Chroma) + sparse (BM25)
                        -> RRF fusion
                        -> Cohere Rerank 3.5 rerank
                        -> ranked images + provenance
```

**Match % on result cards** is a calibrated display value derived from
each hit's raw model score (Cohere rerank relevance for chat search,
cosine similarity for small similar-image result sets). Ranking and the
min-match slider still use raw scores. **100%** appears only for
near-excellent raw scores (rerank ≥ 0.93, cosine ≥ 0.92); weaker but
top-ranked results keep lower percentages.

## Setup

### 1. Python deps

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No local ML model downloads are required — embeddings, captioning,
query parsing, and reranking all run through AWS Bedrock APIs.

### 2. Tesseract OCR (Windows)

1. Install Tesseract from
   https://github.com/UB-Mannheim/tesseract/wiki (the UB-Mannheim
   build is the standard Windows installer).
2. Confirm the install path, typically
   `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Set `TESSERACT_CMD` in your `.env` to that path.

If you don't want OCR right now, leave `TESSERACT_CMD` empty - ingest
will continue and OCR text will simply be blank.

### 3. AWS Bedrock (default)

The default config drives **all** model calls through AWS Bedrock:

| Role | Model | API |
|------|-------|-----|
| Image + text embeddings | `amazon.titan-embed-image-v1` | `invoke_model` |
| VLM captioning | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | `converse` |
| Query parsing | same | `converse` |
| Reranking | `cohere.rerank-v3-5:0` | `invoke_model` |

1. In the AWS Bedrock console for `us-east-1`, enable model access for
   all four models listed above.
2. Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

3. Provide credentials in one of two ways:

   - **Bedrock API key (easiest):** set `AWS_BEARER_TOKEN_BEDROCK=...`
     in your `.env`. boto3 picks it up automatically for all
     `bedrock-runtime` calls (embeddings, captioning, query parsing, and
     reranking). These tokens are short-lived; refresh from the Bedrock
     console when they expire.
   - **Standard AWS credentials:** any of the usual sources works
     (`aws configure`, `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`,
     SSO, instance profile, etc.). Make sure your principal has
     `bedrock:InvokeModel`, `bedrock:Converse`, and rerank permissions
     for the model IDs you set.

4. Leave `AWS_REGION=us-east-1` unless you specifically want a
   different Bedrock region (you'll then also need a matching inference
   profile prefix, e.g. `eu.anthropic...` for EU regions).

Ingest makes **two Bedrock calls per image** (Titan embed + Claude
caption). Cost scales per image and per token. For a fast dry-run that
skips captioning, see `--skip-caption` under [Usage](#usage) (the Titan
embed call still runs — search requires it).

### 4. Optional: OpenAI or Anthropic providers

To bypass Bedrock and use a different cloud VLM, set in `.env`:

```
VLM_PROVIDER=openai      # or anthropic
LLM_PROVIDER=openai
VLM_MODEL=gpt-4o-mini    # or e.g. claude-3-5-sonnet-latest
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...    # or ANTHROPIC_API_KEY=...
```

The rest of the system is provider-agnostic; the only files that touch
the provider are
[imagecb/models/vlm.py](imagecb/models/vlm.py) and
[imagecb/models/llm.py](imagecb/models/llm.py).

## Docker

Run Imagecb in a container with the React UI, Tesseract OCR, and persisted
index data under `./data`. No local Python or Node install is required.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or
  Docker Engine + Compose v2)
- A `.env` file with Bedrock or other provider credentials (same as
  [Setup](#setup) — copy from `.env.example`)

### Start the web UI

```powershell
docker compose up --build
```

Open http://localhost:8080. The image builds `frontend/dist/` during
`docker compose build` and serves it via FastAPI.

Index state is stored in `./data` on the host (bind-mounted to
`/app/data` in the container). A fresh `./data` directory is empty until
you ingest files or use **Add to corpus** in the UI.

### Ingest a host corpus

To index files from your machine via the CLI inside the container:

1. Create a `corpus` folder next to the project (or use any path you
   prefer).
2. In `docker-compose.yml`, uncomment the corpus volume line:
   `# - ./corpus:/corpus:ro`
3. Run ingest:

   ```powershell
   docker compose run --rm imagecb python -m imagecb.cli ingest /corpus
   ```

SQLite stores absolute `source_file` paths. Corpus files must stay at
the **same path inside the container** for **Open source** downloads to
work (hence the fixed `/corpus` mount).

### Other CLI commands

Use the same pattern as ingest:

```powershell
docker compose run --rm imagecb python -m imagecb.cli status
docker compose run --rm imagecb python -m imagecb.cli repair-captions --workers 4
```

### Troubleshooting

| Issue | What to try |
| ----- | ----------- |
| Cannot connect to http://localhost:8080 | Ensure the container is running; the server binds `0.0.0.0` inside the image |
| Bedrock / AWS errors | Refresh `AWS_BEARER_TOKEN_BEDROCK` or check `AWS_REGION` in `.env` |
| `ThrottlingException` during ingest | Lower `INGEST_WORKERS` in `.env` |
| Missing `.env` | `Copy-Item .env.example .env` and fill in credentials before `docker compose up` |

## Usage

### After upgrading: reset Chroma

Embedding dimensions changed (768-dim OpenCLIP → 1024-dim Titan).
Existing Chroma vectors are incompatible and must be rebuilt:

```powershell
Remove-Item -Recurse -Force .\data\chroma
python -m imagecb.cli ingest "C:\path\to\corpus"
```

SQLite metadata and BM25 can stay; only the Chroma directory needs
deleting.

### Ingest a corpus

```powershell
python -m imagecb.cli ingest "C:\path\to\corpus"
```

The corpus path can be a single file or a directory; the directory is
walked recursively for `.pptx`, `.pdf`, and common image extensions
(`.png .jpg .jpeg .webp .bmp .gif .tif .tiff`). Re-running ingest is
idempotent: images are de-duplicated by content hash.

To do a fast dry-run without spending VLM tokens:

```powershell
python -m imagecb.cli ingest "C:\path\to\corpus" --skip-caption
```

(Search quality will be much worse without captions; useful only for
debugging the extraction stage.)

### Faster ingest

Ingest runs **two Bedrock calls per image** (caption + embed). By default
images are processed in parallel:

```powershell
python -m imagecb.cli ingest "C:\path\to\corpus" --force --workers 4
```

For ~50 images this typically lands around **5–10 minutes** instead of
~20+ minutes sequential, depending on Bedrock latency and rate limits.

| Flag | Effect |
|------|--------|
| `--workers 4` | Parallel images (default; set `INGEST_WORKERS` in `.env`) |
| `--skip-ocr` | Skip Tesseract (faster; OCR text empty) |
| `--max-image-side 1024` | Smaller payload to the VLM (default) |
| `--force` | Re-process duplicates (refresh cache, captions, vectors) |

If you see `ThrottlingException`, lower `--workers` to `2`. Refresh
`AWS_BEARER_TOKEN_BEDROCK` for your `AWS_REGION` before `--force` if
`status` still reports failed captions.

### Context-aware embeddings (after upgrade)

Ingest now embeds slide/PDF title and notes together with each image
(Titan `inputText` + `inputImage`). For an existing index, re-embed once
without re-extracting decks:

```powershell
python -m imagecb.cli reindex-embeddings --workers 4
```

### Repair failed captions

If `python -m imagecb.cli status` reports captions failed at ingest:

```powershell
python -m imagecb.cli repair-captions --workers 4
```

This re-runs the VLM only on failed rows and rebuilds the BM25 index.

### Launch the web UI (recommended)

One command serves **chat**, **admin**, and the API on port **8080** — no
local npm required. The repo includes a pre-built React bundle at
`imagecb/web/frontend_dist/` (chat + admin dashboard).

```powershell
python -m imagecb.cli serve-web
```

- Chat: http://127.0.0.1:8080/
- Admin: http://127.0.0.1:8080/admin (enter `ADMIN_API_KEY` from `.env`)

If `frontend_dist` is missing, `serve-web` falls back to the built-in
vanilla UI under `imagecb/web/static/` (chat only, no admin).

**IT / no-script environments:** you do not need to run `npm run build`
locally. Use the committed `imagecb/web/frontend_dist/` or the Docker
image (which builds the UI at image build time).

**Frontend developers** (machines allowed to run npm) after changing
`frontend/`:

```powershell
cd frontend
npm ci
npm run build
cd ..
python scripts/sync_frontend_dist.py
```

CI verifies `frontend_dist` stays in sync when `frontend/` changes.

#### Upload from the UI

Click **Add to corpus**, choose one or more supported files (images,
`.pdf`, or `.pptx`), and ingest. Files are copied to `data/uploads/`
(or `UPLOADS_DIR` if set) and indexed with the same pipeline as CLI
ingest. Optional checkboxes mirror CLI flags: skip captions, skip OCR,
and force re-ingest. Large decks can take several minutes (~2 Bedrock
calls per extracted image).

#### Search features in the web UI

- **Find similar** on any result card runs visual similarity search (no
  query LLM).
- **Attach** in the composer uploads a reference image for similarity
  search.
- **Open source** downloads the original `.pptx`, `.pdf`, or image file;
  **Copy path** puts the on-disk path on the clipboard (use with slide/page
  chips for location).
- **How we interpreted your query** shows interpretation notes (refinement
  pool, carried-forward filters, must-have / exclude keywords).

### Legacy Gradio UI

```powershell
python -m imagecb.cli serve
```

Then open http://127.0.0.1:7860. This interface is deprecated in favor
of `serve-web`.

Try queries like:

- "Diagrams of system architecture from internal decks"
- "Screenshots of dashboards modified after May 2026"
- "Only the ones from Q3_Review.pptx"  (refinement)
- "Drop anything with bar charts"      (refinement, must-avoid)

### Inspect the index

```powershell
python -m imagecb.cli status
python -m imagecb.cli parse-query "screenshots of dashboards from last quarter"
```

## Configuration

Everything is driven by environment variables - see `.env.example` for
the full list. Highlights:

| Variable                    | Purpose                                                                              |
| --------------------------- | ------------------------------------------------------------------------------------ |
| `VLM_PROVIDER`              | `bedrock` (default), `openai`, or `anthropic`                                        |
| `LLM_PROVIDER`              | Same options; defaults to `bedrock`                                                  |
| `VLM_MODEL`                 | Model id for captioning (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`)      |
| `LLM_MODEL`                 | Model id for query understanding (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`) |
| `EMBEDDING_MODEL`           | Bedrock embedding model (default `amazon.titan-embed-image-v1`)                      |
| `EMBEDDING_DIM`             | Titan output dimension: 256, 384, or 1024 (default `1024`)                           |
| `RERANKER_MODEL`            | Bedrock rerank model (default `cohere.rerank-v3-5:0`)                                |
| `AWS_REGION`                | AWS region for Bedrock (default `us-east-1`)                                         |
| `AWS_BEARER_TOKEN_BEDROCK`  | Short-lived Bedrock API key (optional; otherwise use standard AWS credentials)       |
| `DATA_DIR`                  | Root for all persisted state                                                         |
| `UPLOADS_DIR`               | Staging dir for UI uploads (default `<DATA_DIR>/uploads`)                            |
| `TESSERACT_CMD`             | Path to `tesseract.exe`                                                              |
| `INGEST_WORKERS`            | Parallel ingest workers (default `4`)                                                |
| `INGEST_MAX_IMAGE_SIDE`     | Max longest edge for VLM caption input (default `1024`)                              |
| `INGEST_BATCH_UPSERT`       | Chroma vectors per batch upsert (default `16`)                                       |

## Project layout

```
imagecb/
  config.py
  ingest.py
  app.py                 (Gradio UI)
  uploads.py             (UI upload staging)
  cli.py                 (Typer CLI)
  models/
    bedrock_client.py    (shared boto3 clients)
    embedder.py          (Titan Multimodal Embeddings)
    vlm.py               (structured-JSON captioner)
    llm.py               (query-understanding LLM)
    reranker.py          (Cohere Rerank 3.5)
    ocr.py               (Tesseract)
  extractors/
    pptx.py pdf.py image_file.py dispatch.py types.py
  storage/
    metadata_db.py       (SQLite + SQLAlchemy)
    vector_store.py      (Chroma)
    bm25_index.py        (rank_bm25, persisted)
  retrieval/
    query_parser.py      (text -> QuerySpec)
    hybrid.py            (filter + dense + sparse + RRF)
    rerank.py            (Bedrock rerank + provenance formatting)
    session.py           (multi-turn state, sticky filters, refinement)
  web/
    frontend_dist/       (pre-built React UI for serve-web — chat + admin)
    static/              (fallback vanilla chat UI)
```

## Admin layer (telemetry, quality, curation)

Set `ADMIN_API_KEY` in `.env` (see `.env.example`). This key protects:

- All `/api/admin/*` endpoints (analytics, corpus curation, audit log)
- `POST /api/ingest` (corpus uploads)

### Telemetry

Every chat and similar search records a **search event** (query, user id, served image ids, top raw score, result count). The UI sends **interaction events** (view, download, similar) linked by `search_event_id` from the stream metadata payload.

Optional header `X-User-Id` on chat requests labels telemetry until real SSO is added (default: `anonymous`).

### Admin UI

With `serve-web` running, open **http://127.0.0.1:8080/admin** and enter
`ADMIN_API_KEY`. The main chat UI also has an **Admin login** link in the
header and sidebar.

Optional: `npm run dev` in `frontend/` for hot reload at
**http://localhost:5173/admin** (requires API on 8080 for `/api` proxy).

For local dev you may set `VITE_ADMIN_API_KEY` in `frontend/.env.local`
(do not commit secrets).

### Soft delete

`POST /api/admin/images/{image_id}/soft-delete` removes the vector from Chroma and rebuilds BM25 while keeping SQLite metadata and cached PNGs. `POST .../restore` re-embeds and re-indexes.

## Notes / limitations (prototype)

- Single-user, single-process. Chat is open; admin and ingest require `ADMIN_API_KEY`.
- No live folder watcher - re-run `ingest` or use **Add to corpus** in the UI for new files.
- All model inference (embeddings, captioning, query parsing, reranking)
  runs through AWS Bedrock — no local GPU or HuggingFace downloads.
- Aimed at hundreds-to-low-thousands of images; for larger corpora swap
  Chroma for Qdrant/Milvus and move BM25 to OpenSearch or Tantivy.
