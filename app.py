from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import boto3
from botocore.exceptions import ClientError
import hmac
import hashlib
import base64
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import datetime

app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

# AWS Cognito Configuration
CLIENT_ID = os.getenv('COGNITO_CLIENT_ID', 'your_app_client_id')
CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET', 'your_app_client_secret')
USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID', 'your_user_pool_id')
REGION = os.getenv('COGNITO_REGION', 'your_aws_region')

cognito = boto3.client('cognito-idp', region_name=REGION)

# MongoDB Configuration
DB_STRING = os.getenv("MONGO_CONN_STRING")
DB_NAME = os.getenv("MONGO_DB_NAME")
client = MongoClient(DB_STRING)
db = client[DB_NAME]
collection = db["buspass"]

stop_amounts = {
    "Stop 1": 50,
    "Stop 2": 75,
    "Stop 3": 100
}

def get_secret_hash(username):
    message = username + CLIENT_ID
    dig = hmac.new(CLIENT_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('student_portal')) if session['role'] == 'student' else redirect(url_for('bus_incharge_portal'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        secret_hash = get_secret_hash(username)
        try:
            response = cognito.initiate_auth(
                ClientId=CLIENT_ID,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password,
                    'SECRET_HASH': secret_hash
                }
            )
            session['username'] = username
            user_attributes = cognito.get_user(
                AccessToken=response['AuthenticationResult']['AccessToken']
            )['UserAttributes']
            role = next((attr['Value'] for attr in user_attributes if attr['Name'] == 'nickname'), None)
            session['role'] = role
            if 'student' == role:
                return render_template('student_portal.html', username=session['username'])
            elif 'bus_incharge' == role:
                return render_template('bus_incharge_portal.html')
            else:
                return redirect(url_for('home'))
        except ClientError as e:
            return render_template('login.html', error=e.response['Error']['Message'])
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/student_portal')
def student_portal():
    if 'username' in session:
        if session['role'] == 'student':
            return render_template('student_portal.html', username=session['username'])
        else:
            return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/bus_incharge_portal')
def bus_incharge_portal():
    if 'username' in session:
        if session['role'] == 'bus_incharge':
            return render_template('bus_incharge_portal.html', username=session['username'])
        else:
            return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        role = request.form['nickname']  # This should contain the role information
        secret_hash = get_secret_hash(username)
        try:
            response = cognito.sign_up(
                ClientId=CLIENT_ID,
                Username=username,
                Password=password,
                SecretHash=secret_hash,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': full_name},
                    {'Name': 'nickname', 'Value': role}  # Use nickname attribute to store the role
                ]
            )
            return redirect(url_for('confirm', username=username))
        except ClientError as e:
            return render_template('register.html', error=e.response['Error']['Message'])
    return render_template('register.html')

@app.route('/confirm', methods=['GET', 'POST'])
def confirm():
    username = request.args.get('username')
    if 'username' in session:
        if 'student' in session['username']:
            return redirect(url_for('student_portal'))
        else:
            return redirect(url_for('bus_incharge_portal'))
    if request.method == 'POST':
        confirmation_code = request.form['confirmation_code']
        try:
            response = cognito.confirm_sign_up(
                ClientId=CLIENT_ID,
                Username=username,
                ConfirmationCode=confirmation_code,
                SecretHash=get_secret_hash(username)
            )
            return redirect(url_for('login'))
        except ClientError as e:
            return render_template('confirm.html', username=username, error=e.response['Error']['Message'])
    return render_template('confirm.html', username=username)

@app.route('/buy-bus-pass', methods=['POST'])
def buy_bus_pass():
    data = request.json
    roll_number = data.get('roll_number')
    selected_stop = data.get('selected_stop')
    round_trip = data.get('round_trip', 'No')
    pass_number, amount = generate_bus_pass(roll_number, selected_stop, round_trip)
    collection.insert_one({"roll_number": roll_number, "pass_number": pass_number, "total_amount": amount})
    return jsonify({"message": "Bus pass generated successfully", "pass_number": pass_number, "amount": amount})

@app.route('/validate-bus-pass', methods=['POST'])
def validate_bus_pass():
    data = request.json
    pass_number = data.get('pass_number')
    bus_pass = collection.find_one({"pass_number": pass_number})
    if bus_pass:
        return jsonify({"valid": True, "message": "Valid bus pass"})
    else:
        return jsonify({"valid": False, "message": "Invalid bus pass number"})

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

def generate_bus_pass(roll_number, selected_stop, round_trip):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    amount = stop_amounts.get(selected_stop, 0)
    if round_trip == "Yes":
        amount *= 2
    pass_number = f"{roll_number}_{selected_stop}_{timestamp}"
    return pass_number, amount

if __name__ == '__main__':
    app.run(debug=True)
