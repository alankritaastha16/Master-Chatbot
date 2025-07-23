from flask import Flask, request, jsonify, send_from_directory, session
from connector_loader import load_connectors
import openai
import os
import json
from connectors.rdf_connector import RDFConnector
from openai import AsyncOpenAI

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling
connectors, tools = load_connectors()

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

uploaded_file_info = {}

def call_connector(tool_name, query):
    """
    Calls the appropriate connector based on the tool name and query.
    """
    if tool_name == "rdf_connector":
        connector = RDFConnector()
        return connector.query(query)
    # Add more connectors as needed
    return f"No connector found for tool: {tool_name}"

def read_uploaded_file(file_path):
    """Read the content of the uploaded file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@app.route("/")
def index():
    return send_from_directory("static", "chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        question = request.json.get("question", "")
        if not question:
            return jsonify({"error": "No question provided"}), 400

        # Check if a file has been uploaded
        if not uploaded_file_info.get('file_path'):
            return jsonify({"answer": "No file has been uploaded yet. Please upload a file first."}), 200

        # Validate file format
        file_path = uploaded_file_info['file_path']
        if not file_path.endswith('.ttl'):
            return jsonify({"answer": "The uploaded file format is not supported. Please upload a .ttl file."}), 200

        # Read the uploaded file content
        file_content = read_uploaded_file(file_path)
        if file_content.startswith("Error"):
            return jsonify({"answer": file_content}), 500

        # Debugging logs
        print(f"Question: {question}")
        print(f"File content: {file_content[:100]}")  # Print first 100 characters of the file content

        # Use the file content as context for the chatbot
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a federated chatbot that uses the uploaded ontology file as context to answer user questions."},
                {"role": "system", "content": f"Ontology file content:\n{file_content}"},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=200
        )
        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer})
    except Exception as e:
        print(f"Error in /chat endpoint: {str(e)}")  # Debugging log
        return jsonify({"error": f"An error occurred while processing the question: {str(e)}"}), 500

@app.route('/upload', methods=['POST'])
def upload_ontology():
    if 'ontology' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['ontology']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate file format
    if not file.filename.endswith('.ttl'):
        return jsonify({"error": "Unsupported file format. Please upload a .ttl file."}), 400

    try:
        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # Save the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Store file info globally
        uploaded_file_info['file_path'] = file_path
        uploaded_file_info['file_name'] = file.filename

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

