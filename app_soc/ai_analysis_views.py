import json
import logging
import re
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from .models import WazuhFIMAlert, AIAnalysisResult
from .views import fim_access_required

logger = logging.getLogger(__name__)

# Import webhook sending functionality
try:
    from .outgoing_webhook_views import send_fim_alert_webhooks
except ImportError:
    # Fallback if import fails
    def send_fim_alert_webhooks(*args, **kwargs):
        pass


@csrf_exempt
@login_required
@fim_access_required()
def analyze_fim_alert_ai(request):
    """API endpoint for AI analysis of FIM alerts"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        alert_data = data.get('alert_data', {})
        analysis_config = data.get('analysis_config', {})
        
        # Get the AI provider
        provider = analysis_config.get('provider', 'claude')
        model = analysis_config.get('model', '')
        analysis_type = analysis_config.get('analysis_type', 'comprehensive')
        analysis_depth = analysis_config.get('analysis_depth', 'detailed')
        temperature = analysis_config.get('temperature', 0.7)
        custom_prompt = analysis_config.get('custom_prompt', '')
        
        # Validate required fields
        if not alert_data.get('alert_id'):
            return JsonResponse({
                'success': False,
                'error': 'Alert ID is required'
            }, status=400)
        
        if not provider or not model:
            return JsonResponse({
                'success': False,
                'error': 'AI provider and model are required'
            }, status=400)
        
        # Get the FIM alert
        try:
            alert = WazuhFIMAlert.objects.get(alert_id=alert_data['alert_id'])
        except WazuhFIMAlert.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'FIM alert not found'
            }, status=404)
        
        # Get information inclusion settings
        include_alert_info = analysis_config.get('include_alert_info', True)
        include_file_info = analysis_config.get('include_file_info', True)
        include_system_context = analysis_config.get('include_system_context', False)
        include_previous_analysis = analysis_config.get('include_previous_analysis', False)
        
        # Get detailed settings for each category
        alert_info_details = analysis_config.get('alert_info_details', {})
        file_info_details = analysis_config.get('file_info_details', {})
        system_context_details = analysis_config.get('system_context_details', {})
        previous_analysis_details = analysis_config.get('previous_analysis_details', {})
        
        # Build AI prompt based on analysis type and depth
        prompt = build_fim_analysis_prompt(
            alert_data, analysis_type, analysis_depth, custom_prompt,
            include_alert_info, include_file_info, include_system_context, 
            include_previous_analysis, alert_info_details, file_info_details,
            system_context_details, previous_analysis_details
        )
        
        # Get AI response using the specified provider
        ai_response = get_ai_analysis_response(provider, model, prompt, temperature, analysis_type)
        
        if not ai_response or 'error' in ai_response:
            return JsonResponse({
                'success': False,
                'error': ai_response.get('error', 'Failed to get AI response')
            }, status=500)
        
        # Parse and structure the AI response
        analysis_result = parse_ai_analysis_response(ai_response['response'], analysis_type)
        
        # Add metadata
        analysis_result.update({
            'provider': provider,
            'model': model,
            'analysis_type': analysis_type,
            'analysis_depth': analysis_depth,
            'temperature': temperature,
            'analyzed_at': timezone.now().isoformat(),
            'analyzed_by': request.user.username
        })
        
        logger.info(f"AI analysis completed for alert {alert_data['alert_id']} using {provider}/{model}")
        
        return JsonResponse({
            'success': True,
            'analysis_result': analysis_result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error during AI analysis: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to analyze FIM alert with AI'
        }, status=500)


def build_fim_analysis_prompt(alert_data, analysis_type, analysis_depth, custom_prompt, 
                             include_alert_info=True, include_file_info=True, 
                             include_system_context=False, include_previous_analysis=False,
                             alert_info_details=None, file_info_details=None,
                             system_context_details=None, previous_analysis_details=None):
    """Build AI prompt for FIM alert analysis with configurable information sections"""
    
    # Start with base context
    base_context = "You are a cybersecurity expert analyzing a File Integrity Monitoring (FIM) alert. Please provide a detailed analysis.\n\n"
    
    # Add Alert Information section if requested
    if include_alert_info:
        if alert_info_details is None:
            alert_info_details = {}
            
        base_context += "Alert Information:\n"
        
        # Include specific alert details based on settings
        if alert_info_details.get('alert_id', True):  # Default to True
            base_context += f"- Alert ID: {alert_data.get('alert_id', 'N/A')}\n"
        
        if alert_info_details.get('rule_name', True):  # Default to True
            base_context += f"- Rule Name: {alert_data.get('rule_name', 'N/A')}\n"
        
        if alert_info_details.get('description', True):  # Default to True
            base_context += f"- Description: {alert_data.get('description', 'N/A')}\n"
        
        if alert_info_details.get('alert_level', True):  # Default to True
            base_context += f"- Alert Level: {alert_data.get('level', 'N/A')}\n"
        
        if alert_info_details.get('timestamp', True):  # Default to True
            base_context += f"- Alert Timestamp: {alert_data.get('timestamp', 'N/A')}\n"
        
        if alert_info_details.get('agent_basic_info', False):  # Default to False
            base_context += f"- Agent Name: {alert_data.get('agent_name', 'N/A')}\n"
            base_context += f"- Agent IP: {alert_data.get('agent_ip', 'N/A')}\n"
        
        base_context += "\n"
    
    # Add File Information section if requested
    if include_file_info:
        if file_info_details is None:
            file_info_details = {}
            
        base_context += "File Information:\n"
        
        # Include specific file details based on settings
        if file_info_details.get('file_path', True):  # Default to True
            base_context += f"- File Path: {alert_data.get('file_path', 'N/A')}\n"
        
        if file_info_details.get('file_name', True):  # Default to True
            base_context += f"- File Name: {alert_data.get('file_name', 'N/A')}\n"
        
        if file_info_details.get('file_hashes', True):  # Default to True
            base_context += f"- MD5 Hash: {alert_data.get('file_hash_md5', 'N/A')}\n"
            base_context += f"- SHA1 Hash: {alert_data.get('file_hash_sha1', 'N/A')}\n"
            base_context += f"- SHA256 Hash: {alert_data.get('file_hash_sha256', 'N/A')}\n"
        
        if file_info_details.get('file_size', False):  # Default to False
            file_size = alert_data.get('file_size', 'N/A')
            if file_size != 'N/A':
                base_context += f"- File Size: {file_size} bytes\n"
            else:
                base_context += f"- File Size: {file_size}\n"
        
        if file_info_details.get('file_type', False):  # Default to False
            file_type = alert_data.get('file_type', 'N/A')
            base_context += f"- File Type: {file_type}\n"
        
        base_context += "\n"
    
    # Add System Context section if requested
    if include_system_context:
        if system_context_details is None:
            system_context_details = {}
            
        base_context += "System Context:\n"
        
        # Include specific system details based on settings
        if system_context_details.get('agent_name', True):  # Default to True
            base_context += f"- Agent Name: {alert_data.get('agent_name', 'N/A')}\n"
        
        if system_context_details.get('agent_ip', True):  # Default to True
            base_context += f"- Agent IP: {alert_data.get('agent_ip', 'N/A')}\n"
        
        if system_context_details.get('environment', True):  # Default to True
            base_context += f"- Environment: Production monitoring system\n"
        
        if system_context_details.get('detection_source', True):  # Default to True
            base_context += f"- Detection Source: Wazuh FIM agent\n"
        
        if system_context_details.get('os_info', False):  # Default to False
            os_info = alert_data.get('os_info', 'N/A')
            base_context += f"- Operating System: {os_info}\n"
        
        base_context += "\n"
    
    # Add Previous Analysis section if requested
    if include_previous_analysis:
        if previous_analysis_details is None:
            previous_analysis_details = {}
            
        base_context += "Previous Analysis Context:\n"
        
        # Check if we should fetch and include actual previous analysis results
        if any(previous_analysis_details.values()):
            # Fetch previous analysis results for this alert's hashes
            from .views_analysis import get_previous_analysis_for_prompt
            previous_results = get_previous_analysis_for_prompt(alert_data, previous_analysis_details)
            
            if previous_results:
                base_context += previous_results
            else:
                base_context += "- No previous analysis results found for this file\n"
        else:
            # Generic previous analysis guidance
            base_context += """- Consider this alert in context of historical patterns
