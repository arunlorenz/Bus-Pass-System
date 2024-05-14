# app.py
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import datetime
import random
import string
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

DB_STRING = os.getenv("MONGO_CONN_STRING")
DB_NAME = os.getenv("MONGO_DB_NAME")

# Connect to MongoDB
client = MongoClient(DB_STRING)
db = client[DB_NAME]
collection = db["bus_passes"]

# Dummy data for stop amounts (replace with actual data)
stop_amounts = {
    "Stop 1": 50,
    "Stop 2": 75,
    "Stop 3": 100
}

def generate_bus_pass(roll_number, selected_stop, round_trip):
    # Generate a timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Determine the amount based on the selected stop
    amount = stop_amounts.get(selected_stop, 0)
    
    # If round trip is selected, double the amount
    if round_trip == "Yes":
        amount *= 2
    
    # Concatenate roll number, date, and timestamp
    pass_number = f"{roll_number}_{selected_stop}_{timestamp}"
    
    return pass_number, amount

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buy-bus-pass', methods=['POST'])
def buy_bus_pass():
    data = request.json
    roll_number = data.get('roll_number')
    selected_stop = data.get('selected_stop')
    round_trip = data.get('round_trip', 'No')  # Default to 'No' if round_trip is not provided
    
    # Generate bus pass for the student
    pass_number, amount = generate_bus_pass(roll_number, selected_stop, round_trip)
    
    # Store the generated pass number and total amount for the student in MongoDB
    collection.insert_one({"roll_number": roll_number, "pass_number": pass_number, "total_amount": amount})
    
    return jsonify({"message": "Bus pass generated successfully", "pass_number": pass_number, "amount": amount})

@app.route('/validate-bus-pass', methods=['POST'])
def validate_bus_pass():
    data = request.json
    pass_number = data.get('pass_number')
    
    # Check if the pass number exists in MongoDB
    bus_pass = collection.find_one({"pass_number": pass_number})
    
    if bus_pass:
        return jsonify({"valid": True, "message": "Valid bus pass"})
    else:
        return jsonify({"valid": False, "message": "Invalid bus pass number"})

@app.route('/student_portal')
def student_portal():
    return render_template('student_portal.html')

@app.route('/bus_incharge_portal')
def bus_incharge_portal():
    return render_template('bus_incharge_portal.html')

if __name__ == '__main__':
    app.run(debug=True)
