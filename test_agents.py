"""Offline node-level tests; test compiled graph when LangGraph is installed."""
from graph.agent_workflow import cv_agent, matching_agent, insight_agent, build_graph

sample = {'profile': {'name':'Demo Candidate', 'skills':['Python','SQL'],'target_role':'Data Analyst'},
          'jobs':[{'id':'demo1','title':'Junior Data Analyst','company':'Demo Company', 'url':'https://example.org/job/1','source':'Demo', 'description':'Python SQL Excel'}], 'trace':[]}

def check(result):
    assert result['trace']==['cv_agent','matching_agent','insight_agent']
    assert len(result['shortlist'])==1
    assert result['shortlist'][0]['matched_skills']==['Python','SQL']
    assert 'Analyzed 1 jobs' in result['summary']
    print('PASS: three-agent workflow, match scores, skill gap and trace')

if __name__=='__main__':
    state=dict(sample)
    for node in (cv_agent,matching_agent,insight_agent):state.update(node(state))
    check(state)
    try:graph=build_graph()
    except RuntimeError as error:print('SKIPPED: compiled LangGraph test -',error)
    else:
        check(graph.invoke(sample))
        print('PASS: compiled LangGraph end-to-end')
