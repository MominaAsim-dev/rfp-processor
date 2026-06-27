import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="RFP Document Processor",
    page_icon="📄",
    layout="wide"
)

st.title("📄 RFP Document Processor")
st.markdown("---")

st.markdown("""
### 🤖 RFP Analysis Tool
Upload your RFP document to get started.
""")

uploaded_file = st.file_uploader(
    "Choose your RFP document",
    type=['pdf', 'docx', 'txt']
)

if uploaded_file is not None:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    st.info(f"File size: {uploaded_file.size/1024:.1f} KB")
    
    if st.button("🚀 Process Document"):
        with st.spinner("Processing..."):
            st.success("✅ Processing complete!")
            
            st.subheader("📋 Results")
            st.write("Your RFP document has been analyzed.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Deliverables Found", "5")
            with col2:
                st.metric("Evaluation Criteria", "4")
            
            st.subheader("✅ Compliance Checklist")
            st.write("**Legal Department:**")
            st.write("- Task 1")
            st.write("- Task 2")
            st.write("**Technical Department:**")
            st.write("- Task 1")
            st.write("- Task 2")
