from rdflib import Graph
import os

graph = Graph()

def load_graph(file_path):
    graph.parse(file_path, format='turtle' if file_path.endswith('.ttl') else 'xml')

def run_query(sparql_query):
    return graph.query(sparql_query)
