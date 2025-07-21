from flask import Flask, request, jsonify, send_from_directory
from connectors.rdf_connector import RDFConnector
from connectors.mongo_connector import MongoConnector

app = Flask(__name__)

# Instantiate connectors
rdf = RDFConnector('sample_data.ttl')
mongo = MongoConnector()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/ask", methods=["POST"])
def ask():
    question = request.json["question"]
    results = []

    for connector in [rdf, mongo]:
        if connector.can_answer(question):
            query = connector.generate_query(question)
            data = connector.execute_query(query)
            results.extend(data)

    if not results:
        return jsonify({"answer": "No data found or unsupported question."})

    return jsonify({"answer": "; ".join(results)})

if __name__ == "__main__":
    app.run(debug=True)
