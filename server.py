#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import os
import logging
from datetime import datetime, timezone

XDRIP_HOST = os.getenv("XDRIP_HOST", "localhost")
XDRIP_PORT = int(os.getenv("XDRIP_PORT", "17580"))
HTTP_PORT = int(os.getenv("HTTP_PORT", "8007"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def mg_to_mmol(mg_value: float) -> float:
    return round(mg_value * 0.0555, 2)

def get_xdrip_readings(count=20):
    url = f"http://{XDRIP_HOST}:{XDRIP_PORT}/sgv.json?count={count}"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()

def format_direction(direction: str) -> str:
    mapping = {
        "DoubleUp": "Rapidly Rising",
        "SingleUp": "Rising",
        "FortyFiveUp": "Slowly Rising",
        "Flat": "Steady",
        "FortyFiveDown": "Slowly Falling",
        "SingleDown": "Falling",
        "DoubleDown": "Rapidly Falling",
        "NONE": "Unknown",
        "NOT COMPUTABLE": "Unknown",
        "RATE OUT OF RANGE": "Unknown",
    }
    return mapping.get(direction, direction)

def format_time(date_ms: int) -> str:
    dt = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

@app.post("/")
def mcp_endpoint():
    data = request.get_json()
    method = data.get("method")
    req_id = data.get("id")

    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "dexcom-monitor", "version": "2.0.0"}
            }
        })

    elif method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "get_current_glucose",
                        "description": "Get current glucose reading from Dexcom G7 via xDrip+",
                        "inputSchema": {"type": "object", "properties": {}, "required": []}
                    },
                    {
                        "name": "get_glucose_history",
                        "description": "Get glucose history (last N readings)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "count": {
                                    "type": "integer",
                                    "description": "Number of readings to retrieve (default: 12)",
                                    "default": 12
                                }
                            },
                            "required": []
                        }
                    }
                ]
            }
        })

    elif method == "tools/call":
        params = data.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "get_current_glucose":
                readings = get_xdrip_readings(count=1)
                if not readings:
                    return jsonify({
                        "jsonrpc": "2.0", "id": req_id,
                        "error": {"code": -32603, "message": "No readings available"}
                    })
                r = readings[0]
                mmol = mg_to_mmol(r["sgv"])
                result_text = (
                    f"Current Glucose: {r['sgv']} mg/dL ({mmol} mmol/L)\n"
                    f"Trend: {format_direction(r.get('direction', 'Unknown'))}\n"
                    f"Time: {format_time(r['date'])}"
                )
                return jsonify({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": result_text}]}
                })

            elif tool_name == "get_glucose_history":
                count = arguments.get("count", 12)
                readings = get_xdrip_readings(count=count)
                if not readings:
                    result_text = "No glucose readings available."
                else:
                    lines = [f"Last {len(readings)} glucose readings:"]
                    for i, r in enumerate(readings):
                        mmol = mg_to_mmol(r["sgv"])
                        lines.append(
                            f"{i+1}. {format_time(r['date'])} - "
                            f"{r['sgv']} mg/dL ({mmol} mmol/L) [{format_direction(r.get('direction', 'Unknown'))}]"
                        )
                    result_text = "\n".join(lines)
                return jsonify({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": result_text}]}
                })

        except requests.exceptions.ConnectionError:
            return jsonify({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": "Cannot connect to xDrip+. Is it running with REST API enabled?"}
            })
        except Exception as e:
            return jsonify({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": f"Error: {str(e)}"}
            })

    return jsonify({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    })

if __name__ == "__main__":
    logger.info(f"Starting Dexcom MCP server (xDrip+ mode) on port {HTTP_PORT}")
    logger.info(f"Reading from xDrip+ at {XDRIP_HOST}:{XDRIP_PORT}")
    app.run(host="0.0.0.0", port=HTTP_PORT)
