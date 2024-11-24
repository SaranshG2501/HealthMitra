from flask import Blueprint, request, jsonify
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import time

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

import firebase_admin
from firebase_admin import messaging

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
    response = messaging.send(message)
    print('Successfully sent message:', response)

@medications_bp.route('/add_medication', methods=['POST'])
def add_medication():
    # Get the input data from the request
    data = request.get_json()  # Ensure you are getting the JSON data from the request

    # Validate input data
    if not all(k in data for k in ('name', 'dosage', 'reminder_times', 'frequency')):
        return jsonify({'message': 'Missing required fields!'}), 400

    medication = {
        'name': data['name'],
        'dosage': data['dosage'],
        'reminder_times': data['reminder_times'],  # Get reminder_times directly from data
        'frequency': data['frequency'],
        'next_reminder': None
    }

    # Calculate the next reminder time
    try:
        if medication['frequency'] == 'daily':
            medication['next_reminder'] = datetime.now().replace(
                hour=int(medication['reminder_times']['daily'].split(':')[0]), 
                minute=int(medication['reminder_times']['daily'].split(':')[1]), 
                second=0, 
                microsecond=0) + timedelta(days=1)

        elif medication['frequency'] == 'weekly':
            next_reminders = []
            for day in WEEKDAYS:
                if day in medication['reminder_times']:
                    reminder_time = medication['reminder_times'][day]
                    hour, minute = map(int, reminder_time.split(':'))
                    next_reminder = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # If the reminder time has already passed for today, schedule for next week
                    if next_reminder < datetime.now():
                        next_reminder += timedelta(weeks=1)

                    next_reminders.append(next_reminder)

            # Set the next reminder to the earliest one
            medication['next_reminder'] = min(next_reminders)

        elif medication['frequency'] == 'specific':
            medication['next_reminder'] = datetime.strptime(data['specific_time'], '%Y-%m-%d %H:%M:%S')
        else:
            return jsonify({'message': 'Invalid frequency!'}), 400

        # Schedule the reminder with a unique ID
        job_id = f"{medication['name']}_{int(time.time())}"  # Create a unique job ID
        scheduler.add_job(func=send_reminder, trigger='date', run_date=medication['next_reminder'], args=[medication], id=job_id)

        # Save medication to Firestore
        user_id = request.headers.get('Authorization')  # Assuming you pass the user ID in the Authorization header
        if not user_id:
            return jsonify({'message': 'User  ID not found in Authorization header!'}), 401

        medication_ref = db.collection('medications').document()  # Auto-generate document ID
        medication['user_id'] = user_id  # Add user_id to medication
        medication_ref.set(medication)

    except Exception as e:
        return jsonify({'message': f'Error scheduling reminder: {str(e)}'}), 500

    return jsonify({'message': 'Medication added successfully!', 'medication': medication}), 201
    ...

@medications_bp.route('/update_medication/<string:name>', methods=['PUT'])
def update_medication(name):
    data = request .json
    user_id = request.headers.get('Authorization')  # Assuming you pass the user ID in the Authorization header

    # Fetch the medication document
    medication_ref = db.collection('medications').where('user_id', '==', user_id).where('name', '==', name).limit(1).stream()

    medication_doc = None
    for med in medication_ref:
        medication_doc = med.reference

    if not medication_doc:
        return jsonify({'message': 'Medication not found!'}), 404

    # Update medication fields
    updated_fields = {}
    if 'dosage' in data:
        updated_fields['dosage'] = data['dosage']
    if 'reminder_time' in data:
        updated_fields['reminder_time'] = data['reminder_time']
    if 'frequency' in data:
        updated_fields['frequency'] = data['frequency']

    # Calculate the next reminder time if the frequency or reminder time has changed
    if 'frequency' in data or 'reminder_time' in data:
        if 'frequency' in data:
            updated_fields['frequency'] = data['frequency']
        if 'reminder_time' in data:
            updated_fields['reminder_time'] = data['reminder_time']

        # Recalculate next reminder based on updated frequency
        try:
            if updated_fields['frequency'] == 'daily':
                updated_fields['next_reminder'] = datetime.now().replace(hour=int(updated_fields['reminder_time'].split(':')[0]),
                                                                         minute=int(updated_fields['reminder_time'].split(':')[1]),
                                                                         second=0,
                                                                         microsecond=0) + timedelta(days=1)
            elif updated_fields['frequency'] == 'weekly':
                updated_fields['next_reminder'] = datetime.now().replace(hour=int(updated_fields['reminder_time'].split(':')[0]),
                                                                         minute=int(updated_fields['reminder_time'].split(':')[1]),
                                                                         second=0,
                                                                         microsecond=0) + timedelta(weeks=1)
            elif updated_fields['frequency'] == 'specific':
                updated_fields['next_reminder'] = datetime.strptime(data['specific_time'], '%Y-%m-%d %H:%M:%S')
            else:
                return jsonify({'message': 'Invalid frequency!'}), 400

            # Reschedule the reminder with a unique ID
            job_id = f"{updated_fields['name']}_{int(time.time())}"  # Create a unique job ID
            scheduler.add_job(func=send_reminder, trigger='date', run_date=updated_fields['next_reminder'], args=[updated_fields], id=job_id)

        except Exception as e:
            return jsonify({'message': f'Error scheduling reminder: {str(e)}'}), 500

    # Update the medication document in Firestore
    medication_doc.update(updated_fields)

    return jsonify({'message': 'Medication updated successfully!', 'updated_fields': updated_fields}), 200

@medications_bp.route('/medications', methods=['GET'])
def get_medications():
    user_id = request.headers.get('Authorization')  # Assuming you pass the user ID in the Authorization header
    medications_ref = db.collection('medications').where('user_id', '==', user_id).stream()
    
    medications = []
    for med in medications_ref:
        medications.append(med.to_dict())

    return jsonify(medications), 200

@medications_bp.route('/delete_medication/<string:name>', methods=['DELETE'])
def delete_medication(name):
    user_id = request.headers.get('Authorization')  # Assuming you pass the user ID in the Authorization header
    medications_ref = db.collection('medications').where('user_id', '==', user_id).where('name', '==', name).limit(1).stream()

    for med in medications_ref:
        med.reference.delete()  # Delete the medication document

    return jsonify({'message': 'Medication deleted successfully!'}), 200

@medications_bp.route('/all_medications', methods=['GET'])
def get_all_medications():
    medications_ref = db.collection('medications').stream()
    
    medications = []
    for med in medications_ref:
        medications.append(med.to_dict())

    return jsonify(medications), 200