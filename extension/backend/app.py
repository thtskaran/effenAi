# app.py
import os
import base64
import json
import time
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, session # Added session
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
import requests # For direct API calls
from openai import OpenAI # Use the official OpenAI library

from config import Config
from models import db, Company, Employee, Document, ActionPlan, Action, Status, Priority

# --- Flask App Setup ---
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
CORS(app, supports_credentials=True, origins=["chrome-extension://YOUR_EXTENSION_ID"]) # Allow requests from your extension ID
app.secret_key = Config.SECRET_KEY # Needed for session management if used

# --- OpenAI Client Setup ---
try:
    openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    openai_client = None

# --- In-memory buffer for audio chunks (SIMPLE, NOT FOR PRODUCTION) ---
# For production use Redis, a proper file system strategy, or blob storage
recording_buffers = {}

# --- Helper Functions ---
def get_google_user_info(credentials):
    """Fetches user info from Google using credentials."""
    try:
        user_info_service = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        if user_info_service.status_code == 200:
            return user_info_service.json()
        else:
            print(f"Error fetching user info: {user_info_service.status_code} {user_info_service.text}")
            return None
    except Exception as e:
        print(f"Exception fetching user info: {e}")
        return None

def process_audio_and_generate_plan(employee_id, recording_id, audio_file_path):
    """
    Synchronous function to transcribe audio, generate summary/plan, and save.
    WARNING: This will block the request. Move to background tasks in production.
    """
    if not openai_client:
        print("OpenAI client not available.")
        return False, "OpenAI client not configured"

    print(f"Processing audio for recording {recording_id}...")
    start_time = time.time()

    try:
        # 1. Transcribe using Whisper
        print(f"Transcribing {audio_file_path}...")
        with open(audio_file_path, "rb") as audio_data:
             # Use the v2 api
            transcription_response = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_data
                # language="en" # Optional: Specify language
            )
        transcript = transcription_response.text # Correct attribute is 'text'
        print(f"Transcription complete (took {time.time() - start_time:.2f}s). Length: {len(transcript)} chars.")
        if not transcript:
            print("Transcription failed or produced empty text.")
            return False, "Transcription failed"

        # 2. Generate Summary and Action Plan using GPT-4o
        print("Generating summary and action plan with GPT-4o...")
        summary_start_time = time.time()

        # Define the desired JSON structure for the action plan
        # Make sure enum values match your Priority and Status enums
        json_format_description = """
        {
          "action_plan_title": "Concise Title of the Meeting Action Plan",
          "summary": "A brief summary of the meeting discussion.",
          "actions": [
            {
              "action_title": "Specific Action Item 1",
              "description": "Optional details about the action.",
              "due_date": "YYYY-MM-DDTHH:MM:SS or null",
              "priority": "LOW | MEDIUM | HIGH",
              "status": "PENDING | IN_PROGRESS | COMPLETED"
            },
            {
              "action_title": "Specific Action Item 2",
              "priority": "MEDIUM",
               "status": "PENDING"
            }
            // ... more actions
          ]
        }
        """

        prompt = f"""
        Given the following meeting transcript, please perform the following tasks:
        1.  Provide a concise summary of the key discussion points and decisions made.
        2.  Identify specific, actionable tasks or follow-ups mentioned.
        3.  For each action item, determine a suitable title, priority (LOW, MEDIUM, HIGH), initial status (usually PENDING), and due date if explicitly mentioned or clearly implied (use YYYY-MM-DDTHH:MM:SS format or null if not specified).
        4.  Format the entire output STRICTLY as a single JSON object matching the structure below. Do NOT include any text outside the JSON structure.

        Desired JSON Structure:
        {json_format_description}

        Meeting Transcript:
        ---
        {transcript}
        ---
        """

        chat_completion = openai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert meeting assistant. Your task is to summarize transcripts and extract structured action plans in JSON format."},
                {"role": "user", "content": prompt}
            ],
            model="gpt-4o", # Or "gpt-4-turbo" etc.
            response_format={"type": "json_object"}, # Request JSON output
            temperature=0.5 # Adjust creativity/determinism
        )

        gpt_response_content = chat_completion.choices[0].message.content
        print(f"GPT-4o response received (took {time.time() - summary_start_time:.2f}s).")

        # 3. Parse GPT Response and Save to DB
        try:
            plan_data = json.loads(gpt_response_content)
            print("Successfully parsed GPT-4o JSON response.")

            # Find the employee
            employee = Employee.query.get(employee_id)
            if not employee:
                 print(f"Employee not found for ID: {employee_id}")
                 return False, "Employee not found"

            # Create ActionPlan
            new_action_plan = ActionPlan(
                title=plan_data.get("action_plan_title", f"Meeting Summary {datetime.now().strftime('%Y-%m-%d')}"),
                description=plan_data.get("summary", "No summary provided."),
                # Assuming default urgency/priority if not specified, or parse if included
                startDate=datetime.utcnow(),
                employeeId=employee_id
                # Set other fields like urgency, priority based on overall sentiment if needed
            )
            db.session.add(new_action_plan)
            # Need to flush to get the ID for actions
            db.session.flush()

            # Create Actions
            for action_item in plan_data.get("actions", []):
                due_date = None
                if action_item.get("due_date"):
                    try:
                        # Attempt to parse different date/datetime formats flexibility
                         due_date = datetime.fromisoformat(action_item["due_date"].replace('Z', '+00:00'))
                    except ValueError:
                        try:
                            due_date = datetime.strptime(action_item["due_date"], "%Y-%m-%d")
                        except ValueError:
                           print(f"Warning: Could not parse due date '{action_item['due_date']}'")


                new_action = Action(
                    title=action_item.get("action_title", "Untitled Action"),
                    description=action_item.get("description"),
                    dueDate=due_date,
                    priority=Priority[action_item.get("priority", "MEDIUM").upper()], # Map string to Enum
                    status=Status[action_item.get("status", "PENDING").upper()],     # Map string to Enum
                    actionPlanId=new_action_plan.id
                )
                db.session.add(new_action)

            db.session.commit()
            print(f"Action plan and actions saved successfully for recording {recording_id}.")
            return True, "Processing successful"

        except json.JSONDecodeError as e:
            print(f"Error parsing GPT-4o JSON response: {e}")
            print(f"Raw response content:\n{gpt_response_content}")
            # Optionally save the raw transcript and response for debugging
            return False, "Failed to parse AI response"
        except KeyError as e:
             print(f"Missing key in GPT-4o JSON response: {e}")
             print(f"Parsed data: {plan_data}")
             return False, f"Missing key in AI response: {e}"
        except Exception as e:
            db.session.rollback()
            print(f"Error saving action plan to DB: {e}")
            return False, "Database error while saving action plan"

    except Exception as e:
        print(f"Error during audio processing for {recording_id}: {e}")
        return False, f"An error occurred during processing: {e}"
    finally:
        # 4. Cleanup temporary file
        try:
            os.remove(audio_file_path)
            print(f"Removed temporary audio file: {audio_file_path}")
        except OSError as e:
            print(f"Error removing temporary file {audio_file_path}: {e}")
        # Also remove the entry from the buffer dictionary
        if recording_id in recording_buffers:
            del recording_buffers[recording_id]


