# SecBoard/app_compliance/ai_import_helpers.py
import json
import re
import PyPDF2
from datetime import datetime
from app_ai.ai_utils import get_ai_response


def extract_text_from_pdf(pdf_file):
    """Extract text content from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise ValueError(f"Error extracting text from PDF: {str(e)}")


def parse_pdf_with_ai(pdf_text, ai_model, country=None):
    """Parse PDF text using AI to extract requirement and controls"""
    
    # Determine language instruction based on country
    language_instruction = ""
    if country:
        country_name = country.name
        country_local = country.name_local if country.name_local else country.name
        language_instruction = f"""
LANGUAGE CONTEXT:
- Document country: {country_name} ({country.code})
- Local country name: {country_local}
- When extracting "name_local" field, use the language of {country_name}
- If document is in {country_name} language, fill "name_local" with original text
- If document is in English but relates to {country_name}, translate "name" to {country_name} language for "name_local"
"""
    
    user_prompt = f"""ROLE:
You are an expert business analyst and GRC (Governance, Risk, and Compliance) specialist. Your task is to analyze the provided regulatory document text and structure the data into JSON format.
{language_instruction}
TASK 1: REQUIREMENT METADATA
Extract document metadata with these rules:

- Code: Unique document code/number (e.g., order number, policy ID)
- Name: Full document name/title (extract as-is from document)
- Name Local: Document name in local/original language. If document is already in local language, copy the name here. This field should contain the original/native language version
- Type: Document type (policy, standard, procedure, guideline, directive, rule, other)
- Status: Document status (draft or active). If there's an approval order - use "active"
- Priority: Document priority based on content:
  * critical: Financial systems, security, encryption, authentication, data deletion, access control
  * high: Compliance requirements, audit, risk management, incident response
  * medium: Operational procedures, training, documentation
  * low: General guidelines, recommendations
- Mandatory: true for policies/standards with approval, false for guidelines/recommendations
- Description: Brief description (2-3 sentences about document purpose)
- Applicable To: Who this applies to (e.g., "All employees", "IT Department", "Security team")
- Publication Date: Approval/publication date (format: YYYY-MM-DD)
- Effective Date: Date when document takes effect (format: YYYY-MM-DD)
- Deadline Date: Compliance deadline if specified (format: YYYY-MM-DD)

TASK 2: CONTROLS LIST
Extract ALL requirements, rules, and controls from the text. Look for sentences containing:
- "must", "shall", "required", "mandatory", "obliged"
- "should", "need to", "necessary", "prohibited", "forbidden"
- Any imperative statements defining what must be done

For each control, fill:

- Category Code: Section number (e.g., "6.1", "2.3")
- Category Name: Section title
- Category Description: Brief section description
- Control Code: Specific item number (e.g., "6.1.2", "2.3.1")
- Control Name: Short control name (3-7 words summarizing the requirement)
- Description: Full text of the requirement from document
- Priority: Determine based on context:
  * critical: Passwords, encryption, data deletion, backup, authentication, authorization, firewall rules
  * high: Logging, monitoring, access reviews, security patches, incident response
  * medium: Documentation, training, regular reviews, configuration management
  * low: General guidelines, document reviews, informational requirements
- Target Date: Effective date from metadata (YYYY-MM-DD)
- Periodicity: IMPORTANT! Fill ONLY if periodicity is EXPLICITLY stated in text. Convert to days:
  * Daily/Every day = 1
  * Weekly/Every week/Every 7 days = 7
  * Monthly/Every month = 30
  * Quarterly/Every 3 months/Every quarter = 90
  * Semi-annually/Every 6 months/Twice a year = 180
  * Annually/Every year/Once a year = 365
  * If text says "regularly", "constantly", "as needed" - leave EMPTY (null)
- Implementation Notes: Brief technical or organizational description of what needs to be done
- Evidence Notes: What proof of compliance is needed (log, report, screenshot, journal, order, certificate, document)

PERIODICITY EXAMPLES:
- "Review firewall rules every 6 months" → 180
- "Backup data daily" → 1
- "Conduct security training quarterly" → 90
- "Regular monitoring" → null (leave empty)
- "Continuous review" → null (leave empty)

