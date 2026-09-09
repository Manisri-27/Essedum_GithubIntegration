"""
MCP Server for TMF 645 Service Qualification API
Implements TM Forum Service Qualification with AI Risk Assessment
Integrates with LEOSAGENTSERVICEQUAL-0001 agent for intelligent network slice management
"""

import asyncio
import json
import logging
from typing import Any, Dict, List
from datetime import datetime
import uuid
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


API_TIMEOUT = 30.0
MCP_SERVER_PORT = 5000  # MCP Server HTTP port

app = Server("tmf645-servicequal-agent")


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """
    TMF 645 Service Qualification API Tools:
    - check_service_qualification - Validate if service can be provisioned (TMF 645 checkServiceQualification)
    - create_service_qualification - Create service qualification request (TMF 645 createServiceQualification)
    """
    return [
        Tool(
            name="check_service_qualification",
            description="TMF 645: Check service qualification by assessing network congestion risk using Essedum AI model. Validates if requested service can be delivered at specified location with required characteristics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relatedParty": {
                        "type": "object",
                        "description": "TMF 645: Party requesting the service qualification",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier (ElBorn, LesCorts, or PobleSec)",
                                "enum": ["ElBorn", "LesCorts", "PobleSec"]
                            },
                            "name": {"type": "string", "description": "Party name"},
                            "role": {"type": "string", "description": "Party role (e.g., customer)", "default": "customer"}
                        },
                        "required": ["id"]
                    },
                    "serviceQualificationItem": {
                        "type": "object",
                        "description": "TMF 645: Service qualification item details",
                        "properties": {
                            "id": {"type": "string", "description": "Item identifier"},
                            "service": {
                                "type": "object",
                                "description": "Service specification",
                                "properties": {
                                    "serviceSpecification": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string", "description": "Service spec ID"},
                                            "name": {"type": "string", "description": "Service name"}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "network_metrics": {
                        "oneOf": [
                            {
                                "type": "object",
                                "description": "Single time-point network metrics",
                                "properties": {
                                    "timestamp": {"type": "string", "description": "Timestamp of measurements"},
                                    "down": {"type": "number", "description": "Downlink throughput"},
                                    "up": {"type": "number", "description": "Uplink throughput"},
                                    "rnti_count": {"type": "number", "description": "Number of active connections"},
                                    "mcs_down": {"type": "number", "description": "Downlink MCS"},
                                    "mcs_down_var": {"type": "number", "description": "Downlink MCS variance"},
                                    "mcs_up": {"type": "number", "description": "Uplink MCS"},
                                    "mcs_up_var": {"type": "number", "description": "Uplink MCS variance"},
                                    "rb_down": {"type": "number", "description": "Downlink resource blocks"},
                                    "rb_down_var": {"type": "number", "description": "Downlink RB variance"},
                                    "rb_up": {"type": "number", "description": "Uplink resource blocks"},
                                    "rb_up_var": {"type": "number", "description": "Uplink RB variance"}
                                },
                                "required": ["down", "up", "rnti_count", "mcs_down", "mcs_up", "rb_down", "rb_up"]
                            },
                            {
                                "type": "array",
                                "description": "Time-series of network metrics (11+ points for batch prediction)",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "timestamp": {"type": "string"},
                                        "down": {"type": "number"},
                                        "up": {"type": "number"},
                                        "rnti_count": {"type": "number"},
                                        "mcs_down": {"type": "number"},
                                        "mcs_down_var": {"type": "number"},
                                        "mcs_up": {"type": "number"},
                                        "mcs_up_var": {"type": "number"},
                                        "rb_down": {"type": "number"},
                                        "rb_down_var": {"type": "number"},
                                        "rb_up": {"type": "number"},
                                        "rb_up_var": {"type": "number"}
                                    }
                                }
                            }
                        ]
                    },
                    "risk_threshold": {
                        "type": "number",
                        "description": "Risk threshold for determining if network can handle new slice (0-1, default: 0.5)",
                        "default": 0.5
                    }
                },
                "required": ["relatedParty", "network_metrics"]
            }
        ),
        Tool(
            name="provision_slice",
            description="TMF 645: Provision a qualified network slice by calling the orchestrator API. Should only be called after check_service_qualification confirms the service is qualified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relatedParty": {
                        "type": "object",
                        "description": "TMF 645: Party requesting service qualification",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Network client/district (ElBorn, LesCorts, PobleSec)",
                                "enum": ["ElBorn", "LesCorts", "PobleSec"]
                            },
                            "name": {"type": "string"},
                            "role": {"type": "string", "default": "customer"}
                        },
                        "required": ["id"]
                    },
                    "serviceCharacteristic": {
                        "type": "array",
                        "description": "TMF 645: Service characteristics for network slice",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"}
                            }
                        }
                    },
                    "service": {
                        "type": "object",
                        "description": "TMF 645: Service specification details",
                        "properties": {
                            "serviceSpecification": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string", "description": "Network slice type", "enum": ["eMBB", "URLLC", "mMTC"]}
                                }
                            },
                            "serviceCharacteristic": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "bandwidth_mbps, latency_ms, or priority"},
                                        "value": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "qualificationResult": {
                        "type": "string",
                        "description": "TMF 645: Expected qualification result from check",
                        "enum": ["qualified", "unqualified"]
                    }
                },
                "required": ["relatedParty", "service"]
            }
        )
    ]