# --- API Routes ---

@app.route('/')
def index():
    return jsonify({"message": "Meeting Assistant Backend is running!"})

@app.route('/auth/google/callback', methods=['POST'])
def google_callback():
    """Handles the OAuth callback from the Chrome extension."""
    data = request.get_json()
    if not data or 'code' not in data or 'redirectUri' not in data:
        return jsonify({"success": False, "error": "Missing code or redirectUri"}), 400

    auth_code = data['code']
    redirect_uri = data['redirectUri'] # Use the one sent by the extension

    try:
        # Use Flow to exchange code for credentials
        # Note: Load client secrets from the file specified in Config
        flow = Flow.from_client_secrets_file(
            Config.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=Config.GOOGLE_SCOPES,
            redirect_uri=redirect_uri)

        # Exchange authorization code for credentials
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials # Contains access_token, refresh_token, etc.

        if not credentials or not credentials.valid:
             return jsonify({"success": False, "error": "Failed to obtain valid credentials"}), 500

        # Get user info using the obtained credentials
        user_info = get_google_user_info(credentials)
        if not user_info or 'email' not in user_info:
            return jsonify({"success": False, "error": "Failed to fetch user info from Google"}), 500

        user_email = user_info['email']
        user_avatar = user_info.get('picture')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')

        # Find or create employee in DB
        employee = Employee.query.filter_by(email=user_email).first()

        if employee:
            # Update existing employee
            employee.refresh_token = credentials.refresh_token # Update refresh token
            employee.avatar = user_avatar
            employee.lastLogin = datetime.utcnow()
            print(f"Updated employee: {user_email}")
        else:
            # Create new employee (requires company association - how to determine?)
            # --- !!! IMPORTANT !!! ---
            # You need logic here to associate the employee with a Company.
            # This might involve:
            # 1. Assuming a default company.
            # 2. Having the user select a company during onboarding (not handled here).
            # 3. Matching email domain to a known company domain.
            # For now, we'll raise an error or assign to a default if one exists.
            # Let's assume a default company needs to be created or fetched first.
            # This part needs refinement based on your application's user/company structure.

            # --- Placeholder: Find or create a default company ---
            default_company = Company.query.filter_by(email="default@company.com").first()
            if not default_company:
                 # If no default company, maybe create one (or fail the login)
                 # default_company = Company(name="Default Company", email="default@company.com", password="HASHED_PASSWORD")
                 # db.session.add(default_company)
                 # db.session.flush() # Get ID
                 print("Error: Default company not found. Cannot create new employee.")
                 return jsonify({"success": False, "error": "Company setup required for new user"}), 500

            # You also need a placeholder password or a proper user creation flow
            placeholder_password = "DEFAULT_HASHED_PASSWORD" # Replace with actual hashing

            employee = Employee(
                email=user_email,
                firstName=first_name,
                lastName=last_name,
                password=placeholder_password, # Needs proper handling
                refresh_token=credentials.refresh_token,
                avatar=user_avatar,
                companyId=default_company.id, # Assign to default/found company
                lastLogin=datetime.utcnow()
            )
            db.session.add(employee)
            print(f"Created new employee: {user_email}")

        try:
            db.session.commit()
        except Exception as db_err:
             db.session.rollback()
             print(f"Database error during login: {db_err}")
             return jsonify({"success": False, "error": "Database error"}), 500


        # Return user info needed by the extension popup
        user_data_for_extension = {
            "email": employee.email,
            "firstName": employee.firstName,
            "lastName": employee.lastName,
            "avatarUrl": employee.avatar
            # Add other relevant fields if needed
        }

        return jsonify({"success": True, "user": user_data_for_extension})

    except FileNotFoundError:
         print(f"Error: Google client secrets file not found at {Config.GOOGLE_CLIENT_SECRETS_FILE}")
         return jsonify({"success": False, "error": "Server configuration error (OAuth secrets)"}), 500
    except Exception as e:
        print(f"Error during Google OAuth callback: {e}")
        # Consider logging the full traceback
        return jsonify({"success": False, "error": f"An unexpected error occurred: {e}"}), 500


