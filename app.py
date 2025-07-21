from flask import Flask, request, jsonify, send_from_directory, session
from connector_loader import load_connectors
import openai
import os
import json
from connectors.rdf_connector import RDFConnector

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling
connectors, tools = load_connectors()

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def ensure_prefixes(query):
    prefixes = [
        "PREFIX : <http://example.org#>",
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>",
        #"PREFIX dbo: <http://dbpedia.org/ontology>"
    ]
    for prefix in prefixes:
        if prefix not in query:
            query = prefix + "\n" + query

    # Basic validation: Ensure the query contains SELECT or ASK
    if not any(keyword in query.upper() for keyword in ["SELECT", "ASK"]):
        raise ValueError("Invalid SPARQL query. Must contain SELECT or ASK.")
    return query

def call_connector(tool, query):
    global uploaded_ontology_path
    try:
        if tool == "query_sparql":
            if not uploaded_ontology_path:
                return "No ontology file uploaded. Please upload an ontology file first."

            # Dynamically load the ontology
            rdf_connector = RDFConnector(uploaded_ontology_path)
            query = ensure_prefixes(query)
            results = rdf_connector.execute_query(query)
            return "; ".join(results) if results else "No matches found."
        elif tool == "query_mongo":
            if 'MongoConnector' in connectors:
                results = connectors['MongoConnector'].execute_query(query)
                return "; ".join(results) if results else "No service history found."
            else:
                return "MongoDB connector not available."
        else:
            return "Unknown tool selected."
    except Exception as e:
        return f"Error processing query: {str(e)}"

@app.route("/")
def index():
    return send_from_directory("static", "chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    question = request.json["question"]
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "system", "content": "You are a federated chatbot that can query RDF (SPARQL) and MongoDB databases. Use the right tool for each question."},
            {"role": "user", "content": question}
        ],
        tools=tools,
        tool_choice="auto",
        temperature=0,
        max_tokens=200
    )
    choice = response.choices[0]
    if choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        query = args.get("sparql_query") or args.get("mongo_query")
        result = call_connector(tool_name, query)
        
        # Enhance: Ask LLM to summarize results in natural language
        nl_response = openai.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Given a user's question and database results, answer in natural language."},
                {"role": "user", "content": f"Question: {question}\nResults: {result}\nPlease answer in natural language."}
            ],
            temperature=0.7,
            max_tokens=150
        )
        answer = nl_response.choices[0].message.content.strip()
    else:
        answer = choice.message.content

    return jsonify({"answer": answer})

uploaded_ontology_path = None  # Global variable to store the ontology path

@app.route('/upload', methods=['POST'])
def upload_ontology():
    global uploaded_ontology_path
    if 'ontology' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['ontology']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith('.ttl'):
        return jsonify({"error": "Invalid file type. Please upload a .ttl file"}), 400

    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        uploaded_ontology_path = file_path  # Save the file path globally
        return jsonify({"message": "Ontology uploaded successfully!", "file_path": file_path}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to upload ontology: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

