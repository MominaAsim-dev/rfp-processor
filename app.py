import streamlit as st
import os
import json
import tempfile
from dotenv import load_dotenv
from utils.document_processor import RFPProcessor
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
    ### 🤖 AI-Powered RFP Analysis with Gemini
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
        
        st.info("🤖 Using Gemini (auto-detected model)")
    
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
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    file_path = tmp_file.name
                
                # Initialize processor (auto-selects model)
                processor = RFPProcessor(api_key)
                
                with st.spinner("Processing document with Gemini..."):
                    # Extract text
                    text = processor.extract_text(file_path)
                    
                    # Analyze with Gemini
                    results = processor.analyze_rfp(text)
                    
                    # Store in session state
                    st.session_state['results'] = results
                    st.session_state['processed'] = True
                    
                    # Clean up
                    os.unlink(file_path)
                
                st.success("✅ Document processed successfully with Gemini!")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Display results if processed
    if 'processed' in st.session_state and st.session_state['processed']:
        results = st.session_state['results']
        
        # Check for errors
        if 'error' in results:
            st.error(f"⚠️ Analysis error: {results['error']}")
            if st.button("Try Again"):
                st.session_state['processed'] = False
                st.session_state['results'] = None
                # FIXED: Use st.rerun() instead of experimental_rerun
                st.rerun()
            return
        
        # Display Project Summary
        st.markdown("---")
        st.subheader("📋 Project Summary")
        st.info(results.get('project_summary', 'No summary available'))
        
        # Create tabs
        tab1, tab2, tab3 = st.tabs(["📦 Deliverables", "📊 Evaluation Criteria", "✅ Compliance Checklist"])
        
        with tab1:
            st.subheader("Deliverables")
            deliverables = results.get('deliverables', [])
            if isinstance(deliverables, list):
                for i, item in enumerate(deliverables, 1):
                    st.write(f"**{i}.** {item}")
            else:
                st.write(deliverables)
        
        with tab2:
            st.subheader("Evaluation Criteria")
            criteria = results.get('evaluation_criteria', [])
            if isinstance(criteria, list):
                for i, item in enumerate(criteria, 1):
                    st.write(f"**{i}.** {item}")
            else:
                st.write(criteria)
        
        with tab3:
            st.subheader("Compliance Checklist")
            checklist = results.get('compliance_checklist', {})
            if isinstance(checklist, dict):
                for dept, tasks in checklist.items():
                    st.markdown(f"**🏢 {dept} Department**")
                    if isinstance(tasks, list):
                        for task in tasks:
                            st.write(f"- {task}")
                    else:
                        st.write(tasks)
                    st.markdown("---")
            else:
                st.write(checklist)
        
        # Export button
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            json_str = json.dumps(results, indent=2)
            st.download_button(
                label="📥 Download Results (JSON)",
                data=json_str,
                file_name=f"rfp_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        with col2:
            if st.button("🔄 Process New Document"):
                st.session_state['processed'] = False
                st.session_state['results'] = None
                # FIXED: Use st.rerun()
                st.rerun()

if __name__ == "__main__":
    main()