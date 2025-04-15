import streamlit as st 
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()


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
            background-color: #D4A3FF ;
            color: black;
            font-size: 16px;
            border-radius: 8px;
            padding: 10px 20px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Summarizer & Flashcards App")

uploaded_file = st.file_uploader("Upload a Text, PDF or CSV file.", type=["txt", "pdf", "csv"])

llm = ChatOpenAI(model="gpt-3.5-turbo")
parser = StrOutputParser()
prompt_template = ChatPromptTemplate.from_template("Summarize the following document {document}")

chain = prompt_template | llm | parser

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
        st.session_state.final_summary = final_summary  # Store summary in session state
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
