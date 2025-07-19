import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import datetime
import uuid
import json
from functools import wraps

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "7738254253:AAGIqEJETBe3BmC8Givq1jDvjQ-RRE_of4Y" # <<< REPLACE THIS with your actual bot token
TELEGRAM_CHAT_ID = "@sdfwr234"     # <<< REPLACE THIS with your actual chat ID

# Path for the JSON file to store sales records
SALES_FILE = 'sales_records.json'

# --- Basic User Management (For demonstration purposes only) ---
# In a real application, use a proper database, hashed passwords, and more robust user management.
USERS = {
    "admin": "123", # Replace with a strong password in production
    "user": "admin"
}
# A simple token store (in-memory, for demo)
# In production, use JWTs or a more secure token management system
ACTIVE_TOKENS = {}

# --- Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1] # Expects "Bearer <token>"

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        if token not in ACTIVE_TOKENS.values():
            return jsonify({"message": "Token is invalid or expired!"}), 401
        
        # You might want to get the user associated with the token here
        # For this simple demo, we just check token validity

        return f(*args, **kwargs)
    return decorated

# --- Helper Functions for File Operations ---
def load_sales_from_file():
    """Loads sales records from the JSON file."""
    if not os.path.exists(SALES_FILE):
        with open(SALES_FILE, 'w') as f:
            json.dump([], f) # Create an empty JSON array if file doesn't exist
        return []
    
    try:
        with open(SALES_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Handle case where file is empty or corrupted JSON
        print(f"Warning: {SALES_FILE} is empty or contains invalid JSON. Initializing with empty list.")
        return []
    except Exception as e:
        print(f"Error loading sales from file: {e}")
        return []

def save_sales_to_file(sales_data):
    """Saves all sales records to the JSON file."""
    try:
        with open(SALES_FILE, 'w') as f:
            json.dump(sales_data, f, indent=4) # Use indent for pretty printing
    except Exception as e:
        print(f"Error saving sales to file: {e}")

# --- Telegram Helper Function ---
def send_telegram_message(bot_token, chat_id, message_text):
    """
    Sends a message to a specific chat using the Telegram Bot API.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data["ok"]:
            print(f"Telegram message sent successfully for chat ID: {chat_id}")
            return True
        else:
            print(f"Failed to send Telegram message: {data.get('description', 'Unknown error')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False

# --- API Endpoints ---

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to ensure the API is running.
    """
    return jsonify({"status": "healthy", "message": "Sales API is running!"}), 200

@app.route('/login', methods=['POST'])
def login():
    """
    Endpoint for user login.
    Expects JSON payload with 'username' and 'password'.
    Returns a token on successful login.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    if USERS.get(username) == password:
        token = str(uuid.uuid4()) # Generate a simple token
        ACTIVE_TOKENS[username] = token # Store token (in-memory)
        return jsonify({"status": "Login successful", "token": token}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/sales', methods=['POST'])
@token_required # Protect this endpoint
def create_sale():
    """
    Endpoint to create one or more new sales transactions.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request must be JSON"}), 400

        sales_data = data if isinstance(data, list) else [data]
        
        processed_sales = []
        errors = []
        telegram_individual_sale_messages = []

        current_sales = load_sales_from_file()

        for sale_item in sales_data:
            try:
                required_fields = ['item', 'quantity', 'price', 'customer_name']
                if not all(field in sale_item for field in required_fields):
                    raise ValueError(f"Missing required fields. Required: {', '.join(required_fields)}")
                if not isinstance(sale_item['quantity'], int) or sale_item['quantity'] <= 0:
                    raise ValueError("Quantity must be a positive integer")
                if not isinstance(sale_item['price'], (int, float)) or sale_item['price'] <= 0:
                    raise ValueError("Price must be a positive number")

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M%p")
                total_amount = sale_item['quantity'] * sale_item['price']

                new_sale = {
                    "order_id": str(uuid.uuid4()),
                    "timestamp": timestamp,
                    "item": sale_item['item'],
                    "quantity": sale_item['quantity'],
                    "price": sale_item['price'],
                    "total_amount": round(total_amount, 2),
                    "customer_name": sale_item['customer_name']
                }

                current_sales.append(new_sale)
                print(f"New sale recorded: {new_sale}")

                telegram_individual_sale_messages.append(
                    f"<b>Order ID:</b> <code>{new_sale['order_id']}</code>\n"
                    f"<b>Customer:</b> {new_sale['customer_name']}\n"
                    f"<b>Item:</b> {new_sale['item']} (x{new_sale['quantity']})\n"
                    f"<b>Total:</b> ${new_sale['total_amount']:.2f}\n"
                    f"<b>Time:</b> {new_sale['timestamp']}"
                )
                
                processed_sales.append({"status": "success", "sale": new_sale})

            except ValueError as ve:
                errors.append({"status": "error", "message": str(ve), "data": sale_item})
            except Exception as e:
                errors.append({"status": "error", "message": f"An unexpected error occurred: {str(e)}", "data": sale_item})
        
        save_sales_to_file(current_sales)

        if telegram_individual_sale_messages:
            if len(telegram_individual_sale_messages) > 1:
                aggregated_message = (
                    f"<b>🎉 Multiple New Sales Alert! 🎉</b>\n\n" +
                    "\n\n---\n\n".join(telegram_individual_sale_messages)
                )
            else:
                aggregated_message = (
                    f"<b>🎉 New Sale Alert! 🎉</b>\n\n" +
                    telegram_individual_sale_messages[0]
                )
            send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, aggregated_message)

        if errors:
            return jsonify({
                "message": "Some sales could not be processed.",
                "processed_sales": processed_sales,
                "errors": errors
            }), 207
        else:
            return jsonify({"message": "All sales created successfully", "sales": processed_sales}), 201

    except Exception as e:
        print(f"Error processing sales request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sales', methods=['GET'])
@token_required # Protect this endpoint
def get_all_sales():
    """
    Endpoint to retrieve all recorded sales transactions from the JSON file.
    """
    sales = load_sales_from_file()
    return jsonify({"sales": sales}), 200

@app.route('/sales/<order_id>', methods=['PUT'])
@token_required # Protect this endpoint
def update_sale(order_id):
    """
    Endpoint to update an existing sales transaction by order_id.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request must be JSON"}), 400
        
        if not isinstance(data, dict):
            return jsonify({"error": "Request body for update must be a JSON object"}), 400

        current_sales = load_sales_from_file()
        updated = False
        for i, sale in enumerate(current_sales):
            if sale['order_id'] == order_id:
                for key, value in data.items():
                    if key in ['item', 'quantity', 'price', 'customer_name']:
                        if key == 'quantity' and (not isinstance(value, int) or value <= 0):
                            return jsonify({"error": "Quantity must be a positive integer"}), 400
                        if key == 'price' and (not isinstance(value, (int, float)) or value <= 0):
                            return jsonify({"error": "Price must be a positive number"}), 400
                        sale[key] = value
                
                sale['total_amount'] = round(sale['quantity'] * sale['price'], 2)
                
                current_sales[i] = sale
                updated = True
                break
        
        if updated:
            save_sales_to_file(current_sales)
            return jsonify({"message": "Sale updated successfully", "sale": sale}), 200
        else:
            return jsonify({"error": "Sale not found"}), 404
    except Exception as e:
        print(f"Error updating sale: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sales/<order_id>', methods=['DELETE'])
@token_required # Protect this endpoint
def delete_sale(order_id):
    """
    Endpoint to delete a sales transaction by order_id.
    """
    try:
        current_sales = load_sales_from_file()
        initial_len = len(current_sales)
        updated_sales = [sale for sale in current_sales if sale['order_id'] != order_id]

        if len(updated_sales) < initial_len:
            save_sales_to_file(updated_sales)
            return jsonify({"message": "Sale deleted successfully"}), 200
        else:
            return jsonify({"error": "Sale not found"}), 404
    except Exception as e:
        print(f"Error deleting sale: {e}")
        return jsonify({"error": str(e)}), 500

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)