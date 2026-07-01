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
    Upload your RFP document and the AI will automatically evaluate it against our company checklist.
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
        3. View Go/No-Go decision with detailed checklist
        """)
    
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
                
                st.success("✅ Document processed successfully!")
                
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
            decision = go_no_go.get('overall_decision', 'UNDECIDED')
            score = go_no_go.get('overall_score', 0)
            
            if decision == "GO":
                bg_color = "#d4edda"
                border_color = "#28a745"
                emoji = "✅"
                title = "GO"
            elif decision == "NO-GO":
                bg_color = "#f8d7da"
                border_color = "#dc3545"
                emoji = "❌"
                title = "NO-GO"
            elif decision in ["CONDITIONAL", "CONSIDER"]:
                bg_color = "#fff3cd"
                border_color = "#ffc107"
                emoji = "⚠️"
                title = "CONDITIONAL"
            else:
                bg_color = "#e2e3e5"
                border_color = "#6c757d"
                emoji = "❓"
                title = "UNDECIDED"
            
            st.markdown(f"""
            <div style="
                background-color: {bg_color};
                border: 5px solid {border_color};
                border-radius: 15px;
                padding: 30px;
                text-align: center;
                margin: 20px 0;
            ">
                <div style="font-size: 72px;">{emoji}</div>
                <div style="font-size: 48px; font-weight: bold; color: {border_color};">
                    {title}
                </div>
                <div style="font-size: 24px; margin-top: 10px; color: #333;">
                    Score: {score}/100
                </div>
                <div style="font-size: 18px; margin-top: 10px; color: #555;">
                    {go_no_go.get('summary', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 📊 Overall Score")
            st.progress(score / 100 if score > 0 else 0)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ GO Items", go_no_go.get('go_count', 0))
            with col2:
                st.metric("❌ NO-GO Items", go_no_go.get('no_go_count', 0))
            with col3:
                st.metric("⚠️ Conditional", go_no_go.get('conditional_count', 0))
            
            st.markdown("---")
            
            # ============================================================
            # 📋 CHECKLIST TABLE
            # ============================================================
            
            st.markdown("### 📋 Checklist Evaluation")
            st.markdown("Each checklist item is compared against the RFP document.")
            
            checklist = go_no_go.get('checklist', [])
            
            if checklist:
                # Group by category
                categories = {}
                for item in checklist:
                    cat = item.get('category', 'Other')
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(item)
                
                # Display each category
                for category, items in categories.items():
                    st.markdown(f"#### 🏢 {category} Department")
                    
                    # Create table data
                    table_data = []
                    for item in items:
                        status = item.get('status', 'UNKNOWN')
                        if status == "GO":
                            status_display = "✅ GO"
                        elif status == "NO-GO":
                            status_display = "❌ NO-GO"
                        elif status in ["CONDITIONAL", "CONSIDER"]:
                            status_display = "⚠️ CONDITIONAL"
                        else:
                            status_display = f"❓ {status}"
                        
                        table_data.append({
                            "Checklist Item": item.get('item', 'Unknown'),
                            "Decision": status_display,
                            "Reason": item.get('reason', ''),
                            "Evidence from RFP": item.get('evidence', '')
                        })
                    
                    st.table(table_data)
                    st.markdown("---")
                
                # Final summary
                total_go = go_no_go.get('go_count', 0)
                total_no_go = go_no_go.get('no_go_count', 0)
                total_conditional = go_no_go.get('conditional_count', 0)
                
                if total_no_go == 0 and total_go > 0:
                    st.success(f"✅ **GO Decision!** All {total_go} items passed. We should bid on this RFP.")
                elif total_no_go > 0:
                    st.error(f"❌ **NO-GO Decision!** {total_no_go} items failed. We should NOT bid on this RFP.")
                else:
                    st.warning(f"⚠️ **CONDITIONAL Decision!** {total_conditional} items need review. Proceed with caution.")
            
            else:
                st.warning("⚠️ No checklist items were analyzed. Please try again.")
        
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
