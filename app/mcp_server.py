# ruff: noqa
import os
os.environ["TALENTBRIDGE_MCP_RUNNING"] = "True"

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TalentBridge-AI")

# Mock database of scholarships
SCHOLARSHIP_DB = [
    {
        "name": "National Rural Excellence Scholarship",
        "award": "$5,000 per year",
        "eligibility": "Rural residency, GPA > 3.0",
        "description": "Supports students from rural school districts pursuing higher education in STEM fields."
    },
    {
        "name": "First-Gen Pathways Grant",
        "award": "$3,500 one-time",
        "eligibility": "First-generation college student",
        "description": "Assists first-generation college students with tuition, books, and living expenses."
    },
    {
        "name": "State Opportunity Scheme",
        "award": "Full tuition coverage",
        "eligibility": "Low income, state resident",
        "description": "Government scheme covering tuition fees at state universities for qualifying low-income students."
    },
    {
        "name": "Tech for All Grant",
        "award": "$2,000 laptop and learning stipend",
        "eligibility": "GPA > 2.8, demonstrated financial need",
        "description": "Provides hardware and internet access stipends to students from underrepresented communities."
    }
]

# Mock database of opportunities
OPPORTUNITY_DB = [
    {
        "type": "Hackathon",
        "name": "Rural Hack 2026",
        "description": "Virtual hackathon designing technology solutions for agriculture, healthcare, and education in rural communities.",
        "deadline": "2026-09-15"
    },
    {
        "type": "Internship",
        "name": "Open-Source Summer Fellowship",
        "description": "Remote software engineering fellowship working on impactful open-source tools with structured mentorship.",
        "deadline": "2026-10-01"
    },
    {
        "type": "Competition",
        "name": "Green Innovation Contest",
        "description": "Pitch competition for eco-friendly business models with starting seed funding for top 3 teams.",
        "deadline": "2026-11-20"
    },
    {
        "type": "Research Program",
        "name": "Community Impact Research Initiative",
        "description": "Supported research program studying accessibility barrier resolutions in non-urban high schools.",
        "deadline": "2026-12-05"
    }
]

# Mock database of mentors
MENTOR_DB = [
    {
        "name": "Dr. Sarah Jenkins",
        "role": "Director at Rural Tech Coalition",
        "reason": "Expertise in bridging digital divides and guiding tech careers in remote areas."
    },
    {
        "name": "Rajesh Kumar",
        "role": "Senior Software Architect (Alumni Network)",
        "reason": "First-generation graduate willing to mentor on coding interview prep and resume structuring."
    },
    {
        "name": "Elena Rostova",
        "role": "Scholarship Advisor at Future Pathways",
        "reason": "Helps students write compelling applications for national fellowships and financial aid programs."
    }
]

@mcp.tool()
def search_scholarships(query: str) -> list[dict]:
    """Search the scholarship database for matching funding schemes.
    
    Args:
        query: Search term to filter scholarships by (e.g. 'first-gen', 'rural', 'low income').
    """
    query = query.lower()
    matches = []
    for item in SCHOLARSHIP_DB:
        if (query in item["name"].lower() or 
            query in item["eligibility"].lower() or 
            query in item["description"].lower()):
            matches.append(item)
    return matches if matches else SCHOLARSHIP_DB[:2]

@mcp.tool()
def search_opportunities(skills: list[str], interests: list[str]) -> list[dict]:
    """Search for relevant internships, hackathons, competitions, and fellowships.
    
    Args:
        skills: List of skills the student possesses (e.g. ['Python', 'HTML']).
        interests: List of fields the student is interested in (e.g. ['STEM', 'agriculture']).
    """
    matches = []
    terms = [s.lower() for s in skills] + [i.lower() for i in interests]
    for item in OPPORTUNITY_DB:
        text = (item["name"] + " " + item["description"] + " " + item["type"]).lower()
        if any(term in text for term in terms):
            matches.append(item)
    return matches if matches else OPPORTUNITY_DB

@mcp.tool()
def list_mentors(career_goal: str) -> list[dict]:
    """List matching professional mentors and advisors for the student's career goal.
    
    Args:
        career_goal: The student's intended profession or field of interest (e.g. 'Software Developer', 'Advisor').
    """
    matches = []
    goal = career_goal.lower()
    for mentor in MENTOR_DB:
        if (goal in mentor["role"].lower() or 
            goal in mentor["reason"].lower()):
            matches.append(mentor)
    return matches if matches else MENTOR_DB

if __name__ == "__main__":
    mcp.run()
