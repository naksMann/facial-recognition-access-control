import json, os, pyrebase, base64, io, numpy as np
from PIL import Image
import face_recognition
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_mail import Mail, Message
import requests
import firebase_admin
from requests.exceptions import RequestException
from firebase_admin import credentials, auth as admin_auth 
import uuid

# ------------------- Flask App Setup -------------------
app = Flask(__name__)
app.secret_key = "INSERT YOUR OWN SECRET KEY"

# ------------------- Email Configuration -------------------
app.config.from_object('config.Config')
mail = Mail(app)

# ------------------- Firebase Setup -------------------
try:
    # Initialize Firebase Admin SDK with your service account key
    cred = credentials.Certificate("serviceAccountKey.json")  # ← PATH TO YOUR KEY FILE
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized successfully!")
except Exception as e:
    print(f"❌ Firebase Admin SDK initialization failed: {e}")

try:
    with open("firebaseConfig.json") as f:
        firebaseConfig = json.load(f)
    firebase = pyrebase.initialize_app(firebaseConfig)
    auth = firebase.auth()
    db = firebase.database()
    storage = firebase.storage()
    print("Firebase initialized successfully.")
except FileNotFoundError:
    print("❌ FATAL ERROR: firebaseConfig.json not found!")
    exit()
except Exception as e:
    print(f"❌ FATAL ERROR: Failed to initialize Firebase: {e}")
    exit()

# ------------------- Routes -------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')

        if not all([email, password, first_name, last_name]):
            return render_template('register.html', error="All fields are required.")

        try:
            user = auth.create_user_with_email_and_password(email, password)
            uid = user['localId']
            session['uid'] = uid
            session['email'] = email

            db.child("users").child(uid).set({
                 "email": email,
                 "firstName": first_name,
                 "lastName": last_name,
                 "access_logs": {},
                 "failed_logs": {}
            })
            return redirect(url_for('capture'))

        except Exception as e:
            error_str = str(e).lower()
            if "email_exists" in error_str or "email already exists" in error_str:
                error_msg = "Registration failed: Email is already in use."
            elif "weak password" in error_str:
                error_msg = "Registration failed: Password is too weak (min 6 characters)."
            else:
                error_msg = "Registration failed. Please try again."
            return render_template('register.html', error=error_msg)

    return render_template('register.html')

