class BaseConnector:
    def can_answer(self, question: str) -> bool:
        raise NotImplementedError

    def generate_query(self, question: str) -> str:
        raise NotImplementedError

    def execute_query(self, query: str) -> list:
        raise NotImplementedError
