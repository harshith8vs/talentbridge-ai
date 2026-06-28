# ruff: noqa
import os
import re
import json
import logging
from typing import AsyncGenerator, Any
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import Workflow, START, node, FunctionNode, Edge
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool, McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types

from app.config import config

# Ensure logging is set up
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TalentBridgeSecurity")

# Initialize McpToolset to connect to the local mcp_server.py via stdio
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "app/mcp_server.py"],
        )
    )
)

# ==========================================
# 1. Pydantic Schemas for Structured I/O
# ==========================================

class TalentProfile(BaseModel):
    talent_score: int = Field(description="Score from 1 to 100 assessing academic/extracurricular strengths.")
    strengths: list[str] = Field(description="Key personal and academic strengths identified.")
    skills: list[str] = Field(description="Practical skills possessed or demonstrated by the student.")
    career_suitability: list[str] = Field(description="List of career paths matching these strengths.")

class ScholarshipMatch(BaseModel):
    name: str = Field(description="Name of the scholarship, grant, or scheme.")
    award: str = Field(description="Award details, e.g. amount or tuition coverage.")
    eligibility_status: str = Field(description="Eligibility assessment (e.g. Eligible, Potentially Eligible).")
    description: str = Field(description="Short details of the scholarship or application criteria.")

class ScholarshipMatches(BaseModel):
    matches: list[ScholarshipMatch] = Field(description="List of matching financial opportunities.")

class OpportunityMatch(BaseModel):
    type: str = Field(description="Type of opportunity (Internship, Hackathon, Competition, Fellowship, Research).")
    name: str = Field(description="Name of the opportunity.")
    description: str = Field(description="Brief description and why it fits this student.")
    deadline: str = Field(description="Application deadline or 'Ongoing'.")

class OpportunityMatches(BaseModel):
    opportunity_match_score: int = Field(description="Score from 1 to 100 matching opportunities to interests.")
    recommendations: list[OpportunityMatch] = Field(description="List of recommended opportunities.")

class MentorRecommendation(BaseModel):
    name: str = Field(description="Name of the mentor or professional community.")
    role: str = Field(description="Professional title or affiliation.")
    reason: str = Field(description="Why this mentor/community is a good fit for the student.")

class MentorRecommendations(BaseModel):
    mentors: list[MentorRecommendation] = Field(description="List of suggested mentors/communities.")

class GrowthMilestone(BaseModel):
    month: int = Field(description="Month number (1 to 6).")
    goal: str = Field(description="Target goal for this month.")
    action_items: list[str] = Field(description="Actionable steps the student should take.")

class GrowthRoadmap(BaseModel):
    roadmap_milestones: list[GrowthMilestone] = Field(description="Step-by-step 6-month developmental milestones.")

class OrchestratorOutput(BaseModel):
    summary: str = Field(description="A brief, encouraging summary of the evaluation.")

# ==========================================
# 2. Specialized LlmAgents (Sub-agents)
# ==========================================

talent_analyzer = LlmAgent(
    name="talent_analyzer",
    model=config.model,
    instruction="""You are the Talent Analyzer Agent for TalentBridge AI. 
Evaluate the student's profile details including academics, projects, certifications, extracurriculars, and skills.
Identify 3-5 core strengths, list practical skills, suggest career options, and compute a Talent Score (1-100).
Adopt an encouraging tone. Highlight hidden potential, especially in underserved or rural student contexts.""",
    output_schema=TalentProfile,
    output_key="talent_profile",
)

scholarship_discovery = LlmAgent(
    name="scholarship_discovery",
    model=config.model,
    instruction="""You are the Scholarship Discovery Agent for TalentBridge AI. 
Match the student's academic standing, regional location, demographic facts, and financial details against financial opportunities.
Find suitable scholarships, tuition grants, and government schemes.
Assess eligible opportunities with care. Under tools, use the search_scholarships tool to find matching schemes.""",
    output_schema=ScholarshipMatches,
    output_key="scholarships",
    tools=[mcp_toolset],
)

opportunity_discovery = LlmAgent(
    name="opportunity_discovery",
    model=config.model,
    instruction="""You are the Opportunity Discovery Agent for TalentBridge AI. 
Recommend high-impact internships, hackathons, skill-building competitions, fellowships, and research programs.
Calculate an Opportunity Match Score (1-100) reflecting how well they fit.
Prioritize programs that actively recruit students from rural, remote, or first-generation backgrounds.
Use the search_opportunities tool to find suitable programs.""",
    output_schema=OpportunityMatches,
    output_key="opportunities",
    tools=[mcp_toolset],
)

