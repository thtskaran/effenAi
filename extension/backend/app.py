# app.py
import os
import base64
import json
import time
import uuid
from datetime import datetime
import traceback

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
# Allow requests from any origin - Adjust in production for security
CORS(app, supports_credentials=True, origins="*")
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

# --- Ensure Temp Audio Directory Exists ---
if not os.path.exists(Config.TEMP_AUDIO_DIR):
    os.makedirs(Config.TEMP_AUDIO_DIR)
    print(f"Created temporary audio directory: {Config.TEMP_AUDIO_DIR}")


# --- Helper Functions ---
def get_google_user_info(credentials):
    """Fetches user info from Google using credentials."""
    try:
        user_info_service = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        user_info_service.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return user_info_service.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user info: {e}")
        # Consider logging response body if available: e.response.text
        return None
    except Exception as e:
        print(f"Unexpected exception fetching user info: {e}")
        return None

def generate_detailed_actions_and_workflow(summary, action_items):
    """
    Generates detailed action steps and mermaid workflow diagram from an action plan summary.
    """
    if not openai_client:
        print("OpenAI client not available.")
        return [], "", ""

    # Combine the summary and action items into a task description
    task_description = f"Summary: {summary}\n\nAction Items:\n"
    for item in action_items:
        task_description += f"- {item.get('action_title', 'Untitled Action')}: {item.get('description', '')}\n"

    try:
        # Create prompt based on actions.py format
        prompt = f"""
        Based on the following meeting summary and action items, please provide:

        1.  `action_plan`: A detailed, step-by-step action plan to complete the task. List steps clearly. Should be an array of strings.
        2.  `category_code`: A concise category code representing the type of work (e.g., 'TECH-DEV', 'ADMIN-REPORT', 'SALES-LEAD', 'HR-POLICY', 'MARKETING-CAMP', 'OPS-MAINT'). Choose the most appropriate code.
        3.  `mermaid_workflow`: Mermaid JS syntax (using 'graph TD;' for a top-down flowchart) visualizing the high-level workflow based on the action plan. Ensure the syntax is valid Mermaid JS.

        Task Details:
        {task_description}

        Format your response strictly as a JSON object with the keys 'action_plan' (an array of strings), 'category_code' (a string), and 'mermaid_workflow' (a string).
        """

        chat_completion = openai_client.chat.completions.create(
            messages=[
                # --- MODIFIED SYSTEM MESSAGE (More Explicit JSON instruction) ---
                {"role": "system", "content": "You are an expert workflow and action planning assistant. Generate detailed step-by-step plans and workflow diagrams. Your response MUST be a valid JSON object containing the keys 'action_plan', 'category_code', and 'mermaid_workflow'. Do not include any text outside the JSON structure."},
                {"role": "user", "content": prompt}
            ],
            model="gpt-4o", # Or your preferred model
            response_format={"type": "json_object"},
            temperature=0.7 # Adjust as needed
        )

        response_content = chat_completion.choices[0].message.content

        # Debugging: Print raw response before parsing
        print(f"Raw response from detailed action generation:\n{response_content}")

        response_data = json.loads(response_content)

        # Ensure action_plan is returned as a list, even if empty or missing
        action_plan_steps = response_data.get("action_plan", [])
        if not isinstance(action_plan_steps, list):
             print(f"Warning: 'action_plan' in response was not a list. Received: {type(action_plan_steps)}. Defaulting to empty list.")
             action_plan_steps = []

        category_code = response_data.get("category_code", "")
        mermaid_workflow = response_data.get("mermaid_workflow", "")

        return action_plan_steps, category_code, mermaid_workflow

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from detailed action generation: {e}")
        print(f"Raw response content that failed parsing:\n{response_content}")
        traceback.print_exc()
        return [], "", "" # Return default values on failure
    except Exception as e:
        print(f"Error generating detailed actions and workflow: {e}")
        # Print more detailed error information using traceback
        traceback.print_exc()
        return [], "", "" # Return default values on failure


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
    plan_data = {} # Initialize plan_data

    try:
        # 1. Transcribe using Whisper
        print(f"Transcribing {audio_file_path}...")
        if not os.path.exists(audio_file_path):
            print(f"Error: Audio file not found at {audio_file_path}")
            return False, "Audio file not found for processing"
        if os.path.getsize(audio_file_path) == 0:
             print(f"Error: Audio file {audio_file_path} is empty.")
             return False, "Audio file is empty"

        with open(audio_file_path, "rb") as audio_data:
             # Use the v2 api
            transcription_response = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_data
                # language="en" # Optional: Specify language
            )
        transcript = transcription_response.text # Correct attribute is 'text'
        print(f"Transcription complete (took {time.time() - start_time:.2f}s). Length: {len(transcript)} chars.")
        if not transcript or transcript.strip() == "":
            print("Transcription failed or produced empty/whitespace text.")
            # Decide if empty transcript means failure or just no actions
            # For now, let's treat it as success but log it, maybe no actions needed
            summary = "No speech detected or transcription produced empty text."
            actions = []
            plan_data = { # Create minimal plan_data
                "action_plan_title": f"Empty Transcript {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "summary": summary,
                "actions": actions
            }
            # Skip GPT-4o call if transcript is empty
            gpt_response_content = json.dumps(plan_data) # Mock GPT response for saving logic
            print("Skipping GPT-4o summary/action generation due to empty transcript.")

        else:
            # 2. Generate Summary and Action Plan using GPT-4o (only if transcript exists)
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

            Ensure your response is a valid JSON object.
            """

            chat_completion = openai_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert meeting assistant. Your task is to summarize transcripts and extract structured action plans in JSON format. Ensure your response is valid JSON."},
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
                 # Don't return yet, cleanup needs to happen in finally
                 raise ValueError(f"Employee not found for ID: {employee_id}")


            # --- Generate detailed actions and mermaid workflow ---
            # This call now happens *after* the main plan_data is parsed
            print("Generating detailed steps and workflow diagram...")
            detailed_steps, category_code, mermaid_workflow = generate_detailed_actions_and_workflow(
                plan_data.get("summary", ""),
                plan_data.get("actions", [])
            )
            # Note: category_code is generated but not currently saved to the DB model.
            print(f"Generated detailed steps ({len(detailed_steps)}), category '{category_code}', workflow length {len(mermaid_workflow)}")

            # --- Save to Database ---
            # Create ActionPlan with workflow field
            new_action_plan = ActionPlan(
                title=plan_data.get("action_plan_title", f"Meeting Summary {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                description=plan_data.get("summary", "No summary provided."),
                workflow=mermaid_workflow if mermaid_workflow else None,  # Store Mermaid code or None
                startDate=datetime.utcnow(),
                employeeId=employee_id
                # Set other fields like urgency, priority based on overall sentiment if needed
            )
            db.session.add(new_action_plan)
            # Need to flush to get the ID for actions
            db.session.flush()

            # Create Actions from the main 'actions' list
            for action_item in plan_data.get("actions", []):
                due_date = None
                due_date_str = action_item.get("due_date")
                if due_date_str:
                    try:
                        # Attempt ISO format first (more robust)
                        due_date = datetime.fromisoformat(str(due_date_str).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        try:
                            # Fallback to YYYY-MM-DD
                            due_date = datetime.strptime(str(due_date_str), "%Y-%m-%d")
                        except (ValueError, TypeError):
                           print(f"Warning: Could not parse due date '{due_date_str}' for action '{action_item.get('action_title')}'. Setting to null.")

                # Validate Priority and Status Enums
                priority_str = str(action_item.get("priority", "MEDIUM")).upper()
                status_str = str(action_item.get("status", "PENDING")).upper()

                try:
                    priority_enum = Priority[priority_str]
                except KeyError:
                    print(f"Warning: Invalid priority '{priority_str}' received. Defaulting to MEDIUM.")
                    priority_enum = Priority.MEDIUM

                try:
                    status_enum = Status[status_str]
                except KeyError:
                    print(f"Warning: Invalid status '{status_str}' received. Defaulting to PENDING.")
                    status_enum = Status.PENDING


                new_action = Action(
                    title=action_item.get("action_title", "Untitled Action"),
                    description=action_item.get("description"),
                    dueDate=due_date,
                    priority=priority_enum,
                    status=status_enum,
                    actionPlanId=new_action_plan.id
                )
                db.session.add(new_action)

            # Add the detailed steps as additional actions if they exist
            if detailed_steps: # detailed_steps is now guaranteed to be a list
                print(f"Adding {len(detailed_steps)} detailed steps as actions...")
                for i, step in enumerate(detailed_steps):
                    # Ensure step is a string before processing
                    step_text = str(step) if step is not None else ""
                    new_step = Action(
                        # Truncate title to avoid DB errors if step is very long
                        title=f"Step {i+1}: {step_text[:150]}..." if len(step_text) > 150 else f"Step {i+1}: {step_text}",
                        description=step_text, # Store the full step description
                        priority=Priority.MEDIUM, # Default priority for generated steps
                        status=Status.PENDING,    # Default status for generated steps
                        actionPlanId=new_action_plan.id,
                        # Consider linking these steps or adding sequence number if needed
                    )
                    db.session.add(new_step)

            db.session.commit()
            print(f"Action plan (ID: {new_action_plan.id}) with workflow and detailed steps saved successfully for recording {recording_id}.")
            return True, "Processing successful"

        except json.JSONDecodeError as e:
            db.session.rollback() # Rollback DB changes if JSON parsing fails
            print(f"Error parsing GPT-4o JSON response: {e}")
            print(f"Raw response content:\n{gpt_response_content}")
            traceback.print_exc()
            return False, "Failed to parse AI response"
        except KeyError as e:
             db.session.rollback() # Rollback DB changes if key is missing
             print(f"Missing key in GPT-4o JSON response: {e}")
             print(f"Parsed data attempt: {plan_data}")
             traceback.print_exc()
             return False, f"Missing key in AI response: {e}"
        except ValueError as e: # Catch specific errors like employee not found
             db.session.rollback()
             print(f"Value error during processing: {e}")
             traceback.print_exc()
             return False, str(e)
        except Exception as e:
            db.session.rollback() # Rollback on any other DB error
            print(f"Error saving action plan to DB: {e}")
            traceback.print_exc()
            return False, f"Database error while saving action plan: {str(e)}"

    except Exception as e:
        print(f"Error during audio processing pipeline for {recording_id}: {e}")
        traceback.print_exc()
        return False, f"An unexpected error occurred during processing: {str(e)}"

    finally:
        # 4. Cleanup temporary file and buffer entry regardless of success/failure
        if os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                print(f"Removed temporary audio file: {audio_file_path}")
            except OSError as e:
                print(f"Error removing temporary file {audio_file_path}: {e}")
        else:
            print(f"Temporary audio file {audio_file_path} not found for removal (already removed or error).")

        if recording_id in recording_buffers:
            del recording_buffers[recording_id]
            print(f"Removed buffer entry for recording {recording_id}")


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

    # --- Ensure Client Secrets File Exists ---
    if not os.path.exists(Config.GOOGLE_CLIENT_SECRETS_FILE):
         print(f"CRITICAL ERROR: Google client secrets file not found at {Config.GOOGLE_CLIENT_SECRETS_FILE}")
         return jsonify({"success": False, "error": "Server configuration error (OAuth secrets missing)"}), 500

    try:
        # Use Flow to exchange code for credentials
        flow = Flow.from_client_secrets_file(
            Config.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=Config.GOOGLE_SCOPES,
            redirect_uri=redirect_uri)

        # Exchange authorization code for credentials
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials # Contains access_token, refresh_token, etc.

        if not credentials or not credentials.valid:
             # Log credential details (excluding sensitive parts if necessary) for debugging
             print(f"Failed to obtain valid credentials. Credentials object: {credentials}")
             return jsonify({"success": False, "error": "Failed to obtain valid credentials from Google"}), 500

        # Check for refresh token specifically (important for long-term access)
        if not credentials.refresh_token:
            print("Warning: No refresh token received from Google. User might need to re-authenticate later.")
            # Decide if this is an error or just a warning depending on your app's needs

        # Get user info using the obtained credentials
        user_info = get_google_user_info(credentials)
        if not user_info or 'email' not in user_info:
            print(f"Failed to fetch user info. Credentials were valid: {credentials.valid}")
            return jsonify({"success": False, "error": "Failed to fetch user info from Google after successful auth"}), 500

        user_email = user_info['email']
        user_avatar = user_info.get('picture')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')

        # --- Database Interaction ---
        employee = Employee.query.filter_by(email=user_email).first()

        # Use a specific company ID (replace with your actual logic if needed)
        target_company_id = "27f32072-d75b-4d4f-ab5e-83ae10a7693a" # Hardcoded - consider making configurable

        if employee:
            # Update existing employee
            # Only update refresh_token if a new one was provided
            if credentials.refresh_token:
                 employee.refresh_token = credentials.refresh_token
            employee.avatar = user_avatar
            employee.lastLogin = datetime.utcnow()
            employee.updatedAt = datetime.utcnow() # Also update updatedAt

            # Ensure employee is associated with the target company if not already
            if not employee.companyId:
                employee.companyId = target_company_id
                print(f"Associated existing employee {user_email} with company {target_company_id}")

            print(f"Updated employee: {user_email}")
        else:
            # Create new employee
            # Generate a placeholder password (not used for Google login, but model might require it)
            # IMPORTANT: For direct login, implement proper password hashing (e.g., Werkzeug)
            secure_password_placeholder = uuid.uuid4().hex

            employee = Employee(
                email=user_email,
                firstName=first_name,
                lastName=last_name,
                password=secure_password_placeholder, # Placeholder
                refresh_token=credentials.refresh_token,
                avatar=user_avatar,
                companyId=target_company_id, # Assign to target company
                browser_activity=[], # Initialize JSONB array field
                lastLogin=datetime.utcnow(),
                createdAt=datetime.utcnow(),
                updatedAt=datetime.utcnow()
            )
            db.session.add(employee)
            print(f"Created new employee: {user_email} with company ID {target_company_id}")

        try:
            db.session.commit()
        except Exception as db_err:
             db.session.rollback()
             print(f"Database error during login/user update for {user_email}: {db_err}")
             traceback.print_exc()
             return jsonify({"success": False, "error": "Database error during user processing"}), 500


        # Return user info needed by the extension popup
        user_data_for_extension = {
            "email": employee.email,
            "firstName": employee.firstName,
            "lastName": employee.lastName,
            "avatarUrl": employee.avatar,
            "employeeId": employee.id # Send employee ID back if useful for extension
        }

        return jsonify({"success": True, "user": user_data_for_extension})

    except FileNotFoundError:
         # This error is critical and indicates a deployment issue.
         print(f"CRITICAL ERROR: Google client secrets file not found at {Config.GOOGLE_CLIENT_SECRETS_FILE}")
         return jsonify({"success": False, "error": "Server configuration error (OAuth secrets missing)"}), 500
    except Exception as e:
        print(f"Error during Google OAuth callback processing: {e}")
        traceback.print_exc()
        # Avoid leaking detailed internal errors to the client
        return jsonify({"success": False, "error": "An unexpected error occurred during authentication."}), 500


@app.route('/audio/stream', methods=['POST'])
def audio_stream():
    """Receives audio chunks from the extension."""
    data = request.get_json()
    # Robust check for required fields
    if not data or not isinstance(data, dict) or not all(k in data for k in ('userId', 'recordingId', 'chunk')):
        print(f"Invalid audio stream request data: {data}")
        return jsonify({"success": False, "error": "Missing or invalid data (requires userId, recordingId, chunk)"}), 400

    user_id = data['userId'] # This is likely the email
    recording_id = data['recordingId']
    base64_chunk = data['chunk']

    # Basic validation
    if not user_id or not recording_id or not base64_chunk:
         return jsonify({"success": False, "error": "userId, recordingId, and chunk cannot be empty"}), 400

    try:
        audio_chunk = base64.b64decode(base64_chunk)
    except (TypeError, ValueError) as e: # Catch specific base64 decoding errors
        print(f"Error decoding base64 chunk for {recording_id}: {e}")
        return jsonify({"success": False, "error": "Invalid base64 data"}), 400

    # --- Append chunk to temporary file ---
    file_path = os.path.join(Config.TEMP_AUDIO_DIR, f"{recording_id}.webm") # Assuming webm format

    try:
        # Use 'ab' (append binary) if the file exists, 'wb' (write binary) if it's new
        mode = 'ab' if os.path.exists(file_path) else 'wb'
        with open(file_path, mode) as f:
            f.write(audio_chunk)

        # Mark that we have received data for this recording in our simple buffer
        if recording_id not in recording_buffers:
            recording_buffers[recording_id] = {
                'user_id': user_id,
                'file_path': file_path,
                'status': 'receiving',
                'created_at': datetime.utcnow().isoformat() # Store creation time
            }
            print(f"Started receiving audio for recording: {recording_id} at {file_path}")

        # print(f"Received chunk for {recording_id}, size: {len(audio_chunk)}") # Verbose logging if needed
        return jsonify({"success": True, "message": "Chunk received"}), 200 # Use 200 OK for successful chunk receipt

    except IOError as e:
         print(f"Error writing audio chunk to file {file_path} for {recording_id}: {e}")
         traceback.print_exc()
         # Attempt to clean up buffer if writing fails mid-stream? Maybe not necessary.
         return jsonify({"success": False, "error": "Failed to save audio chunk due to I/O error"}), 500
    except Exception as e:
        print(f"Unexpected error handling audio chunk for {recording_id}: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": "Unexpected server error processing audio chunk"}), 500


@app.route('/audio/stream/end', methods=['POST'])
def audio_stream_end():
    """Signals the end of a recording and triggers processing."""
    data = request.get_json()
    if not data or not isinstance(data, dict) or not all(k in data for k in ('userId', 'recordingId')):
        print(f"Invalid audio stream end request data: {data}")
        return jsonify({"success": False, "error": "Missing or invalid data (requires userId, recordingId)"}), 400

    user_id_email = data['userId'] # Email
    recording_id = data['recordingId']
    reason = data.get('reason', 'Unknown') # Optional reason from client

    print(f"Received end signal for recording {recording_id} from user {user_id_email}. Reason: {reason}")

    if recording_id not in recording_buffers:
        print(f"Warning: Received end signal for unknown or already processed recording {recording_id}")
        # Check if file exists anyway - maybe processing failed previously?
        file_path_check = os.path.join(Config.TEMP_AUDIO_DIR, f"{recording_id}.webm")
        if os.path.exists(file_path_check):
             print(f"File {file_path_check} exists, but buffer entry missing. Potential previous error.")
             # Decide whether to attempt reprocessing or just report error
             # For now, report error as the state is inconsistent
             return jsonify({"success": False, "error": "Recording ID state inconsistent (file exists, buffer missing)"}), 409 # Conflict
        else:
             return jsonify({"success": False, "error": "Recording ID not found or already processed"}), 404

    buffer_info = recording_buffers[recording_id]
    audio_file_path = buffer_info['file_path']

    # --- Find Employee ---
    employee = Employee.query.filter_by(email=user_id_email).first()
    if not employee:
         print(f"Error: Employee not found for email {user_id_email} during end stream processing.")
         # Crucial: Clean up buffer and file even if employee not found to avoid orphans
         if recording_id in recording_buffers: del recording_buffers[recording_id]
         if os.path.exists(audio_file_path):
             try: os.remove(audio_file_path)
             except OSError as e: print(f"Error removing orphaned file {audio_file_path}: {e}")
         return jsonify({"success": False, "error": "Associated employee not found"}), 404 # Use 404

    employee_id = employee.id

    # --- Trigger processing (Synchronously for now) ---
    # In production, replace this with a background task queue (Celery, RQ, etc.)
    # e.g., process_audio_task.delay(employee_id, recording_id, audio_file_path)
    print(f"Triggering synchronous processing for {recording_id}...")
    buffer_info['status'] = 'processing' # Update status in buffer

    success, message = process_audio_and_generate_plan(employee_id, recording_id, audio_file_path)

    # Note: The process_audio_and_generate_plan function's finally block handles
    # removing the file and the buffer entry upon completion or error.

    if success:
        print(f"Processing successful for {recording_id}.")
        return jsonify({"success": True, "message": "Recording ended and processing completed."}), 200 # OK
    else:
        print(f"Processing failed for {recording_id}: {message}")
        # Status code 500 indicates a server-side processing error
        return jsonify({"success": False, "error": f"Processing failed: {message}"}), 500


@app.route('/audio/status/<recording_id>', methods=['GET'])
def audio_status(recording_id):
    """Check the status of a recording/transcription (using the simple buffer)."""
    # Basic validation
    if not recording_id:
        return jsonify({"status": "error", "message": "Recording ID is required"}), 400

    if recording_id in recording_buffers:
         buffer_info = recording_buffers[recording_id]
         return jsonify({
            "status": buffer_info.get('status', 'unknown'), # receiving, processing, unknown
            "user_id": buffer_info.get('user_id'),
            "created_at": buffer_info.get('created_at')
         }), 200
    else:
         # Check if an ActionPlan exists for this employee/recording pattern? (More complex)
         # For now, just indicate it's not in the active buffer. It might be completed or failed.
         # To know completion, you'd need to query the ActionPlan table based on some identifier
         # derived from recording_id if possible, or just say it's not actively processing.
        return jsonify({"status": "not_found_or_completed"}), 404


@app.route('/activity/log', methods=['POST'])
def activity_log():
    """Receives daily browsing activity log and stores as a Document."""
    data = request.get_json()
    if not data or not isinstance(data, dict) or not all(k in data for k in ('userId', 'date', 'activity')):
        print(f"Invalid activity log request data: {data}")
        return jsonify({"success": False, "error": "Missing or invalid data (requires userId, date, activity)"}), 400

    user_id_email = data['userId'] # Email
    log_date_str = data['date'] # Expected format 'YYYY-MM-DD'
    activity_data = data['activity'] # Should be a list of dicts

    # Validate activity data structure (basic check)
    if not isinstance(activity_data, list):
         return jsonify({"success": False, "error": "Invalid activity data format: 'activity' must be a list"}), 400

    # Validate date format
    try:
        log_date = datetime.strptime(log_date_str, "%Y-%m-%d").date() # Validate and get date object
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format: 'date' must be YYYY-MM-DD"}), 400


    # Find employee
    employee = Employee.query.filter_by(email=user_id_email).first()
    if not employee:
        print(f"Activity log received for unknown user: {user_id_email}")
        return jsonify({"success": False, "error": "Employee not found"}), 404 # Use 404

    try:
        # Create a new Document to store the activity log
        activity_document = Document(
            title=f"Activity Log - {log_date_str}",
            content=json.dumps(activity_data),  # Store the list as a JSON string in the text field
            type="ACTIVITY_LOG",                # Use a specific type identifier
            employeeId=employee.id,
            # Optional: You could store the specific date of the log if your Document model supports it
            # logDate=log_date, # Example if you add a Date field to Document model
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow()
        )
        db.session.add(activity_document)

        # Optionally update the employee's last activity timestamp if needed
        # employee.updatedAt = datetime.utcnow() # Can be redundant if only logging

        db.session.commit()

        print(f"Saved activity log document (ID: {activity_document.id}) for {user_id_email} on {log_date_str}")
        return jsonify({
            "success": True,
            "message": "Activity log saved successfully",
            "documentId": activity_document.id # Return ID of the created document
        }), 201 # Use 201 Created status code

    except Exception as e:
        db.session.rollback()
        print(f"Error saving activity log for {user_id_email}: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Database error saving activity log: {str(e)}"}), 500

# --- Database Initialization Command ---
@app.cli.command("init-db")
def init_db_command():
    """Creates database tables from SQLAlchemy models."""
    print("Creating database tables...")
    try:
        db.create_all()
        print("Database tables created successfully (if they didn't exist).")
        # You might want to seed initial data here too (e.g., default company)
    except Exception as e:
        print(f"Error creating database tables: {e}")
        traceback.print_exc()

# --- Main Execution ---
if __name__ == '__main__':
    # Create tables if they don't exist - use the command instead for better control
    # with app.app_context():
    #    db.create_all() # Generally avoid doing this on every run

    # Use 0.0.0.0 to make it accessible on your network
    # Turn off debug mode in production!
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)