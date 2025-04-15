import streamlit as st 
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import mysql.connector
import hashlib
import os

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL
    )
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
        "SELECT id, username, password_hash FROM users WHERE username = %s",
        (username,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user and user['password_hash'] == hash_password(password):
        return user
    return None


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


if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None


if not st.session_state.authenticated:
    st.markdown(
        """
        <div style='display: flex; align-items: center; gap: 10px;'>
            <h1 style='margin: 0; color: white;'>EasyLearn - Login</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
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

st.markdown(
    """
    <div style='display: flex; align-items: center; gap: 10px;'>
        <h1 style='margin: 0; color: white;'>EasyLearn</h1>
        <div style='margin-left: auto;'>
            <span style='color: white;'>Welcome, {}</span>
            <button onclick="window.location.href='?logout=true'" style='margin-left: 10px; background-color: #FF6B6B; color: white; border: none; border-radius: 4px; padding: 5px 10px; cursor: pointer;'>Logout</button>
        </div>
    </div>
    """.format(st.session_state.current_user['username']),
    unsafe_allow_html=True
)
if st.query_params.get('logout'):
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.query_params.clear()
    st.rerun()



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
        try:
            for chunk in chunks:
                chunk_prompt = ChatPromptTemplate.from_template("Summarize the following chunk:\n\n{document}")
                chunk_chain = chunk_prompt | llm | parser
                chunk_summary = chunk_chain.invoke({"document": chunk})
                chunk_summaries.append(chunk_summary)
        except Exception as e:
            st.error(f"Error summarizing chunks: {e}")
            return None
    
    with st.spinner("Creating final summary..."):
        try:
            combined_summaries = "\n".join(chunk_summaries)
            final_prompt = ChatPromptTemplate.from_template("Create a comprehensive summary:\n\n{document}")
            final_chain = final_prompt | llm | parser 
            return final_chain.invoke({"document": combined_summaries})
        except Exception as e:
            st.error(f"Error creating final summary: {e}")
            return None

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
        
        st.download_button(
            label="Download Summary",
            data=final_summary,
            file_name="summary.txt",
            mime="text/plain"
        )

if st.button("Generate Flashcards"):
    with st.spinner("Generating flashcards..."):
        flashcards = generate_flashcards(st.session_state.final_summary if 'final_summary' in st.session_state else doc[0].page_content)
        
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
        chatbot_prompt = ChatPromptTemplate.from_template("You are an AI assistant. Answer the following question based on this summary:\n\n{summary}\n\nQ: {question}")
        chatbot_chain = chatbot_prompt | llm | parser
        ai_response = chatbot_chain.invoke({"summary": st.session_state.final_summary, "question": user_input})
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.write(ai_response) 
