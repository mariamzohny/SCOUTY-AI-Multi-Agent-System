"""Opt-in LangGraph workflow; existing SCOUTY routes remain untouched.

Nodes are deterministic tool-using agents, not autonomous LLM agents.
No external LLM credentials are necessary, and this graph never writes jobs to DB.
"""
from typing import TypedDict
from graph.state import CVProfile, JobPosting
from nodes.score_match import score_job_posting
from nodes.parse_cv import extract_profile

class AgentState(TypedDict, total=False):
    cv_text: str
    profile: dict
    jobs: list[dict]
    shortlist: list[dict]
    skills: list[str]
    trace: list[str]
    summary: str


def cv_agent(state: AgentState) -> dict:
    profile = CVProfile.model_validate(state['profile']) if state.get('profile') else extract_profile(state.get('cv_text', ''))
    return {'profile': profile.model_dump(), 'skills': profile.skills, 'trace': state.get('trace', []) + ['cv_agent']}


def matching_agent(state: AgentState) -> dict:
    profile = CVProfile.model_validate(state['profile'])
    shortlist = [score_job_posting(JobPosting.model_validate(job), profile).model_dump() for job in state.get('jobs', [])]
    shortlist.sort(key=lambda x: x['score'], reverse=True)
    return {'shortlist': shortlist, 'trace': state.get('trace', []) + ['matching_agent']}


def insight_agent(state: AgentState) -> dict:
    shortlisted = state.get('shortlist', [])
    high = sum(x['score'] >= 70 for x in shortlisted)
    top = shortlisted[:3]
    missing = list(dict.fromkeys(skill for item in top for skill in item['missing_skills']))[:8]
    summary = f"Analyzed {len(shortlisted)} jobs; {high} high matches."
    if missing:
        summary += ' Skills to consider: ' + ', '.join(missing) + '.'
    return {'summary': summary, 'trace': state.get('trace', []) + ['insight_agent']}


def build_graph():
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError as exc:
        raise RuntimeError('Install optional agent dependencies: pip install -r requirements-agents.txt') from exc
    workflow = StateGraph(AgentState)
    workflow.add_node('cv_agent', cv_agent)
    workflow.add_node('matching_agent', matching_agent)
    workflow.add_node('insight_agent', insight_agent)
    workflow.add_edge(START, 'cv_agent')
    workflow.add_edge('cv_agent', 'matching_agent')
    workflow.add_edge('matching_agent', 'insight_agent')
    workflow.add_edge('insight_agent', END)
    return workflow.compile()
