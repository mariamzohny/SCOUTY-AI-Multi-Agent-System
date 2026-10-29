"""Offline integration tests, with a fake LLM; never needs an external API key."""
from unittest.mock import patch
from graph.agentic_workflow import profile_specialist, job_specialist, market_specialist, review_specialist, build_agentic_graph
from graph.llm_provider import LLMError

sample={'profile':{'name':'Demo','skills':['Python','SQL'],'title':'Data Analyst'},
        'jobs':[{'id':'1','title':'Junior Data Analyst','company':'Example','source':'Demo','url':'https://example.org/1','description':'Python SQL Excel'}],
        'trace':[],'llm_enabled':False,'llm_used':False}

def run_nodes(state):
    state=dict(state)
    for fn in [profile_specialist,job_specialist,market_specialist,review_specialist]:
        state.update(fn(state))
    return state

def test():
    result=run_nodes(sample)
    assert result['review']['passed'] and not result['review']['llm_used']
    assert result['trace']==['cv_agent','matching_agent','insight_agent','review_specialist']
    with patch('graph.agentic_workflow.chat_json', side_effect=[{'target_role':'Data Analyst'},{'recommendations':['Practice Excel']}]) as fake:
        result=run_nodes({**sample,'llm_enabled':True})
        assert result['llm_used'] and result['review']['llm_used']
        assert result['profile']['target_role']=='Data Analyst'
        assert result['recommendations']==['Practice Excel']
        assert fake.call_count==2
    with patch('graph.agentic_workflow.chat_json',side_effect=LLMError('offline')):
        result=run_nodes({**sample,'llm_enabled':True})
        assert result['review']['passed'] and not result.get('llm_used',False)
    print('PASS: deterministic mode, mocked LLM mode, LLM-failure fallback and review')
    try:
        graph=build_agentic_graph()
    except RuntimeError as exc:
        print('SKIPPED compiled LangGraph (not installed):',exc)
    else:
        assert graph.invoke(sample)['review']['passed']
        print('PASS: compiled LangGraph')

if __name__=='__main__':test()
