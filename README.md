# Advatech AI Chatbot — Step 1: Knowledge Base Gathering

This is the first stage of the RAG chatbot: getting Postgres+pgvector running
and pulling raw content from Advatech sites into it.

## 1. Start Postgres + pgvector via Docker

Make sure Docker Desktop (or Docker in WSL) is running, then from this folder:

```bash
docker compose up -d
```

Check it's running:

```bash
docker ps
```

You should see `advatech_vector_db`. This creates the `pages` and `chunks`
tables automatically on first startup (via `db/init.sql`).

To confirm the tables exist:

```bash
docker exec -it advatech_vector_db psql -U advatech -d advatech_kb -c "\dt"
```

## 2. Set up your Python environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # WSL / Linux / Mac

pip install -r requirements.txt
```

Copy `.env.example` to `.env` — the DB values already match docker-compose.yml,
so you don't need to change anything yet (you'll add the Gemini key in the
next step).

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # WSL / Linux / Mac
```

## 3. Scrape a site

Create a text file with the URLs you want for one site (see
`scraper/urls_advaforecourt.example.txt` for the format — one URL per line).
For a real run you'll want the actual page list, ideally pulled from the
site's sitemap.xml if it has one.

```bash
cd scraper
python scrape_site.py --site advaforecourt --urls urls_advaforecourt.txt
```

Repeat for each site (stationery, main advatech site, etc.), using a
different `--site` name each time — that name is what lets the chatbot
later filter results to just the site the user is chatting from.

**Note:** if a site is heavily JS-rendered (content only appears after
JavaScript runs), `requests` won't see the real text. Let me know if that's
the case for any Advatech site and we'll swap in Playwright for those pages.

## 4. Chunk the scraped pages

```bash
cd ../processing
python chunker.py --site advaforecourt
# or, once every site is scraped:
python chunker.py --all
```

This splits each page's text into ~180-word overlapping chunks and stores
them in the `chunks` table, ready for embeddings in the next step.

## Sanity check

```bash
docker exec -it advatech_vector_db psql -U advatech -d advatech_kb \
  -c "SELECT site, count(*) FROM chunks GROUP BY site;"
```

You should see a chunk count per site.

---

**Next step:** generating embeddings with the Gemini API and filling in the
`embedding` column so we can do similarity search.
