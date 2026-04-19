# Rooted

Rooted is a chatbot that uses retrieval augmented generation to serve accurate information for those in need.

i.e. yet another LLM wrapper for a hackathon (for social good!)

[presentation slide](./img/rooted-presentation.pdf)

Submission by Will Orban, Matias Toro, and Max Ficco for the 2026 Hesburgh Library Hackathon.

# Demos



# To Reproduce:

###### 1. Download repository and requirements
```bash
git clone git@github.com:rooted-hud/rooted
python -m venv .venv
pip install -r requirements.txt
cd backend/
```

###### 2. Scrape website data (e.g. [hud.gov/helping-americans](https://www.hud.gov/helping-americans))
```bash
./scraper.py https://www.hud.gov/helping-americans -d 2
```
This does a graph traversal from the webpage (to a depth of 2) and converts all `.html` and `.pdf` files to `.md`.

Use `-o ./path/` to specify an output folder.

###### 3. Concatenate text, recursively split text into chunks, and embed chunks into the chromaDB vector database.
```bash
./rag.py ./www.hud.gov
```
We used Gemini 2.5 Flash and gemini-embedding-001. Make sure to supply an API token as `GEMINI_API_TOKEN=` in your `.env` file.

###### 4. Start the API
```bash
uvicorn api:app --port 8000
```
Make sure to change `const API_URL = ` in `script.js` to the appropriate address (or `localhost:8000/chat`)

To host the website locally, run `python -m http.server 3000` at the root of the repository and go to `localhost:3000`!

