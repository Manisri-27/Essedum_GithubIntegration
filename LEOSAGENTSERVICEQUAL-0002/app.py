#!/usr/bin/env python3
# file: app.py
"""
Flask REST API for Multi-Agent Telecom Q&A System with LangGraph Workflow

Provides REST endpoints for TMF 645 service qualification using LangGraph workflow.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

from src.config import AppConfig
from src.workflow_state import WorkflowState
from src.graph_builder import create_workflow

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load configuration
try:
    config = AppConfig()
    config.validate()
    logger.info(f"Configuration loaded (Federated API: {config.federated_api_url})")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    sys.exit(1)

# Load TMF 645 workflow design
try:
    design_path = Path(__file__).parent / "TMF645_ServiceQual_Design.json"
    with open(design_path, 'r') as f:
        design_json = json.load(f)
    logger.info(f"Loaded design: {design_json.get('name', 'TMF 645 Workflow')}")
except Exception as e:
    logger.error(f"Failed to load design JSON: {e}")
    sys.exit(1)

# Build LangGraph workflow
try:
    workflow = create_workflow(design_json, config)
    logger.info("LangGraph workflow initialized successfully")
except Exception as e:
    logger.error(f"Failed to create workflow: {e}")
    sys.exit(1)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "workflow": "TMF 645 Service Qualification",
        "agents": {
            "validator": "TMF645ValidatorAgent",
            "qualifier": "ServiceQualifierAgent"
        },
        "federated_api": config.federated_api_url
    }), 200


@app.route('/api/ask', methods=['POST'])
@app.route('/ask', methods=['POST'])  # Alias for compatibility
def ask_question():
    """
    Main endpoint for TMF 645 service qualification
    
    Request body:
    {
        "tmf645_request": { ... TMF 645 service qualification request ... },
        "session_id": "optional-session-id"
    }
    
    Response:
    {
        "status": "success" | "rejected" | "error",
        "validation_passed": true | false,
        "service_qualified": true | false,
        "validation_result": { ... },
        "qualification_result": { ... },
        "timestamp": "ISO timestamp"
    }
    """
    try:
        # Parse request
        data = request.get_json()
        
        if not data or 'tmf645_request' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'tmf645_request' field in request body",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        tmf645_request = data['tmf645_request']
        session_id = data.get('session_id', 'default')
        
        logger.info(f"[Session: {session_id}] Received TMF 645 service qualification request")
        
        # Create initial state
        initial_state = WorkflowState(
            messages=[],
            user_input="TMF 645 service qualification request",
            tmf645_request=tmf645_request,
            session_id=session_id
        )
        
        # Execute LangGraph workflow
        logger.info(f"[Session: {session_id}] Executing LangGraph workflow...")
        result = workflow.invoke(initial_state)
        
        logger.info(f"[Session: {session_id}] Workflow completed")
        
        # Extract results
        validation_passed = result.get('validation_passed', False)
        service_qualified = result.get('service_qualified', False)
        validation_result = result.get('validation_result', {})
        qualification_result = result.get('qualification_result', {})
        error = result.get('error')
        
        if error:
            logger.error(f"[Session: {session_id}] Workflow error: {error}")
            return jsonify({
                "status": "error",
                "message": error,
                "timestamp": datetime.now().isoformat()
            }), 500
        
        # Determine status
        if not validation_passed:
            status = "rejected"
        elif service_qualified:
            status = "success"
        else:
            status = "not_qualified"
        
        return jsonify({
            "status": status,
            "validation_passed": validation_passed,
            "service_qualified": service_qualified,
            "validation_result": validation_result,
            "qualification_result": qualification_result,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/api/provision', methods=['POST'])
def provision_slice():
    """
    Endpoint for provisioning a qualified network slice via MCP server
    
    Request body:
    {
        "relatedParty": {"id": "ElBorn", "name": "...", "role": "customer"},
        "serviceSpecification": {"id": "...", "name": "..."},
        "serviceCharacteristic": [{"name": "...", "value": "..."}],
        "session_id": "optional-session-id"
    }
    
    Response:
    {
        "status": "success" | "error",
        "provisioning_result": { ... },
        "timestamp": "ISO timestamp"
    }
    """
    try:
        import asyncio
        from src.mcp_http_client import MCPHttpClient
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Missing request body",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        session_id = data.get('session_id', 'default')
        logger.info(f"[Session: {session_id}] Received provisioning request")
        
        # Extract required fields
        related_party = data.get('relatedParty', {})
        service_spec = data.get('serviceSpecification', {})
        service_chars = data.get('serviceCharacteristic', [])
        
        if not related_party or not service_spec:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: relatedParty and serviceSpecification",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Call MCP server to provision slice
        mcp_url = getattr(config, 'mcp_server_url', 'http://localhost:8094')
        logger.info(f"[Session: {session_id}] Calling MCP server at {mcp_url}")
        
        client = MCPHttpClient(base_url=mcp_url)
        
        # Create async loop and call MCP
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                client.provision_slice(
                    related_party=related_party,
                    service_specification=service_spec,
                    service_characteristics=service_chars
                )
            )
        finally:
            loop.close()
        
        logger.info(f"[Session: {session_id}] Provisioning completed")
        
        return jsonify({
            "status": "success",
            "provisioning_result": result,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing provisioning request: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/api/validate', methods=['POST'])
def validate_question():
    """
    Endpoint for validating TMF 645 requests only (no qualification)
    
    Request body:
    {
        "tmf645_request": { ... TMF 645 service qualification request ... }
    }
    
    Response:
    {
        "status": "valid" | "invalid",
        "validation_result": { ... },
        "timestamp": "ISO timestamp"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'tmf645_request' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'tmf645_request' field in request body",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        tmf645_request = data['tmf645_request']
        
        logger.info("Validating TMF 645 request...")
        
        # Import validator agent directly
        from src.validator_agent import TMF645ValidatorAgent
        
        validator = TMF645ValidatorAgent()
        is_valid, message, details = validator.validate_request(tmf645_request)
        validation_result = validator.validate_and_format_response(is_valid, message, details)
        
        return jsonify({
            "status": "valid" if is_valid else "invalid",
            "validation_result": validation_result,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating request: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API documentation"""
    return jsonify({
        "name": "TMF 645 Service Qualification API with LangGraph",
        "version": "2.0.0",
        "description": "REST API for TMF 645 service qualification using LangGraph multi-agent workflow",
        "workflow": "TMF645Validator → ServiceQualifier → ChatOutput",
        "endpoints": {
            "/health": {
                "method": "GET",
                "description": "Health check endpoint"
            },
            "/api/ask": {
                "method": "POST",
                "description": "Submit TMF 645 service qualification request (full workflow)",
                "request_body": {
                    "tmf645_request": "object (TMF 645 format, required)",
                    "session_id": "string (optional)"
                }
            },
            "/api/validate": {
                "method": "POST",
                "description": "Validate TMF 645 request format only (no qualification)",
                "request_body": {
                    "tmf645_request": "object (TMF 645 format, required)"
                }
            }
        },
        "agents": {
            "TMF645ValidatorAgent": "Validates TMF 645 service qualification request format",
            "ServiceQualifierAgent": "Qualifies service based on network capacity (port 8092)"
        },
        "service_types": ["URLLC", "eMBB", "mMTC"]
    }), 200


if __name__ == '__main__':
    logger.info("Starting TMF 645 Service Qualification API with LangGraph...")
    logger.info(f"Federated API: {config.federated_api_url}")
    logger.info(f"Workflow: TMF645Validator → ServiceQualifier → ChatOutput")
    
    # Print registered routes for debugging
    logger.info("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"  {rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
