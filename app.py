import streamlit as st
import os
import json
import tempfile
from dotenv import load_dotenv
from utils.document_processor import RFPProcessor
from datetime import datetime

load_dotenv()

st.set_page_config(
    page_title="RFP Document Processor",
    page_icon="📄",
    layout="wide"
)

def main():
    st.title("📄 RFP Document Processor")
    st.markdown("---")
    
    st.markdown("""
    ### 🤖 AI-Powered RFP Analysis with Go/No-Go Decision
    Upload your RFP document and the AI will automatically extract:
    - **📦 Deliverables** - What needs to be provided
    - **📊 Evaluation Criteria** - How your proposal will be judged
    - **✅ Compliance Checklist** - Department-specific tasks
    - **🎯 Go/No-Go Decision** - Should you bid?
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
        4. Get Go/No-Go recommendation
        """)
        
        st.info("🤖 Using Google Gemini AI")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose your RFP document",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size/1024:.1f} KB")
        with col3:
            st.metric("File Type", uploaded_file.type)
        
        if st.button("🚀 Process Document", type="primary"):
            if not api_key:
                st.error("❌ Please provide your Gemini API key in the sidebar")
                return
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    file_path = tmp_file.name
                
                processor = RFPProcessor(api_key)
                
                with st.spinner("Processing document with Gemini..."):
                    text = processor.extract_text(file_path)
                    results = processor.analyze_rfp(text)
                    
                    # NEW: Add Go/No-Go analysis
                    go_no_go = processor.go_no_go_analysis(text)
                    results['go_no_go'] = go_no_go
                    
                    st.session_state['results'] = results
                    st.session_state['processed'] = True
                    
                    os.unlink(file_path)
                
                st.success("✅ Document processed successfully with Gemini!")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Display results if processed
    if 'processed' in st.session_state and st.session_state['processed']:
        results = st.session_state['results']
        
        if 'error' in results:
            st.error(f"⚠️ Analysis error: {results['error']}")
            if st.button("Try Again"):
                st.session_state['processed'] = False
                st.session_state['results'] = None
                st.rerun()
            return
        
        # ============================================================
        # 🎯 NEW: Go/No-Go Decision Section
        # ============================================================
        st.markdown("---")
        st.subheader("🎯 Go/No-Go Decision")
        
        go_no_go = results.get('go_no_go', {})
        
        if go_no_go:
            # Display the decision with color
            decision = go_no_go.get('decision', 'No Decision')
            score = go_no_go.get('score', 0)
            
            if decision == "GO":
                st.success(f"✅ RECOMMENDATION: **GO** (Score: {score}/100)")
                st.info("This opportunity looks promising! Consider bidding.")
            elif decision == "NO-GO":
                st.error(f"❌ RECOMMENDATION: **NO-GO** (Score: {score}/100)")
                st.warning("This opportunity has risks. Consider passing.")
            else:
                st.warning(f"⚠️ RECOMMENDATION: **{decision}** (Score: {score}/100)")
            
            # Show the breakdown
            st.markdown("### 📊 Decision Breakdown")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**✅ Strengths**")
                strengths = go_no_go.get('strengths', [])
                if strengths:
                    for s in strengths:
                        st.write(f"- {s}")
                else:
                    st.write("- No strengths identified")
            
            with col2:
                st.markdown("**⚠️ Risks/Weaknesses**")
                risks = go_no_go.get('risks', [])
                if risks:
                    for r in risks:
                        st.write(f"- {r}")
                else:
                    st.write("- No risks identified")
            
            # Show criteria breakdown
            st.markdown("### 📋 Evaluation Criteria")
            criteria = go_no_go.get('criteria', {})
            if criteria:
                for criterion, details in criteria.items():
                    status = "✅" if details.get('passed', False) else "❌"
                    st.write(f"{status} **{criterion}**: {details.get('score', 0)}/10 - {details.get('explanation', '')}")
        
        # ============================================================
        # Existing Results
        # ============================================================
        st.markdown("---")
        st.subheader("📋 Project Summary")
        st.info(results.get('project_summary', 'No summary available'))
        
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
                st.rerun()

if __name__ == "__main__":
    main()
