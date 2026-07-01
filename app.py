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
    ### 🤖 AI-Powered RFP Analysis with Company Checklist
    Upload your RFP document and the AI will automatically evaluate it against our company checklist:
    - **📦 Deliverables** - What needs to be provided
    - **📊 Evaluation Criteria** - How your proposal will be judged
    - **✅ Compliance Checklist** - Department-specific tasks
    - **🎯 Go/No-Go Decision** - Strictly based on company checklist
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
        3. View Go/No-Go decision with detailed breakdown
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
        # 🎯 GO/NO-GO DECISION DASHBOARD
        # ============================================================
        
        st.markdown("---")
        st.subheader("🎯 Go/No-Go Decision Dashboard")
        
        go_no_go = results.get('go_no_go', {})
        
        if go_no_go:
            decision = go_no_go.get('overall_decision', 'NO DECISION')
            score = go_no_go.get('overall_score', 0)
            
            # Determine colors and icons
            if decision == "GO":
                bg_color = "#d4edda"
                border_color = "#28a745"
                emoji = "✅"
                title = "GO"
                subtitle = "We Should Bid!"
            elif decision == "NO-GO":
                bg_color = "#f8d7da"
                border_color = "#dc3545"
                emoji = "❌"
                title = "NO-GO"
                subtitle = "We Should Not Bid"
            elif decision == "CONDITIONAL":
                bg_color = "#fff3cd"
                border_color = "#ffc107"
                emoji = "⚠️"
                title = "CONDITIONAL"
                subtitle = "Proceed with Conditions"
            else:
                bg_color = "#e2e3e5"
                border_color = "#6c757d"
                emoji = "❓"
                title = "UNDECIDED"
                subtitle = "Needs Further Review"
            
            # Big Decision Box
            st.markdown(f"""
            <div style="
                background-color: {bg_color};
                border: 4px solid {border_color};
                border-radius: 15px;
                padding: 30px;
                text-align: center;
                margin: 20px 0;
            ">
                <h1 style="font-size: 60px; margin: 0;">{emoji}</h1>
                <h1 style="font-size: 48px; margin: 10px 0; color: {border_color};">
                    {title}
                </h1>
                <h2 style="font-size: 24px; margin: 0; color: #333;">
                    {subtitle}
                </h2>
                <div style="
                    font-size: 28px;
                    font-weight: bold;
                    margin: 15px 0;
                    color: {border_color};
                ">
                    Score: {score}/100
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Progress Bar for Score
            st.markdown("### 📊 Overall Score")
            st.progress(score / 100)
            
            # Summary
            st.markdown("### 📝 Recommendation Summary")
            st.info(go_no_go.get('recommendation', 'No summary available'))
            
            # ============================================================
            # DETAILED CHECKLIST RESULTS
            # ============================================================
            
            st.markdown("---")
            st.markdown("### 📋 Detailed Checklist Evaluation")
            
            checklist_results = go_no_go.get('checklist_results', {})
            
            # Summary Stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ GO Items", len(go_no_go.get('go_items', [])))
            with col2:
                st.metric("❌ NO-GO Items", len(go_no_go.get('no_go_items', [])))
            with col3:
                st.metric("⚠️ Conditional", len(go_no_go.get('conditional_items', [])))
            
            st.markdown("---")
            
            # Display each department's checklist
            if checklist_results:
                for dept, criteria in checklist_results.items():
                    st.markdown(f"### 🏢 {dept} Department")
                    
                    for criterion, details in criteria.items():
                        status = details.get('status', 'UNKNOWN')
                        reason = details.get('reason', '')
                        evidence = details.get('evidence', '')
                        
                        if status == "GO":
                            icon = "✅"
                            color = "#28a745"
                        elif status == "NO-GO":
                            icon = "❌"
                            color = "#dc3545"
                        elif status == "CONDITIONAL":
                            icon = "⚠️"
                            color = "#ffc107"
                        else:
                            icon = "❓"
                            color = "#6c757d"
                        
                        st.markdown(f"""
                        <div style="
                            background-color: #f8f9fa;
                            border-left: 4px solid {color};
                            padding: 12px 15px;
                            margin: 8px 0;
                            border-radius: 5px;
                        ">
                            <strong style="font-size: 16px;">
                                {icon} {criterion}
                            </strong>
                            <span style="
                                background-color: {color};
                                color: white;
                                padding: 2px 10px;
                                border-radius: 12px;
                                font-size: 12px;
                                font-weight: bold;
                                margin-left: 10px;
                            ">
                                {status}
                            </span>
                            <br>
                            <span style="color: #555; font-size: 14px;">
                                <strong>Reason:</strong> {reason}
                            </span>
                            <br>
                            <span style="color: #888; font-size: 13px;">
                                <strong>Evidence:</strong> "{evidence}"
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
        
        # ============================================================
        # EXISTING RESULTS
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