@app.route('/audio/stream', methods=['POST'])
def audio_stream():
    """Receives audio chunks from the extension."""
    data = request.get_json()
    if not data or not all(k in data for k in ('userId', 'recordingId', 'chunk')):
        return jsonify({"success": False, "error": "Missing data"}), 400

    user_id = data['userId'] # This is likely the email
    recording_id = data['recordingId']
    base64_chunk = data['chunk']

    try:
        audio_chunk = base64.b64decode(base64_chunk)
    except Exception as e:
        print(f"Error decoding base64 chunk for {recording_id}: {e}")
        return jsonify({"success": False, "error": "Invalid base64 data"}), 400

    # --- Append chunk to temporary file ---
    # Use a consistent naming scheme, e.g., recordingId.webm
    file_path = os.path.join(Config.TEMP_AUDIO_DIR, f"{recording_id}.webm")

    try:
        mode = 'ab' if recording_id in recording_buffers else 'wb' # Append if exists, write if new
        with open(file_path, mode) as f:
            f.write(audio_chunk)

        # Mark that we have received data for this recording
        if recording_id not in recording_buffers:
             # Store metadata like user_id and start time if needed
            recording_buffers[recording_id] = {'user_id': user_id, 'file_path': file_path, 'status': 'receiving'}
            print(f"Started receiving audio for recording: {recording_id}")

        # print(f"Received chunk for {recording_id}, size: {len(audio_chunk)}") # Verbose
        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"Error writing audio chunk to file for {recording_id}: {e}")
        return jsonify({"success": False, "error": "Failed to save audio chunk"}), 500


