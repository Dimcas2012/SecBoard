"""
API Documentation for SecBoard Information Security Platform
This file provides machine-readable documentation for AI agents and developers
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json


@require_http_methods(["GET"])
def api_schema(request):
    """
    Provides OpenAPI schema for the SecBoard platform
    This endpoint helps AI agents understand the application structure
    """
    schema = {
        "openapi": "3.0.3",
        "info": {
            "title": "SecBoard API",
            "description": "Information Security Management Platform API",
            "version": "1.0.0",
            "contact": {
                "name": "SecBoard Team",
                "url": "https://secboard.online"
            },
            "license": {
                "name": "Proprietary"
            }
        },
        "servers": [
            {
                "url": request.build_absolute_uri('/').rstrip('/'),
                "description": "Production server"
            }
        ],
        "paths": {
            "/api/security-training/": {
                "get": {
                    "summary": "Get security training modules",
                    "description": "Retrieve available cybersecurity training content",
                    "tags": ["Training"],
                    "responses": {
                        "200": {
                            "description": "List of training modules",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/TrainingModule"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/risk-assessment/": {
                "get": {
                    "summary": "Get risk assessments",
                    "description": "Retrieve security risk assessment data",
                    "tags": ["Risk Management"],
                    "responses": {
                        "200": {
                            "description": "Risk assessment results"
                        }
                    }
                }
            },
            "/api/incidents/": {
                "get": {
                    "summary": "Get security incidents",
                    "description": "Retrieve security incident reports",
                    "tags": ["Incident Management"],
                    "responses": {
                        "200": {
                            "description": "List of security incidents"
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "TrainingModule": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": "Module ID"
                        },
                        "title": {
                            "type": "string",
                            "description": "Training module title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Module description"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["phishing", "malware", "data-protection", "compliance"]
                        }
                    }
                }
            }
        },
        "tags": [
            {
                "name": "Training",
                "description": "Security training and awareness modules"
            },
            {
                "name": "Risk Management",
                "description": "Risk assessment and management tools"
            },
            {
                "name": "Incident Management",
                "description": "Security incident tracking and response"
            }
        ]
    }
    
    return JsonResponse(schema, json_dumps_params={'indent': 2})


@require_http_methods(["GET"])
def platform_info(request):
    """
    Provides general platform information for AI agents
    """
    info = {
        "platform": {
            "name": "SecBoard",
            "type": "Information Security Management Platform",
            "description": "Comprehensive cybersecurity platform providing training, risk assessment, incident management, and compliance tools",
            "version": "1.0.0",
            "categories": [
                "Information Security",
                "Cybersecurity Training", 
                "Risk Management",
                "Incident Response",
                "Compliance Management",
                "Security Assessment"
            ],
            "features": [
                "Security Awareness Training",
                "Phishing Simulation",
                "Risk Assessment Tools",
                "Incident Management System",
                "Document Management",
                "Compliance Tracking",
                "Asset Management",
                "Key & Certificate Management",
                "AI-Powered Security Analytics"
            ],
            "target_audience": [
                "Cybersecurity Professionals",
                "IT Security Teams",
                "Compliance Officers",
                "Risk Managers",
                "Security Consultants",
                "Enterprise Organizations"
            ],
            "supported_languages": ["en", "uk", "ru"],
            "license": "Proprietary",
            "contact": {
                "website": "https://secboard.online",
                "support": "Available through platform"
            }
        },
        "api": {
            "version": "1.0",
            "base_url": request.build_absolute_uri('/api/'),
            "authentication": "Session-based",
            "documentation": request.build_absolute_uri('/api/schema/')
        },
        "last_updated": "2024-01-01T00:00:00Z"
    }
    
    return JsonResponse(info, json_dumps_params={'indent': 2}) 