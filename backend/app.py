import os
import requests
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-4o"  # Using OpenAI's gpt-4o model

# --- Helper Function to call OpenAI API ---
def get_ai_plan(title, description, deadline, priority):
    """Calls the OpenAI API to generate the task plan."""
    if not OPENAI_API_KEY:
        return None, "OpenAI API key is not configured."

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    # --- Prompt Engineering ---
    # Carefully craft the prompt to guide the LLM
    prompt = f"""
    Analyze the following task details:
    Title: {title}
    Description: {description}
    Deadline: {deadline}
    Priority: {priority}

    Based on this information, generate a JSON response containing the following three fields ONLY:
    1.  `action_plan`: A detailed, step-by-step action plan to complete the task. List steps clearly.
    2.  `category_code`: A concise category code representing the type of work (e.g., 'TECH-DEV', 'ADMIN-REPORT', 'SALES-LEAD', 'HR-POLICY', 'MARKETING-CAMP', 'OPS-MAINT'). Choose the most appropriate code.
    3.  `mermaid_workflow`: Mermaid JS syntax (using 'graph TD;' for a top-down flowchart) visualizing the high-level workflow based on the action plan. Ensure the syntax is valid Mermaid JS.

    Output ONLY the JSON object, starting with {{ and ending with }}. Do not include any introductory text or explanations outside the JSON structure.

    Example JSON structure:
    {{
      "action_plan": [
        "Step 1: Understand the core requirement.",
        "Step 2: Break down the requirement into smaller sub-tasks.",
        "Step 3: Estimate time for each sub-task.",
        "Step 4: Execute sub-tasks.",
        "Step 5: Review and test the result.",
        "Step 6: Document the process and outcome."
      ],
      "category_code": "TECH-PROJECT",
      "mermaid_workflow": "graph TD;\\nA[Define Scope] --> B(Breakdown Tasks);\\nB --> C{{Execute Task 1}};\\nB --> D{{Execute Task 2}};\\nC --> E[Review];\\nD --> E;\\nE --> F[Final Delivery];"
    }}
    """

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}  # Request JSON output directly
        # Optional: Add parameters like max_tokens, temperature, etc.
        # "max_tokens": 1000,
        # "temperature": 0.7,
    }

    try:
        response = requests.post(
            OPENAI_API_URL,
            headers=headers,
            json=payload,
            timeout=60  # Add a timeout (in seconds)
        )
        
        # Handle rate limiting specifically
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            return None, f"Rate limit exceeded. Try again after {retry_after} seconds."
            
        response.raise_for_status()  # Raise an exception for other bad status codes

        api_response = response.json()

        # --- Extract the generated content ---
        # Check the structure of OpenAI's response
        if 'choices' in api_response and len(api_response['choices']) > 0:
            message = api_response['choices'][0].get('message', {})
            content_str = message.get('content')

            if not content_str:
                 return None, "Empty content received from OpenAI."

            # Attempt to parse the content string as JSON
            try:
                # The model should ideally return *only* the JSON string
                # due to the prompt and response_format.
                parsed_content = json.loads(content_str)

                # --- Validate the structure of the parsed JSON ---
                if not all(k in parsed_content for k in ["action_plan", "category_code", "mermaid_workflow"]):
                   return None, f"AI response missing required keys. Received: {parsed_content}"
                if not isinstance(parsed_content["action_plan"], list):
                    return None, f"AI response 'action_plan' is not a list. Received: {parsed_content['action_plan']}"
                if not isinstance(parsed_content["category_code"], str):
                     return None, f"AI response 'category_code' is not a string. Received: {parsed_content['category_code']}"
                if not isinstance(parsed_content["mermaid_workflow"], str):
                     return None, f"AI response 'mermaid_workflow' is not a string. Received: {parsed_content['mermaid_workflow']}"

                return parsed_content, None  # Success

            except json.JSONDecodeError:
                # If the AI didn't return valid JSON despite instructions
                print(f"Warning: AI response was not valid JSON:\n{content_str}")
                # Attempt a fallback (less reliable): try to find JSON within the string
                try:
                    json_start = content_str.find('{')
                    json_end = content_str.rfind('}') + 1
                    if json_start != -1 and json_end != 0:
                        potential_json = content_str[json_start:json_end]
                        parsed_content = json.loads(potential_json)
                        # Re-validate after fallback extraction
                        if not all(k in parsed_content for k in ["action_plan", "category_code", "mermaid_workflow"]):
                           return None, f"AI response missing required keys after fallback parse. Received: {parsed_content}"
                        return parsed_content, None  # Success after fallback
                    else:
                        return None, f"Could not parse JSON from AI response: {content_str}"
                except Exception as fallback_e:
                     return None, f"Could not parse JSON from AI response even with fallback: {content_str}. Error: {fallback_e}"
            except Exception as e:
                return None, f"Error processing AI response content: {e}"

        else:
            return None, f"Unexpected API response structure: {api_response}"

    except requests.exceptions.RequestException as e:
        # Handle connection errors, timeouts, etc.
        error_message = f"Error calling OpenAI API: {e}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                 # Include API error details if available
                 error_details = e.response.json()
                 error_message += f" - Status: {e.response.status_code}, Details: {error_details}"
            except json.JSONDecodeError:
                 error_message += f" - Status: {e.response.status_code}, Body: {e.response.text}"
        return None, error_message
    except Exception as e:
        # Catch any other unexpected errors
        return None, f"An unexpected error occurred: {e}"


# --- API Endpoint ---
@app.route('/plan_task', methods=['POST'])
def plan_task():
    """
    API endpoint to receive task details and return a plan.
    Expects JSON input: {"title": "...", "desc": "...", "deadline": "...", "priority": "..."}
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    # --- Input Validation ---
    required_fields = ["title", "desc", "deadline", "priority"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Missing required fields: {required_fields}"}), 400

    title = data.get("title")
    desc = data.get("desc")
    deadline = data.get("deadline")
    priority = data.get("priority")

    if not all([title, desc, deadline, priority]):
         return jsonify({"error": "All fields (title, desc, deadline, priority) must have non-empty values"}), 400

    # --- Call the AI ---
    result, error = get_ai_plan(title, desc, deadline, priority)

    # --- Handle Response ---
    if error:
        # Log the error server-side for debugging
        app.logger.error(f"Error generating plan for task '{title}': {error}")
        # Return a generic error to the client
        if "API key" in error:
             return jsonify({"error": "Internal configuration error."}), 500  # Don't expose key issues
        elif "Status: 401" in error:
             return jsonify({"error": "Authentication failed with AI service."}), 500
        elif "timeout" in error.lower():
             return jsonify({"error": "AI service request timed out."}), 504  # Gateway Timeout
        elif "Rate limit" in error:
             return jsonify({"error": "AI service rate limit reached. Please try again later."}), 429
        elif "AI service request failed" in error or "Status: 5" in error:  # Catch generic or 5xx errors
             return jsonify({"error": "AI service unavailable or encountered an error."}), 503  # Service Unavailable
        else:
            # For other errors like parsing errors, bad AI response structure
            return jsonify({"error": "Failed to generate plan due to processing error."}), 500

    return jsonify(result), 200

# --- Basic Error Handling ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}")  # Log the actual error
    return jsonify({"error": "Internal Server Error"}), 500

# --- Run the App ---
if __name__ == '__main__':
    # Enable debugging for development (gives detailed error pages)
    # Disable debug mode in production!
    app.run(debug=True)