@app.route('/audio/stream/end', methods=['POST'])
def audio_stream_end():
    """Signals the end of a recording and triggers processing."""
    data = request.get_json()
    if not data or not all(k in data for k in ('userId', 'recordingId')):
        return jsonify({"success": False, "error": "Missing data"}), 400

    user_id_email = data['userId'] # Email
    recording_id = data['recordingId']
    reason = data.get('reason', 'Unknown')

    print(f"Received end signal for recording {recording_id} from user {user_id_email}. Reason: {reason}")

    if recording_id not in recording_buffers:
        print(f"Warning: Received end signal for unknown or already processed recording {recording_id}")
        # Decide how to handle: maybe ignore, maybe still try to process if file exists
        return jsonify({"success": False, "error": "Recording ID not found or already processed"}), 404

    buffer_info = recording_buffers[recording_id]
    audio_file_path = buffer_info['file_path']

    # Find employee ID from email
    employee = Employee.query.filter_by(email=user_id_email).first()
    if not employee:
         print(f"Error: Employee not found for email {user_id_email} during end stream processing.")
         # Clean up buffer entry even if employee not found
         if recording_id in recording_buffers: del recording_buffers[recording_id]
         # Optionally try to delete the temp file
         try: os.remove(audio_file_path)
         except: pass
         return jsonify({"success": False, "error": "Associated employee not found"}), 404

    employee_id = employee.id

    # --- Trigger processing (Synchronously for now) ---
    # In production, enqueue this: celery_task.delay(employee_id, recording_id, audio_file_path)
    success, message = process_audio_and_generate_plan(employee_id, recording_id, audio_file_path)

    if success:
        return jsonify({"success": True, "message": "Recording ended and processing initiated."}), 200
    else:
        # Processing function handles cleanup. Buffer entry is removed there.
        return jsonify({"success": False, "error": f"Processing failed: {message}"}), 500


@app.route('/activity/log', methods=['POST'])
def activity_log():
    """Receives daily browsing activity log."""
    data = request.get_json()
    if not data or not all(k in data for k in ('userId', 'date', 'activity')):
        return jsonify({"success": False, "error": "Missing data"}), 400

    user_id_email = data['userId'] # Email
    log_date_str = data['date'] # Expected format 'YYYY-MM-DD'
    activity_data = data['activity'] # Should be a list of dicts

    # Validate activity data structure (basic check)
    if not isinstance(activity_data, list):
         return jsonify({"success": False, "error": "Invalid activity data format"}), 400

    # Find employee
    employee = Employee.query.filter_by(email=user_id_email).first()
    if not employee:
        print(f"Activity log received for unknown user: {user_id_email}")
        return jsonify({"success": False, "error": "Employee not found"}), 404

    try:
        # Update the browser_activity field.
        # This replaces the entire field with the new JSON array for that day.
        # If you need to append or store historically, the logic would change.
        employee.browser_activity = activity_data
        employee.updatedAt = datetime.utcnow() # Update timestamp

        db.session.commit()
        print(f"Updated activity log for {user_id_email} on {log_date_str}")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error saving activity log for {user_id_email}: {e}")
        return jsonify({"success": False, "error": "Database error saving activity log"}), 500


# --- Database Initialization Command ---
@app.cli.command("init-db")
def init_db():
    """Creates database tables from SQLAlchemy models."""
    print("Creating database tables...")
    db.create_all()
    print("Database tables created.")

# --- Main Execution ---
if __name__ == '__main__':
    # Create tables if they don't exist (for development)
    with app.app_context():
        # Uncomment the line below ONLY if you want tables created on every run
        # db.create_all()
        # You should ideally use Flask-Migrate for migrations in production
        pass # Use 'flask init-db' command instead

    # Use 0.0.0.0 to make it accessible on your network if needed
    app.run(host='0.0.0.0', port=5000, debug=True) # Turn off debug in production