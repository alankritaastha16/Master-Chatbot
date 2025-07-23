# app2.py

import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import logging
import json
import traceback

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Make sure these imports are correct based on your project structure
from connector_loader import load_connectors

# Initialize OpenAI client (ensure this happens after env variables are loaded)
from openai import OpenAI
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize OpenAI client: {e}")
    traceback.print_exc()
    client = None

app = Flask(__name__)

# Define and configure UPLOAD_FOLDER directly
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global variables for connectors, tools, and the RAG handler instance
connectors = {}
llm_tools = []
rdf_rag_handler_instance = None
detected_ontology_types_global = []
loaded_ontology_prefixes_global = {}

def initialize_app_data():
    """
    Initializes connectors and tools. This function is called once on app startup.
    """
    global connectors, llm_tools, rdf_rag_handler_instance
    connectors, llm_tools, rdf_rag_handler_instance = load_connectors()
    logger.info("Application data (connectors, tools, RAG handler) initialized.")

initialize_app_data()

ALLOWED_EXTENSIONS = {'ttl', 'owl', 'rdf', 'xml'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/upload-ontology', methods=['POST'])
def upload_ontology():
    global connectors, llm_tools, rdf_rag_handler_instance, detected_ontology_file

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file."}), 400
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        detected_ontology_file = file_path # Update the global path to the current ontology

        try:
            # --- START OF FIX ---
            # Call load_connectors to re-initialize everything with the new file
            connectors, llm_tools, rdf_rag_handler_instance = load_connectors(ontology_file_path=file_path)

            # Check if RDFConnector successfully loaded the graph
            if "rdf_connector" in connectors and connectors["rdf_connector"].graph:
                message = f"Ontology '{filename}' uploaded and loaded successfully!"
                logger.info(message)
                return jsonify({"status": "success", "message": message, "file_name": filename})
            else:
                error_message = f"Failed to load ontology graph from '{filename}'. Please check logs for details."
                logger.error(error_message)
                return jsonify({"status": "error", "message": error_message}), 500
            # --- END OF FIX ---

        except Exception as e:
            logger.error(f"Error processing uploaded file: {e}")
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"An error occurred while processing the file: {e}"}), 500
    
    return jsonify({"status": "error", "message": "Unexpected error during file upload."}), 500



@app.route('/connect-databases', methods=['POST'])
def connect_databases():
    logger.info("Connect to Databases endpoint hit (placeholder).")
    try:
        data = request.json
        graph_db_url = data.get('graphDbUrl')
        nosql_db_url = data.get('nosqlDbUrl')
        nosql_db_name = data.get('nosqlDbName')
        nosql_db_collection = data.get('nosqlDbCollection')

        response_messages = []

        if not response_messages:
            return jsonify({"message": "No database types selected or no URLs provided. (Connection logic not fully implemented yet.)"}), 200

        return jsonify({"message": "\n".join(response_messages)}), 200

    except Exception as e:
        logger.error(f"Error connecting to databases: {e}")
        traceback.print_exc()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route('/chat', methods=['POST'])
def handle_chat():
    global connectors, llm_tools, rdf_rag_handler_instance

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({"response": "No message provided."}), 400

        messages = [
            {"role": "system", "content": """You are a helpful assistant specialized in understanding and querying knowledge graphs.
            You have access to tools that allow you to:
            1. Retrieve information from an uploaded ontology file using Retrieval Augmented Generation (RAG).
            2. Execute SPARQL queries directly on the uploaded RDF graph.

            Always try to use the provided tools to answer questions about the ontology, its classes, properties, and instances.
            If a question is about the structure or content of the ontology, use the appropriate tool.
            If a tool call fails, inform the user that the information could not be retrieved.
            
            Here are the prefixes for the ontology:
            PREFIX dvt: <https://graph.bmwgroup.net/Ontology/DigitalVehicleTwinOntology-1.0/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX sh: <http://www.w3.org/ns/shacl#>
            PREFIX dct: <http://purl.org/dc/terms/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            """},
            {"role": "user", "content": user_message}
        ]

        logger.info(f"User message: {user_message}")

        # Add tools to the LLM call
        if not llm_tools:
            current_ontology_path = detected_ontology_file if 'detected_ontology_file' in globals() else None
            _, llm_tools, _ = load_connectors(ontology_file_path=current_ontology_path)
            logger.info("Re-loaded connectors and tools in handle_chat as they were not populated.")

        tool_specs = [{"type": "function", "function": tool["function"]} for tool in llm_tools]

        response_llm = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tool_specs,
            tool_choice="auto",
            temperature=0.0
        )

        response_message = response_llm.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            logger.info(f"--- LLM called a tool ---")
            logger.info(f"Tool Calls: {tool_calls}")

            # Append the assistant's tool_calls message to the messages list
            messages.append(response_message)

            # --- CRITICAL FIX START: Handle multiple tool calls ---
            tool_responses_for_llm = [] # List to collect all tool outputs
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                current_tool_response = "No tool response." # Default for current tool
                
                if tool_name == "query_text_with_rag":
                    if rdf_rag_handler_instance and rdf_rag_handler_instance.vector_store:
                        try:
                            query_text = json.loads(tool_args).get("query_text")
                            k = json.loads(tool_args).get("k", 4)
                            current_tool_response = rdf_rag_handler_instance.query_text(query_text, k)
                        except Exception as e:
                            logger.error(f"Error executing RAG tool '{tool_name}': {e}")
                            current_tool_response = f"Error executing RAG tool: {e}"
                    else:
                        current_tool_response = "Error: RAG handler or vector store not initialized. Please ensure an ontology is uploaded."
                elif tool_name == "query_uploaded_rdf_graph":
                    if "rdf_connector" in connectors and connectors["rdf_connector"].graph:
                        try:
                            sparql_query = json.loads(tool_args).get("sparql_query")
                            current_tool_response = connectors["rdf_connector"].execute_query(sparql_query)
                        except Exception as e:
                            logger.error(f"Error executing SPARQL tool '{tool_name}': {e}")
                            current_tool_response = f"Error executing SPARQL tool: {e}"
                    else:
                        current_tool_response = "Error: RDF graph not loaded or connector not initialized. Please ensure an ontology is uploaded."
                else:
                    current_tool_response = f"Unknown tool: {tool_name}"

                logger.info(f"Tool '{tool_name}' executed (ID: {tool_call.id}). Response: {current_tool_response}")

                # Append each tool's response to the list
                tool_responses_for_llm.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(current_tool_response) if isinstance(current_tool_response, (list, dict)) else str(current_tool_response)
                })
            # --- CRITICAL FIX END ---

            # Append all collected tool responses to the messages list
            messages.extend(tool_responses_for_llm)


            logger.info(f"--- Sending Tool Outputs to LLM for Final Response Generation ---")
            final_response_llm = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.0
            )
            final_answer = final_response_llm.choices[0].message.content
            logger.info(f"--- Final Answer Generated ---")
            logger.info(f"Answer: {final_answer}")

            return jsonify({"response": final_answer})

        else:
            logger.info("LLM did not call a tool, generating direct response.")
            return jsonify({"response": response_message.content})

    except Exception as e:
        logger.error(f"An error occurred during chat processing: {e}")
        traceback.print_exc()
        return jsonify({"response": f"An error occurred: {e}"}), 500
if __name__ == '__main__':
    app.run(debug=True)