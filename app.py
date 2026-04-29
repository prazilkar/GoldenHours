from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory, render_template_string
from flask_socketio import SocketIO, join_room, emit
import pandas as pd
import os
import csv
import uuid

app = Flask(__name__)
app.secret_key = 'rescue_link_golden_hour_final_2026'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# File Paths
CSV_FILE = 'ambulance.csv'
HOSPITAL_CSV = 'hospitals_tn.csv'
UNKNOWN_CSV = 'unknown_cases.csv' 
UPLOAD_FOLDER = 'static/images'
PATIENT_PHOTOS = 'static/images/patients' 

# Directories Setup
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER, exist_ok=True)
if not os.path.exists(PATIENT_PHOTOS): os.makedirs(PATIENT_PHOTOS, exist_ok=True)

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            csv.writer(f).writerow(['ambulance_name', 'ambulance_no', 'password', 'district', 'driver_mobile', 'img_front', 'img_back', 'img_side', 'status'])
    
    if not os.path.exists(HOSPITAL_CSV):
        with open(HOSPITAL_CSV, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['hospital_name', 'district', 'latitude', 'longitude', 'phone', 'specialization', 'password', 'status', 'icu_beds', 'gen_beds'])
            writer.writerow(['sks', 'Salem', '11.670372487441997', '78.14343611534255', '9360882288', 'Multi Speciality', 'sks@123', 'Approved', '6', '2'])
    
    if not os.path.exists(UNKNOWN_CSV):
        with open(UNKNOWN_CSV, mode='w', newline='') as f:
            csv.writer(f).writerow(['case_id', 'rescue_ambulance', 'location', 'hospital_name', 'photo', 'description', 'status'])

init_csv()

# ==================== LOGIN ROUTES ====================

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/hospital_dashboard")
def hospital_dashboard_page():
    if session.get('role') != 'hospital':
        return redirect(url_for('login_page'))
    
    hosp_name = session.get('user')
    
    if os.path.exists(HOSPITAL_CSV):
        df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        match = df[df['hospital_name'] == hosp_name]
        
        if not match.empty:
            hosp_details = match.to_dict('records')[0]
            u_df = pd.read_csv(UNKNOWN_CSV, on_bad_lines='skip') if os.path.exists(UNKNOWN_CSV) else pd.DataFrame()
            u_df.columns = u_df.columns.str.strip()
            
            # ✅ FILTER CASES BY HOSPITAL NAME
            hospital_cases = u_df[u_df['hospital_name'] == hosp_name].to_dict('records')
            
            return render_template("hospital_dashboard.html", 
                                 hosp=hosp_details, 
                                 unknown_list=hospital_cases)
    
    return "Hospital Data Not Found", 404

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    # Admin Login
    if username.upper() == "ADMINPRAZIL" and password == "prazilsanjay2026":
        session['user'] = 'admin'
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    
    # Hospital Login
    if os.path.exists(HOSPITAL_CSV):
        h_df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
        h_df.columns = h_df.columns.str.strip()
        match = h_df[(h_df['hospital_name'] == username) & (h_df['password'].astype(str) == password) & (h_df['status'] == 'Approved')]
        
        if not match.empty:
            session['user'] = username
            session['role'] = 'hospital'
            return redirect(url_for('hospital_dashboard_page'))

    # Driver Login
    if os.path.exists(CSV_FILE):
        a_df = pd.read_csv(CSV_FILE, on_bad_lines='skip')
        a_df.columns = a_df.columns.str.strip()
        match = a_df[(a_df['ambulance_no'] == username.upper()) & (a_df['password'].astype(str) == password) & (a_df['status'] == 'Approved')]
        if not match.empty:
            session['user'] = username.upper()
            session['role'] = 'driver'
            return redirect(url_for('main_dashboard'))
    
    flash("Invalid Access.")
    return redirect(url_for('login_page'))

@app.route('/registerhospital')
def register_hospital_page():
    return render_template('register_hospital.html')

# ==================== ADMIN ROUTES ====================

@app.route("/admin")
def admin_dashboard():
    if session.get('role') != 'admin': 
        return redirect(url_for('login_page'))
    
    def safe_read(file):
        if os.path.exists(file):
            try:
                df = pd.read_csv(file, on_bad_lines='skip', skipinitialspace=True)
                df.columns = df.columns.str.strip().str.lower()
                return df.to_dict('records')
            except:
                return []
        return []

    return render_template("admin.html", 
                          amb_list=safe_read(CSV_FILE), 
                          hosp_list=safe_read(HOSPITAL_CSV),
                          unknown_list=safe_read(UNKNOWN_CSV))