- Reference any known false positives or legitimate changes
- Factor in previous risk assessments for similar files
"""
        
        base_context += "\n"
    
    # Analysis type specific prompts with role-specific instructions
    analysis_prompts = {
        'threat_assessment': """
🎯 ROLE: You are a Threat Intelligence Analyst specializing in attack detection.

FOCUS ON THREAT ASSESSMENT:
1. Identify potential security threats and attack vectors
2. Assess the likelihood of malicious activity (0-100% probability)
3. Evaluate the risk level (low, medium, high, critical) with specific justification
4. Provide specific threat indicators and IoCs
5. Map to MITRE ATT&CK framework if applicable
6. Assess if this could be part of a larger attack campaign

PRIORITIZE: Security implications over business impact.
TONE: Direct, security-focused, actionable.
""",
        'risk_analysis': """
💼 ROLE: You are a Risk Management Consultant specializing in cybersecurity impact.

FOCUS ON RISK ANALYSIS:
1. Evaluate business impact potential and financial implications
2. Assess technical risk factors and system vulnerabilities
3. Consider compliance implications (GDPR, HIPAA, SOX, PCI-DSS)
4. Provide detailed risk mitigation recommendations with timelines
5. Calculate potential business losses
6. Assess reputational damage risk

PRIORITIZE: Business continuity and compliance over technical details.
TONE: Business-oriented, quantitative, strategic.
""",
        'behavioral_analysis': """
