from rdflib import Graph
from connectors.base import BaseConnector

class RDFConnector(BaseConnector):
    def __init__(self, ttl_path):
        self.graph = Graph()
        self.graph.parse(ttl_path, format='turtle')

    def can_answer(self, question: str) -> bool:
        return "faulty" in question.lower()

    def generate_query(self, question: str) -> str:
        return '''
        PREFIX : <http://example.org#>
        SELECT ?car WHERE {
            ?car a :Vehicle ;
                  :hasComponent ?c .
            ?c a :Component ;
               :isFaulty true .
        }
        '''

    def execute_query(self, query: str) -> list:
        results = self.graph.query(query)
        return [str(row['car'].split('#')[-1]) for row in results]