# API Configuration
API_BASE_URL = "http://192.168.14.103:8092"  # Remote prediction API
ORCHESTRATOR_URL = "http://localhost:8042"  # Network orchestrator endpoint (TMF 645 compliant)

@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """
    TMF 645 Service Qualification Tool Handler:
    - check_service_qualification: Validate service feasibility with AI risk assessment
    - provision_slice: Provision qualified network slices via orchestrator API
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:

            if name == "check_service_qualification":
                # TMF 645: checkServiceQualification - Assess with AI model
                # Log all arguments for debugging
                logger.info(f"MCP Tool Arguments: {json.dumps(arguments, indent=2, default=str)}")
                
                related_party = arguments["relatedParty"]
                client_id = related_party["id"]
                network_metrics = arguments["network_metrics"]
                risk_threshold = arguments.get("risk_threshold", 0.5)
                
                # Extract requested bandwidth from service qualification item (if provided)
                requested_bandwidth_mbps = 0
                num_slices = 0
                
                # Check multiple possible locations for service qualification items
                service_qual_item = arguments.get("serviceQualificationItem")
                if not service_qual_item:
                    service_qual_item = arguments.get("service_qualification_item")
                if not service_qual_item:
                    service_qual_item = arguments.get("service")
                
                # Also check if bandwidth is directly in arguments
                if not service_qual_item and "requested_bandwidth_mbps" in arguments:
                    requested_bandwidth_mbps = arguments["requested_bandwidth_mbps"]
                
                # Handle both single item (dict) and multiple items (list)
                if service_qual_item:
                    items_to_check = []
                    if isinstance(service_qual_item, list):
                        items_to_check = service_qual_item
                    elif isinstance(service_qual_item, dict):
                        items_to_check = [service_qual_item]
                    
                    # Sum bandwidth from all service qualification items
                    for item in items_to_check:
                        num_slices += 1
                        service = item.get("service", {})
                        service_chars = service.get("serviceCharacteristic", [])
                        for char in service_chars:
                            if char.get("name") in ["bandwidth", "bandwidth_mbps"]:
                                # Parse bandwidth value (e.g., "100 Mbps", "30 Gbps")
                                value_str = str(char.get("value", ""))
                                try:
                                    if "Gbps" in value_str or "gbps" in value_str:
                                        requested_bandwidth_mbps += float(value_str.split()[0]) * 1000
                                    elif "Mbps" in value_str or "mbps" in value_str:
                                        requested_bandwidth_mbps += float(value_str.split()[0])
                                    else:
                                        # Try parsing as plain number (assume Mbps)
                                        requested_bandwidth_mbps += float(value_str)
                                except:
                                    pass
                
                logger.info(f"Extracted requested bandwidth: {requested_bandwidth_mbps} Mbps from {num_slices} slices")

                # Determine if single metric or array
                if isinstance(network_metrics, list):
                    # Time-series data
                    features_list = network_metrics
                    is_batch = True
                else:
                    # Single time-point
                    features_list = [network_metrics]
                    is_batch = False

                # Prepare payload for prediction API
                payload = {
                    "client_id": client_id,
                    "features": features_list
                }

                # Call the remote prediction API on port 8092
                response = await client.post(f"{API_BASE_URL}/predict", json=payload)
                result = response.json()

                if response.status_code == 200:
                    # Parse predictions and calculate risk assessment
                    predictions = result.get('predictions', [])

                    if predictions:
                        # Calculate overall risk from all predictions
                        all_risk_scores = []

                        formatted = f"Network Congestion Risk Assessment\n\n"
                        formatted += f"Client: {client_id}\n"
                        formatted += f"Data Points: {len(predictions)}\n"
                        formatted += f"Type: {'Time-series batch' if is_batch else 'Single point'}\n"
                        if requested_bandwidth_mbps > 0:
                            formatted += f"Number of Slices: {num_slices}\n"
                            formatted += f"Total Requested Bandwidth: {requested_bandwidth_mbps:.0f} Mbps ({requested_bandwidth_mbps/1000:.1f} Gbps)\n"
                        formatted += f"\n"

                        # Process each prediction
                        for idx, pred in enumerate(predictions):
                            pred_values = pred.get('predictions', {})

                            if pred_values:
                                # Calculate risk for this sample
                                # Network metrics have different scales:
                                # - Throughput (down/up): billions (bps)
                                # - Resource blocks (rb_down/rb_up): 0-100 range
                                # - RNTI count: thousands to millions
                                
                                # Extract key metrics for risk assessment
                                downlink = pred_values.get('down', 0)
                                uplink = pred_values.get('up', 0)
                                rb_down = pred_values.get('rb_down', 0)
                                rb_up = pred_values.get('rb_up', 0)
                                
                                # Convert throughput to Mbps (assuming values are in bps)
                                downlink_mbps = downlink / 1_000_000 if downlink > 1000 else downlink
                                uplink_mbps = uplink / 1_000_000 if uplink > 1000 else uplink
                                
                                # Calculate capacity score (0-1, higher is better)
                                # Good network: >20 Gbps down, >10 Gbps up, >60 RB (stricter baseline for better detection)
                                downlink_score = min(downlink_mbps / 20000, 1.0)  # Normalize to 20 Gbps baseline
                                uplink_score = min(uplink_mbps / 10000, 1.0)      # Normalize to 10 Gbps baseline
                                rb_score = min((rb_down + rb_up) / 120, 1.0)      # RB utilization (stricter: 60+60)
                                
                                # Overall capacity (weighted average)
                                capacity_score = (downlink_score * 0.5 + uplink_score * 0.3 + rb_score * 0.2)
                                
                                # Check if requested bandwidth exceeds available capacity
                                if requested_bandwidth_mbps > 0:
                                    # Calculate utilization ratio (requested / available)
                                    utilization_ratio = requested_bandwidth_mbps / max(downlink_mbps, 1)
                                    
                                    # If requesting more than available, service MUST fail
                                    if utilization_ratio > 1.0:
                                        # Oversubscribed - CRITICAL: Set risk to maximum to ensure failure
                                        # Even 1% oversubscription should fail qualification
                                        capacity_score = 0.0  # Force maximum risk
                                    elif utilization_ratio > 0.9:
                                        # Very high utilization (>90%) - high risk
                                        capacity_penalty = (utilization_ratio - 0.9) * 5.0  # Aggressive penalty
                                        capacity_score = capacity_score * max(1 - capacity_penalty, 0.0)
                                    elif utilization_ratio > 0.7:
                                        # High utilization (>70%) - moderate risk increase
                                        capacity_penalty = (utilization_ratio - 0.7) * 0.5
                                        capacity_score = capacity_score * (1 - capacity_penalty)
                                
                                # Risk is inverse of capacity (low capacity = high risk)
                                risk_score = 1 - capacity_score
                                all_risk_scores.append(risk_score)

                                if is_batch and len(predictions) > 3:
                                    # For batch, show summary
                                    if idx == 0:
                                        formatted += f"Sample Predictions:\n"
                                        formatted += f"  Sample {pred.get('sample_index', idx)}: Risk {risk_score:.2%}\n"
                                    elif idx < 3:
                                        formatted += f"  Sample {pred.get('sample_index', idx)}: Risk {risk_score:.2%}\n"
                                    elif idx == len(predictions) - 1:
                                        formatted += f"  ... ({len(predictions) - 3} more samples)\n"
                                        formatted += f"  Sample {pred.get('sample_index', idx)}: Risk {risk_score:.2%}\n"
                                else:
                                    # For single or few samples, show details
                                    formatted += f"\nSample {pred.get('sample_index', idx)} Predictions:\n"
                                    for key, val in pred_values.items():
                                        formatted += f"  • {key}: {val:.2f}\n"
                                    if requested_bandwidth_mbps > 0:
                                        formatted += f"  • Available Downlink: {downlink_mbps:.0f} Mbps ({downlink_mbps/1000:.1f} Gbps)\n"
                                        formatted += f"  • Requested: {requested_bandwidth_mbps:.0f} Mbps ({requested_bandwidth_mbps/1000:.1f} Gbps)\n"
                                        utilization = (requested_bandwidth_mbps / max(downlink_mbps, 1)) * 100
                                        formatted += f"  • Utilization: {utilization:.1f}%\n"

                        # Calculate overall risk
                        if all_risk_scores:
                            overall_risk = sum(all_risk_scores) / len(all_risk_scores)
                            max_risk = max(all_risk_scores)
                            min_risk = min(all_risk_scores)

                            risk_level = "LOW" if overall_risk < risk_threshold else "HIGH"
                            qualification_state = "done" if overall_risk < risk_threshold else "terminatedWithError"
                            qualification_result = "qualified" if overall_risk < risk_threshold else "unqualified"

                            formatted += f"\nOverall Risk Assessment:\n"
                            formatted += f"  • Average Risk: {overall_risk:.2%}\n"
                            if is_batch:
                                formatted += f"  • Min Risk: {min_risk:.2%}\n"
                                formatted += f"  • Max Risk: {max_risk:.2%}\n"
                            formatted += f"  • Risk Level: {risk_level}\n"
                            formatted += f"  • Threshold: {risk_threshold:.2%}\n"

                            # TMF 645 Service Qualification Response
                            qualification_id = f"sq-{uuid.uuid4().hex[:12]}"
                            formatted += f"\n--- TMF 645 Service Qualification Response ---\n"
                            formatted += f"serviceQualification:\n"
                            formatted += f"  • id: {qualification_id}\n"
                            formatted += f"  • state: {qualification_state}\n"
                            formatted += f"  • qualificationResult: {qualification_result}\n"
                            formatted += f"  • effectiveQualificationDate: {datetime.now().isoformat()}\n"
                            formatted += f"  • relatedParty.id: {client_id}\n"

                            formatted += f"\nRecommendation: "
                            if overall_risk < risk_threshold:
                                formatted += "Service QUALIFIED - Safe to provision network slice"
                            else:
                                # Check if failure is due to capacity oversubscription
                                if requested_bandwidth_mbps > 0 and any(
                                    requested_bandwidth_mbps > (pred.get('predictions', {}).get('down', 0) / 1_000_000 if pred.get('predictions', {}).get('down', 0) > 1000 else pred.get('predictions', {}).get('down', 0))
                                    for pred in predictions
                                ):
                                    formatted += "Service UNQUALIFIED - Requested bandwidth EXCEEDS available network capacity"
                                else:
                                    formatted += "Service UNQUALIFIED - Network congestion risk is HIGH"

                        return [TextContent(type="text", text=formatted)]
                    else:
                        return [TextContent(type="text", text="WARNING: No predictions returned from model")]
                else:
                    return [TextContent(type="text", text=f"ERROR: Prediction API error: {json.dumps(result, indent=2)}")]

            elif name == "provision_slice":
                # TMF 645: Provision qualified network slice via orchestrator API
                related_party = arguments["relatedParty"]
                client_id = related_party["id"]
                
                # Get service specification and characteristics directly from arguments
                service_spec = arguments.get("serviceSpecification", {})
                service_chars = arguments.get("serviceCharacteristic", [])

                # Extract characteristics
                char_dict = {char["name"]: char["value"] for char in service_chars}
                
                # TMF 645 Service Qualification Request
                qualification_id = f"sq-{uuid.uuid4().hex[:12]}"
                
                # Prepare orchestrator payload (TMF 645 compliant)
                orchestrator_payload = {
                    "qualificationId": qualification_id,
                    "relatedParty": related_party,
                    "serviceSpecification": service_spec,
                    "serviceCharacteristic": service_chars
                }

                formatted = f"TMF 645 Network Slice Provisioning\n\n"
                formatted += f"Qualification ID: {qualification_id}\n"
                formatted += f"Client: {client_id}\n"
                formatted += f"Service: {service_spec.get('name', 'N/A')}\n"
                formatted += f"Characteristics:\n"
                for name, value in char_dict.items():
                    formatted += f"  • {name}: {value}\n"
                formatted += f"\n"

                try:
                    # Call orchestrator to provision slice
                    response = await client.post(
                        f"{ORCHESTRATOR_URL}/provision",
                        json=orchestrator_payload,
                        timeout=10.0
                    )

                    if response.status_code == 200:
                        result = response.json()
                        formatted += f"✓ Provisioning Successful\n"
                        formatted += f"Status: {result.get('status', 'provisioned')}\n"
                        if result.get('slice_id'):
                            formatted += f"Slice ID: {result.get('slice_id')}\n"
                        formatted += f"\nNetwork slice has been provisioned."
                    else:
                        result = response.json()
                        formatted += f"✗ Provisioning Failed\n"
                        formatted += f"Error: {result.get('error', 'Unknown error')}\n"

                except httpx.ConnectError:
                    # Orchestrator not available
                    formatted += f"⚠ Orchestrator Unavailable\n"
                    formatted += f"Endpoint: {ORCHESTRATOR_URL}/provision\n"
                    formatted += f"\nSimulated qualification (for testing):\n"
                    formatted += f"   • Slice configuration validated\n"
                    formatted += f"   • Resources allocated for {client_id}\n"
                    formatted += f"   • Service type: {service_spec.get('name', 'N/A')}\n"
                    formatted += f"\nNote: Start orchestrator API to enable actual provisioning\n"
                except Exception as e:
                    formatted += f"✗ Error: {str(e)}\n"

                return [TextContent(type="text", text=formatted)]

            else:
                return [TextContent(type="text", text=f"ERROR: Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"ERROR: {str(e)}\n\nStack trace: {type(e).__name__}")]


async def handle_sse(request):
    """
    Handle SSE connection for MCP communication.
    """
    from starlette.responses import StreamingResponse
    from starlette.requests import Request
    
    async def event_stream():
        """Generate SSE events"""
        # Send initial connection message
        yield f"event: endpoint\ndata: /messages\n\n"
        
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield f": keepalive\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

async def handle_messages(request):
    """
    Handle POST messages for MCP JSON-RPC communication.
    """
    try:
        logger.info(f"Received request to /messages endpoint")
        # Parse JSON-RPC request
        json_rpc = await request.json()
        logger.info(f"JSON-RPC request: {json_rpc}")
        method = json_rpc.get("method")
        params = json_rpc.get("params", {})
        req_id = json_rpc.get("id")
        
        # Handle initialize
        if method == "initialize":
            logger.info("Handling initialize request")
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "tmf645-servicequal-agent",
                        "version": "1.0.0"
                    }
                }
            }
            return Response(
                content=json.dumps(response),
                media_type="application/json"
            )
        
        # Handle tools/list
        elif method == "tools/list":
            logger.info("Handling tools/list request")
            tools_list = await handle_list_tools()
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools_list
                    ]
                }
            }
            logger.info(f"Returning {len(tools_list)} tools")
            return Response(
                content=json.dumps(response),
                media_type="application/json"
            )
        
        # Handle tools/call
        elif method == "tools/call":
            logger.info(f"Handling tools/call request for tool: {params.get('name')}")
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Call the tool
            result = await handle_call_tool(tool_name, arguments)
            
            # Convert TextContent objects to dictionaries
            content_list = []
            for item in result:
                if hasattr(item, 'type') and hasattr(item, 'text'):
                    # It's a TextContent object
                    content_list.append({
                        "type": item.type,
                        "text": item.text
                    })
                elif isinstance(item, dict):
                    content_list.append(item)
                else:
                    content_list.append({"type": "text", "text": str(item)})
            
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": content_list
                }
            }
            logger.info("Tool execution completed")
            return Response(
                content=json.dumps(response),
                media_type="application/json"
            )
        
        else:
            # Unknown method
            logger.warning(f"Unknown method: {method}")
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            return Response(
                content=json.dumps(response),
                media_type="application/json",
                status_code=400
            )
            
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        response = {
            "jsonrpc": "2.0",
            "id": req_id if 'req_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        return Response(
            content=json.dumps(response),
            media_type="application/json",
            status_code=500
        )

# Create Starlette app
from starlette.middleware.cors import CORSMiddleware

starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ],
)

# Add CORS middleware
starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def main():
    """
    Main entry point for TMF 645 MCP server with HTTP/SSE transport.
    The server listens for incoming queries via HTTP and responds using MCP SSE protocol.
    """
    config = uvicorn.Config(
        starlette_app,
        host="0.0.0.0",
        port=MCP_SERVER_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    print("="*70)
    print("TMF 645 Service Qualification MCP Server (HTTP/SSE)")
    print("LEOSAGENTSERVICEQUAL-0001 Integration")
    print("="*70)
    print(f"MCP Server: http://0.0.0.0:{MCP_SERVER_PORT}")
    print(f"SSE Endpoint: http://localhost:{MCP_SERVER_PORT}/sse")
    print(f"Prediction API: {API_BASE_URL}")
    print(f"TMF 645 Orchestrator: {ORCHESTRATOR_URL}")
    print("\nAvailable Tools:")
    print("  • check_service_qualification - TMF 645 checkServiceQualification")
    print("  • provision_slice - TMF 645 Provision Network Slice")
    print("\nServer ready and listening for MCP queries via HTTP/SSE...")
    print("="*70 + "\n")
    asyncio.run(main())