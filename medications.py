from flask import Blueprint, request, jsonify
from flask_apscheduler import APScheduler
from flask_login import current_user
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
        print('Successfully sent message:', response)
    except Exception as e:
        logging.error(f"Failed to send message: {str(e)}")

def calculate_next_reminder(medication):
    """Calculate the next reminder time based on frequency and reminder times."""
    if medication['frequency'] == 'daily':
        reminder_time = medication['reminder_times']['daily']
        hour, minute = map(int, reminder_time.split(':'))
        next_reminder = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_reminder < datetime.now():
            next_reminder += timedelta(days=1)
        return next_reminder

    elif medication['frequency'] == 'weekly':
        next_reminders = []
        for day in WEEKDAYS:
            if day in medication['reminder_times']:
                reminder_time = medication['reminder_times'][day]
                hour, minute = map(int, reminder_time.split(':'))
                next_reminder = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_reminder < datetime.now():
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
    if not all(k in data for k in ('name', 'dosage', 'reminder_times', 'frequency')):
        return jsonify({'message': 'Missing required fields!'}), 400

    medication = {
        'name': data['name'],
        'dosage': data['dosage'],
        'reminder_times': data['reminder_times'],
        'frequency': data['frequency'],
        'next_reminder': None,
        'user_email': current_user.email  # Ensure user is authenticated
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
        return jsonify({'message': f'Error scheduling reminder: {str(e)}'}), 500

    return jsonify({'message': 'Medication added successfully!', 'medication': medication}), 201

@medications_bp.route('/update_medication/<string:name>', methods=['PUT'])
def update_medication(name):
    data = request.get_json()

    if not data or 'dosage' not in data or 'reminder_times' not in data or 'frequency' not in data:
        return jsonify({'message': 'Missing required fields!'}), 400

    medication_ref = db.collection('medications').where('name', '==', name).where('user_email', '==', current_user.email).limit(1).get()

    if not medication_ref:
        return jsonify({'message': 'Medication not found!'}), 404

    medication_ref = medication_ref[0].reference

    try:
        medication_ref.update({
            'dosage': data['dosage'],
            'reminder_times': data['reminder_times'],
            'frequency': data['frequency']
        })
    except Exception as e:
        logging.error(f"Error updating medication: {str(e)}")
        return jsonify({'message': f'Error updating medication: {str(e)}'}), 500

    return jsonify({'message': 'Medication updated successfully!'}), 200

@medications_bp.route('/medications', methods=['GET'])
def get_medications():
    if not current_user.is_authenticated:
        return jsonify({'message': 'User  not authenticated!'}), 401

    user_email = current_user.email
    medications_ref = db.collection('medications').where('user_email', '==', user_email).stream()

    medications = []
    for med in medications_ref:
        medications.append(med.to_dict())

    return jsonify(medications), 200

@medications_bp.route('/delete_medication/<string:name>', methods=['DELETE'])
def delete_medication(name):
    medication_ref = db.collection('medications').where('name', '==', name).where('user_email', '==', current_user.email).limit(1).get()

    if not medication_ref:
        return jsonify({'message': 'Medication not found!'}), 404

    try:
        medication_ref[0].reference.delete()
    except Exception as e:
        logging.error(f"Error deleting medication: {str(e)}")
        return jsonify({'message': f'Error deleting medication: {str(e)}'}), 500

    return jsonify({'message': 'Medication deleted successfully!'}), 200