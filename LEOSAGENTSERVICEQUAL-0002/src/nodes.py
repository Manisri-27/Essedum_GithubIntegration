# file: src/nodes.py
"""
Workflow Node Implementations

Each function represents a node from the Langflow design JSON.
Nodes receive WorkflowState and AppConfig, execute logic, and return updates as dict.
"""

import logging
from typing import Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.workflow_state import WorkflowState
from src.config import AppConfig
from src.vllm_client import VLLMClient

logger = logging.getLogger(__name__)


def get_model(config: AppConfig, node_params: Optional[dict] = None):
    """
    Get LLM instance based on configuration.
    
    Prioritizes vLLM if configured, then Azure OpenAI, then falls back to OpenAI.
    Applies node-specific parameters or config defaults.
    
    Args:
        config: Application configuration
        node_params: Optional node-specific parameters (temperature, model_name, etc.)
        
    Returns:
        LLM instance (VLLMClient, AzureChatOpenAI, or ChatOpenAI)
    """
    params = node_params or {}
    
    temperature = params.get("temperature", config.temperature)
    max_tokens = params.get("max_tokens", config.max_tokens)
    timeout = params.get("timeout", config.timeout_seconds)
    
    # Use vLLM if configured
    if config.is_vllm():
        logger.info(f"Using vLLM with model: {config.vllm_model_name}")
        
        return VLLMClient(
            url=config.vllm_url,
            model_name=config.vllm_model_name,
            temperature=temperature,
            max_tokens=max_tokens or 500,
            timeout=timeout,
        )
    # Use Azure OpenAI if configured
    elif config.is_azure():
        model_name = params.get("model_name", config.model_name)
        logger.info(f"Using Azure OpenAI with deployment: {config.azure_openai_deployment}")
        
        try:
            return AzureChatOpenAI(
                azure_endpoint=config.azure_openai_endpoint,
                azure_deployment=config.azure_openai_deployment,
                api_version=config.azure_api_version,
                api_key=config.azure_openai_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception as e:
            logger.error(f"Error initializing Azure OpenAI: {e}")
            raise ValueError(f"Azure OpenAI initialization failed: {e}")
    # Fall back to OpenAI
    elif config.is_openai():
        model_name = params.get("model_name", config.model_name)
        logger.info(f"Using OpenAI with model: {model_name}")
        
        try:
            return ChatOpenAI(
                model=model_name,
                api_key=config.openai_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception as e:
            logger.error(f"Error initializing OpenAI: {e}")
            raise ValueError(f"OpenAI initialization failed: {e}")
    else:
        logger.error("No LLM provider configured")
        raise ValueError("No LLM provider configured. Set USE_VLLM=true or configure Azure OpenAI/OpenAI credentials.")


def node_chatinput_vip4f(state: WorkflowState, config: AppConfig) -> dict:
    """
    ChatInput node: Captures user input and adds to message history.
    
    Node ID: ChatInput-viP4f
    Type: ChatInput
    """
    try:
        logger.info("Processing ChatInput node")
        
        # Get the latest user input from messages
        user_input = ""
        if state.messages:
            last_msg = state.messages[-1]
            if isinstance(last_msg, dict):
                user_input = last_msg.get("content", "")
            else:
                user_input = str(last_msg)
        
        logger.info(f"User input captured: {user_input[:100]}...")
        
        return {
            "user_input": user_input
        }
        
    except Exception as e:
        logger.error(f"Error in ChatInput node: {e}")
        return {"error": f"ChatInput failed: {str(e)}"}


def node_prompt_template_t2vsf(state: WorkflowState, config: AppConfig) -> dict:
    """
    Prompt Template node: Formats the system prompt with user input.
    
    Node ID: Prompt Template-t2VSF
    Type: Prompt Template
    """
    try:
        logger.info("Processing Prompt Template node")
        
        # Extract template from JSON design
        template = """You are an intelligent Multi-Purpose Agent that handles both General AI questions and Database queries.

**User Query:** {text}

**ANALYZE REQUEST TYPE:**

**SCENARIO 1: GENERAL AI QUESTIONS**
If the query is about general knowledge, explanations, concepts, or non-database topics:
- Respond naturally as a helpful AI assistant
- Do NOT use database tools
- Provide informative, conversational answers

Examples: "What is machine learning?", "Help me write an email", "Explain artificial intelligence"

**SCENARIO 2: DIRECT SQL QUERIES**
If the user provides a complete SQL statement (starts with SELECT, INSERT, UPDATE, DELETE):
- Execute the SQL immediately using mysql_query()
- Return the actual database results
- Show both query and results

**SCENARIO 3: NATURAL LANGUAGE DATABASE QUERIES**
If the query asks for data/information that requires database lookup:
- First use get_tables() to see available tables
- Use describe_table() for relevant tables to understand structure
- Build appropriate SQL query using actual column names
- Execute with mysql_query() and return results

**CRITICAL RULES:**
1. ALWAYS execute mysql_query() for database requests - return real data
2. ALWAYS show the complete response from mysql_query() tool
3. Use get_tables() and describe_table() for natural language queries
4. Never just show query JSON format - always execute and show results
5. For general questions, respond normally without database tools
"""
        
        # Safe formatting - substitute missing keys with empty string
        user_input = state.user_input or ""
        safe_vars = {"text": user_input}
        
        try:
            formatted_prompt = template.format(**safe_vars)
        except KeyError as ke:
            logger.warning(f"Missing template variable: {ke}, using partial format")
            formatted_prompt = template.replace("{text}", user_input)
        
        logger.info("Prompt template formatted successfully")
        
        return {
            "formatted_prompt": formatted_prompt
        }
        
    except Exception as e:
        logger.error(f"Error in Prompt Template node: {e}")
        return {"error": f"Prompt Template failed: {str(e)}"}


def node_mcp_ufeql(state: WorkflowState, config: AppConfig) -> dict:
    """
    MCP Tools node: Placeholder for MCP (Model Context Protocol) tools.
    
    Node ID: MCP-ufEql
    Type: MCP
    
    Phase-1: Returns stub tools list. Real MCP integration requires external server.
    """
    try:
        logger.info("Processing MCP Tools node")
        logger.warning("MCP tools not fully implemented in phase-1; returning stub")
        
        # Stub tools for phase-1
        # In production, this would connect to MCP server and fetch real tools
        mcp_tools = []
        
        return {
            "mcp_tools": mcp_tools
        }
        
    except Exception as e:
        logger.error(f"Error in MCP node: {e}")
        return {"error": f"MCP node failed: {str(e)}"}


def node_azureopenaimodel_6aodl(state: WorkflowState, config: AppConfig) -> dict:
    """
    Azure OpenAI Model node: Invokes LLM with formatted prompt.
    
    Node ID: AzureOpenAIModel-6aodL
    Type: AzureOpenAIModel
    """
    try:
        logger.info("Processing Azure OpenAI Model node")
        
        # Get node-specific parameters from design JSON
        node_params = {
            "temperature": 0.7,
            "max_tokens": None,
        }
        
        llm = get_model(config, node_params)
        
        # Build messages for LLM
        messages = []
        
        # Use formatted prompt if available
        if state.formatted_prompt:
            messages.append(HumanMessage(content=state.formatted_prompt))
        elif state.user_input:
            messages.append(HumanMessage(content=state.user_input))
        else:
            logger.warning("No input available for LLM")
            return {"model_response": "No input provided"}
        
        # Invoke LLM
        logger.info("Invoking LLM...")
        response = llm.invoke(messages)
        
        # Extract text from response
        if hasattr(response, "content"):
            model_response = response.content
        else:
            model_response = str(response)
        
        logger.info(f"LLM response received: {model_response[:100]}...")
        
        return {
            "model_response": model_response
        }
        
    except Exception as e:
        logger.error(f"Error in LLM Model node: {e}")
        return {"error": f"LLM Model failed: {str(e)}"}


def node_agent_zgq5d(state: WorkflowState, config: AppConfig) -> dict:
    """
    Agent node: Executes agentic workflow with tools.
    
    Node ID: Agent-Zgq5D
    Type: Agent
    
    Uses create_react_agent if tools are available, otherwise direct LLM invocation.
    """
    try:
        logger.info("Processing Agent node")
        
        # Get LLM instance
        node_params = {
            "temperature": 0.7,
        }
        llm = get_model(config, node_params)
        
        # Prepare tools list
        tools = state.mcp_tools or []
        
        # Build input message
        user_input = state.user_input or ""
        
        # If tools exist, use react agent; otherwise direct invocation
        if tools:
            logger.info(f"Creating agent with {len(tools)} tools")
            
            # System message from formatted prompt
            system_message = state.formatted_prompt or "You are a helpful AI assistant."
            
            try:
                agent = create_react_agent(llm, tools, state_modifier=system_message)
                
                # Run agent
                result = agent.invoke({"messages": [HumanMessage(content=user_input)]})
                
                # Extract response
                if "messages" in result and result["messages"]:
                    last_message = result["messages"][-1]
                    agent_response = last_message.content if hasattr(last_message, "content") else str(last_message)
                else:
                    agent_response = str(result)
                    
            except Exception as agent_error:
                logger.warning(f"Agent execution failed, falling back to direct LLM: {agent_error}")
                # Fallback to direct LLM
                messages = [
                    SystemMessage(content=state.formatted_prompt or "You are a helpful assistant."),
                    HumanMessage(content=user_input)
                ]
                response = llm.invoke(messages)
                agent_response = response.content if hasattr(response, "content") else str(response)
        else:
            logger.info("No tools available; using direct LLM invocation")
            
            # Direct LLM invocation without tools
            messages = []
            if state.formatted_prompt:
                messages.append(SystemMessage(content=state.formatted_prompt))
            messages.append(HumanMessage(content=user_input))
            
            response = llm.invoke(messages)
            agent_response = response.content if hasattr(response, "content") else str(response)
        
        logger.info(f"Agent response: {agent_response[:100]}...")
        
        return {
            "agent_response": agent_response
        }
        
    except Exception as e:
        logger.error(f"Error in Agent node: {e}")
        return {"error": f"Agent failed: {str(e)}"}


def node_chatoutput_avpjo(state: WorkflowState, config: AppConfig) -> dict:
    """
    Chat Output node: Formats final output for display.
    
    Node ID: ChatOutput-AVpjO
    Type: ChatOutput
    """
    try:
        logger.info("Processing Chat Output node")
        
        # Get final output from agent or model
        final_output = state.agent_response or state.model_response or "No response generated"
        
        logger.info("Chat output prepared")
        
        return {
            "final_output": final_output
        }
        
    except Exception as e:
        logger.error(f"Error in Chat Output node: {e}")
        return {"error": f"Chat Output failed: {str(e)}"}


def node_tmf645_validator(state: WorkflowState, config: AppConfig) -> dict:
    """
    TMF 645 Validator node: Validates service qualification request format.
    
    Node Type: TMF645Validator
    """
    try:
        logger.info("Processing TMF 645 Validator node")
        
        from src.validator_agent import TMF645ValidatorAgent
        
        validator = TMF645ValidatorAgent()
        
        # Get TMF 645 request from state
        tmf645_request = state.tmf645_request
        
        if not tmf645_request:
            logger.error("No TMF 645 request found in state")
            return {
                "validation_passed": False,
                "validation_result": {
                    "validation_status": "failed",
                    "message": "No TMF 645 request provided",
                    "is_valid": False
                },
                "error": "No TMF 645 request provided"
            }
        
        # Validate the request
        is_valid, message, details = validator.validate_request(tmf645_request)
        
        validation_result = validator.validate_and_format_response(is_valid, message, details)
        
        logger.info(f"Validation result: {'PASSED' if is_valid else 'FAILED'}")
        
        return {
            "validation_passed": is_valid,
            "validation_result": validation_result
        }
        
    except Exception as e:
        logger.error(f"Error in TMF 645 Validator node: {e}")
        return {
            "validation_passed": False,
            "validation_result": {
                "validation_status": "error",
                "message": f"Validator error: {str(e)}",
                "is_valid": False
            },
            "error": f"TMF 645 Validator failed: {str(e)}"
        }


def node_service_qualifier(state: WorkflowState, config: AppConfig) -> dict:
    """
    Service Qualifier node: Analyzes user request and calls appropriate MCP tool.
    Supports both service qualification and provisioning via MCP server.
    
    Node Type: ServiceQualifier with MCP Tool Selection
    """
    try:
        logger.info("Processing Service Qualifier with MCP tool selection")
        
        # Check if validation passed
        if not state.validation_passed:
            logger.warning("Skipping qualification - validation failed")
            return {
                "service_qualified": False,
                "qualification_result": {
                    "qualification_status": "skipped",
                    "message": "Qualification skipped due to validation failure",
                    "is_qualified": False
                }
            }
        
        # Get configuration
        mcp_server_url = getattr(config, 'mcp_server_url', 'http://localhost:8094')
        use_mcp = getattr(config, 'use_mcp', True)
        
        if not use_mcp:
            logger.warning("MCP is disabled, falling back to direct API")
            # Fallback to old method
            from src.qualifier_agent import ServiceQualifierAgent
            federated_api_url = getattr(config, 'federated_api_url', 'http://localhost:8092')
            qualifier = ServiceQualifierAgent(
                federated_api_url=federated_api_url,
                mcp_server_url=mcp_server_url,
                use_mcp=False
            )
            tmf645_request = state.tmf645_request
            is_qualified, message, details = qualifier.qualify_service(tmf645_request)
            qualification_result = qualifier.format_qualification_response(
                is_qualified, message, details, tmf645_request
            )
            return {
                "service_qualified": is_qualified,
                "qualification_result": qualification_result
            }
        
        # Use MCP with intelligent tool selection
        logger.info(f"Using MCP server at {mcp_server_url}")
        
        import asyncio
        from src.mcp_http_client import MCPHttpClient
        
        # Initialize MCP client
        mcp_client = MCPHttpClient(base_url=mcp_server_url)
        
        # Get user input and TMF 645 request
        user_input = state.user_input or ""
        tmf645_request = state.tmf645_request
        
        # Analyze user intent to determine which tool to call
        intent = _analyze_intent(user_input, tmf645_request)
        logger.info(f"Detected intent: {intent}")
        
        # Execute appropriate MCP tool based on intent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if intent == "provision":
                # Call provision_slice tool
                result = loop.run_until_complete(_call_provision_tool(mcp_client, tmf645_request))
                qualification_result = {
                    "qualification_status": "provisioned",
                    "message": "Service provisioning completed",
                    "mcp_response": result.get('content', ''),
                    "tool_used": "provision_slice"
                }
                return {
                    "service_qualified": True,
                    "qualification_result": qualification_result
                }
            else:
                # Call check_service_qualification tool (default)
                result = loop.run_until_complete(_call_qualification_tool(mcp_client, tmf645_request))
                
                # Parse MCP response to determine if qualified
                content = result.get('content', '')
                is_qualified = 'QUALIFIED' in content and 'UNQUALIFIED' not in content
                
                qualification_result = {
                    "qualification_status": "done" if is_qualified else "terminatedWithError",
                    "message": "Service qualified via MCP" if is_qualified else "Service not qualified",
                    "is_qualified": is_qualified,
                    "mcp_response": content,
                    "tool_used": "check_service_qualification"
                }
                
                return {
                    "service_qualified": is_qualified,
                    "qualification_result": qualification_result
                }
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error in Service Qualifier node: {e}", exc_info=True)
        return {
            "service_qualified": False,
            "qualification_result": {
                "qualification_status": "error",
                "message": f"Qualifier error: {str(e)}",
                "is_qualified": False
            },
            "error": f"Service Qualifier failed: {str(e)}"
        }


def _analyze_intent(user_input: str, tmf645_request: dict) -> str:
    """
    Analyze user intent to determine which MCP tool to call.
    
    Args:
        user_input: User's original input
        tmf645_request: Validated TMF 645 request
        
    Returns:
        'provision' or 'qualify'
    """
    # Check for provisioning keywords
    provision_keywords = [
        'provision', 'create', 'deploy', 'allocate', 'setup',
        'establish', 'activate', 'implement', 'install'
    ]
    
    # Check for qualification keywords  
    qualify_keywords = [
        'check', 'qualify', 'validate', 'assess', 'evaluate',
        'verify', 'can i', 'is it possible', 'feasible'
    ]
    
    user_lower = user_input.lower()
    
    # Check TMF 645 request action if present
    items = tmf645_request.get('serviceQualificationItem', [])
    if items:
        action = items[0].get('action', '').lower()
        if action in ['add', 'modify']:
            # Check if this is an add/modify with intent to provision
            if any(keyword in user_lower for keyword in provision_keywords):
                return 'provision'
    
    # Analyze user input
    if any(keyword in user_lower for keyword in provision_keywords):
        return 'provision'
    
    # Default to qualification
    return 'qualify'


async def _call_qualification_tool(mcp_client, tmf645_request: dict) -> dict:
    """Call check_service_qualification MCP tool"""
    from datetime import datetime, timedelta
    
    # Extract party info
    related_parties = tmf645_request.get('relatedParty', [])
    if related_parties:
        related_party = related_parties[0]
    else:
        related_party = {'id': 'ElBorn', 'name': 'Default Client', 'role': 'customer'}
    
    # Extract service qualification items (contains bandwidth/latency requirements)
    service_qual_items = tmf645_request.get('serviceQualificationItem', [])
    
    # Generate time-series network metrics (11 points)
    base_time = datetime.now()
    metrics_timeseries = []
    for i in range(11):
        ts = base_time - timedelta(minutes=10-i)
        metrics_timeseries.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "down": 120.0 + (i * 0.5),
            "up": 60.0 + (i * 0.3),
            "rnti_count": 150.0 + i,
            "mcs_down": 15.0 + (i * 0.1),
            "mcs_down_var": 2.3,
            "mcs_up": 12.8 + (i * 0.05),
            "mcs_up_var": 1.9,
            "rb_down": 85.0 + (i * 0.2),
            "rb_down_var": 10.5,
            "rb_up": 45.0 + (i * 0.1),
            "rb_up_var": 5.2
        })
    
    return await mcp_client.check_service_qualification(
        related_party=related_party,
        network_metrics=metrics_timeseries,
        risk_threshold=0.5,
        service_qualification_items=service_qual_items  # Forward service requirements to MCP
    )


async def _call_provision_tool(mcp_client, tmf645_request: dict) -> dict:
    """Call provision_slice MCP tool"""
    
    # Extract party info
    related_parties = tmf645_request.get('relatedParty', [])
    if related_parties:
        related_party = related_parties[0]
    else:
        related_party = {'id': 'ElBorn', 'name': 'Default Client', 'role': 'customer'}
    
    # Extract service specification and characteristics
    items = tmf645_request.get('serviceQualificationItem', [])
    if items:
        service = items[0].get('service', {})
        service_spec = service.get('serviceSpecification', {})
        service_chars = service.get('serviceCharacteristic', [])
    else:
        service_spec = {'id': 'default', 'name': '5G Network Slice'}
        service_chars = []
    
    return await mcp_client.provision_slice(
        related_party=related_party,
        service_specification=service_spec,
        service_characteristics=service_chars
    )
