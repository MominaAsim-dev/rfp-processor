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
        """Perform Go/No-Go analysis on RFP"""
        
        prompt = f"""
        You are a Bid/No-Bid decision expert. Analyze this RFP and provide a Go/No-Go recommendation.
        
        Evaluate these 5 key criteria (each scored 0-10):
        1. STRATEGIC FIT: Does this align with our business goals?
        2. CAPABILITY: Can we deliver successfully?
        3. COMPETITIVENESS: Can we win?
        4. FINANCIAL: Is it profitable?
        5. RISK: Are risks acceptable?
        
        RFP Text:
        {text[:8000]}
        
        Return ONLY valid JSON in this format:
        {{
            "decision": "GO" or "NO-GO" or "CONSIDER",
            "score": 85,
            "criteria": {{
                "Strategic Fit": {{"score": 9, "passed": true, "explanation": "..."}},
                "Capability": {{"score": 8, "passed": true, "explanation": "..."}},
                "Competitiveness": {{"score": 7, "passed": true, "explanation": "..."}},
                "Financial": {{"score": 6, "passed": true, "explanation": "..."}},
                "Risk": {{"score": 5, "passed": false, "explanation": "..."}}
            }},
            "strengths": ["Strength 1", "Strength 2"],
            "risks": ["Risk 1", "Risk 2"],
            "recommendation": "Brief recommendation summary"
        }}
        
        Rules:
        - Score >= 70 = GO
        - Score 50-69 = CONSIDER (with conditions)
        - Score < 50 = NO-GO
        - Be specific and practical
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
                "decision": "NO-GO",
                "score": 0,
                "criteria": {},
                "strengths": ["Unable to analyze"],
                "risks": ["Error in analysis"],
                "recommendation": f"Error: {str(e)}"
            }
