from connectors.base import BaseConnector
from pymongo import MongoClient

class MongoConnector(BaseConnector):
    def __init__(self, uri='mongodb://localhost:27017', db_name='vehicles'):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def can_answer(self, question: str) -> bool:
        return "service history" in question.lower()

    def generate_query(self, question: str) -> str:
        return "{}"  # Simple filter for all records

    def execute_query(self, query: str) -> list:
        results = self.db.service_logs.find()
        return [f"{r['vehicle_id']} serviced on {r['date']}" for r in results]
