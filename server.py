import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from services import TaskService

app = Flask(__name__)
# Enable CORS for cross-origin local testing if needed
CORS(app)

DB_FILE = "db.json"
SEED_FILE = "gemini-code-1780008469746.json"

task_service = TaskService(DB_FILE)

# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def initialize_database():
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        print(f"[{DB_FILE}] not found or empty. Initializing empty database...")
        try:
            with open(DB_FILE, "w") as f:
                json.dump({"tasks": [], "history": []}, f, indent=2)
            print("Database initialized empty.")
        except Exception as e:
            print(f"Critical error during database initialization: {e}")

# ==========================================
# API ROUTE CONTROLLERS
# ==========================================

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"
    try:
        tasks = task_service.get_all_tasks(include_deleted)
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    try:
        task = task_service.get_task_by_id(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
def create_task():
    try:
        task_data = request.json
        if not task_data or not task_data.get("title"):
            return jsonify({"error": "Missing required field: title"}), 400
            
        created = task_service.create_task(task_data)
        return jsonify(created), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    try:
        update_data = request.json
        if not update_data:
            return jsonify({"error": "No update fields provided"}), 400
            
        updated = task_service.update_task(task_id, update_data)
        return jsonify(updated), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    try:
        deleted = task_service.delete_task(task_id)
        return jsonify(deleted), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/restore", methods=["POST"])
def restore_task(task_id):
    try:
        restored = task_service.restore_task(task_id)
        return jsonify(restored), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<task_id>/history", methods=["GET"])
def get_task_history(task_id):
    try:
        history = task_service.get_task_history(task_id)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_database():
    try:
        task_service.reset_database()
        return jsonify({"message": "Database reset completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    initialize_database()
    # Run server locally on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