@app.route('/capture', methods=['GET', 'POST'])
def capture():
    if request.method == 'POST':
        uid = session.get('uid')
        if not uid:
            return jsonify({"error": "No user session found."}), 401

        data = request.get_json()
        if 'image' not in data:
            return jsonify({"error": "No image data received."}), 400

        try:
            base64_image = data['image']
            img_bytes = base64.b64decode(base64_image.split(",")[1])
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            img_np = np.array(img)

            encodings = face_recognition.face_encodings(img_np)
            if not encodings:
                return jsonify({"error": "No face detected. Please try again."}), 400

            embedding = encodings[0].tolist()
            db.child("users").child(uid).update({"embedding": embedding})
            return jsonify({"success": True, "redirect": url_for('login')})

        except Exception as e:
            print(f"Capture error: {e}")
            return jsonify({"error": "An unexpected error occurred."}), 500

    if 'uid' not in session:
        return redirect(url_for('register'))
    return render_template('capture.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return render_template('login.html', error="Email and password required.")
        
        try:
            # This returns the user object with idToken
            user = auth.sign_in_with_email_and_password(email, password)
            
            # Store user session data
            session['uid'] = user['localId']
            session['user_email'] = email
            session['id_token'] = user['idToken']  # ← STORE THE TOKEN HERE
            session['refresh_token'] = user['refreshToken']
            
            print(f"User {email} logged in successfully. Token stored.")
            return render_template('login.html', success="Login successful! Redirecting...")
            
        except Exception as e:
            print(f"Login error: {e}")
            return render_template('login.html', error="Invalid email or password.")

    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    uid = session.get('uid')
    if not uid:
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.get_json()
        if 'image' not in data:
            return jsonify({"error": "No image data received."}), 400

        try:
            base64_image = data['image']
            img_bytes = base64.b64decode(base64_image.split(",")[1])
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            img_np = np.array(img)

            encodings = face_recognition.face_encodings(img_np)
            if not encodings:
                return jsonify({"error": "No face detected. Please try again."}), 400
            
            embedding_current = encodings[0]
            stored_embedding_data = db.child("users").child(uid).child("embedding").get().val()
            
            if stored_embedding_data is None:
                return jsonify({"error": "No face registration data found."}), 404
            
            embedding_stored = np.array(stored_embedding_data)
            results = face_recognition.compare_faces([embedding_stored], embedding_current, tolerance=0.43)
            match = results[0]

            user_data = db.child("users").child(uid).get().val()
            user_email = user_data.get('email', 'Unknown') if user_data else 'Unknown'
            user_name = f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip()

            if match:
                send_esp32_command(uid, granted=True)
                log_attempt(uid, success=True)
                
                # Get user data to check if admin
                user_data = db.child("users").child(uid).get().val()
                first_name = user_data.get("firstName", "User")
                last_name = user_data.get("lastName", "")
                is_admin = user_data.get("isAdmin", False)
                
                if is_admin:
                    # Admin goes to dashboard
                    return jsonify({"success": True, "redirect": url_for('dashboard')})
                else:
                    # Standard user goes to granted page
                    session['user_first_name'] = first_name
                    session['user_last_name'] = last_name
                    return jsonify({
                        "success": True, 
                        "redirect": url_for('granted')
                    })
            else:
                send_esp32_command(uid, granted=False)
                intruder_image_url = save_intruder_image(img, uid, user_name)
                log_attempt(uid, success=False, intruder_image_url=intruder_image_url)
                send_intruder_alert(user_name, user_email, intruder_image_url)
                return jsonify({"error": "Unknown User"}), 403

        except Exception as e:
            print(f"Verify error: {e}")
            return jsonify({"error": "An unexpected error occurred."}), 500

    return render_template('verify.html')

@app.route('/granted')
def granted():
    """Welcome page for standard users after successful access"""
    user_first_name = session.get('user_first_name', 'User')
    user_last_name = session.get('user_last_name', '')
    return render_template('granted.html', 
                         user_first_name=user_first_name,
                         user_last_name=user_last_name)

@app.route('/dashboard')
def dashboard():
    uid = session.get('uid')
    
    # If no user logged in, show PUBLIC security view
    if not uid:
        try:
            all_failed_logs = []
            all_access_logs = []
            total_users = 0

            all_users = db.child("users").get().val()
            if all_users:
                total_users = len(all_users)
                
                for user_id, user_data in all_users.items():
                    # Only process failed logs for public view
                    user_failed_logs = user_data.get("failed_logs", {})
                    for log_key, log_data in user_failed_logs.items():
                        if isinstance(log_data, dict):
                            log_time = log_data.get('timestamp', 'Unknown')
                            intruder_image = log_data.get('intruder_image', None)
                        else:
                            log_time = log_data
                            intruder_image = None
                        all_failed_logs.append({"time": log_time, "user": "Unknown", "intruder_image": intruder_image, "status": "Denied"})
            
            all_failed_logs.sort(key=lambda x: x["time"], reverse=True)
            
            # Return PUBLIC dashboard view
            return render_template('dashboard.html',
                               user_first_name="Security",
                               user_last_name="Viewer",
                               all_access_logs=[],  # Empty for public
                               all_failed_logs=all_failed_logs[:50],
                               granted_count=0,  # Hide for public
                               denied_count=len(all_failed_logs),
                               users_count=total_users,
                               all_users_details=[],  # Hide user details
                               is_admin=False,
                               is_public=True)  # Add this flag
            
        except Exception as e: 
            print(f"Public dashboard error: {e}")
            return redirect(url_for('login'))
    
    # NORMAL DASHBOARD for logged-in users
    user_data = db.child("users").child(uid).get().val()
    first_name = user_data.get("firstName", "User") if user_data else "User"
    last_name = user_data.get("lastName", "") if user_data else ""
    is_admin_user = user_data.get("isAdmin", False) if user_data else False

    all_access_logs = []
    all_failed_logs = []
    all_users_details = []
    total_users = 0

    try:
        all_users = db.child("users").get().val()
        if all_users:
            total_users = len(all_users)
            
            for user_id, user_data in all_users.items():
                all_users_details.append({
                    "id": user_id,
                    "firstName": user_data.get("firstName", "Unknown"),
                    "lastName": user_data.get("lastName", ""),
                    "email": user_data.get("email", "No email"),
                    "isAdmin": user_data.get("isAdmin", False)
                })
                
                user_full_name = f"{user_data.get('firstName', 'Unknown')} {user_data.get('lastName', '')}".strip()
                
                # Process access logs
                user_access_logs = user_data.get("access_logs", {})
                for log_key, log_data in user_access_logs.items():
                    if isinstance(log_data, dict):
                        log_time = log_data.get('timestamp', 'Unknown')
                    else:
                        log_time = log_data
                    all_access_logs.append({"time": log_time, "user": user_full_name, "status": "Granted"})
                
                # Process failed logs
                user_failed_logs = user_data.get("failed_logs", {})
                for log_key, log_data in user_failed_logs.items():
                    if isinstance(log_data, dict):
                        log_time = log_data.get('timestamp', 'Unknown')
                        intruder_image = log_data.get('intruder_image', None)
                    else:
                        log_time = log_data
                        intruder_image = None
                    all_failed_logs.append({"time": log_time, "user": "Unknown", "intruder_image": intruder_image, "status": "Denied"})
        
        all_access_logs.sort(key=lambda x: x["time"], reverse=True)
        all_failed_logs.sort(key=lambda x: x["time"], reverse=True)
        
    except Exception as e: 
        print(f"Dashboard error: {e}")

    return render_template('dashboard.html',
                           user_first_name=first_name,
                           user_last_name=last_name,
                           all_access_logs=all_access_logs[:50],
                           all_failed_logs=all_failed_logs[:50],
                           granted_count=len(all_access_logs),
                           denied_count=len(all_failed_logs),
                           users_count=total_users,
                           all_users_details=all_users_details,
                           is_admin=is_admin_user,
                           is_public=False)

# ------------------- User Management Routes -------------------

@app.route('/admin/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    """Delete a user with comprehensive error handling"""
    try:
        # Check if current user is admin
        current_uid = session.get('uid')
        if not current_uid:
            return jsonify({"error": "Not logged in"}), 401
        
        current_user_data = db.child("users").child(current_uid).get().val()
        if not current_user_data or not current_user_data.get("isAdmin", False):
            return jsonify({"error": "Admin access required"}), 403
        
        if user_id == current_uid:
            return jsonify({"error": "Cannot delete your own account"}), 400
        
        # Validate that user_id is a valid Firebase UID (not an email)
        if '@' in user_id or '.' in user_id:
            return jsonify({"error": "Invalid user ID format. Expected UID, got email."}), 400
        
        print(f"🔄 Starting deletion process for user: {user_id}")
        
        # Step 1: Try to delete from Firebase Authentication
        try:
            admin_auth.delete_user(user_id)
            print(f"✅ User {user_id} deleted from Firebase Authentication")
        except admin_auth.UserNotFoundError:
            print(f"ℹ️ User {user_id} not found in Authentication (might be database-only)")
        except Exception as auth_error:
            print(f"⚠️ Auth deletion warning: {auth_error}")
            # Continue with database deletion even if auth fails
        
        # Step 2: Delete from Realtime Database
        try:
            # Verify the user exists in database before deleting
            user_data = db.child("users").child(user_id).get().val()
            if not user_data:
                return jsonify({"error": "User not found in database"}), 404
                
            db.child("users").child(user_id).remove()
            print(f"✅ User {user_id} deleted from Realtime Database")
        except Exception as db_error:
            print(f"❌ Database deletion error: {db_error}")
            return jsonify({"error": f"Database deletion failed: {str(db_error)}"}), 500
        
        print(f"🎉 User {user_id} deletion process completed by admin {current_uid}")
        return jsonify({"success": True, "message": "User deleted successfully"})
        
    except Exception as e:
        print(f"❌ Critical error deleting user {user_id}: {e}")
        return jsonify({"error": f"Delete operation failed: {str(e)}"}), 500

@app.route('/admin/update_user/<user_id>', methods=['POST'])
def update_user(user_id):
    """Update user details"""
    try:
        # Check if current user is admin
        current_uid = session.get('uid')
        if not current_uid:
            return jsonify({"error": "Not logged in"}), 401
        
        current_user_data = db.child("users").child(current_uid).get().val()
        if not current_user_data.get("isAdmin", False):
            return jsonify({"error": "Admin access required"}), 403
        
        data = request.get_json()
        updated_data = {}
        
        # Only update allowed fields
        if 'firstName' in data:
            updated_data['firstName'] = data['firstName']
        if 'lastName' in data:
            updated_data['lastName'] = data['lastName']
        if 'isAdmin' in data:
            updated_data['isAdmin'] = bool(data['isAdmin'])
        
        if updated_data:
            db.child("users").child(user_id).update(updated_data)
            print(f"User {user_id} updated by admin {current_uid}")
            return jsonify({"success": True, "message": "User updated successfully"})
        else:
            return jsonify({"error": "No valid fields to update"}), 400
        
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/user_modal/<user_id>')
def user_modal(user_id):
    """Get user data for modal editing"""
    try:
        current_uid = session.get('uid')
        if not current_uid:
            return jsonify({"error": "Not logged in"}), 401
        
        current_user_data = db.child("users").child(current_uid).get().val()
        if not current_user_data.get("isAdmin", False):
            return jsonify({"error": "Admin access required"}), 403
        
        user_data = db.child("users").child(user_id).get().val()
        if not user_data:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "firstName": user_data.get("firstName", ""),
                "lastName": user_data.get("lastName", ""),
                "email": user_data.get("email", ""),
                "isAdmin": user_data.get("isAdmin", False)
            }
        })
        
    except Exception as e:
        print(f"Error getting user data: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/debug_users')
def debug_users():
    """Debug route to see user structure"""
    try:
        all_users = db.child("users").get().val()
        user_list = []
        
        if all_users:
            for user_id, user_data in all_users.items():
                user_list.append({
                    'uid': user_id,
                    'email': user_data.get('email', 'No email'),
                    'firstName': user_data.get('firstName', 'No name'),
                    'isAdmin': user_data.get('isAdmin', False)
                })
        
        return jsonify({"users": user_list})
    except Exception as e:
        return jsonify({"error": str(e)})
# -------- Logout --------
@app.route('/logout')
def logout():
    user_email = session.get('user_email', 'Unknown')
    session.clear()
    print(f"User {user_email} logged out.")
    
    # Get the current request's host to redirect properly
    if request.host.startswith('10.161.214.15'):
        return redirect('http://10.161.214.15:5000/login')
    else:
        return redirect(url_for('login'))
# ------------------- Security Functions -------------------

def save_intruder_image(img, user_id, user_name):
    try:
        # Create intruders folder if it doesn't exist
        intruders_dir = os.path.join("static", "intruders")
        os.makedirs(intruders_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in user_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(intruders_dir, filename)
        
        # Save image locally
        img.save(filepath, format='JPEG', quality=85)
        print(f"✅ Intruder image saved locally: {filepath}")
        
        # Return relative path for web display
        return f"static/intruders/{filename}"
        
    except Exception as e:
        print(f"❌ Error saving intruder image: {e}")
        return None

def send_intruder_alert(user_name, user_email, intruder_image_url):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"🚨 SECURITY ALERT: Unauthorized Access Attempt - {timestamp}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .alert {{ background: #fff3f3; border-left: 4px solid #dc2626; padding: 20px; margin: 20px 0; }}
                .button {{ background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; }}
            </style>
        </head>
        <body>
            <h2>🚨 Security Alert - Unauthorized Access Attempt</h2>
            <div class="alert">
                <h3>⚠️ Intruder Detected</h3>
                <p><strong>Time:</strong> {timestamp}</p>
                <p><strong>Target Account:</strong> {user_name} ({user_email})</p>
                <p><strong>Status:</strong> Access Denied</p>
            </div>
            <p>
                <a href="http://10.161.214.15:5000/dashboard" class="button">🚨 View Live Security Dashboard</a>
            </p>
        </body>
        </html>
        """
        
        msg = Message(subject=subject, recipients=[app.config['ADMIN_EMAIL']], html=html_body)
        mail.send(msg)
        print(f"Security alert email sent to {app.config['ADMIN_EMAIL']}")
        
    except Exception as e:
        print(f"Error sending security alert email: {e}")

def log_attempt(user_id, success: bool, intruder_image_url=None):
    log_node = "access_logs" if success else "failed_logs"
    try:
        sast = timezone(timedelta(hours=2))
        timestamp_utc = datetime.now(timezone.utc)
        timestamp_sast = timestamp_utc.astimezone(sast)
        timestamp_str = timestamp_sast.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        log_data = {"timestamp": timestamp_str}
        if not success and intruder_image_url:
            log_data["intruder_image"] = intruder_image_url
        
        db.child("users").child(user_id).child(log_node).push(log_data)
        print(f"Logged {'successful' if success else 'FAILED'} access for UID: {user_id}")
        
    except Exception as log_err:
        print(f"Failed to log access for UID {user_id}: {log_err}")

def send_esp32_command(user_id, granted: bool):
    esp32_ip = "10.161.214.138"
    if not esp32_ip:
        print("!!! WARNING: ESP32 IP address not set!")
        return

    command = "access_granted" if granted else "access_denied"
    url = f"http://{esp32_ip}/{command}"
    
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        print(f"ESP32 command sent: {url}")
    except RequestException as e:
        print(f"Error sending command to ESP32: {e}")

# ------------------- Run App -------------------
if __name__ == '__main__':
    print("Starting Flask app with enhanced security features...")
    app.run(debug=True, host='0.0.0.0', port=5000)