@app.route("/update_status/<type>/<id>/<action>")
def update_status(type, id, action):
    file = HOSPITAL_CSV if type == 'hosp' else CSV_FILE
    df = pd.read_csv(file, on_bad_lines='skip')
    df.columns = df.columns.str.strip()
    col = 'hospital_name' if type == 'hosp' else 'ambulance_no'
    df.loc[df[col] == id, 'status'] = 'Approved' if action == 'approve' else 'Rejected'
    df.to_csv(file, index=False)
    return redirect(url_for('admin_dashboard'))

# ==================== HOSPITAL VIEW ====================

@app.route("/hospital_view/<hosp_name>")
def hospital_view_redirect(hosp_name):
    # For specific hospital files
    if hosp_name.lower() == 'vibha':
        return render_template("vibha.html")
    elif hosp_name.lower() == 'sks':
        return render_template("sks.html")
    else:
        # Generic fallback
        return render_template("sks.html")

# ==================== REGISTRATION ====================

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            reg_type = request.form.get("reg_type", "ambulance")
            if reg_type == 'hospital':
                with open(HOSPITAL_CSV, mode='a', newline='') as f:
                    csv.writer(f).writerow([
                        request.form.get("hospital_name"),
                        request.form.get("district"),
                        request.form.get("latitude"),
                        request.form.get("longitude"),
                        request.form.get("phone"),
                        request.form.get("specialization"),
                        request.form.get("password"),
                        "Pending", 0, 0
                    ])
            else:
                no = request.form.get("ambulance_no").upper()
                img_f = request.files.get('img_front')
                img_b = request.files.get('img_back')
                img_s = request.files.get('img_side')
                
                f_n = f"f_{no}.jpg"
                b_n = f"b_{no}.jpg"
                s_n = f"s_{no}.jpg"
                
                if img_f:
                    img_f.save(os.path.join(UPLOAD_FOLDER, f_n))
                if img_b:
                    img_b.save(os.path.join(UPLOAD_FOLDER, b_n))
                if img_s:
                    img_s.save(os.path.join(UPLOAD_FOLDER, s_n))

                with open(CSV_FILE, mode='a', newline='') as f:
                    csv.writer(f).writerow([
                        request.form.get("ambulance_name"),
                        no,
                        request.form.get("password"),
                        request.form.get("district"),
                        request.form.get("driver_mobile"),
                        f_n, b_n, s_n, "Pending"
                    ])
            
            flash("Registration Successful!")
            return redirect(url_for('login_page'))
        except Exception as e:
            return f"Error: {e}", 500
    return render_template('register.html')

@app.route("/register_page")
def register_page():
    return render_template("register.html")

# ==================== UNKNOWN CASES ====================

@app.route('/report_unknown', methods=['POST'])
def report_unknown():
    try:
        target_hosp = request.form.get('target_hospital')
        location = request.form.get('location')
        file = request.files.get('patient_photo')
        ambulance_name = request.form.get('ambulance_name', 'AMB-UNIT')  # ✅ Get ambulance name
        
        if not file or not target_hosp:
            return jsonify({"status": "error", "message": "Missing photo or hospital name"}), 400

        filename = f"unidentified_{uuid.uuid4().hex[:6]}.jpg"
        save_path = os.path.join('static', 'images', 'patients', filename)
        file.save(save_path)
        
        with open(UNKNOWN_CSV, mode='a', newline='') as f:
            csv.writer(f).writerow([
                uuid.uuid4().hex[:8],
                ambulance_name,  # ✅ Use actual ambulance name
                location,
                target_hosp,
                filename,
                "Unconscious Patient",
                "Under Process"
            ])
        
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== DATA FETCHING ====================

@app.route("/dashboard")
def main_dashboard():
    df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
    df.columns = df.columns.str.strip()
    districts = sorted(df['district'].dropna().unique())
    return render_template("index.html", districts=districts)

@app.route("/public_trace")
def public_trace_page():
    all_cases = []
    if os.path.exists(UNKNOWN_CSV):
        try:
            u_df = pd.read_csv(UNKNOWN_CSV, on_bad_lines='skip')
            u_df.columns = u_df.columns.str.strip()
            all_cases = u_df.to_dict('records')
        except:
            all_cases = []
    return render_template("public_trace.html", unknown_list=all_cases)

