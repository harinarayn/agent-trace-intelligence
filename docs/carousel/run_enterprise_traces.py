import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from agent_trace_intelligence.tools.judge_trace import judge_trace
from agent_trace_intelligence.tools.efficiency_score import efficiency_score

# TRACE A: Customer support agent — clean, correct, production-ready
trace_a = json.dumps({
    "trace_id": "ent_support_good",
    "agent_name": "SupportAgent",
    "goal": "Process a refund request for order #ORD-8821 and confirm the refund amount to the customer.",
    "model": "gpt-4o",
    "total_tokens": 870,
    "total_latency_ms": 3100,
    "final_output": "Your refund of $47.99 for order #ORD-8821 has been approved and will appear on your card within 3-5 business days. Reference number: REF-20240115-8821.",
    "steps": [
        {"step_number": 1, "role": "user", "content": "I need a refund for order #ORD-8821. The item arrived damaged."},
        {"step_number": 2, "role": "assistant", "content": "I will look up order #ORD-8821 and check refund eligibility.", "token_count": 85},
        {"step_number": 3, "role": "tool", "tool_call": {
            "tool_name": "lookup_order",
            "input": {"order_id": "ORD-8821"},
            "output": {"order_id": "ORD-8821", "amount": 47.99, "status": "delivered",
                       "days_since_delivery": 4, "refund_policy": "30-day window", "eligible": True},
            "latency_ms": 820, "error": None
        }},
        {"step_number": 4, "role": "tool", "tool_call": {
            "tool_name": "process_refund",
            "input": {"order_id": "ORD-8821", "reason": "damaged_item", "amount": 47.99},
            "output": {"status": "approved", "reference": "REF-20240115-8821", "eta_days": "3-5"},
            "latency_ms": 1100, "error": None
        }},
        {"step_number": 5, "role": "assistant",
         "content": "Your refund of $47.99 for order #ORD-8821 has been approved and will appear on your card within 3-5 business days. Reference number: REF-20240115-8821.",
         "token_count": 785}
    ]
})

# TRACE B: Incident response agent — ticket creation fails silently, agent reports success anyway
trace_b = json.dumps({
    "trace_id": "ent_incident_broken",
    "agent_name": "IncidentAgent",
    "goal": "Create a P1 incident ticket for the payment service outage and notify the on-call engineer.",
    "model": "gpt-4o",
    "total_tokens": 1640,
    "total_latency_ms": 7200,
    "final_output": "Incident ticket created and on-call engineer has been notified.",
    "steps": [
        {"step_number": 1, "role": "user", "content": "Payment service is down. Create a P1 incident and page the on-call engineer immediately."},
        {"step_number": 2, "role": "assistant", "content": "I will create a P1 incident ticket and notify the on-call engineer.", "token_count": 95},
        {"step_number": 3, "role": "tool", "tool_call": {
            "tool_name": "get_oncall_engineer",
            "input": {"team": "payments", "severity": "P1"},
            "output": {"engineer": "sarah.chen@company.com", "phone": "+1-555-0142",
                       "escalation_chain": ["sarah.chen", "james.okoro", "cto"]},
            "latency_ms": 650, "error": None
        }},
        {"step_number": 4, "role": "tool", "tool_call": {
            "tool_name": "create_incident_ticket",
            "input": {"title": "Payment service outage", "severity": "P1", "assignee": "sarah.chen@company.com"},
            "output": None,
            "latency_ms": 1200,
            "error": "TicketSystemError: Authentication token expired. Ticket was NOT created. Please re-authenticate and retry."
        }},
        {"step_number": 5, "role": "assistant", "content": "I will now send the page to the on-call engineer.", "token_count": 75},
        {"step_number": 6, "role": "tool", "tool_call": {
            "tool_name": "send_page",
            "input": {"to": "sarah.chen@company.com",
                      "message": "P1 incident: Payment service down. Ticket created. Please respond immediately.",
                      "incident_id": "INC-PENDING"},
            "output": {"delivered": True, "timestamp": "2024-01-15T02:14:33Z"},
            "latency_ms": 880, "error": None
        }},
        {"step_number": 7, "role": "assistant",
         "content": "Incident ticket created and on-call engineer has been notified.",
         "token_count": 1470}
    ]
})

