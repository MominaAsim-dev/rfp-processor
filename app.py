import streamlit as st
import streamlit.components.v1 as components
import os
import json
import tempfile
import base64
import re
import uuid
import urllib.parse
from dotenv import load_dotenv
from utils.document_processor import RFPProcessor
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io

load_dotenv()

st.set_page_config(
    page_title="RFP Document Processor",
    page_icon="📄",
    layout="wide"
)

# ============================================================
# STORAGE FUNCTIONS
# ============================================================
RESULTS_DIR = "analysis_results"

def ensure_results_dir():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

def generate_analysis_id():
    date_str = datetime.now().strftime("%Y%m%d")
    uid = str(uuid.uuid4())[:8]
    return f"RFP-{date_str}-{uid}"

def save_analysis_results(analysis_id, results):
    ensure_results_dir()
    filepath = os.path.join(RESULTS_DIR, f"{analysis_id}.json")
    results_to_save = results.copy()
    results_to_save['_metadata'] = {
        'analysis_id': analysis_id,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results_to_save, f, indent=2, ensure_ascii=False)

def load_analysis_results(analysis_id):
    filepath = os.path.join(RESULTS_DIR, f"{analysis_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_all_analysis_ids():
    ensure_results_dir()
    files = os.listdir(RESULTS_DIR)
    return [f.replace('.json', '') for f in files if f.endswith('.json')]

# ============================================================
# ✅ EMBEDDED PDF.js VIEWER — real cross-browser search + highlight
# ============================================================
def build_pdf_viewer_html(pdf_base64, search_text="", page_hint=None):
    """
    Renders the PDF entirely client-side using PDF.js, walks every page's
    real text layer, finds the closest match to `search_text`, highlights it,
    and auto-scrolls to that page. Works in Chrome/Edge/Firefox/Safari alike
    (unlike the old data-URI '#search=' hash, which only Firefox's native
    viewer understands) and has no page-count limit since it just iterates
    pdf.numPages.
    """
    search_js = json.dumps(search_text or "")

    page_hint_val = "null"
    if page_hint not in (None, "N/A", ""):
        m = re.search(r'\d+', str(page_hint))
        if m:
            page_hint_val = m.group()

    html = f"""
    <div id="pdfToolbar" style="background:#2d2d5e;color:#eee;padding:8px 14px;
         border-radius:8px 8px 0 0;font-family:sans-serif;font-size:13px;">
      📄 <span id="matchStatus">Loading PDF…</span>
    </div>
    <div id="viewerContainer" style="height:750px;overflow-y:auto;background:#525659;
         border-radius:0 0 8px 8px;">
      <div id="pdfPages" style="display:flex;flex-direction:column;align-items:center;padding:15px 0;"></div>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script>
    (function() {{
      pdfjsLib.GlobalWorkerOptions.workerSrc =
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

      function b64toUint8Array(b64) {{
        const raw = atob(b64);
        const arr = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
        return arr;
      }}

      function normalize(s) {{
        return s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\\s+/g, ' ').trim();
      }}

      const pdfBytes = b64toUint8Array("{pdf_base64}");
      const searchTextRaw = {search_js};
      const pageHint = {page_hint_val};

      const normSearchFull = normalize(searchTextRaw);
      // Use first ~12 words: long quotes rarely survive PDF text-extraction
      // formatting (line wraps, hyphenation) verbatim, so match on a
      // shorter, more robust prefix instead of the full sentence.
      const normSearch = normSearchFull.split(' ').filter(Boolean).slice(0, 12).join(' ');

      const statusEl = document.getElementById('matchStatus');

      pdfjsLib.getDocument({{ data: pdfBytes }}).promise.then(async function(pdf) {{
        const container = document.getElementById('pdfPages');
        let matchedPage = null;

        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {{
          const page = await pdf.getPage(pageNum);
          const viewport = page.getViewport({{ scale: 1.4 }});

          const pageWrap = document.createElement('div');
          pageWrap.id = 'page-' + pageNum;
          pageWrap.style.position = 'relative';
          pageWrap.style.width = viewport.width + 'px';
          pageWrap.style.height = viewport.height + 'px';
          pageWrap.style.marginBottom = '15px';
          pageWrap.style.boxShadow = '0 2px 10px rgba(0,0,0,0.45)';
          container.appendChild(pageWrap);

          const canvas = document.createElement('canvas');
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          pageWrap.appendChild(canvas);
          const ctx = canvas.getContext('2d');
          await page.render({{ canvasContext: ctx, viewport: viewport }}).promise;

          const textContent = await page.getTextContent();
          const textLayerDiv = document.createElement('div');
          textLayerDiv.style.position = 'absolute';
          textLayerDiv.style.top = '0';
          textLayerDiv.style.left = '0';
          textLayerDiv.style.width = viewport.width + 'px';
          textLayerDiv.style.height = viewport.height + 'px';
          pageWrap.appendChild(textLayerDiv);

          let pageTextNorm = '';
          const spanInfos = [];

          textContent.items.forEach(function(item) {{
            const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
            const fontHeight = Math.hypot(tx[2], tx[3]);
            const span = document.createElement('span');
            span.textContent = item.str;
            span.style.position = 'absolute';
            span.style.left = tx[4] + 'px';
            span.style.top = (tx[5] - fontHeight) + 'px';
            span.style.fontSize = fontHeight + 'px';
            span.style.color = 'transparent';
            span.style.whiteSpace = 'pre';
            textLayerDiv.appendChild(span);

            const norm = item.str.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\\s+/g, ' ');
            const startOffset = pageTextNorm.length;
            pageTextNorm += norm + ' ';
            spanInfos.push({{ span: span, start: startOffset, end: startOffset + norm.length }});
          }});

          if (normSearch && matchedPage === null) {{
            const idx = pageTextNorm.indexOf(normSearch);
            if (idx !== -1) {{
              matchedPage = pageNum;
              const endIdx = idx + normSearch.length;
              spanInfos.forEach(function(info) {{
                if (info.end > idx && info.start < endIdx) {{
                  info.span.style.background = 'rgba(255,213,79,0.65)';
                  info.span.style.borderRadius = '2px';
                }}
              }});
            }}
          }}
        }}

        const scrollTargetPage = matchedPage || pageHint || 1;

        if (matchedPage) {{
          statusEl.textContent = 'Match highlighted on page ' + matchedPage + ' ✅';
          statusEl.style.color = '#8bc34a';
        }} else if (normSearch) {{
          statusEl.textContent = 'Exact wording not found — jumped to page ' + scrollTargetPage + ' (try opening the full PDF to confirm)';
          statusEl.style.color = '#ffb74d';
        }} else {{
          statusEl.textContent = 'Showing page ' + scrollTargetPage;
        }}

        const targetEl = document.getElementById('page-' + scrollTargetPage);
        if (targetEl) {{
          setTimeout(function() {{
            targetEl.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
          }}, 150);
        }}
      }}).catch(function(err) {{
        statusEl.textContent = 'Error loading PDF: ' + err.message;
        statusEl.style.color = '#e57373';
      }});
    }})();
    </script>
    """
    return html

# ============================================================
# ✅ RENDER DELIVERABLES – each item gets a "🔍 View" button
# ============================================================
def render_deliverables(deliverables, pdf_base64=None, file_name=None):
    """Render deliverables; each item has a View button that opens the
    embedded PDF.js viewer scrolled + highlighted to its exact source line."""
    if not deliverables:
        st.info("No deliverables found in this RFP.")
        return

    if isinstance(deliverables, list) and len(deliverables) > 0 and isinstance(deliverables[0], str):
        deliverables = [{"category": "General", "items": deliverables}]

    category_counter = 1
    for cat_group in deliverables:
        category = cat_group.get('category', 'Uncategorized')
        items = cat_group.get('items', [])

        if not items:
            continue

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1e1e3f, #2d2d5e);
            border-left: 6px solid #6c5ce7;
            border-radius: 10px;
            padding: 12px 20px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(108, 92, 231, 0.2);
        ">
            <div style="font-size: 22px; font-weight: 700; color: #a29bfe;">
                {category_counter}. {category}
            </div>
            <div style="font-size: 14px; color: #888; margin-top: 4px;">
                📄 {len(items)} deliverable(s) identified
            </div>
        </div>
        """, unsafe_allow_html=True)

        item_counter = 1
        for item in items:
            if isinstance(item, dict):
                item_name = item.get('name', 'Unknown')
                section_ref = item.get('section_ref', 'N/A')
                reason = item.get('reason', 'Required by RFP')
                source_file = item.get('source_file', 'Unknown')
                exact_text = item.get('exact_text', reason)
                page_num = item.get('page_num', 'N/A')
            else:
                item_name = item
                section_ref = 'N/A'
                reason = 'Required by RFP'
                source_file = 'Unknown'
                exact_text = reason
                page_num = 'N/A'

            section_ref_clean = re.sub(r'<[^>]+>', '', str(section_ref))
            section_ref_clean = section_ref_clean.replace('&lt;', '<').replace('&gt;', '>')

            if source_file and source_file != 'Unknown' and source_file != 'Unknown file':
                source_display = source_file.replace('", "', ', ').replace('"', '')
                if ',' in source_display:
                    file_display = f"[From: {source_display}]"
                else:
                    file_display = f"[From: {source_file}]"
            else:
                file_display = ""

            reason_text = f"{file_display} {reason}" if file_display else reason
            section_display = section_ref_clean if section_ref_clean and section_ref_clean != 'N/A' else ''

            card_col, btn_col = st.columns([7, 1])

            with card_col:
                st.markdown(f"""
                <div style="
                    display: flex;
                    flex-direction: column;
                    padding: 10px 0 10px 30px;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                ">
                    <div style="display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px;">
                        <span style="font-size: 16px; font-weight: 600; color: #e0e0e0; min-width: 60px;">
                            {category_counter}.{item_counter}
                        </span>
                        <span style="font-size: 16px; color: #f0f0f0; flex: 1;">
                            {item_name}
                        </span>
                        <span style="font-size: 12px; color: #6c5ce7; background: rgba(108, 92, 231, 0.15); padding: 2px 12px; border-radius: 12px; border: 1px solid rgba(108, 92, 231, 0.2); white-space: nowrap;">
                            📜 {section_display}
                        </span>
                    </div>
                    <div style="font-size: 14px; color: #aaa; margin-top: 4px; padding-left: 60px; font-style: italic;">
                        💡 {reason_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with btn_col:
                if pdf_base64:
                    btn_key = f"pdfview_{category_counter}_{item_counter}"
                    if st.button("🔍 View", key=btn_key, help="Open the PDF and highlight this exact source line"):
                        st.session_state['pdf_view_request'] = {
                            'search': exact_text,
                            'page': page_num,
                            'label': item_name
                        }
                        st.rerun()

            item_counter += 1

        category_counter += 1

# ============================================================
# PDF GENERATION FUNCTIONS
# ============================================================
def generate_deliverables_pdf(deliverables, file_name=None):
    if not deliverables:
        return None
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    story.append(Paragraph("Deliverables Required by RFP", title_style))
    story.append(Spacer(1, 10))
    
    if isinstance(deliverables, list) and len(deliverables) > 0 and isinstance(deliverables[0], str):
        deliverables = [{"category": "General", "items": deliverables}]
    
    category_style = ParagraphStyle(
        'Category',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#6c5ce7'),
        spaceAfter=8,
        spaceBefore=15
    )
    
    item_style = ParagraphStyle(
        'Item',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#2c3e50'),
        leftIndent=20,
        spaceAfter=2
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6c5ce7'),
        leftIndent=40,
        spaceAfter=2,
        fontName='Helvetica-Oblique'
    )
    
    reason_style = ParagraphStyle(
        'Reason',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        leftIndent=40,
        spaceAfter=6,
        fontName='Helvetica'
    )
    
    category_counter = 1
    for cat_group in deliverables:
        category = cat_group.get('category', 'Uncategorized')
        items = cat_group.get('items', [])
        
        if not items:
            continue
        
        story.append(Paragraph(f"{category_counter}. {category}", category_style))
        
        item_counter = 1
        for item in items:
            if isinstance(item, dict):
                item_name = item.get('name', 'Unknown')
                section_ref = item.get('section_ref', 'N/A')
                reason = item.get('reason', 'Required by RFP')
                source_file = item.get('source_file', 'Unknown')
            else:
                item_name = item
                section_ref = 'N/A'
                reason = 'Required by RFP'
                source_file = 'Unknown'
            
            item_name = item_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            section_ref = section_ref.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            reason = reason.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            source_file = source_file.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if source_file and source_file != 'Unknown' and source_file != 'Unknown file':
                source_display = source_file.replace('", "', ', ').replace('"', '')
                if ',' in source_display:
                    file_display = f"[From: {source_display}]"
                else:
                    file_display = f"[From: {source_file}]"
                full_reason = f"{file_display} {reason}"
            else:
                full_reason = reason
            
            story.append(Paragraph(f"{category_counter}.{item_counter} <b>{item_name}</b>", item_style))
            story.append(Paragraph(f"<font color='#6c5ce7'>📜 Section: {section_ref}</font>", section_style))
            story.append(Paragraph(f"💡 {full_reason}", reason_style))
            story.append(Spacer(1, 2))
            
            item_counter += 1
        
        category_counter += 1
        story.append(Spacer(1, 8))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
        spaceBefore=20
    )
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generate_full_results_pdf(results, file_name=None):
    if not results:
        return None
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    story.append(Paragraph("RFP Analysis Report", title_style))
    story.append(Spacer(1, 10))
    
    summary = results.get('project_summary', 'No summary available')
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=15
    )
    story.append(Paragraph("<b>📋 Project Summary</b>", styles['Heading2']))
    story.append(Paragraph(summary, summary_style))
    story.append(Spacer(1, 10))
    
    go_no_go = results.get('go_no_go', {})
    if go_no_go:
        decision = go_no_go.get('overall_decision', 'UNDECIDED')
        score = go_no_go.get('overall_score', 0)
        
        story.append(Paragraph("<b>🎯 Go/No-Go Decision</b>", styles['Heading2']))
        
        decision_color = '#28a745' if decision == 'GO' else '#dc3545' if decision == 'NO-GO' else '#ffc107'
        story.append(Paragraph(f"<font color='{decision_color}' size='18'><b>{decision}</b></font>", styles['Normal']))
        story.append(Paragraph(f"Score: {min(100, round(score))}/100", styles['Normal']))
        story.append(Paragraph(f"<i>{go_no_go.get('summary', '')}</i>", styles['Normal']))
        story.append(Spacer(1, 10))
        
        go_count = go_no_go.get('go_count', 0)
        no_go_count = go_no_go.get('no_go_count', 0)
        escalate_count = go_no_go.get('escalate_count', 0)
        
        data = [
            ['Status', 'Count'],
            ['✅ GO', str(go_count)],
            ['❌ NO-GO', str(no_go_count)],
            ['⚠️ ESCALATE', str(escalate_count)]
        ]
        table = Table(data, colWidths=[150, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5ce7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        story.append(table)
        story.append(Spacer(1, 15))
    
    checklist = go_no_go.get('checklist', []) if go_no_go else []
    if checklist:
        story.append(Paragraph("<b>📋 Checklist Evaluation</b>", styles['Heading2']))
        
        categories = {}
        for item in checklist:
            cat = item.get('category', 'Other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        for category, items in categories.items():
            story.append(Paragraph(f"🏢 {category} Department", styles['Heading3']))
            
            data = [['Checklist Item', 'Decision', 'Reason', 'Evidence']]
            for item in items:
                status = item.get('status', 'UNKNOWN')
                status_display = '✅ GO' if status == 'GO' else '❌ NO-GO' if status == 'NO-GO' else '⚠️ CONDITIONAL'
                data.append([
                    item.get('item', 'Unknown'),
                    status_display,
                    item.get('reason', ''),
                    item.get('evidence', '')[:50] + '...' if len(item.get('evidence', '')) > 50 else item.get('evidence', '')
                ])
            
            table = Table(data, colWidths=[120, 70, 150, 150])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5ce7')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
        
        total_go = go_no_go.get('go_count', 0)
        total_no_go = go_no_go.get('no_go_count', 0)
        total_conditional = go_no_go.get('conditional_count', 0)
        
        if total_no_go == 0 and total_go > 0:
            story.append(Paragraph(f"<font color='#28a745'><b>✅ GO Decision!</b> All {total_go} items passed.</font>", styles['Normal']))
        elif total_no_go > 0:
            story.append(Paragraph(f"<font color='#dc3545'><b>❌ NO-GO Decision!</b> {total_no_go} items failed.</font>", styles['Normal']))
        else:
            story.append(Paragraph(f"<font color='#ffc107'><b>⚠️ CONDITIONAL Decision!</b> {total_conditional} items need review.</font>", styles['Normal']))
        story.append(Spacer(1, 15))
    
    deliverables = results.get('deliverables', [])
    if deliverables:
        story.append(Paragraph("<b>📦 Deliverables Required by RFP</b>", styles['Heading2']))
        
        if isinstance(deliverables, list) and len(deliverables) > 0 and isinstance(deliverables[0], str):
            deliverables = [{"category": "General", "items": deliverables}]
        
        category_counter = 1
        for cat_group in deliverables:
            category = cat_group.get('category', 'Uncategorized')
            items = cat_group.get('items', [])
            
            if not items:
                continue
            
            story.append(Paragraph(f"{category_counter}. {category}", styles['Heading3']))
            
            item_counter = 1
            for item in items:
                if isinstance(item, dict):
                    item_name = item.get('name', 'Unknown')
                    section_ref = item.get('section_ref', 'N/A')
                    reason = item.get('reason', 'Required by RFP')
                    source_file = item.get('source_file', 'Unknown')
                else:
                    item_name = item
                    section_ref = 'N/A'
                    reason = 'Required by RFP'
                    source_file = 'Unknown'
                
                item_name = item_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                section_ref = section_ref.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                reason = reason.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                source_file = source_file.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                if source_file and source_file != 'Unknown' and source_file != 'Unknown file':
                    source_display = source_file.replace('", "', ', ').replace('"', '')
                    if ',' in source_display:
                        file_display = f"[From: {source_display}]"
                    else:
                        file_display = f"[From: {source_file}]"
                    full_reason = f"{file_display} {reason}"
                else:
                    full_reason = reason
                
                story.append(Paragraph(f"{category_counter}.{item_counter} <b>{item_name}</b>", styles['Normal']))
                story.append(Paragraph(f"📜 Section: {section_ref}", styles['Normal']))
                story.append(Paragraph(f"💡 {full_reason}", styles['Normal']))
                story.append(Spacer(1, 4))
                
                item_counter += 1
            
            category_counter += 1
            story.append(Spacer(1, 8))
    
    criteria = results.get('evaluation_criteria', [])
    if criteria:
        story.append(Paragraph("<b>📊 Evaluation Criteria</b>", styles['Heading2']))
        for i, criterion in enumerate(criteria, 1):
            story.append(Paragraph(f"{i}. {criterion}", styles['Normal']))
        story.append(Spacer(1, 10))
    
    compliance = results.get('compliance_checklist', {})
    if compliance:
        story.append(Paragraph("<b>✅ Compliance Checklist</b>", styles['Heading2']))
        for dept, tasks in compliance.items():
            story.append(Paragraph(f"🏢 {dept} Department", styles['Heading3']))
            for task in tasks:
                story.append(Paragraph(f"- {task}", styles['Normal']))
            story.append(Spacer(1, 5))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
        spaceBefore=20
    )
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================
# MAIN FUNCTION
# ============================================================
def main():
    st.title("📄 RFP Document Processor")
    st.markdown("---")

    if 'pdf_view_request' not in st.session_state:
        st.session_state['pdf_view_request'] = None

    st.markdown("""
    ### 🤖 AI-Powered RFP Analysis with Company Checklist
    Upload your RFP document(s) or paste text directly.
    """)
    
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
        1. Upload one or multiple files (PDF, DOCX, TXT)
        2. OR paste text below
        3. Click "Process Document"
        4. View Go/No-Go decision with detailed checklist
        """)
        
        st.markdown("---")
        st.subheader("🔍 Fetch Analysis by ID")
        fetch_id = st.text_input("Enter Analysis ID:", placeholder="e.g., RFP-20260727-a1b2c3d4")
        if st.button("Fetch Results", use_container_width=True):
            if fetch_id:
                fetched = load_analysis_results(fetch_id)
                if fetched:
                    st.session_state['results'] = fetched
                    st.session_state['processed'] = True
                    st.session_state['analysis_id'] = fetch_id
                    st.success("✅ Results loaded successfully!")
                    st.rerun()
                else:
                    st.error("❌ Analysis ID not found. Please check the ID.")
        
        st.markdown("---")
        st.subheader("📂 Saved Analyses")
        saved_ids = get_all_analysis_ids()
        if saved_ids:
            for aid in saved_ids[-5:]:
                st.code(aid, language="text")
            if len(saved_ids) > 5:
                st.caption(f"... and {len(saved_ids) - 5} more")
        else:
            st.caption("No saved analyses yet.")
    
    input_method = st.radio(
        "Choose input method:",
        ["Upload Files", "Paste Text"],
        horizontal=True
    )
    
    if input_method == "Upload Files":
        uploaded_files = st.file_uploader(
            "Choose one or more RFP documents",
            type=['pdf', 'docx', 'txt'],
            help="Supported formats: PDF, DOCX, TXT",
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} document(s) uploaded")
            
            file_names = []
            total_size = 0
            for f in uploaded_files:
                file_names.append(f"{f.name} ({f.size/1024:.1f} KB)")
                total_size += f.size
            
            st.write("📄 " + ", ".join(file_names))
            st.info(f"Total size: {total_size/1024:.1f} KB")
            
            # ============================================================
            # ✅ Store PDF bytes for the FIRST PDF found
            # ============================================================
            pdf_base64 = None
            pdf_name = None
            for f in uploaded_files:
                if f.name.lower().endswith('.pdf'):
                    f.seek(0)
                    pdf_bytes = f.read()
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    pdf_name = f.name
                    break
            
            # Store in session state
            st.session_state['pdf_base64'] = pdf_base64
            st.session_state['pdf_name'] = pdf_name
            st.session_state['uploaded_file_names'] = [f.name for f in uploaded_files]
            
            if st.button("🚀 Process Documents", type="primary"):
                if not api_key:
                    st.error("❌ Please provide your Gemini API key in the sidebar")
                    return
                
                try:
                    combined_text = ""
                    file_paths = []
                    file_name_list = []
                    
                    for uploaded_file in uploaded_files:
                        uploaded_file.seek(0)
                        file_name_list.append(uploaded_file.name)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                            tmp_file.write(uploaded_file.read())
                            file_paths.append(tmp_file.name)
                    
                    processor = RFPProcessor(api_key)
                    
                    with st.spinner(f"Processing {len(uploaded_files)} document(s) with Gemini..."):
                        for idx, file_path in enumerate(file_paths):
                            text = processor.extract_text(file_path)
                            file_label = file_name_list[idx]
                            combined_text += f"\n\n========================================\n"
                            combined_text += f"FILE: {file_label}\n"
                            combined_text += f"========================================\n\n"
                            combined_text += text + "\n\n"
                            os.unlink(file_path)
                        
                        results = processor.analyze_rfp(combined_text)
                        go_no_go = processor.go_no_go_analysis(combined_text)
                        results['go_no_go'] = go_no_go
                        
                        analysis_id = generate_analysis_id()
                        save_analysis_results(analysis_id, results)
                        st.session_state['analysis_id'] = analysis_id
                        st.session_state['results'] = results
                        st.session_state['processed'] = True
                        st.session_state['combined_text'] = combined_text
                        st.session_state['uploaded_file_names'] = file_name_list
                    
                    st.success(f"✅ All {len(uploaded_files)} document(s) processed successfully!")
                    st.info(f"🔑 **Analysis ID:** `{analysis_id}`  \nShare this ID to let others fetch the results without re-uploading.")
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    for path in file_paths:
                        try:
                            os.unlink(path)
                        except:
                            pass
    
    else:
        pasted_text = st.text_area(
            "Paste your RFP text here:",
            height=300,
            placeholder="Paste the RFP content here..."
        )
        
        if pasted_text:
            st.info(f"📝 {len(pasted_text)} characters pasted")
            st.session_state['text_input'] = pasted_text
            st.session_state['uploaded_files'] = None
            st.session_state['pdf_base64'] = None
            st.session_state['uploaded_file_names'] = ["Pasted Text"]
            
            if st.button("🚀 Process Document", type="primary"):
                if not api_key:
                    st.error("❌ Please provide your Gemini API key in the sidebar")
                    return
                
                try:
                    processor = RFPProcessor(api_key)
                    
                    with st.spinner("Processing text with Gemini..."):
                        results = processor.analyze_rfp(pasted_text)
                        go_no_go = processor.go_no_go_analysis(pasted_text)
                        results['go_no_go'] = go_no_go
                        
                        analysis_id = generate_analysis_id()
                        save_analysis_results(analysis_id, results)
                        st.session_state['analysis_id'] = analysis_id
                        st.session_state['results'] = results
                        st.session_state['processed'] = True
                    
                    st.success("✅ Document processed successfully!")
                    st.info(f"🔑 **Analysis ID:** `{analysis_id}`  \nShare this ID to let others fetch the results without re-uploading.")
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # ============================================================
    # DISPLAY RESULTS
    # ============================================================
    
    if 'processed' in st.session_state and st.session_state['processed']:
        results = st.session_state['results']
        analysis_id = st.session_state.get('analysis_id', 'unknown')
        
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
                    Score: {min(100, round(score))}/100
                </div>
                <div style="font-size: 18px; margin-top: 10px; color: #555;">
                    {go_no_go.get('summary', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 📊 Overall Score")
            st.progress(min(score / 100, 1.0) if score > 0 else 0.0)
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
                categories = {}
                for item in checklist:
                    cat = item.get('category', 'Other')
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(item)
                
                for category, items in categories.items():
                    st.markdown(f"#### 🏢 {category} Department")
                    
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
        
        # ============================================================
        # 📦 DELIVERABLES WITH "VIEW IN PDF" BUTTONS
        # ============================================================
        st.subheader("📦 Deliverables Required by RFP")
        deliverables = results.get('deliverables', [])
        
        pdf_base64 = st.session_state.get('pdf_base64', None)
        pdf_name = st.session_state.get('pdf_name', None)
        
        if not pdf_base64:
            st.caption("ℹ️ Upload the original PDF (not just paste text) to enable click-to-highlight source viewing.")
        
        render_deliverables(deliverables, pdf_base64, pdf_name)

        # ============================================================
        # 📄 EMBEDDED PDF VIEWER — shows when a "🔍 View" button is clicked
        # ============================================================
        if st.session_state.get('pdf_view_request') and pdf_base64:
            req = st.session_state['pdf_view_request']
            st.markdown("---")
            header_col, close_col = st.columns([8, 1])
            with header_col:
                st.markdown(f"### 📄 PDF Viewer — {req.get('label', '')}")
            with close_col:
                if st.button("✖ Close", key="close_pdf_viewer"):
                    st.session_state['pdf_view_request'] = None
                    st.rerun()
            viewer_html = build_pdf_viewer_html(pdf_base64, req.get('search', ''), req.get('page'))
            components.html(viewer_html, height=820, scrolling=True)
        
        # ============================================================
        # 📥 DOWNLOAD BUTTONS
        # ============================================================
        st.markdown("---")
        st.subheader("📥 Download Reports")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if deliverables:
                pdf_data = generate_deliverables_pdf(deliverables, pdf_name)
                if pdf_data:
                    st.download_button(
                        label="📥 Download Deliverables PDF",
                        data=pdf_data,
                        file_name=f"deliverables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col2:
            full_pdf_data = generate_full_results_pdf(results, pdf_name)
            if full_pdf_data:
                st.download_button(
                    label="📥 Download Full Report PDF",
                    data=full_pdf_data,
                    file_name=f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # ============================================================
        # DOWNLOAD FULL JSON
        # ============================================================
        st.subheader("📥 Download Raw Data")
        
        col1, col2 = st.columns(2)
        with col1:
            json_str = json.dumps(results, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Full Analysis (JSON)",
                data=json_str,
                file_name=f"analysis_{analysis_id}.txt",
                mime="application/octet-stream",
                use_container_width=True
            )
        with col2:
            if st.button("🔄 Process New Document", use_container_width=True):
                st.session_state['processed'] = False
                st.session_state['results'] = None
                st.session_state['pdf_base64'] = None
                st.session_state['pdf_name'] = None
                st.session_state['pdf_view_request'] = None
                st.rerun()
        
        st.markdown("---")
        
        # Evaluation Criteria
        st.subheader("📊 Evaluation Criteria")
        criteria = results.get('evaluation_criteria', [])
        if isinstance(criteria, list):
            for i, item in enumerate(criteria, 1):
                st.write(f"**{i}.** {item}")
        else:
            st.write(criteria)
        
        st.markdown("---")
        
        # Compliance Checklist
        st.subheader("✅ Compliance Checklist")
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
        
        st.caption(f"🔑 Analysis ID: `{analysis_id}`")

if __name__ == "__main__":
    main()
