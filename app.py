from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_login import LoginManager
from medications import medications_bp
from auth import auth_bp, User  # Import the User class from auth.py
from camera import capture_image, store_image, retrieve_image, upload_image
import firebase_admin
from firebase_admin import credentials, auth  # Import auth from firebase_admin
import os
import logging
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')

# Initialize Firebase Admin SDK
cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json')

try:
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    logging.info("Firebase Admin SDK initialized successfully.")
except FileNotFoundError:
    logging.error(f"Credential file not found at: {cred_path}")
    raise
except Exception as e:
    logging.error(f"An error occurred while initializing Firebase Admin SDK: {e}")
    raise

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # Redirect to login view if unauthorized

# Load user callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        user = auth.get_user(user_id)  # Fetch user from Firebase
        return User(user.uid, user.email)  # Create User instance
    except Exception as e:
        logging.error(f"Error loading user: {e}")
        return None

# Register the blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')  # Prefix for auth routes
app.register_blueprint(medications_bp)

# Route to capture an image
@app.route('/capture', methods=['POST'])
def capture():
    prescriptions_date = request.json.get('date')
    if not prescriptions_date:
        return jsonify({"success": False, "message": "Date is required!"}), 400

    image_data = capture_image()
    if image_data:
        store_image(prescriptions_date, image_data)
        return jsonify({"success": True, "message": "Prescriptions image uploaded successfully!"}), 201
    else:
        logging.error("Failed to capture image.")
        return jsonify({"success": False, "message": "Failed to capture image."}), 500

# Route to upload an image from a specified file path
@app.route('/upload', methods=['POST'])
def upload():
    prescriptions_date = request.json.get('date')
    file_path = request.json.get('file_path')
    if not prescriptions_date or not file_path:
        return jsonify({"success": False, "message": "Date and file path are required!"}), 400

    image_data = upload_image(file_path)
    if image_data:
        store_image(prescriptions_date, image_data)
        return jsonify({"success": True, "message": "Prescriptions image uploaded successfully!"}), 201
    else:
        logging.error("Failed to upload image.")
        return jsonify({"success": False, "message": "Failed to upload image."}), 500

# Route to retrieve an image based on the date
@app.route('/retrieve/<date>', methods=['GET'])
def retrieve(date):
    retrieved_image_data = retrieve_image(date)
    logging.info(f"Retrieved image data type: {type(retrieved_image_data)}")

    if isinstance(retrieved_image_data, bytes):
        base64_image = base64.b64encode(retrieved_image_data).decode('utf-8')
        return jsonify({"success": True, "data": base64_image}), 200
    else:
        logging.warning(f"No image found for the date: {date}.")
        return jsonify({"success": False, "message": "No image found for the specified date."}), 404

# Route for password reset
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({"success": False, "message": "Email is required!"}), 400

    try:
        firebase_admin.auth.send_password_reset_email(email)
        return jsonify({"success": True, "message": "Password reset email sent!"}), 200
    except Exception as e:
        logging.error(f"Error sending password reset email: {e}")
        return jsonify({"success": False, "message": "Failed to send password reset email."}), 500

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