PRIORITY LOGIC:
- Keywords for CRITICAL: password, encryption, decrypt, authentication, authorization, delete, backup, restore, firewall, access control, key management
- Keywords for HIGH: log, audit, monitor, patch, update, vulnerability, incident, breach, review access
- Keywords for MEDIUM: document, procedure, training, guideline, report, notify
- Keywords for LOW: review document, familiarize, inform, general procedure

OUTPUT FORMAT:
Return ONLY valid JSON in this EXACT structure. IMPORTANT RULES:
- Use "true" or "false" for booleans (NOT "t" or "f")
- Use null for empty numbers (NOT empty string)
- Use empty string "" for empty text fields
- Ensure ALL quotes are properly closed
- Ensure proper JSON syntax with commas

{{
    "requirement": {{
        "code": "string",
        "name": "string",
        "name_local": "string or empty",
        "type": "policy|standard|procedure|guideline|directive|rule|other",
        "status": "draft|active",
        "priority": "critical|high|medium|low",
        "is_mandatory": true,
        "description": "string",
        "applicable_to": "string or empty",
        "publication_date": "YYYY-MM-DD or empty string",
        "effective_date": "YYYY-MM-DD or empty string",
        "deadline_date": "YYYY-MM-DD or empty string"
    }},
    "controls": [
        {{
            "code": "string",
            "name": "string (3-7 words)",
            "description": "full requirement text",
            "category": "category name",
            "category_code": "section number",
            "category_description": "section description or empty string",
            "priority": "critical|high|medium|low",
            "target_date": "YYYY-MM-DD or empty string",
            "periodicity": 30,
            "implementation_notes": "what to do",
            "evidence_notes": "what proof needed"
        }}
    ]
}}

CRITICAL RULES:
- Use complete words for booleans: "true" and "false" (never "t", "f", "True", "False")
- Use null (not "null" string) for empty periodicity
- For "name_local": preserve original language text from document (Ukrainian, Polish, etc.)
- Extract control names and descriptions exactly as they appear in the document
- If a field is not found in document, use empty string "" (not null)

DOCUMENT TEXT:
{pdf_text[:10000]}

