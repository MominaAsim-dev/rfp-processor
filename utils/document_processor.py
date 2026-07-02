import google.generativeai as genai
import PyPDF2
import docx
import os
import json
import re
from typing import Dict, Any

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
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"Error reading PDF: {str(e)}")
    
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
        
        Analyze the following RFP text and extract specific information in JSON format.
        
        RFP TEXT:
        {text[:10000]}
        
        Extract the following information and format as JSON:
        
        1. "project_summary": A brief 2-3 sentence summary of the project
        2. "deliverables": List of specific items, products, or services that need to be provided
        3. "evaluation_criteria": List of criteria the client will use to judge proposals
        4. "compliance_checklist": An object with departments as keys and lists of tasks as values
           Departments: Legal, Accounting, Technical, Operations, HR
        
        Return ONLY valid JSON in this exact format:
        {{
            "project_summary": "summary text",
            "deliverables": ["deliverable 1", "deliverable 2"],
            "evaluation_criteria": ["criterion 1", "criterion 2"],
            "compliance_checklist": {{
                "Legal": ["task 1", "task 2"],
                "Accounting": ["task 1", "task 2"],
                "Technical": ["task 1", "task 2"],
                "Operations": ["task 1", "task 2"],
                "HR": ["task 1", "task 2"]
            }}
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
            return result
            
        except Exception as e:
            return {
                "project_summary": "Error processing document",
                "deliverables": ["Unable to extract deliverables"],
                "evaluation_criteria": ["Unable to extract evaluation criteria"],
                "compliance_checklist": {
                    "Legal": ["Unable to extract compliance tasks"],
                    "Accounting": ["Unable to extract compliance tasks"],
                    "Technical": ["Unable to extract compliance tasks"],
                    "Operations": ["Unable to extract compliance tasks"],
                    "HR": ["Unable to extract compliance tasks"]
                },
                "error": str(e)
            }
    
    def go_no_go_analysis(self, text: str) -> Dict[str, Any]:
        """Perform Go/No-Go analysis based on company checklist - WITH NUMERIC EXTRACTION"""
        
        prompt = f"""
        You are a Bid/No-Bid decision expert. Analyze this RFP against our company checklist.
        
        **CRITICAL: You MUST read and extract ALL numeric values (payment terms, dollar amounts, dates, deadlines) from the RFP text.**
        
        RFP TEXT:
        {text[:10000]}
        
        ========================================
        COMPANY CHECKLIST - Evaluate Each Item
        ========================================
        
        FINANCIAL CHECKLIST (Score each 0-10):
        1. "Payment Terms" - SEARCH for: "NET30", "NET 30", "30 days", "payment terms"
           - NET30 or better = 10
           - NET45 = 7
           - NET60 = 4
           - Not mentioned = 3 (ESCALATE - need to ask client)
        
        2. "Insurance Requirements" - SEARCH for: "$", "million", "M", "coverage", "liability"
           - $5M or less = 10
           - $10M = 5
           - More than $10M = 0
           - Not mentioned = 3 (ESCALATE - need to ask client)
        
        3. "Financial Stability" - SEARCH for: "audited", "financial statements", "balance sheet"
           - Required and we have = 10
           - Required but we don't have = 0
           - Not mentioned = 7
        
        4. "Profitability" - SEARCH for: "budget", "estimated value", "contract value", "$"
           - Clear budget/profit opportunity = 10
           - Vague budget = 5
           - No budget mentioned = 3 (ESCALATE - need budget info)
        
        5. "Bid Bond" - SEARCH for: "bid bond", "bond", "surety"
           - Not required = 10
           - Required and we can provide = 7
           - Required and we can't = 0
        
        LEGAL CHECKLIST (Score each 0-10):
        6. "Eligibility Criteria" - SEARCH for: "experience", "years", "qualifications"
           - We meet all = 10
           - Meet most = 7
           - Don't meet = 0
        
        7. "State Registration" - SEARCH for: "registered in", "license", "authorized to do business"
           - Not required = 10
           - Required and we have = 7
           - Required and we don't = 0
        
        8. "E-Verify" - SEARCH for: "E-Verify", "e-verify", "employment verification"
           - Not required = 10
           - Required and we have = 7
           - Required and we don't = 0
        
        9. "Contract Terms" - SEARCH for: "contract", "terms", "conditions", "liability", "indemnification"
           - Acceptable = 10
           - Need minor review = 7
           - Major issues = 3 (ESCALATE - legal review needed)
           - Not attached = 3 (ESCALATE - need to request contract)
        
        10. "Legal Compliance" - SEARCH for: "comply", "regulations", "laws", "data protection"
            - We comply = 10
            - Mostly comply = 7
            - Don't comply = 0
        
        OPERATIONS CHECKLIST (Score each 0-10):
        11. "Required Forms" - SEARCH for: "form", "certification", "attachment", "schedule"
            - All standard = 10
            - Some effort = 7
            - Extensive = 4
        
        12. "Submission Deadlines" - SEARCH for: "due date", "deadline", "submit by", "August", "September"
            - Feasible (30+ days) = 10
            - Tight (15-29 days) = 7
            - Very tight (<15 days) = 4
            - Not mentioned = 3 (ESCALATE - need deadline)
        
        13. "Signatory Authority" - SEARCH for: "sign", "authorized", "authority"
            - Available = 10
            - Need approval = 7
            - Not available = 0
        
        14. "Vendor Registration" - SEARCH for: "register", "vendor portal", "supplier registration"
            - Not required = 10
            - Required and we have = 7
            - Required and we don't = 3 (ESCALATE - need to register)
        
        TECHNICAL CHECKLIST (Score each 0-10):
        15. "Scope Alignment" - SEARCH for: "services", "products", "requirements", "scope"
            - Perfect match = 10
            - Good fit = 7
            - Partial = 4
        
        16. "Technical Requirements" - SEARCH for: "technical", "specifications", "standards", "NIST", "ISO"
            - We meet all = 10
            - Meet most = 7
            - Don't meet = 0
        
        17. "Industry Standards" - SEARCH for: "ISO", "NIST", "standards", "compliance"
            - We comply = 10
            - Mostly = 7
            - Don't = 0
        
        18. "Security Requirements" - SEARCH for: "security", "encryption", "access control", "cybersecurity"
            - We meet = 10
            - Mostly = 7
            - Don't = 0
        
        19. "Integration Needs" - SEARCH for: "integrate", "integration", "API", "connect"
            - We can do = 10
            - With effort = 7
            - Can't = 0
        
        ========================================
        
        STATUS DEFINITIONS:
        - "GO" = Score 7-10 (We fully meet this)
        - "ESCALATE" = Score 3-6 (Missing info or needs management review)
        - "NO-GO" = Score 0-2 (Cannot meet this)
        
        ESCALATE means: "We need more information or management approval before deciding."
        
        ========================================
        
        Return JSON ONLY in this format:
        {{
            "overall_score": 75,
            "checklist": [
                {{"category": "Financial", "item": "Payment Terms", "score": 10, "status": "GO", "reason": "NET30 terms found in Section 6", "evidence": "Section 6: 'NET30 payment terms'"}},
                {{"category": "Financial", "item": "Insurance", "score": 5, "status": "ESCALATE", "reason": "$10M required, we have $5M - need to discuss", "evidence": "Section 7: '$10M liability coverage required'"}},
                {{"category": "Operations", "item": "Submission Deadlines", "score": 10, "status": "GO", "reason": "45 days to submit", "evidence": "Header: 'PROPOSAL DUE DATE: August 15, 2026'"}}
            ],
            "go_count": 12,
            "no_go_count": 0,
            "escalate_count": 4,
            "summary": "We should bid, but escalate insurance and contract terms to management."
        }}
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
            if 'overall_score' not in result:
                result['overall_score'] = 50
            
            # Calculate actual score from checklist
            total_score = 0
            max_score = len(result.get('checklist', [])) * 10
            for item in result.get('checklist', []):
                total_score += item.get('score', 0)
            
            if max_score > 0:
                calculated_score = (total_score / max_score) * 100
                result['overall_score'] = max(calculated_score, result.get('overall_score', 0))
            
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
            result['conditional_count'] = escalate_count  # For backward compatibility
            
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
