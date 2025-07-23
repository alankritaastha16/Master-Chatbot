# connector_loader.py

import os
import json
import traceback
import logging
from abc import ABC, abstractmethod
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, SH

from pymongo import MongoClient
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Set up logging for connector_loader
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


# --- Debugging: Check OpenAI API Key loading in connector_loader ---
try:
    openai_api_key_status = bool(os.getenv("OPENAI_API_KEY"))
    logger.debug(f"DEBUG (connector_loader): OPENAI_API_KEY loaded status: {openai_api_key_status}")
    if not openai_api_key_status:
        logger.warning("WARNING (connector_loader): OPENAI_API_KEY is not set. Embedding models might fail.")
except Exception as e:
    logger.error(f"ERROR (connector_loader): Could not check OPENAI_API_KEY: {e}")
# --- End Debugging ---


class BaseConnector(ABC):
    """Abstract base class for all database connectors."""
    @abstractmethod
    def connect(self, config):
        pass

    @abstractmethod
    def execute_query(self, query):
        pass


class RDFConnector(BaseConnector):
    def __init__(self, config=None):
        self.graph = Graph()
        self.config = config
        self.initNs = {} # NEW: Initialize dictionary to store initial namespaces

    def connect(self, file_path=None):
        """
        Connects to the RDF graph by loading the ontology file.
        Returns True on success, False on failure.
        """
        # Clear existing graph and namespaces before loading a new one
        self.graph = Graph()
        self.initNs = {}

        if file_path and os.path.exists(file_path):
            try:
                self.graph.parse(file_path)
                logger.info(f"RDF graph loaded from {file_path}")

                # NEW: Populate initNs with common prefixes and bind them to the graph
                self.initNs = {
                    "dvt": URIRef("https://graph.bmwgroup.net/Ontology/DigitalVehicleTwinOntology-1.0/"),
                    "rdf": RDF,
                    "rdfs": RDFS,
                    "owl": OWL,
                    "sh": SH,
                    "dct": URIRef("http://purl.org/dc/terms/"),
                    "xsd": URIRef("http://www.w3.org/2001/XMLSchema#"),
                    "skos": URIRef("http://www.w3.org/2004/02/skos/core#"),
                    # Add any other prefixes you expect to be used in queries
                }
                for prefix, uri in self.initNs.items():
                    self.graph.bind(prefix, uri)

            except Exception as e:
                logger.error(f"Error loading RDF graph from {file_path}: {e}")
                traceback.print_exc()
                self.graph = None # Ensure graph is None on failure
                return False
        else:
            logger.warning("WARNING: Ontology file path not provided or file does not exist.")
            self.graph = None # No graph loaded
            return False
        return True

    def execute_query(self, query):
        """
        Executes a SPARQL query on the loaded RDF graph.
        Returns query results.
        """
        if not self.graph:
            logger.error("ERROR: RDF graph is not loaded. Cannot execute query.")
            return []
        try:
            # NEW: Pass initNs to the query method
            results = self.graph.query(query, initNs=self.initNs)
            
            # Format results for readability
            formatted_results = []
            for row in results:
                row_dict = {}
                for var, value in row.asdict().items():
                    # Check if value is a URIRef and shorten it if possible
                    if isinstance(value, URIRef):
                        # Attempt to shorten URIRefs using bound namespaces
                        shortened = False
                        for prefix, uri in self.initNs.items():
                            if str(value).startswith(str(uri)):
                                value = f"{prefix}:{str(value)[len(str(uri)):]}"
                                shortened = True
                                break
                        if not shortened:
                            value = str(value) # Fallback to full URI if not shortened
                    else:
                        value = str(value) # Convert Literals/BNode to string
                    row_dict[str(var)] = value
                formatted_results.append(row_dict)
            
            logger.info(f"SPARQL query executed. Results: {formatted_results}")
            return formatted_results
        except Exception as e:
            logger.error(f"ERROR in RDFConnector execute_query: {e}")
            traceback.print_exc()
            return []

