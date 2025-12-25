from flask import Flask, request, jsonify
from flask_cors import CORS
import argparse

# Initialize the Flask app
app = Flask(__name__)
CORS(app)

# Define your routes AFTER initializing `app`
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "API is running"})

@app.route("/query", methods=["POST"])
def query():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Query is missing"}), 400
    return jsonify({"message": f"Received query: {query}"})

# Entry point for the script
if __name__ == "__main__":
    # Use argparse to allow specifying a port dynamically
    parser = argparse.ArgumentParser(description="Run the Flask API Gateway")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the Flask server on")
    args = parser.parse_args()

    try:
        app.run(host="0.0.0.0", port=args.port)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Port {args.port} is already in use. Please use a different port.")
        else:
            raise
