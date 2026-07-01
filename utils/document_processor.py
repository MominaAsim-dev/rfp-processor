import google.generativeai as genai
import PyPDF2
import docx
import os
import json
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
    
    # ============================================================
    # 🆕 NEW: Go/No-Go Analysis Method
    # ============================================================
   def go_no_go_analysis(self, text: str) -> Dict[str, Any]:
    """Perform Go/No-Go analysis based on company checklist"""
    
    prompt = f"""
    You are a Bid/No-Bid decision expert for a company. 
    Analyze this RFP against our company's strict checklist.
    
    ========================================
    🏢 OUR COMPANY CHECKLIST
    ========================================
    
    ### FINANCIAL / ACCOUNTING CHECKLIST
    1. Payment Terms: NET30 is GO. More than NET30 is NO-GO.
    2. Financial Stability: Check if RFP requires audited financial statements.
    3. Insurance Requirements: If $5M or less = GO. If more than $5M = NO-GO.
    4. Profitability Analysis: Can we make profit?
    5. Bid Bond: Is it required? Can we provide it?
    
    ### LEGAL CHECKLIST
    6. Eligibility Criteria: Do we have relevant experience?
    7. Registration: Need to be registered in the state?
    8. E-Verify: Is it required?
    9. Contractual Obligations: Are terms acceptable (termination, liability, dispute)?
    10. Compliance: Does it comply with laws and regulations?
    
    ### OPERATIONS CHECKLIST
    11. Required Forms: Can we complete all required forms?
    12. Submission Deadlines: Can we meet them?
    13. Signatory Authority: Do we have the right person to sign?
    14. Vendor Registration: Do we need to register? Can we?
    
    ### TECHNICAL CHECKLIST
    15. Scope Alignment: Does this match our services (IAM, cybersecurity, etc.)?
    16. Technical Requirements: Can we meet the specs?
    17. Industry Standards: Does it comply with standards we follow?
    18. Security: Can we meet security requirements (encryption, access controls)?
    19. Integration: Can we integrate with other systems?
    
    ========================================
    RFP TEXT:
    {text[:10000]}
    ========================================
    
    For EACH checklist item, evaluate:
    - Status: "GO" or "NO-GO" or "CONDITIONAL"
    - Reason: Specific explanation based on the RFP text
    - Evidence: Quote or reference from the RFP that supports your decision
    
    Then provide:
    - Overall Decision: "GO" or "NO-GO" or "CONDITIONAL"
    - Overall Score: 0-100
    - Summary of why you recommend this decision
    
    Return ONLY valid JSON in this exact format:
    {{
        "overall_decision": "GO",
        "overall_score": 85,
        "summary": "This RFP aligns well with our capabilities...",
        "checklist_results": {{
            "Financial": {{
                "Payment Terms": {{
                    "status": "GO",
                    "reason": "NET30 payment terms match our policy",
                    "evidence": "RFP states NET30 on page 5"
                }},
                "Insurance": {{
                    "status": "NO-GO",
                    "reason": "Insurance requirement is $10M, exceeds our $5M limit",
                    "evidence": "Section 3.2 requires $10M coverage"
                }},
                "Profitability": {{
                    "status": "GO",
                    "reason": "Budget of $500K aligns with our cost structure",
                    "evidence": "Budget range is $400K-$600K"
                }}
            }},
            "Legal": {{
                "Eligibility": {{
                    "status": "GO",
                    "reason": "We have 10+ years relevant experience",
                    "evidence": "RFP requires 5+ years, we have 10"
                }},
                "Registration": {{
                    "status": "GO",
                    "reason": "We are already registered in the state",
                    "evidence": "No specific state registration mentioned"
                }},
                "Contract Terms": {{
                    "status": "CONDITIONAL",
                    "reason": "Indemnification clause needs review",
                    "evidence": "Section 7.2 has unlimited liability clause"
                }}
            }},
            "Operations": {{
                "Forms": {{
                    "status": "GO",
                    "reason": "All forms are standard and we have them ready",
                    "evidence": "Standard W-9, insurance certificates required"
                }},
                "Deadlines": {{
                    "status": "GO",
                    "reason": "30-day submission timeline is feasible",
                    "evidence": "Due date is August 15, 2026"
                }}
            }},
            "Technical": {{
                "Scope": {{
                    "status": "GO",
                    "reason": "IAM and cybersecurity are our core services",
                    "evidence": "RFP requires identity management solutions"
                }},
                "Security": {{
                    "status": "GO",
                    "reason": "We meet all security requirements",
                    "evidence": "RFP requires ISO 27001, we are certified"
                }}
            }}
        }},
        "go_items": ["Payment Terms", "Eligibility", "Scope"],
        "no_go_items": ["Insurance"],
        "conditional_items": ["Contract Terms"],
        "recommendation": "We should bid, but negotiate insurance requirements"
    }}
    
    RULES:
    - Be STRICT with the checklist
    - Only mark GO if the RFP clearly meets the criteria
    - Mark NO-GO if the RFP violates any mandatory criteria
    - Mark CONDITIONAL if it can be negotiated or needs review
    - Provide specific evidence from the RFP text
    - Overall GO only if ALL critical items are GO or CONDITIONAL
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
            "overall_decision": "ERROR",
            "overall_score": 0,
            "summary": f"Error in analysis: {str(e)}",
            "checklist_results": {},
            "go_items": [],
            "no_go_items": [],
            "conditional_items": [],
            "recommendation": "Unable to analyze - please try again"
        }
   
      
                "recommendation": f"Error: {str(e)}"
            }
