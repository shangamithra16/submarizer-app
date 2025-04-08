import streamlit as st 
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import mysql.connector
import hashlib
import razorpay 
from datetime import datetime, timedelta

# Razorpay client setup using Streamlit secrets
razorpay_client = razorpay.Client(
    auth=(st.secrets["RAZORPAY_KEY_ID"], st.secrets["RAZORPAY_KEY_SECRET"])
)

def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["DB_HOST"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        database=st.secrets["DB_NAME"]
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COLUMN_NAME 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'is_subscribed'
    """)
    if not cursor.fetchone():
        cursor.execute("""
        ALTER TABLE users
        ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE,
        ADD COLUMN subscription_date TIMESTAMP NULL,
        ADD COLUMN subscription_end_date TIMESTAMP NULL,
        ADD COLUMN razorpay_payment_id VARCHAR(255) NULL
        """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_files (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        file_name VARCHAR(255) NOT NULL,
        file_type VARCHAR(50) NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
init_db()

# Razorpay functions
def create_razorpay_payment_link(amount, user_id, email):
    try:
        payment_link = razorpay_client.payment_link.create({
            "amount": int(amount * 100),
            "currency": "INR",
            "description": "EasyLearn Monthly Subscription",
            "customer": {"email": email},
            "notify": {"email": True},
            "callback_url": "http://localhost:8501",
            "callback_method": "get"
        })
        return payment_link['short_url'], payment_link['id']
    except Exception as e:
        st.error(f"Failed to create payment link: {e}")
        return None, None

def verify_payment_link(payment_link_id):
    try:
        payment_link = razorpay_client.payment_link.fetch(payment_link_id)
        return payment_link["status"] == "paid"
    except:
        return False

def update_subscription_status(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()
        end_date = now + timedelta(days=30)
        cursor.execute(
            """UPDATE users 
            SET is_subscribed = TRUE, 
                subscription_date = %s, 
                subscription_end_date = %s 
            WHERE id = %s""",
            (now, end_date, user_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating subscription: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_subscription(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT is_subscribed, subscription_end_date FROM users WHERE id = %s",
            (user_id,))
        user = cursor.fetchone()
        if user and user['is_subscribed']:
            if user['subscription_end_date'] and user['subscription_end_date'] > datetime.now():
                return True
            else:
                cursor.execute("UPDATE users SET is_subscribed = FALSE WHERE id = %s", (user_id,))
                conn.commit()
        return False
    finally:
        cursor.close()
        conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)",
            (username, hash_password(password), email)
        )
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error creating user: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, password_hash, email FROM users WHERE username = %s",
        (username.lower(),)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user and user['password_hash'] == hash_password(password):
        return user
    return None

# UI Styling
st.markdown(
    """
    <style>
        [data-testid="stAppViewContainer"] {
            background-color: #2C2F33;
        }
        .main {
            background-color: #FAFAFA;
            padding: 20px;
            border-radius: 10px;
        }
        div.stButton > button {
            background-color: #D4A3FF;
            color: black;
            font-size: 16px;
            border-radius: 8px;
            padding: 10px 20px;
        }
        .flashcard-q {
            background-color: #F0E6FF;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 5px;
            font-weight: bold;
        }
        .flashcard-a {
            background-color: #E6F3FF;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Auth state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Login/Signup
if not st.session_state.authenticated:
    st.markdown("<h1 style='color: white;'>EasyLearn - Login</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            if submit:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.current_user = user
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("signup_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submit = st.form_submit_button("Create Account")
            
            if submit:
                if new_password != confirm_password:
                    st.error("Passwords don't match!")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    if create_user(new_username, new_password, new_email):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username or email already exists")
    
    st.stop()

# Subscription check
if not check_subscription(st.session_state.current_user['id']):
    st.warning("""
    🔒 Premium Access Required  
    To use EasyLearn, please subscribe for ₹10/month.
    """)
    
    if st.button("Subscribe Now (₹10)"):
        payment_link_url, payment_link_id = create_razorpay_payment_link(
            10,
            st.session_state.current_user['id'],
            st.session_state.current_user.get('email', '')
        )
        if payment_link_url:
            st.session_state.razorpay_payment_link_id = payment_link_id
            st.markdown(f"[👉 Click here to pay securely via Razorpay]({payment_link_url})", unsafe_allow_html=True)
            st.stop()

    if "payment_link_id" in st.query_params:
        returned_id = st.query_params["payment_link_id"]
        if returned_id == st.session_state.get("razorpay_payment_link_id"):
            if verify_payment_link(returned_id):
                if update_subscription_status(st.session_state.current_user['id']):
                    st.success("✅ Subscription activated! Thank you for your support.")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Error updating subscription.")
            else:
                st.error("❌ Payment not completed or failed.")
    st.stop()

# App Header
st.markdown(
    f"""
    <div style='display: flex; align-items: center; gap: 10px;'>
        <h1 style='margin: 0; color: white;'>EasyLearn</h1>
        <div style='margin-left: auto;'>
            <span style='color: white;'>Welcome, {st.session_state.current_user['username']}</span>
            <button onclick="window.location.href='?logout=true'" style='margin-left: 10px; background-color: #FF6B6B; color: white; border: none; border-radius: 4px; padding: 5px 10px;'>Logout</button>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.query_params.get('logout'):
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.query_params.clear()
    st.rerun()

# Langchain setup
llm = ChatOpenAI(model="gpt-4o-mini")
parser = StrOutputParser()
prompt_template = ChatPromptTemplate.from_template("Summarize the following document {document}")
chain = prompt_template | llm | parser

uploaded_file = st.file_uploader("Upload a Text, PDF or CSV file.", type=["txt", "pdf", "csv"])

if uploaded_file is not None:
    with st.spinner("Processing..."):
        try:
            temp_file_path = uploaded_file.name
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            if uploaded_file.type == "text/plain":
                loader = TextLoader(temp_file_path)
            elif uploaded_file.type == "text/csv":
                loader = CSVLoader(temp_file_path)
            elif uploaded_file.type == "application/pdf":
                loader = PyPDFLoader(temp_file_path)
            else:   
                st.error("File type is not supported!")
                st.stop()
            
            doc = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(doc)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_files (user_id, file_name, file_type) VALUES (%s, %s, %s)",
                (st.session_state.current_user['id'], uploaded_file.name, uploaded_file.type)
            )
            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            st.error(f"Error processing file: {e}")
            st.stop()

    st.success("File Uploaded")

def summarize_text(chunks):
    chunk_summaries = []
    with st.spinner("Summarizing Chunks..."):
        for chunk in chunks:
            chunk_prompt = ChatPromptTemplate.from_template("Summarize the following chunk:\n\n{document}")
            chunk_chain = chunk_prompt | llm | parser
            chunk_summary = chunk_chain.invoke({"document": chunk})
            chunk_summaries.append(chunk_summary)
    
    with st.spinner("Creating final summary..."):
        combined = "\n".join(chunk_summaries)
        final_prompt = ChatPromptTemplate.from_template("Create a comprehensive summary:\n\n{document}")
        final_chain = final_prompt | llm | parser 
        return final_chain.invoke({"document": combined})

def generate_flashcards(text):
    flashcard_prompt = ChatPromptTemplate.from_template("Generate 5 flashcards (Q&A) from:\n\n{document}")
    flashcard_chain = flashcard_prompt | llm | parser
    return flashcard_chain.invoke({"document": text})

if st.button("Summarize"):
    final_summary = summarize_text(chunks)
    if final_summary:
        st.session_state.final_summary = final_summary 
        st.subheader("Summary")
        st.write(final_summary)
        st.download_button("Download Summary", data=final_summary, file_name="summary.txt", mime="text/plain")

if st.button("Generate Flashcards"):
    with st.spinner("Generating flashcards..."):
        base_text = st.session_state.final_summary if 'final_summary' in st.session_state else doc[0].page_content
        flashcards = generate_flashcards(base_text)
        if flashcards:
            st.subheader("Flashcards")
            flashcard_list = flashcards.split('\n')
            for i in range(0, len(flashcard_list), 2):
                if i + 1 < len(flashcard_list):
                    st.markdown(f"<div class='flashcard-q'>Q: {flashcard_list[i]}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='flashcard-a'>A: {flashcard_list[i + 1]}</div>", unsafe_allow_html=True)

st.markdown("---")
st.subheader("Ask Questions About the Summary")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = st.chat_input("Ask a question about the summary...")

if user_input:
    if "final_summary" not in st.session_state:
        st.error("Please generate a summary first!")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        chatbot_prompt = ChatPromptTemplate.from_template(
            "You are an AI assistant. Answer the following question based on this summary:\n\n{summary}\n\nQ: {question}"
        )
        chatbot_chain = chatbot_prompt | llm | parser
        ai_response = chatbot_chain.invoke({
            "summary": st.session_state.final_summary,
            "question": user_input
        })
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.write(ai_response)
