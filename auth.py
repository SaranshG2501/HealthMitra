from flask import Blueprint, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import firebase_admin
from firebase_admin import auth
from firebase_admin._auth_utils import UserNotFoundError
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, firestore
import logging

# Initialize Firebase Admin SDK if not already done
cred_path = r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json'  # Change to your path
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Create a Blueprint for authentication
auth_bp = Blueprint('auth', __name__)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "auth.login"  # Redirect to login view

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, uid, email):
        self.id = uid
        self.email = email

# Load user callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        user = auth.get_user(user_id)
        return User(user.uid, user.email)
    except UserNotFoundError:
        return None

# User registration function
def create_user(username, password, email):
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=username
        )
        # Store user information in Firestore
        user_ref = db.collection('users').document(user.uid)
        user_ref.set({
            'username': username,
            'email': email
        })
        return user.uid
    except auth.EmailAlreadyExistsError:
        return {"error": "The email address is already in use."}
    except Exception as e:
        return {"error": f"Error creating user: {str(e)}"}

# User registration route
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not username or not password or not email:
        return jsonify({"success": False, "message": "Username, password, and email are required!"}), 400

    user_id = create_user(username, password, email)
    if isinstance(user_id, str):  # Check if user_id is a string (valid UID)
        return jsonify({"success": True, "message": "User  registered successfully!", "user_id": user_id}), 201
    else:  # user_id is an error message
        return jsonify({"success": False, "message": user_id['error']}), 400

# User login route
@auth_bp.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    # Validate input
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required!"}), 400

    try:
        # Authenticate the user with Firebase
        user = auth.get_user_by_email(email)
        
        # Note: Password verification should be handled via the Firebase Client SDK on the frontend.
        # If you're using Firebase Admin SDK, you cannot verify the password here.
        # You should typically authenticate on the client side and send the ID token to your backend.

        return jsonify({
            "success": True,
            "message": "Login successful!",
            "user_id": user.uid,
            "email": user.email
        }), 200

    except auth.UserNotFoundError:
        logging.warning(f"User  not found: {email}")
        return jsonify({"success": False, "message": "User  not found."}), 404

    except Exception as e:
        logging.error(f"Error during login: {e}")
        return jsonify({"success": False, "message": "An error occurred during login."}), 500

# Protected resource route
@auth_bp.route('/protected', methods=['GET'])
@login_required
def protected():
    return jsonify({'message': f'Welcome, {current_user.email}!'}), 200

# User logout route
@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()  # Log the user out using Flask-Login
    return jsonify({"success": True, "message ": "User  logged out successfully!"}), 200

# Password reset route
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({"success": False, "message": "Email is required!"}), 400

    try:
        auth.send_password_reset_email(email)
        return jsonify({"success": True, "message": "Password reset email sent!"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to send password reset email: {str(e)}"}), 500

# Error handler for 404 Not Found
@auth_bp.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Resource not found."}), 404

# Error handler for 500 Internal Server Error
@auth_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "An internal error occurred."}), 500