mentor_matching = LlmAgent(
    name="mentor_matching",
    model=config.model,
    instruction="""You are the Mentor Matching Agent for TalentBridge AI. 
Suggest relevant industry mentors, alumni networks, student associations, or tech communities that can support the student's career vision.
Provide 2-3 tailored matches with clear justifications. Use the list_mentors tool.""",
    output_schema=MentorRecommendations,
    output_key="mentors",
    tools=[mcp_toolset],
)

roadmap_agent = LlmAgent(
    name="roadmap_agent",
    model=config.model,
    instruction="""You are the Growth Roadmap Agent for TalentBridge AI. 
Generate a clear, milestone-driven 6-month plan.
Structure each month with a clear goal and 2-3 specific action items.
Avoid overly complex jargon; translate concepts into practical steps for first-generation college students.""",
    output_schema=GrowthRoadmap,
    output_key="roadmap",
)

# ==========================================
# 3. Main Orchestrator Agent (delegates to sub-agents)
# ==========================================

orchestrator = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction="""You are the TalentBridge AI Orchestrator. 
Your goal is to coordinate a complete evaluation of the student's profile.
You must call these specialized agents (using their corresponding tool names) in sequence to build the final report:
1. First, call 'talent_analyzer' to establish the student's profile strengths and Talent Score.
2. Next, call 'scholarship_discovery' to list financial aid opportunities.
3. Then, call 'opportunity_discovery' to find internships and competitions.
4. Then, call 'mentor_matching' to suggest guides and networks.
5. Finally, call 'roadmap_agent' to generate the 6-month growth plan.

Once all tools have returned, write a warm, encouraging welcome message to the student summarizing that their report is now ready.""",
    tools=[
        AgentTool(talent_analyzer),
        AgentTool(scholarship_discovery),
        AgentTool(opportunity_discovery),
        AgentTool(mentor_matching),
        AgentTool(roadmap_agent),
    ],
    output_schema=OrchestratorOutput,
)

# ==========================================
# 4. Security Checkpoint and Flow Nodes
# ==========================================

@node
def security_checkpoint(ctx: Context, node_input: Any) -> Event:
    """Validates student inputs, redacts sensitive PII, and flags injections."""
    # Handle START node output
    text_content = ""
    if hasattr(node_input, 'parts'):
        text_content = "".join([part.text for part in node_input.parts if part.text])
    elif isinstance(node_input, str):
        text_content = node_input
    else:
        text_content = str(node_input)

    # 1. PII Redaction
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_regex = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    
    redacted_text = re.sub(email_regex, "[EMAIL_REDACTED]", text_content)
    redacted_text = re.sub(phone_regex, "[PHONE_REDACTED]", redacted_text)

    # 2. Prompt Injection Check
    injection_keywords = [
        "ignore all previous instructions", "ignore instructions",
        "override system prompt", "jailbreak", "you are now an evil",
        "forget your instructions"
    ]
    
    is_injection = any(kw in text_content.lower() for kw in injection_keywords)
    
    # 3. Domain-Specific Rule: Validate GPA bounds
    gpa_match = re.search(r'\bgpa\b[:\s\-]*(\d+(?:\.\d+)?)\b', text_content, re.IGNORECASE)
    invalid_gpa = False
    if gpa_match:
        gpa_val = float(gpa_match.group(1))
        if gpa_val < 0.0 or gpa_val > 10.0:
            invalid_gpa = True
            
    # 4. Structured Audit Log
    decision_log = {
        "session_id": ctx.session.id,
        "pii_detected": text_content != redacted_text,
        "injection_detected": is_injection,
        "invalid_gpa": invalid_gpa,
        "action": "BLOCK" if (is_injection or invalid_gpa) else "ALLOW",
        "severity": "CRITICAL" if is_injection else ("WARNING" if (text_content != redacted_text or invalid_gpa) else "INFO")
    }
    logger.info(f"AUDIT_LOG: {json.dumps(decision_log)}")

    if is_injection:
        return Event(
            route="security_violation",
            output="Security Policy Block: Input contained potential instructions designed to override the system security parameters."
        )

    if invalid_gpa:
        return Event(
            route="security_violation",
            output="Security Policy Block: Invalid academic data detected. GPA value must be between 0.0 and 10.0."
        )

    # Proceed with redacted content
    return Event(route="continue", output=redacted_text, state={"raw_input": text_content})

@node
def security_error_node(node_input: Any) -> str:
    """Terminal node for security blocks."""
    return str(node_input)

