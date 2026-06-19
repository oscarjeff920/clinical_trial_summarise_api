# Medical Trials Data Extractor
 
A backend service that extracts Serious Adverse Event (SAE) tables from a clinical-trial
`.docx` file and generates plain-English summary sentences comparing two compounds.
 
Upload a single `.docx` document and two compound names (detailed in the .docx table); the service detects the SAE
tables, compares the two compounds for each preferred term, and returns structured JSON.
 
## What it does
 
For each SAE table found in the document, the service returns:
 
- the table number and title
- the two user supplied compounds
- a **totals sentence** — total participants with an SAE per compound
- a **per-term sentence** for each preferred term, comparing the two compounds
Non-SAE tables (demographics, fatal-AE summaries, etc.) are detected and ignored.
 
## Setup & running
 
### 1. Configuration (optional)
 
```bash
./init_project.sh        # copies .env.example -> .env
```
 
This scaffolds a `.env` file. It's optional — the service runs on sensible defaults
without it — but the Docker setup reads the published port from `.env`, so it's the
simplest way to get a complete, configurable environment.
 
### 2. Run it
 
Either locally:
 
```bash
./run_api.sh             # uv bootstraps the venv + dependencies, then starts the API
```
 
or containerised:
 
```bash
docker compose up
```
 
The API is then available at **http://localhost:8000/docs** (interactive Swagger UI).
 
## API
 
### `POST /summarise`
 
A `multipart/form-data` request:
 
| field        | type   | description                  |
|--------------|--------|------------------------------|
| `file`       | file   | the `.docx` document         |
| `compound_1` | string | first compound to compare    |
| `compound_2` | string | second compound to compare   |
 
Example:
 
```bash
curl -X POST http://localhost:8000/summarise \
  -F "file=@client1.docx" \
  -F "compound_1=Placebo" \
  -F "compound_2=Compound X"
```
 
Compound matching is case-insensitive; the response preserves the casing as written
in the table.
 
### Responses
 
| status | meaning                                                              |
|--------|---------------------------------------------------------------------|
| `200`  | success — returns `{ "tables": [...] }`                              |
| `200`  | no SAE tables found — returns `{ "tables": [] }` (a valid empty result) |
| `415`  | file is not a `.docx`, or is not a readable document                |
| `422`  | a requested compound is not present in the table                    |
| `422`  | a required field is missing (FastAPI request validation)            |
 
The request is `multipart/form-data` (it carries a file), so it is validated via the
endpoint signature rather than a request-body model.
 
## How it works
 
The request flows through two stages:
 
**1. Extract.** The document is walked in order, pairing each table with the heading
above it. Only tables whose title contains an SAE keyword (e.g. *serious*, *SAE*) are
kept. Each kept table is parsed into a *term-first* structure: one entry per preferred
term holding each compound's count and percentage, plus a separate totals list.
Percentages are read directly from the document (they appear in brackets) and never
recalculated.
 
**2. Translate.** For the two selected compounds, a totals sentence and one sentence per
term are generated. The per-term sentence is chosen from a set of templates based on the
two percentages (both non-zero, equal, one zero, both zero).
 
## Design decisions
 
- **Term-first data structure.** Parsed data is grouped by preferred term rather than by
  compound, because the task is to *compare* the two compounds per term — so both
  compounds' values need to sit side by side for each term.
- **Row-based table traversal.** Tables are read via `table.rows`, not `table.columns`.
  python-docx synthesises columns by assuming a clean rectangular grid, so column access
  can misalign or error on merged cells (common in clinical tables); row access reads the
  format's native structure and is robust.
- **`Decimal` for percentage comparison.** Percentages are compared as `Decimal` values,
  not rounded to integers. Rounding would silently merge genuinely different values (e.g.
  10.3% and 10.4%) and could render an "equal" sentence for unequal data. The original
  percentage string is preserved separately for display.
- **`def`, not `async def`, for the endpoint.** Parsing is CPU-bound with nothing to
  `await`. A sync handler runs in FastAPI's threadpool, keeping the event loop free to
  serve other requests; an `async` handler would block the loop and serialise requests.
- **Truthful sentence ordering.** When both compounds have a non-zero percentage, the
  higher-percentage compound is named first, so the comparison sentence is factually
  correct regardless of the order the user supplies the compounds.
- **Case-insensitive compound matching.** A compound is matched regardless of case; the
  name as written in the table is preserved in the output.
- **Nullable table number.** A table without a parseable "Table N.N" number returns
  `null` rather than failing the whole response.
- **Empty result is a valid 200.** A well-formed request that finds no SAE tables returns
  `200` with an empty list, not an error — the request was valid, there was simply nothing
  to summarise.
## Testing
 
```bash
pytest
```
 
Three layers of coverage:
 
- **Unit (extractor)** — SAE-title detection, table-number parsing, cell parsing
  (counts, percentages, bracket handling), and table extraction.
- **Unit (translator)** — the sentence-selection branch logic (the core business rules),
  substitution, and compound selection.
- **Integration** — the `/summarise` endpoint end-to-end via `TestClient`: the happy path
  plus the error responses, using a sample document fixture.
Tests were added once the extractor and translator interfaces had stabilised. The data
shapes evolved during the build (the grouping and table traversal both changed), so
writing tests against intermediate shapes would have meant churning them repeatedly. In a
production codebase against a fixed spec, tests would be included within each feature PR.
 
## Notes & assumptions
 
- SAE tables are identified by keywords in the table title. A table whose title doesn't
  contain an SAE keyword is treated as out of scope.
- The totals row is identified by keyword density in its label cell.
- Percentages are taken verbatim from the document, not computed from counts.
- The Docker container currently serves as a clean, reproducible run/demo environment. In
  production it would also be the deployment artifact.
## Initial design & future scaling
 
My first instinct was a persistent, queue-backed pipeline that stored the input and output
of every stage for a full audit trail — valuable in a regulated clinical context. On
re-reading the brief I scoped this back: the spec is stateless (one document per request,
JSON out, nothing to persist), so a stateless service is the correct fit and keeps the
focus on parsing and sentence-generation correctness. The fuller design is where I'd take
this under real load:
 
**Minimal next step** — a single Postgres table storing each request's filename, a content
hash, timestamp, and the generated output (`JSONB`). This gives an audit trail and lets a
repeat upload of the same file be served from cache rather than re-parsed.
 
**Full production shape** — persist input and output as early as possible at each stage:
 
- User uploads file + compound names.
- The API forwards the job to a message queue (e.g. Redis).
- The file is given a UUID and uploaded to cloud storage under that key.
- On successful upload, a row is written with the UUID and timestamp.
- A task executor (e.g. a Celery worker) parses the document and writes the extracted data
  back, linked by UUID.
- A further step generates the sentences, stores the output, and returns it.
This persists the input and output of each step, leaving an audit trail end to end, and
moves the CPU-bound work off the request path so the API stays responsive and the
processing scales horizontally across workers.