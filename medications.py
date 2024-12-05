from flask import Blueprint, request, jsonify
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import time
from firebase_admin import messaging
import logging

# Create a Blueprint for medications
medications_bp = Blueprint('medications', __name__)

# Initialize Firebase Admin SDK if not already done
cred = credentials.Certificate(r'C:\Users\DELL\Desktop\Saransh\healthmitra-bbd5c-firebase-adminsdk-77wq5-39153a58a8.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Initialize the APScheduler
scheduler = APScheduler()
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

def send_reminder(medication):
    name = medication['name']
    dosage = medication['dosage']
    user_fcm_token = medication.get('user_fcm_token')  # Get the user's FCM token

    # Create a message to send
    message = messaging.Message(
        notification=messaging.Notification(
            title='Medication Reminder',
            body=f"It's time to take your medication '{name}' with dosage '{dosage}'."
        ),
        token=user_fcm_token,
    )

    # Send the message
    try:
        response = messaging.send(message)
        logging.info('Successfully sent message: %s', response)
    except Exception as e:
        logging.error(f"Failed to send message: {str(e)}")

def calculate_next_reminder(medication):
    """Calculate the next reminder time based on frequency and reminder times."""
    now = datetime.now()
    
    if medication['frequency'] == 'daily':
        reminder_time = medication['reminder_times']['daily']
        hour, minute = map(int, reminder_time.split(':'))
        next_reminder = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_reminder < now:
            next_reminder += timedelta(days=1)
        return next_reminder

    elif medication['frequency'] == 'weekly':
        next_reminders = []
        for day in WEEKDAYS:
            if day in medication['reminder_times']:
                reminder_time = medication['reminder_times'][day]
                hour, minute = map(int, reminder_time.split(':'))
                next_reminder = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_reminder < now:
                    next_reminder += timedelta(weeks=1)
                next_reminders.append(next_reminder)
        return min(next_reminders) if next_reminders else None

    elif medication['frequency'] == 'specific':
        return datetime.strptime(medication['reminder_times']['specific'], '%Y-%m-%d %H:%M:%S')

    return None

@medications_bp.route('/add_medication', methods=['POST'])
def add_medication():
    # Get the input data from the request
    data = request.get_json()

    # Validate input data
    required_fields = ('name', 'dosage', 'reminder_times', 'frequency')
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields!'}), 400

    medication = {
        'name': data['name'],
        'dosage': data['dosage'],
        'reminder_times': data['reminder_times'],
        'frequency': data['frequency'],
        'next_reminder': None,
        'user_email': data.get('user_email')  # Optional: Store user email if provided
    }

    # Calculate the next reminder time
    try:
        medication['next_reminder'] = calculate_next_reminder(medication)
        if medication['next_reminder'] is None:
            return jsonify({'message': 'Invalid frequency or reminder times!'}), 400

        # Schedule the reminder with a unique ID
        job_id = f"{medication['name']}_{int(time.time())}"  # Create a unique job ID
        scheduler.add_job(func=send_reminder, trigger='date', run_date=medication['next_reminder'], args=[medication], id=job_id)

        # Save medication to Firestore
        medication_ref = db.collection('medications').document()  # Auto-generate document ID
        medication_ref.set(medication)

    except Exception as e:
        logging.error(f"Error scheduling reminder: {str(e)}")
        return jsonify ({'message': f'Error scheduling reminder: {str(e)}'}), 500

    return jsonify({'message': 'Medication added successfully!', 'medication': medication}), 201

@medications_bp.route('/get_medications', methods=['GET'])
def get_medications():
    # Retrieve medications from Firestore
    try:
        medications_ref = db.collection('medications').stream()
        medications = [{**med.to_dict(), 'id': med.id} for med in medications_ref]
    except Exception as e:
        logging.error(f"Error retrieving medications: {str(e)}")
        return jsonify({'message': f'Error retrieving medications: {str(e)}'}), 500

    return jsonify({'medications': medications}), 200

@medications_bp.route('/delete_medication/<medication_id>', methods=['DELETE'])
def delete_medication(medication_id):
    # Delete medication from Firestore
    try:
        medication_ref = db.collection('medications').document(medication_id)
        medication_ref.delete()
    except Exception as e:
        logging.error(f"Error deleting medication: {str(e)}")
        return jsonify({'message': f'Error deleting medication: {str(e)}'}), 500

    return jsonify({'message': 'Medication deleted successfully!'}), 200

# Register the blueprint
def register_medications_bp(app):
    app.register_blueprint(medications_bp, url_prefix='/medications')