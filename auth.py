from flask import Blueprint, request, jsonify
import firebase_admin
from firebase_admin import auth
from firebase_admin._auth_utils import UserNotFoundError
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, firestore

# Initialize Firebase Admin SDK if not already done
cred_path = r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json'
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Create a Blueprint for authentication
auth_bp = Blueprint('auth', __name__)

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
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required!"}), 400

    try:
        user = auth.get_user_by_email(email)
        # Note: Password verification should be done on the client-side
        # Here you would typically return a token or user data
        return jsonify({"success": True, "message": "User  authenticated successfully!", "user_id": user.uid}), 200
    except UserNotFoundError:
        return jsonify({"success": False, "message": "No user record found for the provided email!"}), 404
    except FirebaseError as e:
        return jsonify({"success": False, "message": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Protected resource route
@auth_bp.route('/protected', methods=['GET'])
def protected():
    token = request.headers.get('Authorization')
    if token:
        try:
            # Ensure to split and get the token part
            decoded_token = auth.verify_id_token(token.split(" ")[1])  
            uid = decoded_token['uid']
            return jsonify({'message': f'Welcome, {uid}!'}), 200
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
    else:
        return jsonify({'error': 'No token provided'}), 401