RETURN ONLY THE COMPLETE JSON OBJECT. NO MARKDOWN, NO EXPLANATIONS, NO ADDITIONAL TEXT."""

    conversation_history = []
    
    try:
        response_text, usage_info = get_ai_response(ai_model, user_prompt, conversation_history, pdf_text[:12000])
        
        # Log response for debugging
        print(f"AI Response (first 500 chars): {response_text[:500]}")
        
        if not response_text or not response_text.strip():
            raise ValueError("AI returned empty response")
        
        # Clean response - remove markdown code blocks and extra text
        response_text = response_text.strip()
        
        # Check if AI returned an error message instead of JSON
        error_indicators = [
            "error occurred",
            "Error:",
            "An error",
            "429 Resource exhausted",
            "authentication error",
            "API error",
            "rate limit",
            "quota exceeded"
        ]
        
        response_lower = response_text.lower()
        for indicator in error_indicators:
            if indicator.lower() in response_lower:
                # Extract a meaningful error message
                error_msg = response_text[:500]
                raise ValueError(f"AI service error: {error_msg}")
        
        # Try to find JSON in the response
        # Look for { and } to extract JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError(f"No JSON object found in AI response. Response: {response_text[:300]}")
        
        json_text = response_text[start_idx:end_idx+1]
        
        # Parse JSON with aggressive cleaning
        try:
            parsed_data = json.loads(json_text)
        except json.JSONDecodeError as je:
            print(f"Initial JSON parse failed: {str(je)}, attempting cleanup...")
            
            # Try additional cleaning
            json_text_cleaned = json_text
            
            # Remove newlines and carriage returns
            json_text_cleaned = json_text_cleaned.replace('\n', ' ').replace('\r', ' ')
            
            # Remove trailing commas before } or ]
            json_text_cleaned = re.sub(r',\s*}', '}', json_text_cleaned)
            json_text_cleaned = re.sub(r',\s*]', ']', json_text_cleaned)
            
            # Fix common AI mistakes with boolean values
            # Replace ": t" or ": f" with proper boolean (but not in strings)
            json_text_cleaned = re.sub(r':\s*t\s*([,}])', r': true\1', json_text_cleaned)
            json_text_cleaned = re.sub(r':\s*f\s*([,}])', r': false\1', json_text_cleaned)
            
            # Fix "true"/"false" if they appear as "t"/"f" in boolean context
            json_text_cleaned = re.sub(r'"is_mandatory":\s*t\b', '"is_mandatory": true', json_text_cleaned)
            json_text_cleaned = re.sub(r'"is_mandatory":\s*f\b', '"is_mandatory": false', json_text_cleaned)
            
            # Try to complete incomplete JSON if it ends abruptly
            if not json_text_cleaned.rstrip().endswith('}'):
                # Count opening and closing braces
                open_braces = json_text_cleaned.count('{')
                close_braces = json_text_cleaned.count('}')
                open_brackets = json_text_cleaned.count('[')
                close_brackets = json_text_cleaned.count(']')
                
                # Add missing closing brackets/braces
                if open_brackets > close_brackets:
                    json_text_cleaned += ']' * (open_brackets - close_brackets)
                if open_braces > close_braces:
                    json_text_cleaned += '}' * (open_braces - close_braces)
            
            print(f"Cleaned JSON (first 500 chars): {json_text_cleaned[:500]}")
            parsed_data = json.loads(json_text_cleaned)
        
        # Validate structure
        if 'requirement' not in parsed_data:
            parsed_data['requirement'] = {}
        if 'controls' not in parsed_data:
            parsed_data['controls'] = []
        
        return parsed_data, usage_info
        
    except json.JSONDecodeError as e:
        error_msg = f"AI returned invalid JSON: {str(e)}. Response was: {response_text[:500] if response_text else 'Empty'}"
        print(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error parsing with AI: {str(e)}"
        print(error_msg)
        raise ValueError(error_msg)


def validate_parsed_data(data):
    """Validate and clean parsed data"""
    requirement = data.get('requirement', {})
    controls = data.get('controls', [])
    
    # Ensure requirement has required fields
    if not requirement.get('code'):
        requirement['code'] = 'REQ-' + str(int(datetime.now().timestamp()))
    if not requirement.get('name'):
        requirement['name'] = 'Unnamed Requirement'
    if not requirement.get('type'):
        requirement['type'] = 'policy'
    if not requirement.get('status'):
        requirement['status'] = 'draft'
    if not requirement.get('priority'):
        requirement['priority'] = 'medium'
    if 'is_mandatory' not in requirement:
        requirement['is_mandatory'] = True
    
    # Ensure all date fields exist (can be empty)
    for date_field in ['publication_date', 'effective_date', 'deadline_date']:
        if date_field not in requirement:
            requirement[date_field] = ''
    
    # Ensure text fields exist
    for text_field in ['name_local', 'description', 'applicable_to']:
        if text_field not in requirement:
            requirement[text_field] = ''
    
    # Validate controls
    validated_controls = []
    for idx, control in enumerate(controls):
        # Required fields with defaults
        if not control.get('code'):
            control['code'] = f'CTRL-{idx+1:03d}'
        if not control.get('name'):
            control['name'] = f'Control {idx+1}'
        if not control.get('priority'):
            control['priority'] = 'medium'
        
        # Ensure category fields exist
        if 'category' not in control:
            control['category'] = ''
        if 'category_code' not in control:
            control['category_code'] = ''
        if 'category_description' not in control:
            control['category_description'] = ''
        
        # Ensure text fields exist
        for text_field in ['description', 'implementation_notes', 'evidence_notes']:
            if text_field not in control:
                control[text_field] = ''
        
        # Ensure date field exists
        if 'target_date' not in control:
            control['target_date'] = ''
        
        # Validate periodicity (should be number or None/null)
        if 'periodicity' in control:
            if control['periodicity'] is not None:
                try:
                    control['periodicity'] = int(control['periodicity'])
                    if control['periodicity'] <= 0:
                        control['periodicity'] = None
                except (ValueError, TypeError):
                    control['periodicity'] = None
        else:
            control['periodicity'] = None
        
        validated_controls.append(control)
    
    return {
        'requirement': requirement,
        'controls': validated_controls
    }

