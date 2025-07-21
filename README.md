# KG-Chatbot Federated

This is a modular chatbot framework that supports federated querying over multiple data sources such as RDF files, MongoDB, and external APIs.

## 🚀 Features

- 🧩 Plug-in based connector system (`BaseConnector`)
- 🔀 Smart router that dispatches questions to the correct backend(s)
- 📡 Support for RDF (via SPARQL) and MongoDB (via PyMongo)
- 🌐 Simple Web UI for chat interaction
- 📁 Easily extensible to REST APIs, SQL, GraphDBs, etc.

---

## 📁 Project Structure

```
kg-chatbot-federated/
├── app.py
├── connector_loader.py
├── connectors/
│   ├── base.py
│   ├── mongo_connector.py
│   └── rdf_connector.py
├── router.py
├── sample_data.ttl
├── static/
│   └── index.html
├── uploads/
├── requirements.txt
└── README.md
```

---

## 🔧 Connectors

To add a new data source:

1. Create a new class in `connectors/` that extends `BaseConnector`.
2. Implement:
   - `can_answer(question)`
   - `generate_query(question)`
   - `execute_query(query)`

3. It will be auto-discovered and loaded at runtime.

---

## ⚙️ How to Run

### 🧰 Prerequisites

- Python 3.7+
- MongoDB running locally (if testing Mongo connector)

### ▶️ Start the App

```bash
pip install -r requirements.txt
python app.py
```

Visit [http://localhost:5000](http://localhost:5000)

---

## 📌 Example Questions

- "Which vehicles have faulty engines?" → answered from RDF
- "Show me service history" → answered from MongoDB

## 🧠 Planned Extensions

- OpenAI/GPT-based dynamic SPARQL/SQL generator
- Chat history + session context
- Knowledge unification across source types

---

Enjoy building your federated KG chatbot!
