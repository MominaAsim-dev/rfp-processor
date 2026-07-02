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
        """Perform Go/No-Go analysis based on company checklist"""
        
        prompt = f"""
        You are a Bid/No-Bid decision expert. Analyze this RFP against our company checklist.
        
        RFP TEXT:
        {text[:8000]}
        
        ========================================
        COMPANY CHECKLIST - Evaluate Each Item
        ========================================
        
        FINANCIAL CHECKLIST:
        1. "Payment Terms" - Are payment terms NET30 or better? GO if yes, NO-GO if worse
        2. "Insurance Requirements" - Is insurance required $5M or less? GO if yes, NO-GO if more
        3. "Financial Stability" - Are audited financial statements required? 
        4. "Profitability" - Can we make profit on this?
        5. "Bid Bond" - Is a bid bond required? Can we provide it?
        
        LEGAL CHECKLIST:
        6. "Eligibility Criteria" - Do we meet experience requirements?
        7. "State Registration" - Is state registration required?
        8. "E-Verify" - Is E-Verify required?
        9. "Contract Terms" - Are terms acceptable?
        10. "Legal Compliance" - Does it comply with laws?
        
        OPERATIONS CHECKLIST:
        11. "Required Forms" - Can we complete all forms?
        12. "Submission Deadlines" - Can we meet deadlines?
        13. "Signatory Authority" - Do we have the right person?
        14. "Vendor Registration" - Can we register?
        
        TECHNICAL CHECKLIST:
        15. "Scope Alignment" - Matches our services (IAM, cybersecurity)?
        16. "Technical Requirements" - Can we meet specs?
        17. "Industry Standards" - Complies with standards?
        18. "Security Requirements" - Can we meet security needs?
        19. "Integration Needs" - Can we integrate?
        
        ========================================
        
        For EACH checklist item, decide:
        - GO = We meet this requirement
        - NO-GO = We don't meet this requirement
        - CONDITIONAL = We can meet it with conditions
        
        Return **ONLY** valid JSON (no extra text, no markdown) in this format:
        {{
            "overall_decision": "GO",
            "overall_score": 75,
            "checklist": [
                {{"category": "Financial", "item": "Payment Terms", "status": "GO", "reason": "NET30 terms", "evidence": "Found on page 5"}},
                {{"category": "Financial", "item": "Insurance", "status": "NO-GO", "reason": "Requires $10M", "evidence": "Section 3.2"}},
                {{"category": "Legal", "item": "Eligibility", "status": "GO", "reason": "We have experience", "evidence": "We have 10+ years"}}
            ],
            "go_count": 10,
            "no_go_count": 2,
            "conditional_count": 1,
            "summary": "We should bid because we meet most requirements"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Try to extract JSON from the response (in case AI added extra text)
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_text
            
            # Clean up common JSON issues
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # Parse JSON
            result = json.loads(json_str)
            
            # Ensure all required fields exist
            if 'checklist' not in result:
                result['checklist'] = []
            if 'overall_decision' not in result:
                result['overall_decision'] = 'UNDECIDED'
            if 'overall_score' not in result:
                result['overall_score'] = 0
            
            # Enforce strict score-based decision
            score = result.get('overall_score', 0)
            if score >= 71:
                result['overall_decision'] = 'GO'
            elif 51 <= score <= 70:
                result['overall_decision'] = 'CONDITIONAL'
            else:
                result['overall_decision'] = 'NO-GO'
            
            return result
            
        except Exception as e:
            # Return a fallback with sample data so the app doesn't crash
            return {
                "overall_decision": "NEEDS REVIEW",
                "overall_score": 50,
                "checklist": [
                    {"category": "Financial", "item": "Payment Terms", "status": "CONDITIONAL", "reason": "Could not analyze due to parsing error", "evidence": "Check RFP manually"},
                    {"category": "Legal", "item": "Eligibility", "status": "CONDITIONAL", "reason": "Could not analyze due to parsing error", "evidence": "Check RFP manually"},
                    {"category": "Operations", "item": "Deadlines", "status": "CONDITIONAL", "reason": "Could not analyze due to parsing error", "evidence": "Check RFP manually"},
                    {"category": "Technical", "item": "Scope", "status": "CONDITIONAL", "reason": "Could not analyze due to parsing error", "evidence": "Check RFP manually"}
                ],
                "go_count": 0,
                "no_go_count": 0,
                "conditional_count": 4,
                "summary": f"AI analysis encountered an error: {str(e)}. Please review the RFP manually."
            }
