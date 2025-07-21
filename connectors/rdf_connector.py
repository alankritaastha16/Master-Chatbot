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
        var_names = results.vars
        output = []
        for row in results:
            # Try to get 'car' if present, else use the first variable
            value = None
            if 'car' in var_names:
                idx = var_names.index('car')
                value = row[idx]
            else:
                value = row[0] if len(row) > 0 else None
            if value:
                output.append(str(value).split('#')[-1])
        return output
