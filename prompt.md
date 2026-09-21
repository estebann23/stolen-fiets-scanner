CONTEXT
You are working in an existing Python 3.11 hackathon repo. SPEC.md is the single source of
truth — read §5.2 (enrichment), §6 (SQLite schema), and §11 (coding conventions) before
coding. Do NOT restructure the repo, change the DB schema, or touch any files other than the
ones listed under SCOPE. Match the style of the existing config.py and db.py (from __future__
import annotations, full type hints, small functions, a __main__ smoke block).

TASK
Implement the VLM attribute-extraction path in exactly two new modules plus minimal plumbing:
1. enrichment/llm_client.py — the ONE helper all model calls go through (SPEC §11 hard rule).
2. enrichment/attributes.py — VLM → strict-JSON bike attributes, Pydantic-validated.

PROVIDER: OpenRouter (OpenAI-compatible Chat Completions).
- Use the `openai` Python SDK, constructed with base_url and api_key from config, e.g.
  OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY).
- Send images as OpenAI-style multimodal content: {"type":"image_url","image_url":{"url":
  "data:image/jpeg;base64,..."}}. Read image bytes from disk and base64-encode; infer the
  mime type from the file suffix (jpg/jpeg/png). Text goes in a {"type":"text"} part.
- Request JSON via response_format={"type":"json_object"} when possible, but ALWAYS parse
  defensively regardless (strip ``` fences, extract the first balanced {...} object,
  json.loads) so it works even if the model ignores response_format.
- Temperature 0.

SUPPORTING EDITS (only these three existing files, minimal diffs):
- config.py: add OPENROUTER_API_KEY (from env, no default), OPENROUTER_BASE_URL (default
  "https://openrouter.ai/api/v1"), VLM_MODEL (already present — keep it env-driven, no hard-
  coded model in code), LLM_TIMEOUT_S (default 60), LLM_CACHE_DIR (default DATA_DIR/"cache"/
  "llm"). Never hard-code the key or model.
- .env.example: replace the ANTHROPIC/OPENAI lines with OPENROUTER_API_KEY=...,
  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1, and VLM_MODEL=<paste an OpenRouter vision
  slug, e.g. anthropic/claude-sonnet-4>. Keep DB_PATH, CLIP_MODEL, API_URL.
- requirements.txt: add `openai`. (httpx/pillow/numpy already present.)
- .gitignore: add data/cache/.

enrichment/llm_client.py — REQUIREMENTS
- Public function, roughly:
    def call_vlm_json(system: str, user_text: str, image_paths: list[Path],
                      *, max_retries: int = 1, timeout_s: float | None = None) -> dict | None
  Returns the parsed JSON dict, or None if it still fails after the retries (so callers can
  store nulls per SPEC §5.2 "on parse failure retry once, then store nulls").
- DISK CACHE (hard rule: never re-pay per listing): before calling the API, compute a stable
  cache key = sha256 of (VLM_MODEL + system + user_text + the raw bytes of each image in
  order). If LLM_CACHE_DIR/<key>.json exists, load and return its parsed content — no API
  call. On a successful call, write {"model","key","raw_content","parsed"} to that file.
- RETRIES/TIMEOUTS: wrap the API call with the configured timeout; on timeout, network error,
  empty response, or JSON-parse failure, retry up to max_retries (so 2 attempts total by
  default), then return None. Log one line per attempt with counts, no secrets.
- If OPENROUTER_API_KEY or VLM_MODEL is unset, raise a clear, actionable error naming the
  missing env var (do not silently no-op).
- Keep JSON extraction in a small pure helper (parse_json_loose(text) -> dict | None) so it's
  unit-testable.
- __main__: a tiny smoke test that calls the model on a 1-line text-only prompt and prints the
  parsed dict; if the key is missing, print the setup hint and exit 0 (don't crash).

enrichment/attributes.py — REQUIREMENTS
- Pydantic model BikeAttributes with EXACTLY the SPEC §5.2 fields, all Optional so a failed
  extraction can be all-nulls:
    brand: str | None, model: str | None,
    bike_type: Literal["city","e-bike","race","mtb","cargo","hybrid","other"] | None,
    colors: list[str] | None, frame_shape: Literal["low-step","diamond","mixte","unknown"]
    | None, wheel_size: str | None, is_electric: bool | None,
    accessories: list[str] | None, marks: list[str] | None, confidence: float | None
  Use a validator to coerce out-of-enum/unknown values to None (or "unknown" for frame_shape)
  rather than raising.
- SHARED BY LISTINGS AND REPORTS (SPEC key principle): the core function takes generic inputs,
  not a listing row:
    def extract_attributes(image_paths: list[Path], description: str) -> BikeAttributes
  Build a system prompt that: demands STRICT JSON only matching the schema; lists the allowed
  enum values; says the description may be Dutch and colours must be normalised to canonical
  English (black, grey, blue, green, white, red, silver, anthracite, ...); says use null (or
  "unknown" for frame_shape) when unsure; sets confidence 0–1. Call llm_client.call_vlm_json;
  if it returns None OR Pydantic validation fails after that, return BikeAttributes() with all
  fields None and confidence 0.0 (never raise to the caller).
- DB PERSISTENCE (write to the existing listing_attributes table, do not alter schema):
    def store_attributes(conn, listing_id: str, attrs: BikeAttributes) -> None
  Upsert brand, model, bike_type, frame_shape, wheel_size, is_electric, and colors/accessories
  /marks as JSON strings. IMPORTANT: leave serial_found untouched (it is populated by a
  separate serial_ocr module) — on conflict, update only the attribute columns, not
  serial_found.
    def enrich_listing(conn, listing_id: str, *, force: bool = False) -> BikeAttributes
  Idempotent: if the listing already has a non-null brand in listing_attributes and force is
  False, skip the API call and return the stored row. Otherwise fetch the listing's
  description and image paths from the DB (use db.connect / the listings + listing_images
  tables), run extract_attributes, store, and return. Log "skip"/"done" with the id.
- __main__: run enrich_listing on the first listing id in the DB and print the resulting JSON
  (pretty). If no key is set, print the setup hint and exit 0.

HARD RULES (from SPEC §11 — do not violate)
- Every VLM output is Pydantic-validated; on parse failure retry once (handled in llm_client),
  then store nulls.
- All model calls go through llm_client — attributes.py must not import openai directly.
- Cache every result (disk JSON here; DB is the validated store). Never re-pay per listing.
- No secrets in code; everything via config/.env. No live scraping. Typed everywhere.

OUT OF SCOPE — do NOT create or edit: embeddings.py, serial_ocr.py, risk_signals.py,
run_enrichment.py, anything under matching/, api/, app/, eval/, db.py, or the DB schema. No
mock/offline mode and no synthetic-ground-truth fallback — real API path only.

VERIFY BEFORE FINISHING
- `python -c "import enrichment.llm_client, enrichment.attributes"` imports cleanly.
- parse_json_loose handles: a bare JSON object, one wrapped in ```json fences, and junk-return
  -> None.
- With OPENROUTER_API_KEY and VLM_MODEL set, `python -m enrichment.attributes` prints a valid
  BikeAttributes JSON for one listing and a second run logs "skip" (idempotent + cached).
- Print the files you created/changed and the exact run command.

######Prompt 2 Stage 3




CONTEXT
Existing Python 3.11 hackathon repo; SPEC.md is the single source of truth — read §5.2
(embeddings), §6 (schema), §7.2 (how image similarity is used), and §11 (conventions) first.
enrichment/llm_client.py and enrichment/attributes.py already exist from a prior step — do not
touch them. Match the style of config.py / db.py (from __future__ import annotations, full type
hints, small functions, a __main__ smoke block). Do NOT change the DB schema.

TASK
Implement CLIP embeddings + a simple in-memory vector index in ONE new module:
  enrichment/embeddings.py
plus minimal plumbing in config.py and requirements.txt.

EMBEDDING BACKEND: local open_clip (NOT OpenRouter — embeddings are computed locally).
- Load the model ONCE at module level (lazy singleton), using CLIP_MODEL and a new
  CLIP_PRETRAINED from config. Default device: "cuda" if torch.cuda.is_available() else "cpu".
- Produce L2-normalized float32 vectors so cosine similarity == dot product.
- Note in a comment that the first run downloads the model weights (~350MB for ViT-B-32).

SUPPORTING EDITS (only these):
- config.py: add CLIP_PRETRAINED (default "laion2b_s34b_b79k"), EMB_CACHE_DIR (default
  DATA_DIR/"cache"/"embeddings"). Keep CLIP_MODEL as-is (env-driven, default "ViT-B-32").
- requirements.txt: add `open-clip-torch` and `torch`. (numpy/pillow already present.)
- .gitignore: ensure data/cache/ is ignored (add if missing).

enrichment/embeddings.py — REQUIREMENTS

Core encoders (typed, small, pure where possible):
- def embed_image(path: Path) -> np.ndarray   # opens with PIL, preprocess, encode, L2-norm,
                                               # returns float32 shape (D,)
- def embed_text(text: str) -> np.ndarray      # open_clip tokenizer + encode_text, L2-norm
- Both operate under torch.no_grad(); reuse the singleton model/preprocess/tokenizer.

BLOB (de)serialization for the DB (matches listing_images.clip_vec / report_images.clip_vec):
- def vec_to_blob(v: np.ndarray) -> bytes      # v.astype(float32).tobytes()
- def blob_to_vec(b: bytes) -> np.ndarray      # np.frombuffer(b, dtype=float32)

IMAGE VECTORS -> DB (idempotent):
- def embed_listing_images(conn, listing_id: str, *, force: bool = False) -> int
  For each row in listing_images for this listing: if clip_vec is already non-null and not
  force, skip; else embed the image at `path` and UPDATE that row's clip_vec. Return the
  number of vectors written. Log "done <id>: n/total" (skip when nothing to do).
- Provide the analogous def embed_report_images(conn, report_id, *, force=False) -> int so the
  online report path reuses the exact same code (SPEC key principle).

TEXT VECTORS -> DISK CACHE (schema has no text-vector column; do NOT add one):
- def embed_description_cached(entity_id: str, text: str, *, force: bool = False) -> np.ndarray
  Cache to EMB_CACHE_DIR/text/<entity_id>.npy; on cache hit load and return; else compute,
  save, return. This satisfies the "cache every embedding" hard rule via disk.

VECTOR INDEX (the "vector index" deliverable — brute-force numpy, no FAISS):
- class ImageIndex with:
    @classmethod build_from_db(cls, conn) -> "ImageIndex"
      Load every listing_images row that has a non-null clip_vec into: a float32 matrix of
      shape (N, D) and a parallel list of (listing_id, image_id, path). Skip nulls.
    def query(self, query_vecs: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]
      query_vecs is (Q, D) (one row per report photo). Compute cosine (matrix @ query.T),
      take the max over BOTH photos-of-a-listing AND query photos, i.e. per listing_id keep
      the single best similarity across all its images vs any query image (SPEC §7.2: "max
      image cosine similarity, any report photo vs any listing photo"). Return the top_k
      (listing_id, score) sorted desc. Handle an empty index gracefully (return []).

__main__ smoke test:
- Connect to the DB, pick the first listing that has image rows, embed_listing_images on it,
  print vectors-written and the vector dim; assert a photo's cosine self-similarity ≈ 1.0;
  embed_description_cached on its description and print the text-vector dim; build ImageIndex
  and run query() with that listing's own photo vectors, printing the top-3 (its own id should
  rank #1). A second run must log "skip" (idempotent) and hit the caches.

HARD RULES (SPEC §11)
- Idempotent & resumable: skip already-embedded images/text unless force=True; log counts.
- Cache every embedding (image vecs in DB BLOB, text vecs on disk). Never recompute silently.
- Typed everywhere; small testable functions. No secrets, no network beyond the one-time model
  weight download. Do NOT alter the SQLite schema.

OUT OF SCOPE — do NOT create or edit: llm_client.py, attributes.py, serial_ocr.py,
risk_signals.py, run_enrichment.py, anything under matching/, api/, app/, eval/, db.py, or the
schema. No FAISS/sqlite-vec.

VERIFY BEFORE FINISHING
- `python -c "import enrichment.embeddings"` imports cleanly.
- vec_to_blob/blob_to_vec round-trips a random vector exactly (float32).
- embed_image on a solid-color PIL image returns an L2-normalized vector (‖v‖≈1) of the
  expected dim.
- `python -m enrichment.embeddings` prints dims, the ≈1.0 self-similarity, and a top-3 where
  the source listing ranks first; a second run logs skips.
- Print the files you created/changed and the exact run command.