🔍 ROLE: You are a Digital Forensics Expert specializing in behavioral analysis.

FOCUS ON BEHAVIORAL ANALYSIS:
1. Analyze file modification patterns and timelines
2. Assess normal vs abnormal behavior based on baseline
3. Identify suspicious indicators and anomalies
4. Evaluate context, timing, and sequence of events
5. Correlate with user activities and system processes
6. Identify patterns suggesting insider threat or external compromise

PRIORITIZE: Forensic evidence and behavioral patterns over business impact.
TONE: Analytical, detailed, evidence-based.
""",
        'comprehensive': """
🎓 ROLE: You are a Senior Cybersecurity Consultant providing executive-level analysis.

PROVIDE COMPREHENSIVE ANALYSIS INCLUDING:
1. Threat assessment and security implications (like a Threat Analyst)
2. Risk analysis and business impact (like a Risk Manager)
3. Behavioral analysis and patterns (like a Forensics Expert)
4. Technical findings and recommendations (like a Security Engineer)
5. Executive summary for C-level decision making
6. Integrated view of security, risk, and operational impact

PRIORITIZE: Balanced view addressing all stakeholder concerns.
TONE: Executive-level, comprehensive, strategic.
"""
    }
    
    # Analysis depth modifiers with specific output requirements
    depth_modifiers = {
        'basic': """
📄 OUTPUT DEPTH: BASIC (Executive Summary)
- Provide 3-5 key bullet points maximum
- Focus only on critical findings
- Keep summary under 200 words
- Use high-level terminology
- Prioritize actionable items
""",
        'detailed': """
📊 OUTPUT DEPTH: DETAILED (Technical Report)
- Provide comprehensive explanations for each finding
- Include supporting evidence and reasoning
- Add context and background information
- Use technical terminology appropriate for security teams
- Target 500-800 words in detailed_analysis
- Include specific recommendations with implementation steps
""",
        'comprehensive': """
📋 OUTPUT DEPTH: COMPREHENSIVE (Full Investigation Report)
- Provide exhaustive analysis with full context
- Include multiple perspectives and scenarios
- Add threat modeling and impact analysis
- Use both technical and business terminology
- Target 1000+ words in detailed_analysis
- Include timeline analysis, root cause investigation
- Provide strategic and tactical recommendations
- Consider long-term implications and monitoring requirements
"""
    }
    
    prompt = base_context + analysis_prompts.get(analysis_type, analysis_prompts['comprehensive'])
    prompt += "\n" + depth_modifiers.get(analysis_depth, depth_modifiers['detailed'])
    
    if custom_prompt:
        prompt += f"\n\nAdditional Instructions: {custom_prompt}"
    
    prompt += """

