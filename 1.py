# Import necessary modules from Flask and for file operations
from flask import Flask, request, jsonify, Response
import json
import os
from functools import wraps # Import wraps for decorator
import uuid # For generating a simple token

# Create a Flask application instance
app = Flask(__name__)

# Define the JSON files where data will be stored
ITEMS_JSON_FILE = 'items.json'
TOKENS_JSON_FILE = 'tokens.json' # New file for storing tokens

# --- Authentication Configuration ---
# Define the required username and password for basic authentication
REQUIRED_USERNAME = "admin"
REQUIRED_PASSWORD = "123"

# --- Helper functions for token file operations ---

def load_tokens():
    """
    Loads active tokens from the TOKENS_JSON_FILE.
    If the file does not exist or is empty, returns an empty dictionary.
    """
    if not os.path.exists(TOKENS_JSON_FILE) or os.path.getsize(TOKENS_JSON_FILE) == 0:
        return {}
    try:
        with open(TOKENS_JSON_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {TOKENS_JSON_FILE} is malformed. Starting with empty tokens.")
        return {}
    except Exception as e:
        print(f"Error loading tokens from {TOKENS_JSON_FILE}: {e}")
        return {}

def save_tokens(tokens_data):
    """
    Saves the current dictionary of active tokens to the TOKENS_JSON_FILE.
    """
    try:
        with open(TOKENS_JSON_FILE, 'w') as f:
            json.dump(tokens_data, f, indent=4) # Use indent for pretty-printing
    except Exception as e:
        print(f"Error saving tokens to {TOKENS_JSON_FILE}: {e}")

# Initialize active_tokens by loading from the JSON file at startup
active_tokens = load_tokens()

def check_auth(username, password):
    """
    This function checks if a username / password combination is valid.
    In a real application, you would typically check against a database.
    """
    return username == REQUIRED_USERNAME and password == REQUIRED_PASSWORD

def authenticate():
    """
    Sends a 401 response that enables basic auth or indicates token requirement.
    """
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials (Basic Auth or X-Access-Token header)', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """
    Decorator to protect API routes with either token-based or basic authentication.
    It first checks for a valid X-Access-Token header.
    If not found or invalid, it falls back to basic authentication.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Always reload active_tokens to ensure the latest state from file
        global active_tokens
        active_tokens = load_tokens()

        # 1. Check for X-Access-Token header
        access_token = request.headers.get('X-Access-Token')
        if access_token:
            # Check if the provided token is among the active tokens
            # For this simple example, we check if it's a value in our active_tokens and if the username matches
            if access_token in active_tokens.values():
                # Find the username associated with this token
                for user, token in active_tokens.items():
                    if token == access_token and user == REQUIRED_USERNAME: # Ensure it's the admin's token
                        return f(*args, **kwargs) # Token is valid, proceed
                
        # 2. Fallback to Basic Authentication if no valid token is present
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate() # Basic auth failed or not provided

        return f(*args, **kwargs) # Basic auth successful, proceed
    return decorated

# --- Helper functions for item file operations ---

def load_items():
    """
    Loads items from the ITEMS_JSON_FILE.
    If the file does not exist or is empty, returns an empty list.
    """
    if not os.path.exists(ITEMS_JSON_FILE) or os.path.getsize(ITEMS_JSON_FILE) == 0:
        return []
    try:
        with open(ITEMS_JSON_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Handle cases where the JSON file is malformed
        print(f"Warning: {ITEMS_JSON_FILE} is malformed. Starting with empty items.")
        return []
    except Exception as e:
        print(f"Error loading items from {ITEMS_JSON_FILE}: {e}")
        return []

def save_items(items_data):
    """
    Saves the current list of items to the ITEMS_JSON_FILE.
    """
    try:
        with open(ITEMS_JSON_FILE, 'w') as f:
            json.dump(items_data, f, indent=4) # Use indent for pretty-printing
    except Exception as e:
        print(f"Error saving items to {ITEMS_JSON_FILE}: {e}")

# Initialize items by loading from the JSON file at startup
items = load_items()

# Determine the next available ID based on existing items
# If no items exist, start from 1, otherwise find the max ID and add 1
next_id = max([item['id'] for item in items]) + 1 if items else 1

# --- API Endpoints ---

# Login API endpoint
@app.route('/login', methods=['POST'])
def login():
    """
    Handles POST requests for /login.
    Expects a JSON body with 'username' and 'password'.
    Verifies credentials and returns a success message along with an access token.
    This endpoint does NOT require basic authentication itself.
    """
    global active_tokens # Declare global to modify the dictionary

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if check_auth(username, password):
        # Generate a simple token upon successful login
        token = str(uuid.uuid4()) # Generate a unique token
        active_tokens[username] = token # Store the token (persisted via save_tokens)
        save_tokens(active_tokens) # Save the updated tokens to file
        return jsonify({"message": "Login successful", "username": username, "access_token": token}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

# GET all items or a specific item by ID
@app.route('/items', methods=['GET'])
@requires_auth # Apply the authentication decorator
def get_items():
    """
    Handles GET requests for /items.
    Always reloads items from the JSON file to ensure the latest data.
    If an 'id' query parameter is provided, returns the specific item.
    Otherwise, returns all items.
    """
    current_items = load_items() # Load the latest data from file
    item_id = request.args.get('id', type=int) # Get 'id' from query parameters

    if item_id:
        # Filter items to find the one with the matching ID
        item = next((item for item in current_items if item["id"] == item_id), None)
        if item:
            # Return the found item with a 200 OK status
            return jsonify(item), 200
        else:
            # Return a 404 Not Found error if item is not found
            return jsonify({"message": "Item not found"}), 404
    else:
        # Return all items if no ID is specified, with a 200 OK status
        return jsonify(current_items), 200

# POST a new item
@app.route('/items', methods=['POST'])
@requires_auth # Apply the authentication decorator
def add_item():
    """
    Handles POST requests for /items.
    Expects a JSON body with 'name' and 'description' for the new item.
    Assigns a new ID, adds the item, and saves the updated list to the file.
    """
    global next_id # Declare next_id as global to modify it

    data = request.get_json()

    # Basic validation: check if 'name' is provided
    if not data or 'name' not in data:
        return jsonify({"message": "Name is required"}), 400

    current_items = load_items() # Load latest data to append to

    # Create a new item dictionary
    new_item = {
        "id": next_id,
        "name": data['name'],
        "description": data.get('description', '') # Use .get to provide a default empty string if description is missing
    }
    current_items.append(new_item) # Add the new item to the list
    save_items(current_items) # Save the updated list back to the file
    next_id += 1 # Increment the next available ID for future additions

    # Return the newly created item with a 201 Created status
    return jsonify(new_item), 201

# PUT (update) an existing item
@app.route('/items/<int:item_id>', methods=['PUT'])
@requires_auth # Apply the authentication decorator
def update_item(item_id):
    """
    Handles PUT requests for /items/<item_id>.
    Expects a JSON body with updated 'name' and/or 'description'.
    Updates the item with the given ID and saves the updated list to the file.
    """
    data = request.get_json()
    current_items = load_items() # Load latest data to update

    item_found = False
    for item in current_items:
        if item["id"] == item_id:
            if 'name' in data:
                item['name'] = data['name']
            if 'description' in data:
                item['description'] = data['description']
            item_found = True
            break

    if item_found:
        save_items(current_items) # Save the updated list back to the file
        # Find and return the updated item for confirmation
        updated_item = next((item for item in current_items if item["id"] == item_id), None)
        return jsonify(updated_item), 200
    else:
        return jsonify({"message": "Item not found"}), 404

# DELETE an item
@app.route('/items/<int:item_id>', methods=['DELETE'])
@requires_auth # Apply the authentication decorator
def delete_item(item_id):
    """
    Handles DELETE requests for /items/<item_id>.
    Removes the item with the given ID from the list and saves the updated list to the file.
    """
    current_items = load_items() # Load latest data to delete from
    
    initial_len = len(current_items)
    # Filter out the item to be deleted
    updated_items = [item for item in current_items if item["id"] != item_id]

    if len(updated_items) < initial_len:
        save_items(updated_items) # Save the updated list back to the file
        return '', 204 # No content to return for a successful DELETE
    else:
        return jsonify({"message": "Item not found"}), 404

# Main entry point for running the Flask app
if __name__ == '__main__':
    # Run the Flask app in debug mode.
    app.run(debug=True)
