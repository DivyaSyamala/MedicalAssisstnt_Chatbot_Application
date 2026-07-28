import streamlit as st
from main import MedicalAssistant
import sys
import os
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

# Adds the 'src' directory to the system path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment configuration from .env
load_dotenv()

from database.auth_db import init_db, add_user, authenticate_user, verify_user, save_history, get_history, save_reset_code, verify_reset_code, reset_password, get_user_by_email, get_user_by_username, generate_reset_code

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8501"  # Adjust for your Streamlit port

# Initialize Database
init_db()

st.set_page_config(page_title="AI Medical Portal", page_icon="🏥")

# Handle Google OAuth callback
query_params = st.query_params
if "code" in query_params:
    code = query_params.get("code")
    if isinstance(code, list):
        code = code[0]
    if code:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
                headers = {"Authorization": f"Bearer {access_token}"}
                user_response = requests.get(user_info_url, headers=headers)
                if user_response.status_code == 200:
                    user_info = user_response.json()
                    email = user_info.get("email")
                    name = user_info.get("name", email)
                    username = get_user_by_email(email)
                    if not username:
                        add_user(name, "google_auth", email)
                        username = name
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.google_auth = True
                    try:
                        st.query_params = {}
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.error("Google user info fetch failed.")
            else:
                st.error("Google token response missing access_token.")
        else:
            st.error(f"Google login failed: {response.status_code} {response.text}")

# Session State Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "bot" not in st.session_state:
    st.session_state.bot = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "auto_analysis" not in st.session_state:
    st.session_state.auto_analysis = None
if "google_auth" not in st.session_state:
    st.session_state.google_auth = False

# Sidebar Navigation
if not st.session_state.logged_in:
    page = st.sidebar.radio("Navigation", ["Login", "Sign Up", "Forgot Password"])
else:
    page = st.sidebar.radio("Navigation", ["AI Assistant", "Search History"])
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.bot = None  # Reset bot
        st.session_state.uploaded_file = None
        st.session_state.auto_analysis = None
        st.session_state.google_auth = False
        st.rerun()

# --- PAGE: SIGN UP ---
if page == "Sign Up":
    st.title("Create Account")
    with st.form("signup_form"):
        new_user = st.text_input("Username")
        new_email = st.text_input("Email")
        new_pw = st.text_input("Password", type="password")
        if st.form_submit_button("Register"):
            if not new_user or not new_email or not new_pw:
                st.error("Please fill in all fields.")
            elif len(new_pw) < 6:
                st.error("Password must be at least 6 characters long.")
            elif "@" not in new_email:
                st.error("Please enter a valid email address.")
            else:
                if add_user(new_user, new_pw, new_email):
                    st.success("Account created! Please switch to Login.")
                else:
                    st.error("Username already exists.")

# --- PAGE: LOGIN ---
elif page == "Login":
    st.title("User Login")
    with st.form("login_form"):
        user = st.text_input("Username or Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if not user or not pw:
                st.error("Please fill in all fields.")
            else:
                authenticated_username = authenticate_user(user, pw)
                if authenticated_username:
                    st.session_state.logged_in = True
                    st.session_state.username = authenticated_username
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please check your username/email and password.")
    
    st.divider()
    if st.button("Login with Google"):
        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
            auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": "openid email profile",
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
            })
            st.markdown(f'<a href="{auth_url}" target="_blank">Click here to login with Google</a>', unsafe_allow_html=True)
            st.info("After authorizing, you'll be redirected back to localhost:8501.")
        else:
            st.error("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")