@app.route("/get_unknown_cases")
def get_unknown_cases():
    """API endpoint for fast JSON data - NO DELAY"""
    all_cases = []
    if os.path.exists(UNKNOWN_CSV):
        try:
            df = pd.read_csv(UNKNOWN_CSV, on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            all_cases = df.to_dict('records')
        except:
            all_cases = []
    return jsonify(all_cases)

@app.route("/get_hospitals_data")
def get_hospitals_data():
    district = request.args.get("district", "").strip()
    
    if os.path.exists(HOSPITAL_CSV):
        df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        filtered_df = df[
            (df['district'].str.lower() == district.lower()) & 
            (df['status'].str.strip().str.lower() == 'approved')
        ]
        return jsonify(filtered_df.to_dict('records'))
    
    return jsonify([])

# ==================== BED UPDATE ====================

@app.route("/update_beds", methods=["POST"])
def update_beds():
    if session.get('role') != 'hospital':
        return redirect(url_for('login_page'))
    
    hosp_name = session.get('user')
    icu = request.form.get("icu_beds")
    gen = request.form.get("gen_beds")

    if os.path.exists(HOSPITAL_CSV):
        df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        df.loc[df['hospital_name'] == hosp_name, 'icu_beds'] = icu
        df.loc[df['hospital_name'] == hosp_name, 'gen_beds'] = gen
        df.to_csv(HOSPITAL_CSV, index=False)
        flash("Beds Updated Successfully!")
        
    return redirect(url_for('hospital_dashboard_page'))

# ==================== STATUS VIEW ====================

@app.route("/view_status_page")
def view_status_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RescueLink | Check Status</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #000; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: rgba(20, 20, 20, 0.95); padding: 40px; border-radius: 20px; width: 100%; max-width: 400px; text-align: center; border-top: 5px solid #d32f2f; }
            input { width: 100%; padding: 15px; margin: 20px 0; background: #222; border: 1px solid #444; border-radius: 10px; color: white; outline: none; text-align: center; font-size: 16px; }
            .btn { background: #d32f2f; color: white; padding: 15px; border: none; border-radius: 10px; width: 100%; cursor: pointer; font-weight: bold; }
            #result { margin-top: 25px; font-weight: bold; padding: 15px; border-radius: 10px; display: none; }
            .approved { background: rgba(46, 125, 50, 0.2); color: #4ade80; }
            .pending { background: rgba(239, 108, 0, 0.2); color: #ffb74d; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="color:#d32f2f;"><i class="fas fa-search"></i> STATUS TRACKER</h2>
            <input type="text" id="regId" placeholder="Enter ID or Hospital Name">
            <button class="btn" onclick="checkStatus()">SEARCH STATUS</button>
            <div id="result"></div>
            <br><a href="/" style="color:#888; text-decoration:none; font-size:13px;">Back to Login</a>
        </div>
        <script>
            async function checkStatus() {
                let id = document.getElementById('regId').value.trim();
                if(!id) return alert("Please enter ID");
                let res = await fetch('/get_reg_status/' + id);
                let data = await res.json();
                let div = document.getElementById('result');
                div.style.display = 'block';
                div.innerText = "STATUS: " + data.status.toUpperCase();
                div.className = data.status.toLowerCase().includes('approved') ? 'approved' : 'pending';
            }
        </script>
    </body>
    </html>
    """)

# ==================== ALERT FUNCTIONS ====================

@app.route("/trigger_alert", methods=["POST"])
def trigger_alert():
    data = request.json
    target_hospital = data.get("hospital", "").strip()
    
    print(f"🚨 ALERT TO: {target_hospital}")
    
    socketio.emit("emergency_alert", {
        "hospital": target_hospital,
        "case": data.get("case", "Emergency"),
        "dist": data.get("dist", "--"),
        "eta": data.get("eta", "--"),
        "uLat": data.get("uLat"),
        "uLng": data.get("uLng"),
        "ambName": data.get("ambName", "Ambulance"),
        "ambNumber": data.get("ambNumber", "AMB-001")
    }, room=target_hospital)
    
    return jsonify({"status": "success"})

@app.route("/signal_status/<hosp_name>/<action>")
def signal_status(hosp_name, action):
    if action == "reach":
        socketio.emit("case_reaching", {"status": "arriving"}, room=hosp_name)
    elif action == "cancel":
        socketio.emit("case_canceled", {"status": "canceled"}, room=hosp_name)
    return jsonify({"status": "signal sent"})

@app.route("/get_reg_status/<id>")
def get_reg_status(id):
    if os.path.exists(HOSPITAL_CSV):
        df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
        df.columns = df.columns.str.strip().str.lower()
        match = df[df['hospital_name'].str.lower() == id.lower()]
        if not match.empty:
            return jsonify({"status": match.iloc[0]['status']})
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE, on_bad_lines='skip')
        df.columns = df.columns.str.strip().str.lower()
        match = df[df['ambulance_no'].str.upper() == id.upper()]
        if not match.empty:
            return jsonify({"status": match.iloc[0]['status']})
    return jsonify({"status": "Not Found"})

@app.route("/save_hospital", methods=["POST"])
def save_hospital():
    try:
        data = [
            request.form.get("hospital_name"),
            request.form.get("district"),
            request.form.get("latitude"),
            request.form.get("longitude"),
            request.form.get("phone"),
            request.form.get("specialization"),
            request.form.get("password"),
            "Pending", 0, 0
        ]
        with open(HOSPITAL_CSV, mode='a', newline='') as f:
            csv.writer(f).writerow(data)
        flash("Hospital Registered! Wait for approval.")
        return redirect(url_for('login_page'))
    except:
        return "Error saving hospital", 500

# ==================== STATIC FILES ====================

@app.route('/images/patients/<filename>')
def get_patient_photo(filename):
    return send_from_directory(PATIENT_PHOTOS, filename)

@app.route('/static/images/<filename>')
def get_ambulance_photo(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ==================== HOSPITAL BEDS API ====================

@app.route("/get_hospital_beds")
def get_hospital_beds():
    hospital_name = request.args.get("hospital_name", "").strip()
    print(f"🔍 Fetching beds for: {hospital_name}")
    
    try:
        if os.path.exists(HOSPITAL_CSV):
            df = pd.read_csv(HOSPITAL_CSV, on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            
            match = df[df['hospital_name'].str.lower() == hospital_name.lower()]
            
            if not match.empty:
                icu_val = match.iloc[0]['icu_beds']
                gen_val = match.iloc[0]['gen_beds']
                print(f"✅ Found: ICU={icu_val}, GEN={gen_val}")
                return jsonify({
                    "status": "success",
                    "icu_beds": str(icu_val),
                    "gen_beds": str(gen_val)
                })
            else:
                print(f"❌ Hospital not found: {hospital_name}")
                return jsonify({"status": "error", "message": "Hospital not found"})
        else:
            print(f"❌ CSV file not found: {HOSPITAL_CSV}")
            return jsonify({"status": "error", "message": "CSV file not found"})
    except Exception as e:
        print(f"❌ Error in get_hospital_beds: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

# ==================== UPDATE CASE STATUS ====================

@app.route("/update_case_status", methods=["POST"])
def update_case_status():
    data = request.json
    case_id = data.get("id")
    new_status = data.get("status")
    
    print(f"📝 Updating case {case_id} to status: {new_status}")
    
    if os.path.exists(UNKNOWN_CSV):
        try:
            df = pd.read_csv(UNKNOWN_CSV, on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            df.loc[df['case_id'] == case_id, 'status'] = new_status
            df.to_csv(UNKNOWN_CSV, index=False)
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"Error updating case status: {e}")
            return jsonify({"status": "error", "message": str(e)})
    
    return jsonify({"status": "error", "message": "CSV file not found"})

# ==================== LOGOUT ====================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==================== SOCKET.IO EVENTS ====================

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"✅ Hospital JOINED room: '{room}'")
        emit('join_confirmation', {'room': room, 'status': 'joined'})

@socketio.on('emergency_alert')
def handle_emergency_alert(data):
    target = data.get("hospital", "").strip()
    print(f"📡 Socket alert to: '{target}'")
    emit("emergency_alert", data, room=target)

@socketio.on('location_update')
def handle_location_update(data):
    target_hospital = data.get("hospital", "").strip()
    if target_hospital:
        emit("ambulance_location", data, room=target_hospital)

@socketio.on('reaching_alert')
def handle_reaching_alert(data):
    target = data.get("hospital", "").strip()
    print(f"⏰ Reaching alert to: '{target}' - ETA: {data.get('eta', '--')} minutes")
    emit("reaching_alert", data, room=target)

# ==================== MAIN ====================

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, debug=True, use_reloader=False)