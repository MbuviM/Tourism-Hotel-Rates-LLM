import streamlit as st
from PyPDF2 import PdfReader
from openai import OpenAI
import re

# Streamlit UI configuration (must be the first Streamlit command)
st.set_page_config(page_title="🌴 Tourism Rate Explainer", layout="wide")

# Access API key from Streamlit secrets
api_key = st.secrets["OPENAI_API_KEY"]
assistant_id = st.secrets["assistant_id"]

# Initialize OpenAI client with the API key
client = OpenAI(api_key=api_key)

# Custom CSS
st.markdown("""
<style>
.big-font {
    font-size:18px !important;
}
.stButton>button {
    background-color: #4CAF50;
    color: white;
    font-size: 16px;
}
.sidebar .sidebar-content {
    background-image: linear-gradient(#f0f8ff,#e6f3ff);
}
</style>
""", unsafe_allow_html=True)

# Sidebar for conversation history
st.sidebar.title("Conversation History")
if 'history' not in st.session_state:
    st.session_state['history'] = []

# Button to clear conversation history
if st.sidebar.button("Clear History"):
    st.session_state['history'] = []
    st.sidebar.success("History cleared.")

# Navigation for previous conversations
if st.session_state['history']:
    selected_index = st.sidebar.selectbox(
        "Select a conversation to view:",
        list(range(len(st.session_state['history']))),
        format_func=lambda x: f"Query {x + 1}"
    )
    
    if selected_index is not None:
        user_query, response = st.session_state['history'][selected_index]
        st.sidebar.markdown(f"**Query {selected_index + 1}:** {user_query}")
        st.sidebar.markdown(f"**Response:** {response[:100]}...")  # Show truncated response

# Main content area
st.title("Tourism Rate Explainer 🌴")

# File upload section
uploaded_files = st.file_uploader("Upload your documents (PDFs)", type="pdf", accept_multiple_files=True)

# User query input
user_query = st.text_area("How can I help you better understand the uploaded files?:", "")

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Process the user query if provided
if user_query and st.session_state['uploaded_files']:
    document_text = ""
    for file in st.session_state['uploaded_files']:
        document_text += extract_text_from_pdf(file)

if st.button("Submit Query"):
    if st.session_state['uploaded_files'] and user_query:
        documents_content = ""
        for uploaded_file in st.session_state['uploaded_files']:
            # Extract text content from each uploaded PDF
            file_content = extract_text_from_pdf(uploaded_file)
            documents_content += f"\n\n{file_content}"

        if documents_content:
            with st.spinner('Processing your request...'):
                # Create a thread for the user's query
                thread = client.beta.threads.create(
                    messages=[
                        {
                            "role": "user",
                            "content": f"{user_query}\n\nDocuments:\n{documents_content}",
                        }
                    ]
                )
                
                # Run and poll the thread for a response
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=thread.id, assistant_id=assistant_id
                )
                
                # Retrieve messages
                messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
                
                if not messages:
                    st.error("No response received. Please try again.")
                else:
                    try:
                        message_content = messages[0].content[0].text if messages[0].content else None
                        if message_content:
                            # Clean up the response
                            cleaned_response = message_content.value
                            cleaned_response = re.sub(r'【\d+:\d+†source】', '', cleaned_response)
                            
                            # Store conversation in session state
                            st.session_state['history'].append((user_query, cleaned_response))
                            
                            # Display the response
                            st.markdown("<hr>", unsafe_allow_html=True)
                            st.markdown(f'<div class="big-font">{cleaned_response}</div>', unsafe_allow_html=True)
                            
                        else:
                            st.error("Response content is missing or malformed.")
                    except (IndexError, AttributeError) as e:
                        st.error(f"An error occurred while processing the response: {e}")
    else:
        st.warning("Please upload files and enter a query.")
        
# Footer
st.markdown("""
<hr>
<footer style='text-align: center; color: #aaa; padding: 10px;'>
    Powered by OpenAI | Built with Streamlit
</footer>
""", unsafe_allow_html=True)

# Instructions to run the Streamlit app
if __name__ == "__main__":
    st.sidebar.info("To run this Streamlit app, use the command: `streamlit run ChatApp.py`")
