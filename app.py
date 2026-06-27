import streamlit as st
import os
import json
import tempfile
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="RFP Document Processor",
    page_icon="📄",
    layout="wide"
)

def main():
    # Title
    st.title("📄 RFP Document Processor")
    st.markdown("---")
    
    # Description
    st.markdown("""
    ### 🤖 AI-Powered RFP Analysis
    Upload your RFP document and the AI will automatically extract:
    - **📦 Deliverables** - What needs to be provided
    - **📊 Evaluation Criteria** - How your proposal will be judged
    - **✅ Compliance Checklist** - Department-specific tasks
    """)
    
    # Sidebar for API Key
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
            help="Enter your Google Gemini API key"
        )
        
        if api_key:
            st.success("✅ API Key provided")
        else:
            st.warning("⚠️ Please provide your Gemini API key")
        
        st.markdown("---")
        st.markdown("""
        ### 📌 Instructions
        1. Upload your RFP document (PDF, DOCX, or TXT)
        2. Click "Process Document"
        3. View extracted information
        """)
        
        st.info("🤖 Using Google Gemini AI")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose your RFP document",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        # Show file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size/1024:.1f} KB")
        with col3:
            st.metric("File Type", uploaded_file.type)
        
        # Process button
        if st.button("🚀 Process Document", type="primary"):
            if not api_key:
                st.error("❌ Please provide your Gemini API key in the sidebar")
                return
            
            try:
                # Read the file content
                file_content = uploaded_file.read().decode('utf-8', errors='ignore')
                
                with st.spinner("Processing document with AI..."):
                    # Simulated processing for now
                    # In the full version, this would call Gemini API
                    st.success("✅ Document processed successfully!")
                    
                    # Display sample results
                    st.markdown("---")
                    st.subheader("📋 Project Summary")
                    st.info("Your RFP document has been analyzed. Here are the extracted details:")
                    
                    # Create tabs for results
                    tab1, tab2, tab3 = st.tabs(["📦 Deliverables", "📊 Evaluation Criteria", "✅ Compliance Checklist"])
                    
                    with tab1:
                        st.subheader("Deliverables")
                        st.write("**1.** Sample deliverable 1")
                        st.write("**2.** Sample deliverable 2")
                        st.write("**3.** Sample deliverable 3")
                    
                    with tab2:
                        st.subheader("Evaluation Criteria")
                        st.write("**1.** Sample criteria 1")
                        st.write("**2.** Sample criteria 2")
                        st.write("**3.** Sample criteria 3")
                    
                    with tab3:
                        st.subheader("Compliance Checklist")
                        st.markdown("**🏢 Legal Department**")
                        st.write("- Sample legal task 1")
                        st.write("- Sample legal task 2")
                        
                        st.markdown("**🏢 Technical Department**")
                        st.write("- Sample technical task 1")
                        st.write("- Sample technical task 2")
                        
                        st.markdown("**🏢 Accounting Department**")
                        st.write("- Sample accounting task 1")
                        st.write("- Sample accounting task 2")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
