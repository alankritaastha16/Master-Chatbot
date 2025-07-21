# KG-Chatbot (Local RDF/SPARQL Chatbot)

This project is a simple chatbot that allows users to upload RDF/Turtle files and ask natural language questions that are answered using SPARQL queries on an in-memory RDF graph.

## Features

- 📁 Upload your own `.ttl` or `.rdf` file
- 💬 Ask natural language questions like “Which vehicles have faulty engines?”
- 🧠 Uses pattern-matched or LLM-based SPARQL generation
- 🗃 Powered entirely by Python (`rdflib`, `flask`) — no external triple store required

## Quickstart

### 🧰 Requirements

- Python 3.7+
- Pip

### 🚀 Run Locally

```bash
git clone <repo>
cd kg-chatbot
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

### 📂 Files

- `graph_handler.py`: Loads & queries RDF files
- `app.py`: Flask backend
- `static/index.html`: Chatbot UI + upload form
- `uploads/`: Where uploaded files are stored
- `sample_data.ttl`: Sample RDF to get started

## 📌 To Do

- [ ] Add GPT-based SPARQL generation
- [ ] Answer refinement with templates
- [ ] Session memory

---
Made with ❤️ for local KG exploration.
