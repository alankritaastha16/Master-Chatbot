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
    global uploaded_file_info
    try:
        # Ensure a file has been uploaded
        if not uploaded_file_info:
            return "No file uploaded. Please upload a file first."

        file_path = uploaded_file_info.get("path")
        file_format = uploaded_file_info.get("format")

        # Decide the connector based on file format
        if file_format == '.ttl':  # RDF Turtle file
            rdf_connector = RDFConnector(file_path)
            query = ensure_prefixes(query)
            results = rdf_connector.execute_query(query)
            return "; ".join(results) if results else "No matches found."
        elif file_format == '.json':  # JSON file
            # Implement a JSON connector (example placeholder)
            return "JSON connector not implemented yet."
        elif file_format == '.csv':  # CSV file
            # Implement a CSV connector (example placeholder)
            return "CSV connector not implemented yet."
        else:
            return "Unsupported file format."
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

uploaded_file_info = {}  # Global dictionary to store file path and format

@app.route('/upload', methods=['POST'])
def upload_ontology():
    if 'ontology' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['ontology']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        return jsonify({"message": "File uploaded successfully!", "file_path": file_path}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to upload file: {str(e)}"}), 500

@app.route('/connect', methods=['POST'])
def connect_database():
    data = request.json
    graph_db_url = data.get('graphDbUrl')
    mongo_db_url = data.get('mongoDbUrl')

    connections = {}

    try:
        # Connect to Graph Database
        if graph_db_url:
            # Placeholder for actual graph database connection logic
            connections['graph_db'] = f"Connected to Graph Database at {graph_db_url}"

        # Connect to MongoDB
        if mongo_db_url:
            # Placeholder for actual MongoDB connection logic
            connections['mongo_db'] = f"Connected to MongoDB at {mongo_db_url}"

        if not connections:
            return jsonify({"error": "No database connection details provided."}), 400

        return jsonify({"message": "Connected successfully!", "connections": connections}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to connect to database(s): {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

