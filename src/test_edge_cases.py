import pytest
from langchain_core.messages import AIMessage

from agent_advanced import AdvancedAgent
from benchmark import recall_points
from config import load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import ProviderConfig, build_live_graph, normalize_provider


def test_interests_survive_new_preference(tmp_path):
    agent = AdvancedAgent(load_config(tmp_path), True)
    agent.reply('user', 'one', 'Mình thích Python, AI ứng dụng.')
    agent.reply('user', 'one', 'Mình thích markdown.')
    answer = agent.reply('user', 'two', 'Mối quan tâm kỹ thuật của mình là gì?')['response']
    assert 'Python' in answer and 'AI' in answer and 'markdown' in answer


def test_correction_replaces_fact_and_noise_does_not_write(tmp_path):
    agent = AdvancedAgent(load_config(tmp_path), True)
    agent.reply('u', 'one', 'Mình ở Đà Nẵng và đang làm backend engineer.')
    agent.reply('u', 'two', 'Mình đang ở Huế chứ không còn ở Đà Nẵng. Mình không còn làm backend engineer nữa, giờ chuyển sang MLOps engineer.')
    before = agent.profile_store.read_text('u')
    agent.reply('u', 'three', 'Nếu mình ở Hà Nội thì sao? Mình tên gì? Mình đùa là product manager.')
    assert agent.profile_store.read_text('u') == before
    assert agent.profile_store.facts('u')['location'] == 'Huế'
    assert agent.profile_store.facts('u')['profession'] == 'MLOps engineer'
    assert 'backend engineer' not in before and 'Đà Nẵng' not in before


def test_profile_users_are_isolated_and_paths_cannot_escape(tmp_path):
    store = UserProfileStore(tmp_path)
    for name in ('../alice', '/absolute', '..\\alice', 'a/b', 'a-b'):
        store.write_text(name, '# User\n')
        assert store.path_for(name).resolve().is_relative_to(tmp_path.resolve())
    assert store.path_for('a/b') != store.path_for('a-b')
    agent = AdvancedAgent(load_config(tmp_path), True)
    agent.reply('alice', 'a', 'Mình tên là Alice.')
    assert 'Alice' not in agent.reply('bob', 'b', 'Mình tên gì?')['response']
    with pytest.raises(ValueError, match='another user'):
        agent.reply('bob', 'a', 'Mình tên gì?')


def test_summary_survives_multiple_compactions_without_growth():
    memory = CompactMemoryManager(200, 2)
    memory.append('one', 'user', 'Mình tên là An.')
    for i in range(60):
        memory.append('one', 'user', f'Ghi chú số {i}: ' + 'tin tức không thuộc hồ sơ ' * 100)
    context = memory.context('one')
    assert 'An' in context['summary']
    assert len(context['summary']) < 1600 and len(context['messages']) <= 2
    assert memory.compaction_count('one') > 10
    assert memory.context('new')['summary'] == ''


def test_questions_and_quoted_facts_do_not_become_memory():
    assert extract_profile_updates('Bạn có biết DũngCT không?') == {}
    assert extract_profile_updates('Ví dụ: "Mình tên là Lan. Mình ở Paris."') == {}
    assert extract_profile_updates('Nếu mình ở Hà Nội thì sẽ thế nào?') == {}
    assert extract_profile_updates('Mình ở Huế?') == {}
    assert extract_profile_updates('Mình tên là Lan?') == {}
    assert estimate_tokens('') == 0 and estimate_tokens('abcd') == 1
    assert recall_points('A', ['A', 'B']) == 0.5


def test_latest_number_of_bullets_replaces_old_style(tmp_path):
    agent = AdvancedAgent(load_config(tmp_path), True)
    agent.reply('u', 'a', 'Mình muốn trả lời ngắn gọn thành 3 bullet.')
    agent.reply('u', 'b', 'Mình muốn trả lời thành 4 bullet.')
    style = agent.profile_store.facts('u')['response_style']
    assert '4 bullet' in style and '3 bullet' not in style


def test_coordinated_first_person_fact_is_extracted():
    updates = extract_profile_updates('Mình tên là An, hiện ở Huế và đang làm backend engineer.')
    assert updates['name'] == 'An'
    assert updates['location'] == 'Huế'
    assert updates['profession'] == 'backend engineer'


@pytest.mark.parametrize('provider', ['openai', 'custom', 'gemini', 'anthropic', 'ollama', 'openrouter'])
def test_provider_configuration_is_supported_and_secret_not_printed(provider):
    config = ProviderConfig(provider, 'demo', 0, api_key='local-test-secret')
    assert normalize_provider(provider) == provider
    assert 'local-test-secret' not in repr(config)


def test_provider_alias_and_rejection():
    assert normalize_provider(' anthorpic ') == 'anthropic'
    with pytest.raises(ValueError):
        normalize_provider('invalid')


def test_live_graph_only_sends_curated_context():
    class FakeModel:
        def __init__(self):
            self.seen = []
        def invoke(self, messages):
            self.seen.append(messages)
            return AIMessage(content='ok')
    model = FakeModel()
    graph = build_live_graph(model)
    config = {'configurable': {'thread_id': 'thread'}}
    graph.invoke({'messages': [{'role': 'user', 'content': 'previous'}]}, config)
    graph.invoke({'messages': [{'role': 'user', 'content': 'compacted'}]}, config)
    assert model.seen[-1] == [{'role': 'user', 'content': 'compacted'}]
