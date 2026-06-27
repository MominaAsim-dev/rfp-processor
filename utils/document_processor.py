import google.generativeai as genai
import PyPDF2
import docx
import os
import json
from typing import Dict, Any

class RFPProcessor:
    """Handles document extraction and AI analysis for RFP documents using Gemini"""
    
    def __init__(self, api_key: str):
        """Initialize with Gemini API key and auto-select available model"""
        genai.configure(api_key=api_key)
        
        # Auto-select first available model that supports generateContent
        self.model = None
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                self.model = genai.GenerativeModel(model.name)
                print(f"✅ Using model: {model.name}")
                break
        
        if self.model is None:
            raise Exception("No available Gemini model found that supports generateContent.")
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
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
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            raise Exception(f"Error reading DOCX: {str(e)}")
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error reading TXT: {str(e)}")
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from various document formats"""
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
        """Analyze RFP document using Gemini"""
        
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
            
            # Remove markdown code blocks if present
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