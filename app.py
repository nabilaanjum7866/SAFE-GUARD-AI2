import streamlit as st
import pandas as pd
import datetime
import requests
import joblib
import os
import smtplib
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

# ─── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="SafeGuard AI — Women Safety Portal",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS FOR STYLING ───────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #fafafa; }
    .countdown { 
        font-size: 50px; 
        font-weight: bold; 
        color: #D32F2F; 
        text-align: center; 
        padding: 20px; 
        border: 5px solid #D32F2F; 
        border-radius: 20px; 
        background-color: #FFEBEE;
        margin: 20px 0;
    }
    .help-card { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        border-left: 8px solid #E91E63; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        color: #444;
    }
    .step-box { 
        background-color: #E3F2FD; 
        padding: 20px; 
        border-radius: 10px; 
        border: 2px dashed #1E88E5; 
        margin: 15px 0; 
        color: #0D47A1;
        font-size: 15px;
    }
    .stButton>button { border-radius: 8px; }
    .stTextArea>div>div>textarea { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ SafeGuard AI")
st.subheader("Intelligent Safety System for Women")

# ─── SESSION STATE INITIALIZATION ──────────────────────────────
if "history" not in st.session_state: st.session_state.history = []
if "typed_msg" not in st.session_state: st.session_state.typed_msg = ""
if "contacts" not in st.session_state: st.session_state.contacts = []
if "checkin_active" not in st.session_state: st.session_state.checkin_active = False
if "checkin_end" not in st.session_state: st.session_state.checkin_end = None
if "sos_countdown" not in st.session_state: st.session_state.sos_countdown = False
if "sos_start" not in st.session_state: st.session_state.sos_start = None
if "fake_call_active" not in st.session_state: st.session_state.fake_call_active = False

# ─── SIDEBAR: USER PROFILE & SETTINGS ──────────────────────────
with st.sidebar:
    st.header("👤 Personal Profile")
    u_name = st.text_input("Your Full Name", key="user_name", placeholder="e.g. Anjali Sharma")
    u_phone = st.text_input("Phone Number", key="user_phone", placeholder="+91 98765 43210")
    
    st.divider()
    st.header("📧 Email Configuration")
    st.info("Required to send automated emergency alerts.")
    s_email = st.text_input("Your Gmail Address", key="sender_email", placeholder="example@gmail.com")
    s_pass = st.text_input("Gmail App Password", key="sender_password", type="password", help="16-character code from Google Security settings.")
    
    if s_email and s_pass:
        st.success("✅ Email System Configured")
    else:
        st.error("❌ Email System Offline")

    st.divider()
    st.header("👥 Emergency Contacts")
    
    with st.expander("➕ Add New Contact"):
        new_c_name = st.text_input("Contact Name", key="nc_name")
        new_c_phone = st.text_input("Phone Number", key="nc_phone")
        new_c_email = st.text_input("Contact Email", key="nc_email")
        if st.button("Save Contact"):
            if new_c_name and (new_c_phone or new_c_email):
                st.session_state.contacts.append({
                    "name": new_c_name, 
                    "phone": new_c_phone, 
                    "email": new_c_email
                })
                st.success(f"Added {new_c_name}")
                st.rerun()
            else:
                st.warning("Please provide Name and Email/Phone.")

    if st.session_state.contacts:
        for i, contact in enumerate(st.session_state.contacts):
            col_a, col_b = st.columns([4, 1])
            col_a.write(f"**{contact['name']}**")
            if col_b.button("🗑️", key=f"del_{i}"):
                st.session_state.contacts.pop(i)
                st.rerun()
    else:
        st.caption("No contacts added yet.")

    st.divider()
    st.header("📩 Additional Recipients")
    manual_emails = st.text_area("Emergency Email List (Manual)", key="extra_emails", placeholder="email1@gmail.com, email2@gmail.com")

# ─── MACHINE LEARNING ENGINE ──────────────────────────────────
@st.cache_resource
def initialize_ai():
    safe_data = [
        "I am safe now", "Reached home safely", "I am at home", "Everything is okay", 
        "Going to the market", "At the office now", "Reached college safely", 
        "I am fine", "With my family", "Just reached my destination", "All good here",
        "Waiting for the bus", "I'm safe", "Safe and sound", "I reached safely"
    ]
    danger_data = [
        "Help me please", "I am in big danger", "Someone is following me", 
        "I feel unsafe here", "Emergency help needed", "Please save me", 
        "I am being attacked", "Call the police now", "Someone is stalking me",
        "I am scared", "Stop following me", "I am trapped", "Help help help",
        "Send help to my location", "I am in trouble"
    ]
    
    all_texts = safe_data + danger_data
    all_labels = ["safe"] * len(safe_data) + ["danger"] * len(danger_data)
    
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(all_texts)
    
    classifier = RandomForestClassifier(n_estimators=100, random_state=42)
    classifier.fit(X, all_labels)
    
    return classifier, vectorizer

safety_model, safety_vectorizer = initialize_ai()

# ─── CORE COMMUNICATION FUNCTIONS ─────────────────────────────
def get_all_recipients():
    contact_emails = [c["email"] for c in st.session_state.contacts if c.get("email")]
    extra_emails_list = [e.strip() for e in manual_emails.replace("\n", ",").split(",") if e.strip()]
    return list(set(contact_emails + extra_emails_list))

def get_all_phone_numbers():
    return [c["phone"] for c in st.session_state.contacts if c.get("phone")]

def trigger_email_alert(subject, content):
    sender = st.session_state.get("sender_email")
    password = st.session_state.get("sender_password")
    recipients = get_all_recipients()
    
    if not sender or not password or not recipients:
        st.error("📧 Email alert failed: Configuration incomplete.")
        return False
        
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender, password)
        for target in recipients:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = target
            msg.attach(MIMEText(content, 'plain'))
            server.sendmail(sender, target, msg.as_string())
            st.info(f"📧 Alert successfully sent to: **{target}**")
        server.quit()
        return True
    except Exception as e:
        st.error(f"Mail System Error: {e}")
        return False