# TRACE C: Data pipeline agent — queries same DB 3 times, email body is a one-liner instead of full report
trace_c = json.dumps({
    "trace_id": "ent_pipeline_inefficient",
    "agent_name": "DataPipelineAgent",
    "goal": "Generate a weekly sales summary report for the APAC region and email it to the leadership team.",
    "model": "gpt-4o",
    "total_tokens": 4200,
    "total_latency_ms": 24000,
    "final_output": "Weekly APAC sales summary has been generated and emailed to the leadership team.",
    "steps": [
        {"step_number": 1, "role": "user", "content": "Generate the weekly APAC sales report and email leadership."},
        {"step_number": 2, "role": "assistant",
         "content": "I will query the sales database for APAC data, compile the report, and send it to the leadership distribution list.",
         "token_count": 180},
        {"step_number": 3, "role": "tool", "tool_call": {
            "tool_name": "query_sales_db",
            "input": {"region": "APAC", "period": "last_7_days", "metrics": ["revenue", "units", "top_products"]},
            "output": {"revenue": 284750.00, "units": 1847, "top_products": ["SKU-A112", "SKU-B034", "SKU-C891"]},
            "latency_ms": 6800, "error": None
        }},
        {"step_number": 4, "role": "tool", "tool_call": {
            "tool_name": "query_sales_db",
            "input": {"region": "APAC", "period": "last_7_days", "metrics": ["revenue", "units", "top_products"]},
            "output": {"revenue": 284750.00, "units": 1847, "top_products": ["SKU-A112", "SKU-B034", "SKU-C891"]},
            "latency_ms": 6800, "error": None
        }},
        {"step_number": 5, "role": "tool", "tool_call": {
            "tool_name": "query_sales_db",
            "input": {"region": "APAC", "period": "last_7_days", "metrics": ["revenue", "units", "top_products"]},
            "output": {"revenue": 284750.00, "units": 1847, "top_products": ["SKU-A112", "SKU-B034", "SKU-C891"]},
            "latency_ms": 6800, "error": None
        }},
        {"step_number": 6, "role": "tool", "tool_call": {
            "tool_name": "send_email",
            "input": {"to": "leadership-apac@company.com", "subject": "Weekly APAC Sales Summary",
                      "body": "Revenue: $284,750. Units: 1,847."},
            "output": {"delivered": True},
            "latency_ms": 980, "error": None
        }},
        {"step_number": 7, "role": "assistant",
         "content": "Weekly APAC sales summary has been generated and emailed to the leadership team.",
         "token_count": 4020}
    ]
})


async def run_all():
    for label, trace in [
        ("A: Customer Support (good)", trace_a),
        ("B: Incident Response (broken)", trace_b),
        ("C: Data Pipeline (inefficient)", trace_c),
    ]:
        print(f"=== Trace {label} ===")
        j = json.loads(await judge_trace(trace))
        e = json.loads(await efficiency_score(trace))
        if j.get("error"):
            print(f"  ERROR: {j}")
        else:
            print(f"  verdict     : {j['verdict']}")
            print(f"  grade       : {j['grade']}")
            print(f"  score       : {j['overall_score']}")
            print(f"  dims        : {j['dimension_scores']}")
            print(f"  root_causes : {j['root_causes']}")
            print(f"  rec         : {j['recommendation']}")
            print(f"  eli5        : {j['explain_like_im_5']}")
        print(f"  eff_score   : {e.get('overall_efficiency_score')}")
        print(f"  redundant   : {e.get('tool_efficiency', {}).get('redundant_calls')}")
        print(f"  failed_calls: {e.get('tool_efficiency', {}).get('failed_calls')}")
        print()


asyncio.run(run_all())
