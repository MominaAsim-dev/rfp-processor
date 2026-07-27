import google.generativeai as genai
import PyPDF2
import docx
import os
import json
import re
from typing import Dict, Any, List

class RFPProcessor:
    """Handles document extraction and AI analysis for RFP documents"""
    
    def __init__(self, api_key: str):
        """Initialize with Gemini API key"""
        genai.configure(api_key=api_key)
        
        # Auto-select first available model
        self.model = None
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                self.model = genai.GenerativeModel(model.name)
                print(f"✅ Using model: {model.name}")
                break
        
        if self.model is None:
            raise Exception("No available Gemini model found.")
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if len(text.strip()) < 200:
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                except ImportError:
                    pass
            
            if not text or len(text.strip()) < 50:
                raise Exception("No text could be extracted from PDF.")
            
            text = self._clean_extracted_text(text)
            return text
            
        except Exception as e:
            raise Exception(f"Error reading PDF: {str(e)}")
    
    def _clean_extracted_text(self, text: str) -> str:
        if not text:
            return text
        
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        text = re.sub(r'Page \d+', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[^\w\s\.\,\-\$\d\%]', ' ', text)
        text = re.sub(r'\$ (\d+)', r'$\1', text)
        text = re.sub(r'(\d+) \%', r'\1%', text)
        text = re.sub(r'(\d+) M', r'\1M', text)
        text = re.sub(r'(\d+) K', r'\1K', text)
        
        return text
    
    def extract_text_from_docx(self, file_path: str) -> str:
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            raise Exception(f"Error reading DOCX: {str(e)}")
    
    def extract_text_from_txt(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error reading TXT: {str(e)}")
    
    def extract_text(self, file_path: str) -> str:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_extension == '.docx':
            return self.extract_text_from_docx(file_path)
        elif file_extension == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def analyze_rfp(self, text: str) -> Dict[str, Any]:
        prompt = f"""
        You are an expert in analyzing Request for Proposal (RFP) documents.
        
        The text below contains content from MULTIPLE FILES. Each file is clearly marked with:
        "========================================"
        "FILE: [filename]"
        "========================================"
        
        **CRITICAL INSTRUCTION: For EVERY deliverable you identify, you MUST include:**
        1. The EXACT filename where it appears
        2. The EXACT text/line from the RFP that mentions this deliverable (for highlighting)
        3. The page number where it appears (if available in the text)
        
        Total RFP text length: {len(text)} characters.
        
        RFP TEXT:
        {text}
        
        Extract the following information:
        
        1. "project_summary": A brief 2-3 sentence summary of the project
        
        2. "deliverables": Group deliverables into BUSINESS CATEGORIES (max 5-6 categories, max 5-6 items per category).
           For EACH deliverable, include:
           - "name": The deliverable name
           - "section_ref": The section number (e.g., "Section XI.B.1", "Article IV")
           - "reason": Why this deliverable is required
           - "source_file": The EXACT filename where this deliverable was found
           - "exact_text": The EXACT quote/sentence from the RFP that mentions this deliverable (copy it word-for-word)
           - "page_num": The page number where this appears (if mentioned, e.g., "Page 11")
        
        3. "evaluation_criteria": List of criteria (flat list)
        
        4. "compliance_checklist": Object with departments as keys and lists of tasks
        
        Return ONLY valid JSON.
        
        Example format:
        {{
            "project_summary": "Old Dominion University is seeking an AI-driven search solution...",
            "deliverables": [
                {{
                    "category": "Documentation & Forms",
                    "items": [
                        {{
                            "name": "RFP Cover Sheet",
                            "section_ref": "Section XI.B.1",
                            "reason": "Requires the return of the RFP cover sheet",
                            "source_file": "doc1.txt",
                            "exact_text": "The return of the RFP cover sheet and all addenda acknowledgments, if any, signed and filled out as required.",
                            "page_num": "11"
                        }}
                    ]
                }}
            ],
            "evaluation_criteria": ["Experience", "Capability"],
            "compliance_checklist": {{"Legal": ["NDA"], "Accounting": ["Insurance"]}}
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            json_str = response.text.strip()
            
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            
            # Ensure all deliverables have required fields
            if 'deliverables' in result:
                for cat in result['deliverables']:
                    if 'items' in cat:
                        for item in cat['items']:
                            if isinstance(item, dict):
                                if 'source_file' not in item:
                                    item['source_file'] = 'Unknown'
                                if 'exact_text' not in item:
                                    item['exact_text'] = item.get('reason', 'Required by RFP')
                                if 'page_num' not in item:
                                    item['page_num'] = 'N/A'
            
            return result
            
        except Exception as e:
            return {
                "project_summary": "Error processing document",
                "deliverables": [],
                "evaluation_criteria": ["Unable to extract"],
                "compliance_checklist": {},
                "error": str(e)
            }
    
    def go_no_go_analysis(self, text: str) -> Dict[str, Any]:
        """Perform Go/No-Go analysis based on company checklist - WITH NUMERIC EXTRACTION"""
        
        prompt = f"""
        You are a Bid/No-Bid decision expert. Analyze this RFP against our company checklist.
        
        **CRITICAL: You MUST read and extract ALL numeric values (payment terms, dollar amounts, dates, deadlines) from the RFP text.**
        
        Total RFP text length: {len(text)} characters.
        
        RFP TEXT (FULL DOCUMENT):
        {text}
        
        ========================================
        COMPANY CHECKLIST - Evaluate Each Item
        ========================================
        
        FINANCIAL CHECKLIST (Score each 0-10):
        1. "Payment Terms" - NET30 or better = 10, NET45 = 7, NET60 = 4, Not mentioned = 3
        2. "Insurance Requirements" - $5M or less = 10, $10M = 5, More = 0, Not mentioned = 3
        3. "Financial Stability" - We meet = 10, Partial = 7, Don't meet = 0
        4. "Profitability" - Budget known = 10, Vague = 5, Not mentioned = 3
        5. "Bid Bond" - Not required = 10, Can provide = 7, Can't = 0
        
        LEGAL CHECKLIST (Score each 0-10):
        6. "Eligibility Criteria" - Meet all = 10, Meet most = 7, Don't meet = 0
        7. "State Registration" - Not required = 10, Have it = 7, Don't have = 0
        8. "E-Verify" - Not required = 10, Have it = 7, Don't have = 0
        9. "Contract Terms" - Acceptable = 10, Review needed = 7, Major issues = 3
        10. "Legal Compliance" - Comply = 10, Mostly = 7, Don't = 0
        
        OPERATIONS CHECKLIST (Score each 0-10):
        11. "Required Forms" - All standard = 10, Some effort = 7, Extensive = 4
        12. "Submission Deadlines" - Feasible (30+ days) = 10, Tight (15-29 days) = 7, Very tight (<15 days) = 4
        13. "Signatory Authority" - Available = 10, Need approval = 7, Not available = 0
        14. "Vendor Registration" - Not required = 10, Have it = 7, Need to register = 3
        
        TECHNICAL CHECKLIST (Score each 0-10):
        15. "Scope Alignment" - Perfect = 10, Good fit = 7, Partial = 4
        16. "Technical Requirements" - Meet all = 10, Meet most = 7, Don't meet = 0
        17. "Industry Standards" - Comply = 10, Mostly = 7, Don't = 0
        18. "Security Requirements" - Meet = 10, Mostly = 7, Don't = 0
        19. "Integration Needs" - Can do = 10, With effort = 7, Can't = 0
        
        ========================================
        
        STATUS DEFINITIONS:
        - "GO" = Score 7-10 (We fully meet this)
        - "ESCALATE" = Score 3-6 (Missing info or needs management review)
        - "NO-GO" = Score 0-2 (Cannot meet this)
        
        Return JSON ONLY in this format:
        {{
            "checklist": [
                {{"category": "Financial", "item": "Payment Terms", "score": 10, "status": "GO", "reason": "NET30 terms found", "evidence": "Section 1: NET30"}},
                {{"category": "Financial", "item": "Insurance", "score": 5, "status": "ESCALATE", "reason": "$10M required, we have $5M", "evidence": "Section 2: $10M"}}
            ],
            "go_count": 10,
            "no_go_count": 0,
            "escalate_count": 2,
            "summary": "We should bid with escalation items"
        }}
        
        IMPORTANT: DO NOT include "overall_score" in your JSON. The score will be calculated automatically from the checklist scores.
        """
        
        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Extract JSON
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_text
            
            # Clean up
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            result = json.loads(json_str)
            
            # Ensure all required fields exist
            if 'checklist' not in result:
                result['checklist'] = []
            
            # ============================================================
            # ✅ CALCULATE SCORE ONLY FROM CHECKLIST ITEMS
            # ============================================================
            total_score = 0
            max_score = len(result.get('checklist', [])) * 10
            
            for item in result.get('checklist', []):
                total_score += item.get('score', 0)
            
            if max_score > 0:
                calculated_score = (total_score / max_score) * 100
                result['overall_score'] = round(min(100, calculated_score))
            else:
                result['overall_score'] = 50
            
            # Enforce strict score-based decision
            score = result.get('overall_score', 0)
            if score >= 71:
                result['overall_decision'] = 'GO'
            elif 51 <= score <= 70:
                result['overall_decision'] = 'ESCALATE'
            else:
                result['overall_decision'] = 'NO-GO'
            
            # Count statuses
            go_count = sum(1 for item in result.get('checklist', []) if item.get('status') == 'GO')
            no_go_count = sum(1 for item in result.get('checklist', []) if item.get('status') == 'NO-GO')
            escalate_count = sum(1 for item in result.get('checklist', []) if item.get('status') == 'ESCALATE')
            
            result['go_count'] = go_count
            result['no_go_count'] = no_go_count
            result['escalate_count'] = escalate_count
            result['conditional_count'] = escalate_count
            
            return result
            
        except Exception as e:
            return {
                "overall_decision": "NEEDS REVIEW",
                "overall_score": 50,
                "checklist": [
                    {"category": "Financial", "item": "Payment Terms", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                    {"category": "Legal", "item": "Eligibility", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                    {"category": "Operations", "item": "Deadlines", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                    {"category": "Technical", "item": "Scope", "score": 5, "status": "ESCALATE", "reason": "Could not analyze", "evidence": "Check RFP manually"}
                ],
                "go_count": 0,
                "no_go_count": 0,
                "escalate_count": 4,
                "conditional_count": 4,
                "summary": f"AI analysis encountered an error: {str(e)}. Please review the RFP manually."
            }
