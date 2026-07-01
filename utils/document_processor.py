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
    
    Return JSON ONLY in this format:
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
        json_str = response.text.strip()
        
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        result = json.loads(json_str)
        
        # Ensure all required fields exist
        if 'checklist' not in result:
            result['checklist'] = []
        if 'overall_decision' not in result:
            result['overall_decision'] = 'UNDECIDED'
        if 'overall_score' not in result:
            result['overall_score'] = 0
        
        # ============================================================
        # 🆕 ENFORCE STRICT SCORE-BASED DECISION (NO OVERRIDES)
        # ============================================================
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
                {"category": "Financial", "item": "Payment Terms", "status": "CONDITIONAL", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Legal", "item": "Eligibility", "status": "CONDITIONAL", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Operations", "item": "Deadlines", "status": "CONDITIONAL", "reason": "Could not analyze", "evidence": "Check RFP manually"},
                {"category": "Technical", "item": "Scope", "status": "CONDITIONAL", "reason": "Could not analyze", "evidence": "Check RFP manually"}
            ],
            "go_count": 0,
            "no_go_count": 0,
            "conditional_count": 4,
            "summary": "AI analysis encountered an error. Please review the RFP manually."
        }
