from flask import Flask, request, jsonify
from flask_apscheduler import APScheduler
from medications import medications_bp  # Import the medications blueprint
from auth import auth_bp  # Import the auth blueprint
from camera import capture_image, store_image, retrieve_image, upload_image
import firebase_admin
from firebase_admin import credentials
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')  # Use environment variable for secret key

# Initialize Firebase Admin SDK
cred_path = r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json'

try:
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    logging.info("Firebase Admin SDK initialized successfully.")
except FileNotFoundError:
    logging.error(f"Credential file not found at: {cred_path}")
    raise  # Re-raise the exception after logging
except Exception as e:
    logging.error(f"An error occurred while initializing Firebase Admin SDK: {e}")
    raise  # Re-raise the exception after logging

# Register the blueprints
app.register_blueprint(auth_bp)  # Register authentication blueprint
app.register_blueprint(medications_bp)  # Register medications blueprint

# Route to capture an image
@app.route('/capture', methods=['POST'])
def capture():
    prescribtions_date = request.json.get('date')

    if not prescribtions_date:
        return jsonify({"success": False, "message": "Date is required!"}), 400

    # Capture the image
    image_data = capture_image()

    if image_data:
        # Store the image in Firestore
        store_image(prescribtions_date, image_data)
        return jsonify({"success": True, "message": "Prescriptions image uploaded successfully!"}), 201
    else:
        logging.error("Failed to capture image.")
        return jsonify({"success": False, "message": "Failed to capture image."}), 500

# Route to upload an image from a specified file path
@app.route('/upload', methods=['POST'])
def upload():
    prescribtions_date = request.json.get('date')
    file_path = request.json.get('file_path')

    if not prescribtions_date or not file_path:
        return jsonify({"success": False, "message": "Date and file path are required!"}), 400

    # Upload the image from the specified file path
    image_data = upload_image(file_path)

    if image_data:
        # Store the image in Firestore
        store_image(prescribtions_date, image_data)
        return jsonify({"success": True, "message": "Prescriptions image uploaded successfully!"}), 201
    else:
        logging.error("Failed to upload image.")
        return jsonify({"success": False, "message": "Failed to upload image."}), 500

# Route to retrieve an image based on the date
@app.route('/retrieve/<date>', methods=['GET'])
def retrieve(date):
    # Retrieve the image from Firestore
    retrieved_image_data = retrieve_image(date)
    if retrieved_image_data:
        return jsonify({"success": True, "data": retrieved_image_data}), 200
    else:
        logging.warning(f"No image found for the date: {date}.")
        return jsonify({"success": False, "message": "No image found for the specified date."}), 404

# Error handler for 404 Not Found
@app.errorhandler(404)
def not_found(error):
    logging.error("Resource not found.")
    return jsonify({"success": False, "message": "Resource not found."}), 404

# Error handler for 500 Internal Server Error
@app.errorhandler(500)
def internal_error(error):
    logging.error(f"An internal error occurred: {str(error)}")
    return jsonify({"success": False, "message": "An internal error occurred."}), 500

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