# --- PAGE: FORGOT PASSWORD ---
elif page == "Forgot Password":
    st.title("Forgot Password")
    if "reset_step" not in st.session_state:
        st.session_state.reset_step = "identifier"
    
    if st.session_state.reset_step == "identifier":
        with st.form("forgot_form"):
            identifier = st.text_input("Enter your email address or username").strip()
            if st.form_submit_button("Send Reset Code"):
                if not identifier:
                    st.error("Please enter your email or username.")
                else:
                    username = None
                    email = None
                    if "@" in identifier:
                        username = get_user_by_email(identifier)
                        email = identifier.strip().lower()
                        if not username:
                            user = get_user_by_username(identifier)
                            if user:
                                username, email = user
                    else:
                        user = get_user_by_username(identifier)
                        if user:
                            username, email = user
                    if username:
                        code = generate_reset_code()
                        save_reset_code(identifier, code)
                        temp_bot = MedicalAssistant()
                        if email:
                            if temp_bot.send_reset_email(email, code):
                                st.success("Reset code sent to your email.")
                            else:
                                st.success("Reset code generated. (Email failed, code: " + code + ")")
                        else:
                            st.success("Reset code generated. Use this code to reset your password: " + code)
                        st.session_state.reset_identifier = identifier
                        st.session_state.reset_step = "code"
                        st.rerun()
                    else:
                        st.error("Account not found. Use your registered email or username.")
    
    elif st.session_state.reset_step == "code":
        with st.form("code_form"):
            code = st.text_input("Enter the reset code")
            new_pw = st.text_input("New Password", type="password")
            if st.form_submit_button("Reset Password"):
                if not code or not new_pw:
                    st.error("Please fill in all fields.")
                elif len(new_pw) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    identifier = st.session_state.get("reset_identifier", "")
                    if verify_reset_code(identifier, code):
                        if reset_password(identifier, new_pw):
                            st.success("Password reset successfully! Please login.")
                            st.session_state.reset_step = "identifier"
                            st.rerun()
                        else:
                            st.error("Error resetting password.")
                    else:
                        st.error("Invalid or expired code.")

# --- PAGE: AI ASSISTANT ---
elif page == "AI Assistant":
    st.title(f"Welcome, {st.session_state.username}")
    
    # Initialize the assistant once
    if st.session_state.bot is None:
        st.session_state.bot = MedicalAssistant()
    
    bot = st.session_state.bot
    
    # Report Upload
    uploaded_file = st.file_uploader("Upload Medical Report", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    if uploaded_file is not None:
        if st.session_state.uploaded_file != uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            st.session_state.auto_analysis = None  # Reset analysis
            with st.spinner("Analyzing report..."):
                try:
                    analysis, is_complicated = bot.auto_analyze(uploaded_file)
                    st.session_state.auto_analysis = analysis
                    if is_complicated:
                        st.warning("⚠️ Potential complications detected. Please consult a doctor.")
                except Exception as e:
                    st.error(f"Error analyzing report: {e}")
        
        st.info(f"📁 {uploaded_file.name} ready for analysis.")
        if st.session_state.auto_analysis:
            with st.expander("📋 Quick Scan Results"):
                st.write(st.session_state.auto_analysis)
    
    # Chat Input
    if prompt := st.chat_input("Describe your symptoms or ask about the report..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if uploaded_file:
                        raw_response, is_complicated = bot.ask(prompt, file=uploaded_file)
                    else:
                        raw_response, is_complicated = bot.ask(prompt)
                    
                    # Clean response
                    if isinstance(raw_response, str):
                        clean_response = raw_response
                    elif isinstance(raw_response, list) and raw_response:
                        clean_response = str(raw_response[0].get('text', raw_response[0]))
                    else:
                        clean_response = "No response generated."
                    
                    st.markdown(clean_response)
                    
                    if is_complicated:
                        st.warning("⚠️ This response indicates potential complications. Please seek medical attention.")
                    
                    # SAVE TO HISTORY
                    save_history(st.session_state.username, prompt, clean_response)
                    
                except Exception as e:
                    st.error(f"Error generating response: {e}")

# --- PAGE: SEARCH HISTORY ---
elif page == "Search History":
    st.title("Your Consultation History")
    history = get_history(st.session_state.username)
    
    if not history:
        st.info("No history found.")
    else:
        # Reversed history so newest entries appear first
        for q, r, t in reversed(history):
            with st.expander(f"🔍 {q[:50]}... ({t})"):
                st.write(f"**Question:** {q}")
                st.write(f"**Assistant:** {r}")