Please structure your response as a JSON object with the following fields:
{
    "risk_level": "low|medium|high|critical",
    "confidence": 0-100,
    "summary": "Brief summary of the analysis",
    "key_findings": ["finding1", "finding2", "finding3"],
    "recommendations": ["recommendation1", "recommendation2", "recommendation3"],
    "detailed_analysis": "Detailed explanation of the findings",
    "threat_indicators": ["indicator1", "indicator2"],
    "business_impact": "Assessment of business impact"
}
"""
    
    return prompt


def get_ai_analysis_response(provider, model, prompt, temperature, analysis_type='comprehensive'):
    """Get AI response using the specified provider with type-specific adjustments"""
    
    # Adjust temperature based on analysis type for more varied responses
    type_temperature_adjustments = {
        'threat_assessment': 0.3,  # More focused and deterministic
        'risk_analysis': 0.5,      # Balanced approach
        'behavioral_analysis': 0.4, # Slightly more analytical
        'comprehensive': 0.6       # More creative and varied
    }
    
    # Apply temperature adjustment
    adjusted_temperature = min(1.0, max(0.0, 
        temperature * type_temperature_adjustments.get(analysis_type, 1.0)))
    
    # Add type-specific system message
    type_system_messages = {
        'threat_assessment': "You are a Threat Intelligence Analyst. Focus on security threats and provide precise, actionable threat analysis.",
        'risk_analysis': "You are a Risk Management Consultant. Focus on business impact, compliance, and strategic risk mitigation.",
        'behavioral_analysis': "You are a Digital Forensics Expert. Focus on behavioral patterns, anomalies, and evidence-based analysis.",
        'comprehensive': "You are a Senior Cybersecurity Consultant. Provide balanced, executive-level analysis covering all aspects."
    }
    
    system_message = type_system_messages.get(analysis_type, 
        "You are a cybersecurity expert analyzing FIM alerts.")
    
    try:
        if provider == 'claude':
            from app_ai.ai_utils import get_claude_response
            response = get_claude_response(prompt, [])
            return {'response': response}
        elif provider == 'google':
            from app_ai.ai_utils import get_google_response
            response = get_google_response(prompt, [], '')
            return {'response': response}
        elif provider == 'groq':
            from app_ai.ai_utils import get_groq_response
            response = get_groq_response(prompt, [])
            return {'response': response}
        elif provider == 'deepseek':
            # Use centralized DeepSeek function with adjusted parameters
            from app_ai.ai_utils import get_deepseek_response
            response = get_deepseek_response(prompt, [], system_message)
            return {'response': response}
        else:
            return {'error': f'Unsupported AI provider: {provider}'}
            
    except Exception as e:
        logger.error(f"Error getting AI response from {provider}: {str(e)}")
        return {'error': str(e)}


def parse_ai_analysis_response(response, analysis_type):
    """Parse AI response and extract structured data"""
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            ai_data = json.loads(json_match.group())
            return ai_data
        else:
            # Fallback: parse unstructured response
            return {
                'risk_level': 'medium',
                'confidence': 75,
                'summary': response[:200] + '...' if len(response) > 200 else response,
                'key_findings': ['AI analysis completed'],
                'recommendations': ['Review the analysis results'],
                'detailed_analysis': response,
                'threat_indicators': [],
                'business_impact': 'To be assessed'
            }
    except Exception as e:
        logger.error(f"Error parsing AI response: {str(e)}")
        return {
            'risk_level': 'medium',
            'confidence': 50,
            'summary': 'AI analysis completed but response parsing failed',
            'key_findings': ['AI analysis attempted'],
            'recommendations': ['Manual review required'],
            'detailed_analysis': response,
            'threat_indicators': [],
            'business_impact': 'Unknown'
        }


@require_http_methods(["GET"])
@login_required
@fim_access_required()
def get_ai_models_api(request):
    """API endpoint for getting available AI models by provider"""
    provider = request.GET.get('provider', '')
    
    if not provider:
        return JsonResponse({
            'success': False,
            'error': 'Provider parameter is required'
        }, status=400)
    
    try:
        from app_ai.models import ModelChoice
        
        # Get active models for the specified provider
        models = ModelChoice.objects.filter(
            provider=provider,
            is_active=True
        ).values('model_id', 'model_name').order_by('model_name')
        
        models_list = list(models)
        
        logger.info(f"Retrieved {len(models_list)} models for provider: {provider}")
        
        return JsonResponse({
            'success': True,
            'provider': provider,
            'models': models_list
        })
        
    except Exception as e:
        logger.error(f"Error retrieving AI models for provider {provider}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to retrieve AI models'
        }, status=500)


@require_http_methods(["GET"])
@login_required  
@fim_access_required()
def get_ai_providers_api(request):
    """API endpoint for getting available AI providers"""
    try:
        from app_ai.models import (
            APISettingsClaude, APISettingsGoogle, APISettingsGroq, 
            APISettingsDeepSeek, APISettingsOllama, ModelChoice
        )
        
        providers = []
        
        # Check each provider type and their configuration status
        provider_configs = [
            ('claude', APISettingsClaude),
            ('google', APISettingsGoogle),
            ('groq', APISettingsGroq),
            ('deepseek', APISettingsDeepSeek),
            ('ollama', APISettingsOllama)
        ]
        
        for provider_name, provider_model in provider_configs:
            # Check if provider is configured
            is_configured = provider_model.objects.exists()
            
            # Get model count for this provider
            model_count = ModelChoice.objects.filter(
                provider=provider_name,
                is_active=True
            ).count()
            
            providers.append({
                'name': provider_name,
                'display_name': provider_name.title(),
                'configured': is_configured,
                'model_count': model_count
            })
        
        logger.info(f"Retrieved {len(providers)} AI providers")
        
        return JsonResponse({
            'success': True,
            'providers': providers
        })
        
    except Exception as e:
        logger.error(f"Error retrieving AI providers: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to retrieve AI providers'
        }, status=500)


@csrf_exempt
@login_required
@fim_access_required()
def save_ai_analysis_result_api(request):
    """API endpoint for saving AI analysis results"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['alert_id', 'ai_provider', 'ai_model', 'analysis_type', 'risk_level', 'confidence', 'summary']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Get the alert
            try:
                alert = WazuhFIMAlert.objects.get(alert_id=data['alert_id'])
            except WazuhFIMAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Generate unique analysis ID
            analysis_id = f"ai_{data['ai_provider']}_{uuid.uuid4().hex[:12]}"
            
            # Create AI analysis result
            result = AIAnalysisResult.objects.create(
                analysis_id=analysis_id,
                alert=alert,
                ai_provider=data['ai_provider'],
                ai_model=data['ai_model'],
                analysis_type=data['analysis_type'],
                analysis_depth=data.get('analysis_depth', 'detailed'),
                temperature=data.get('temperature', 0.7),
                risk_level=data['risk_level'],
                confidence=data['confidence'],
                summary=data['summary'],
                detailed_analysis=data.get('detailed_analysis', ''),
                key_findings=data.get('key_findings', []),
                recommendations=data.get('recommendations', []),
                alert_context=data.get('alert_context', {}),
                custom_prompt=data.get('custom_prompt', ''),
                included_info=data.get('included_info', {}),
                analysis_config=data.get('analysis_config', {}),
                raw_response=data.get('raw_response', ''),
                analyzed_by=request.user,
            )
            
            # Send outgoing webhooks for AI analysis completion
            try:
                webhook_result = send_fim_alert_webhooks(alert, 'ai_analysis_complete', ai_analysis=result)
                if webhook_result['sent'] > 0:
                    logger.info(f"Sent {webhook_result['sent']} AI analysis webhooks for alert {alert.alert_id}")
                if webhook_result['failed'] > 0:
                    logger.warning(f"Failed to send {webhook_result['failed']} AI analysis webhooks")
            except Exception as e:
                logger.error(f"Error sending AI analysis webhooks: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'analysis_id': result.analysis_id,
                'result_id': result.id,
                'message': 'AI analysis result saved successfully'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error saving AI analysis result: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to save AI analysis result'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def ai_analysis_results_api(request, alert_id):
    """API endpoint for getting AI analysis results for a specific alert"""
    if request.method == 'GET':
        try:
            # Get the alert
            try:
                alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
            except WazuhFIMAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 5))
            
            # Get AI analysis results for this alert
            results_queryset = AIAnalysisResult.objects.filter(alert=alert).order_by('-created_at')
            
            # Apply pagination
            paginator = Paginator(results_queryset, per_page)
            page_obj = paginator.get_page(page)
            
            results_data = []
            
            for result in page_obj:
                results_data.append({
                    'id': result.id,
                    'analysis_id': result.analysis_id,
                    'ai_provider': result.ai_provider,
                    'ai_model': result.ai_model,
                    'analysis_type': result.analysis_type,
                    'analysis_depth': result.analysis_depth,
                    'temperature': result.temperature,
                    'risk_level': result.risk_level,
                    'confidence': result.confidence,
                    'summary': result.summary[:200] + '...' if len(result.summary) > 200 else result.summary,
                    'key_findings': result.key_findings[:3] if len(result.key_findings) > 3 else result.key_findings,  # First 3 findings
                    'recommendations': result.recommendations[:3] if len(result.recommendations) > 3 else result.recommendations,  # First 3 recommendations
                    'created_at': result.created_at.isoformat(),
                    'analyzed_by': result.analyzed_by.username if result.analyzed_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'alert_id': alert_id,
                'results': results_data,
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'per_page': per_page,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                    'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting AI analysis results: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get AI analysis results'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def ai_analysis_result_detail_api(request, analysis_id):
    """API endpoint for getting detailed AI analysis result information"""
    if request.method == 'GET':
        try:
            # Get the AI analysis result
            try:
                result = AIAnalysisResult.objects.get(analysis_id=analysis_id)
            except AIAnalysisResult.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'AI analysis result not found'
                }, status=404)
            
            # Prepare detailed data
            detailed_data = {
                'id': result.id,
                'analysis_id': result.analysis_id,
                'alert': {
                    'alert_id': result.alert.alert_id,
                    'rule_name': result.alert.rule_name,
                    'description': result.alert.description,
                    'file_path': result.alert.file_path,
                    'file_name': result.alert.file_name,
                    'agent_name': result.alert.agent_name,
                    'agent_ip': result.alert.agent_ip,
                    'timestamp': result.alert.timestamp.isoformat(),
                    'received_at': result.alert.received_at.isoformat(),
                },
                'ai_provider': result.ai_provider,
                'ai_model': result.ai_model,
                'analysis_type': result.analysis_type,
                'analysis_depth': result.analysis_depth,
                'temperature': result.temperature,
                'risk_level': result.risk_level,
                'confidence': result.confidence,
                'summary': result.summary,
                'detailed_analysis': result.detailed_analysis,
                'key_findings': result.key_findings,
                'recommendations': result.recommendations,
                'alert_context': result.alert_context,
                'custom_prompt': result.custom_prompt,
                'included_info': result.included_info,
                'analysis_config': result.analysis_config,
                'raw_response': result.raw_response,
                'created_at': result.created_at.isoformat(),
                'updated_at': result.updated_at.isoformat(),
                'analyzed_by': {
                    'username': result.analyzed_by.username if result.analyzed_by else None,
                    'first_name': result.analyzed_by.first_name if result.analyzed_by else None,
                    'last_name': result.analyzed_by.last_name if result.analyzed_by else None,
                },
            }
            
            return JsonResponse({
                'success': True,
                'result': detailed_data
            })
        except Exception as e:
            logger.error(f"Error getting AI analysis result detail: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get AI analysis result detail'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