class RAGHandler:
    def __init__(self, rdf_connector: RDFConnector = None, embeddings_model=None):
        self.rdf_connector = rdf_connector
        self.vector_store = None
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY is not set. RAG embeddings may fail.")

    def initialize_vector_store(self, ontology_file_path: str = None):
        """
        Initializes the vector store from the ontology file.
        This method will replace any existing vector store.
        """
        if not ontology_file_path or not os.path.exists(ontology_file_path):
            logger.warning("WARNING: Ontology file path is not provided or file does not exist. Skipping vector store initialization.")
            self.vector_store = None
            return

        try:
            logger.info(f"Initializing vector store from {ontology_file_path}...")
            loader = TextLoader(ontology_file_path)
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                is_separator_regex=False,
            )
            texts = text_splitter.split_documents(documents)
            
            # Create a new Chroma vector store from the documents
            self.vector_store = Chroma.from_documents(texts, self.embeddings_model)
            logger.info("Vector store initialized successfully.")
        except Exception as e:
            logger.error(f"ERROR: Cannot initialize vector store: {e}")
            traceback.print_exc()
            self.vector_store = None # Ensure vector store is None on failure

    def query_text(self, query: str, k: int = 4):
        """
        Queries the vector store for text relevant to the input query.
        Returns a list of relevant document snippets.
        """
        if not self.vector_store:
            logger.warning("RAG vector store is not initialized. Cannot perform text query.")
            return "RAG vector store is not initialized. Please upload an ontology file first."
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            # Format docs to include page_content and metadata.source
            formatted_docs = []
            for doc in docs:
                formatted_docs.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                })
            logger.info(f"RAG query for '{query}' returned {len(formatted_docs)} documents.")
            return formatted_docs
        except Exception as e:
            logger.error(f"ERROR in RAGHandler query_text: {e}")
            traceback.print_exc()
            return f"Error during RAG query: {e}"

def load_connectors(ontology_file_path: str = None):
    """
    Initializes and returns configured connectors and LLM tools based on the provided ontology file path.
    """
    configured_connectors = {}
    llm_tools = []
    rdf_rag_handler = None

    logger.info(f"Attempting to load connectors with ontology_file_path: {ontology_file_path}")

    # Initialize RDFConnector
    rdf_connector = RDFConnector()
    if rdf_connector.connect(file_path=ontology_file_path): # Pass file_path here
        configured_connectors["rdf_connector"] = rdf_connector
    else:
        logger.warning("WARNING: RDF connector not initialized as ontology failed to load.")

    # Initialize RAGHandler (and its vector store)
    # Ensure embeddings_model is passed if needed, or initialized within RAGHandler
    rdf_rag_handler = RAGHandler(rdf_connector=rdf_connector)
    rdf_rag_handler.initialize_vector_store(ontology_file_path=ontology_file_path)

    # Define tools only if their underlying handlers are successfully initialized
    # Tool for RAG
    if rdf_rag_handler and rdf_rag_handler.vector_store:
        llm_tools.append({
            "type": "function",
            "function": {
                "name": "query_text_with_rag",
                "description": "Retrieve information from the uploaded ontology based on natural language queries using Retrieval Augmented Generation (RAG). This is useful for understanding concepts, descriptions, or relationships described in the ontology.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_text": {
                            "type": "string",
                            "description": "The natural language query to retrieve context for."
                        },
                        "k": {
                            "type": "integer",
                            "description": "The number of top relevant documents to retrieve (default is 4). Max is 10."
                        }
                    },
                    "required": ["query_text"]
                }
            }
        })
        logger.debug("DEBUG (connector_loader): RAG tool added.")
    else:
        logger.warning("WARNING: RAG tool not added as RDF RAG handler or its vector store failed to initialize.")

    # Tool for SPARQL queries
    if "rdf_connector" in configured_connectors and configured_connectors["rdf_connector"].graph:
        llm_tools.append({
            "type": "function",
            "function": {
                "name": "query_uploaded_rdf_graph",
                "description": "Execute a SPARQL query directly on the previously uploaded RDF ontology file. Use this for precise queries about classes, properties, relationships, and instances. Ensure you use the correct prefixes (like dvt:, rdf:, rdfs:, owl:) provided in the system prompt. Always provide the full SPARQL query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sparql_query": {
                            "type": "string",
                            "description": "The SPARQL query string to execute on the uploaded graph. E.g., 'SELECT DISTINCT ?class WHERE { ?class a owl:Class }'"
                        }
                    },
                    "required": ["sparql_query"]
                }
            }
        })
        logger.debug("DEBUG (connector_loader): SPARQL query tool added.")
    else:
        logger.warning("WARNING: SPARQL query tool not added as RDF graph is not loaded.")
        
    logger.debug("DEBUG (connector_loader): Tools defined.")
    return configured_connectors, llm_tools, rdf_rag_handler