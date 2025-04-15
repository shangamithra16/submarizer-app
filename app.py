import streamlit as st 
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()
st.title("Summarizer & Flashcards App")
st.divider()

st.markdown("## Start summarizing your documents and generating flashcards.")

# Upload file
uploaded_file = st.file_uploader("Upload a Text, PDF or CSV file.", type=["txt", "pdf", "csv"])

llm = ChatOpenAI(model="gpt-4o-mini")
parser = StrOutputParser()

prompt_template = ChatPromptTemplate.from_template("Summarize the following document {document}")

# Chain
chain = prompt_template | llm | parser

if uploaded_file is not None:
    with st.spinner("Processing..."):
        try:
            temp_file_path = uploaded_file.name
            
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            # Create document loader
            if uploaded_file.type == "text/plain":
                loader = TextLoader(temp_file_path)
            elif uploaded_file.type == "text/csv":
                loader = CSVLoader(temp_file_path)
            elif uploaded_file.type == "application/pdf":
                loader = PyPDFLoader(temp_file_path)
            else:   
                st.error("File type is not supported!")
                st.stop()
            
            # Create the document
            doc = loader.load()
            
            # Text Splitter
            text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(doc)
        
        except Exception as e:
            st.error(f"Error processing file: {e}")
            st.stop()
    
    st.success("File Uploaded")
    
# Summarize
def summarize_text(chunks):
    chunk_summaries = []
    with st.spinner("Summarizing Chunks..."):
        try:
            for chunk in chunks:
                chunk_prompt = ChatPromptTemplate.from_template(
                    "Summarize the following chunk of text in a concise manner:\n\n{document}"
                ) 
                chunk_chain = chunk_prompt | llm | parser
                chunk_summary = chunk_chain.invoke({"document": chunk})
                chunk_summaries.append(chunk_summary)
        except Exception as e:
            st.error(f"Error summarizing chunks: {e}")
            return None
    
    with st.spinner("Creating final summary..."):
        try:
            combined_summaries = "\n".join(chunk_summaries)
            final_prompt = ChatPromptTemplate.from_template(
                "Combine the key points from the provided summaries into a cohesive and comprehensive summary:\n\n{document}"
            )
            final_chain = final_prompt | llm | parser 
            return final_chain.invoke({"document": combined_summaries})
        except Exception as e:
            st.error(f"Error creating final summary: {e}")
            return None

# Generate Flashcards
def generate_flashcards(text):
    flashcard_prompt = ChatPromptTemplate.from_template(
        "Generate 5 flashcards (question-answer pairs) from the following text:\n\n{document}"
    )
    flashcard_chain = flashcard_prompt | llm | parser
    return flashcard_chain.invoke({"document": text})

if st.button("Summarize"):
    final_summary = summarize_text(chunks)
    if final_summary:
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
        flashcards = generate_flashcards(final_summary if 'final_summary' in locals() else doc[0].page_content)
        
        if flashcards:
            st.subheader("Flashcards")
            flashcard_list = flashcards.split('\n')
            for i in range(0, len(flashcard_list), 2):
                if i + 1 < len(flashcard_list):
                    with st.expander(flashcard_list[i]):
                        st.write(flashcard_list[i + 1])