def generate_sms_links(message_body):
    phones = get_all_phone_numbers()
    if phones:
        st.markdown("### 📲 One-Tap SMS Alerts")
        st.info("Tap the links below to send an instant SMS from your phone.")
        for phone in phones:
            encoded_msg = urllib.parse.quote(message_body[:300])
            st.markdown(f"👉 [Send Emergency SMS to {phone}](sms:{phone}?body={encoded_msg})")

def compose_alert_text(header, user_message, risk_level, confidence=""):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = (
        f"{'='*30}\n"
        f"🚨 {header}\n"
        f"{'='*30}\n\n"
        f"USER: {st.session_state.get('user_name', 'Unknown')}\n"
        f"PHONE: {st.session_state.get('user_phone', 'Not Set')}\n"
        f"TIME: {timestamp}\n\n"
        f"MESSAGE: {user_message}\n"
        f"RISK ASSESSMENT: {risk_level}\n"
    )
    if confidence:
        body += f"AI CONFIDENCE: {confidence}%\n"
    body += f"\n{'='*30}"
    return body

# ─── FAKE CALL MODULE ──────────────────────────────────────────
if st.session_state.fake_call_active:
    st.markdown("""
        <div style="text-align:center; padding:100px 20px; background-color:#000; color:white; border-radius:30px;">
            <h1 style="font-size:100px;">📱</h1>
            <h2 style="font-size:40px;">Mom</h2>
            <p style="color:#aaa;">Incoming Call...</p>
            <br><br><br>
            <div style="display:flex; justify-content:center; gap:80px;">
                <div style="color:#f44336; font-size:60px;">🔴</div>
                <div style="color:#4caf50; font-size:60px;">🟢</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("❌ Terminate Call"):
        st.session_state.fake_call_active = False
        st.rerun()
    st.stop()

# ─── SOS COUNTDOWN MODULE ─────────────────────────────────────
if st.session_state.sos_countdown:
    elapsed_time = time.time() - st.session_state.sos_start
    countdown_val = max(0, 10 - int(elapsed_time))
    
    st.markdown(f"<div class='countdown'>🚨 SOS IN {countdown_val} SECONDS</div>", unsafe_allow_html=True)
    
    if st.button("🛑 STOP SOS - I AM SAFE", use_container_width=True, type="primary"):
        st.session_state.sos_countdown = False
        st.rerun()
        
    if countdown_val == 0:
        st.session_state.sos_countdown = False
        emergency_text = compose_alert_text("EMERGENCY PANIC ALERT", "The user triggered the manual SOS button.", "CRITICAL", "100")
        trigger_email_alert("🚨 EMERGENCY: SOS FROM SAFEGUARD", emergency_text)
        generate_sms_links(emergency_text)
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()

# ─── MAIN INTERFACE TABS ──────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["🚨 Alert Hub", "⏱️ Safety Timer", "📝 Activity Log", "📘 User Guide"])

with t1:
    st.markdown("### Emergency Dashboard")
    col_sos, col_safe = st.columns(2)
    
    with col_sos:
        if st.button("🚨 TRIGGER SOS", use_container_width=True, help="Starts a 10s countdown to alert everyone."):
            st.session_state.sos_countdown = True
            st.session_state.sos_start = time.time()
            st.rerun()
            
    with col_safe:
        if st.button("✅ I AM SAFE", use_container_width=True, help="Send a 'Safe' update to your contacts."):
            safe_text = compose_alert_text("SAFETY UPDATE", "I am safe and okay.", "NONE")
            trigger_email_alert("🟢 SafeGuard: User is Safe", safe_text)
            generate_sms_links(safe_text)

    if st.button("📞 Initiate Fake Call", use_container_width=True):
        st.session_state.fake_call_active = True
        st.rerun()

    st.divider()
    st.markdown("### 🤖 AI Threat Analysis")
    st.write("Type a message or click an example below to analyze risk and alert contacts.")
    
    example_prompts = [
        "Help me someone is following me", 
        "I am safe at home", 
        "Emergency please help", 
        "I'm going to market", 
        "I feel unsafe in this cab", 
        "Reached college safely",
        "Someone is stalking me",
        "I am fine now",
        "Help! I'm in trouble"
    ]
    
    cols = st.columns(3)
    for index, text in enumerate(example_prompts):
        if cols[index % 3].button(text, key=f"ex_btn_{index}", use_container_width=True):
            st.session_state.typed_msg = text
            st.rerun()

    user_input = st.text_area("Describe your situation:", key="typed_msg", height=120)
    
    if st.button("🔍 Run AI Analysis & Alert Contacts", use_container_width=True, type="primary"):
        if user_input.strip():
            transformed_input = safety_vectorizer.transform([user_input])
            prediction = safety_model.predict(transformed_input)[0]
            probabilities = safety_model.predict_proba(transformed_input)[0]
            confidence_score = round(float(max(probabilities)) * 100, 2)
            
            # Hybrid Risk logic (AI + Keywords)
            safe_keywords = ["safe", "home", "market", "college", "fine", "okay", "arrived"]
            is_keyword_safe = any(word in user_input.lower() for word in safe_keywords)
            
            risk_label = "HIGH RISK" if (prediction == "danger" and not is_keyword_safe) else "LOW RISK"
            
            analysis_alert = compose_alert_text("AI ANALYSIS ALERT", user_input, risk_label, confidence_score)
            
            st.subheader("Analysis Result")
            if risk_label == "HIGH RISK":
                st.error(f"Threat Detected: {risk_label} ({confidence_score}%)")
            else:
                st.success(f"Result: {risk_label} ({confidence_score}%)")
            
            st.code(analysis_alert)
            trigger_email_alert(f"🚨 SafeGuard Alert: {risk_label}", analysis_alert)
            generate_sms_links(analysis_alert)
            
            st.session_state.history.append({
                "Timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "Risk": risk_label,
                "Message": user_input
            })
        else:
            st.warning("Please enter a message to analyze.")

with t2:
    st.markdown("### ⏱️ Automated Check-in Timer")
    st.write("Set a timer when you are traveling. If you don't 'Check-in' before it ends, we alert your contacts.")
    
    timer_mins = st.slider("Select Duration (Minutes):", 1, 120, 15)
    
    if not st.session_state.checkin_active:
        if st.button("▶️ START TIMER", use_container_width=True):
            st.session_state.checkin_active = True
            st.session_state.checkin_end = datetime.datetime.now() + datetime.timedelta(minutes=timer_mins)
            st.rerun()
    else:
        time_diff = (st.session_state.checkin_end - datetime.datetime.now()).total_seconds()
        
        if time_diff > 0:
            st.warning(f"⏳ ALERT PENDING: {int(time_diff // 60)}m {int(time_diff % 60)}s remaining.")
            if st.button("✅ I AM SAFE - STOP TIMER", use_container_width=True):
                st.session_state.checkin_active = False
                st.success("Timer deactivated.")
                st.rerun()
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.checkin_active = False
            timer_sos = compose_alert_text("MISSED CHECK-IN ALERT", f"The user set a {timer_mins} minute timer and failed to check in.", "HIGH RISK", "100")
            trigger_email_alert("🚨 EMERGENCY: MISSED CHECK-IN", timer_sos)
            generate_sms_links(timer_sos)
            st.error("Time expired! Emergency alerts have been sent.")

with t3:
    st.markdown("### 📊 Activity History")
    if st.session_state.history:
        history_df = pd.DataFrame(st.session_state.history)
        st.table(history_df)
        if st.button("Clear Log"):
            st.session_state.history = []
            st.rerun()
    else:
        st.info("No activity recorded in this session.")

with t4:
    st.markdown("## 📖 Comprehensive Safety Guide")
    
    st.markdown("### 🔑 Setting up your Gmail App Password")
    st.markdown("""
    To allow SafeGuard to send emails automatically, you must generate a special **App Password**.
    <div class='step-box'>
        1. Go to your <a href='https://myaccount.google.com/' target='_blank'>Google Account Settings</a>.<br>
        2. Select <b>Security</b> from the left sidebar.<br>
        3. Under "How you sign in to Google," ensure <b>2-Step Verification</b> is enabled.<br>
        4. In the search bar at the top of the screen, type <b>"App Passwords"</b>.<br>
        5. Provide a name (e.g., "Safety Portal") and click <b>Create</b>.<br>
        6. <b>Copy the 16-character code</b> shown in the yellow box.<br>
        7. Paste this code into the "Gmail App Password" field in this app's sidebar.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🛠️ App Features Explained")
    
    st.markdown("""
    <div class='help-card'>
        <b>🚨 Emergency SOS:</b> Triggers a loud visual countdown. If you don't stop it in 10 seconds, an alert is emailed to everyone in your list.
    </div>
    <div class='help-card'>
        <b>🤖 AI Analysis:</b> Not sure if you should be worried? Type a message describing your situation. 
        Our AI detects danger signals and alerts your family with a professional risk assessment.
    </div>
    <div class='help-card'>
        <b>⏱️ Safety Timer:</b> Perfect for taxi rides. Set a timer for the estimated trip duration. 
        If you don't check in safely, your family gets an alert automatically.
    </div>
    <div class='help-card'>
        <b>📞 Fake Call:</b> If you feel someone is following you or making you uncomfortable, use this to 
        simulate an incoming call from 'Mom'. It gives you a reason to walk away or talk loudly.
    </div>
    <div class='help-card'>
        <b>📩 SMS Integration:</b> After any alert, the app provides direct 'SMS Links'. Tap them to 
        open your messaging app with a pre-written text.
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.caption("Shielding you with AI · 🛡️ SafeGuard Portal 2026")