@node
async def hitl_verification(ctx: Context, node_input: Any) -> AsyncGenerator[Event, None]:
    """Asks the student to confirm starting the growth plan generation (HITL)."""
    # Check if we already received a response from the human in the loop
    if not ctx.resume_inputs or "approve" not in ctx.resume_inputs:
        yield RequestInput(
            interrupt_id="approve",
            message="Your Talent Evaluation Report is ready. Do you want to finalize the growth plan and matches? (Please type 'yes' to proceed, or share any additional details/feedback to update your profile):"
        )
        return

    user_response = ctx.resume_inputs["approve"]
    if user_response.strip().lower() == "yes":
        yield Event(output={"approved": True, "feedback": None}, route="continue")
    else:
        yield Event(output={"approved": True, "feedback": user_response}, route="continue")

@node
def final_output(ctx: Context, node_input: Any) -> Any:
    """Formats and prints the final report using the state populated by specialized sub-agents."""
    if isinstance(node_input, str) and "Security" in node_input:
        msg = f"### ⚠️ Security Alert\n\n{node_input}"
        yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=msg)]))
        yield Event(output=msg)
        return

    # Extract state variables populated by sub-agents
    talent_profile = ctx.state.get("talent_profile", {})
    scholarships = ctx.state.get("scholarships", {})
    opportunities = ctx.state.get("opportunities", {})
    mentors = ctx.state.get("mentors", {})
    roadmap = ctx.state.get("roadmap", {})
    feedback = node_input.get("feedback") if isinstance(node_input, dict) else None

    # Formulate report in clear, accessible markdown
    report = []
    report.append("# 🌟 TalentBridge AI — Personalized Strength & Opportunity Plan 🌟")
    report.append("Here is your custom guidance plan, specifically prepared to help you map out your potential and connect with funding and growth opportunities.")

    # 1. Talent Profile
    if talent_profile:
        score = talent_profile.get("talent_score", "N/A")
        report.append(f"\n## 👤 1. Your Talent Profile (Talent Score: {score}/100)")
        report.append("**Your Key Strengths:**")
        for strength in talent_profile.get("strengths", []):
            report.append(f"- **{strength}**")
        report.append("\n**Your Skills:**")
        report.append(", ".join(talent_profile.get("skills", [])))
        report.append("\n**Suggested Career Paths:**")
        for career in talent_profile.get("career_suitability", []):
            report.append(f"- {career}")

    # 2. Scholarships
    if scholarships:
        report.append("\n## 💰 2. Matching Scholarships & Financial Aid")
        for match in scholarships.get("matches", []):
            report.append(f"- **{match.get('name')}**: {match.get('award')} (Status: *{match.get('eligibility_status')}*)")
            report.append(f"  *Details: {match.get('description')}*")

    # 3. Opportunities
    if opportunities:
        match_score = opportunities.get("opportunity_match_score", "N/A")
        report.append(f"\n## 🚀 3. Recommended Internships, Hackathons & Programs (Match Score: {match_score}/100)")
        for opt in opportunities.get("recommendations", []):
            report.append(f"- **{opt.get('name')}** ({opt.get('type')})")
            report.append(f"  *Why it fits you: {opt.get('description')}*")
            report.append(f"  *Deadline: {opt.get('deadline')}*")

    # 4. Mentors
    if mentors:
        report.append("\n## 🤝 4. Suggested Mentors & Support Networks")
        for mentor in mentors.get("mentors", []):
            report.append(f"- **{mentor.get('name')}** ({mentor.get('role')})")
            report.append(f"  *Connection Reason: {mentor.get('reason')}*")

    # 5. Roadmap
    if roadmap:
        report.append("\n## 📅 5. Your 6-Month Actionable Growth Roadmap")
        for milestone in roadmap.get("roadmap_milestones", []):
            report.append(f"### Month {milestone.get('month')}: {milestone.get('goal')}")
            for item in milestone.get('action_items', []):
                report.append(f"- [ ] {item}")

    if feedback:
        report.append(f"\n---\n*Note: We included your additional feedback/notes in this plan: \"{feedback}\"*")

    report_text = "\n".join(report)
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=report_text)]))
    yield Event(output=report_text)

# ==========================================
# 5. Workflow Graph Assembly
# ==========================================

root_agent = Workflow(
    name="talentbridge_workflow",
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=security_error_node, route='security_violation'),
        Edge(from_node=security_checkpoint, to_node=orchestrator, route='continue'),
        Edge(from_node=orchestrator, to_node=hitl_verification),
        Edge(from_node=hitl_verification, to_node=final_output),
        Edge(from_node=security_error_node, to_node=final_output),
    ],
    description="Orchestrates student talent analysis, opportunity matching, and growth roadmap planning."
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True)
)
