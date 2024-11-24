import cv2
import base64
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Initialize Firebase Admin SDK
cred = credentials.Certificate(r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

def capture_image():
    """Capture an image from the device camera and return it as a base64 string."""
    camera = cv2.VideoCapture(0)

    try:
        if not camera.isOpened():
            raise RuntimeError("Error: Could not open camera.")

        ret, frame = camera.read()
        if not ret:
            raise RuntimeError("Error: Failed to capture image.")

        # Encode the image as JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        image_data = base64.b64encode(buffer).decode('utf-8')  # Convert to base64 string
        return image_data

    finally:
        camera.release()  # Ensure the camera is released

def upload_image(file_path):
    """Upload an image from a file and return its base64 representation."""
    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return None

    with open(file_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
        return image_data

def store_image(date, image_data):
    """Store the captured image in Firestore under the given date."""
    try:
        db.collection('prescriptions').document(date).set({
            'image': image_data,
            'date': date
        })
        print(f"Image stored successfully for date: {date}")
    except Exception as e:
        print(f"Error storing image: {e}")

def retrieve_image(date):
    """Retrieve the image stored in Firestore for the given date."""
    try:
        doc = db.collection('prescriptions').document(date).get()
        if doc.exists:
            data = doc.to_dict()
            return data['image']
        else:
            print(f"No prescriptions found for date: {date}")
            return None
    except Exception as e:
        print(f"Error retrieving image: {e}")
        return None