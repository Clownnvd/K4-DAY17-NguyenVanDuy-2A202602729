from dataclasses import replace
from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config
from memory_store import CompactMemoryManager, UserProfileStore


def make_config(tmp_path: Path):
    return replace(load_config(tmp_path), compact_threshold_tokens=300, compact_keep_messages=2)


def test_user_markdown_read_write_edit(tmp_path):
    store = UserProfileStore(tmp_path / 'profiles')
    assert store.read_text('user') == ''
    path = store.write_text('user', '# User\n- location: Huế\n')
    assert path.name == 'User.md' and path.exists()
    assert store.edit_text('user', 'Huế', 'Đà Nẵng')
    assert 'Đà Nẵng' in UserProfileStore(store.root_dir).read_text('user')
    assert not store.edit_text('user', 'missing', 'new')
    assert store.file_size('user') == len(path.read_bytes())


def test_compact_trigger(tmp_path):
    config = make_config(tmp_path)
    memory = CompactMemoryManager(config.compact_threshold_tokens, config.compact_keep_messages)
    memory.append('thread', 'user', 'Mình tên là An.')
    for _ in range(8):
        memory.append('thread', 'user', 'Nội dung tạm thời của cuộc thảo luận. ' * 100)
    context = memory.context('thread')
    assert memory.compaction_count('thread') > 0
    assert context['summary'] and len(context['messages']) <= config.compact_keep_messages
    assert 'An' in context['summary']


def test_cross_session_recall(tmp_path):
    config = make_config(tmp_path)
    baseline, advanced = BaselineAgent(config, True), AdvancedAgent(config, True)
    for agent in (baseline, advanced):
        agent.reply('user', 'first', 'Mình tên là An. Mình ở Huế và đang làm backend engineer.')
        assert 'An' in agent.reply('user', 'first', 'Mình tên gì?')['response']
    assert 'An' not in baseline.reply('user', 'new', 'Mình tên gì?')['response']
    restarted = AdvancedAgent(config, True)
    assert 'An' in restarted.reply('user', 'new', 'Mình tên gì?')['response']
    assert advanced.memory_file_size('user') > 0


def test_compact_reduces_prompt_load_on_long_thread(tmp_path):
    config = make_config(tmp_path)
    baseline, advanced = BaselineAgent(config, True), AdvancedAgent(config, True)
    for i in range(16):
        message = f'Lượt {i}: ' + 'Đây là nội dung trao đổi dài để kiểm tra chi phí ngữ cảnh. ' * 100
        for agent in (baseline, advanced):
            agent.reply('user', 'long', message)
    assert advanced.compaction_count('long') > 0
    assert advanced.prompt_token_usage('long') < baseline.prompt_token_usage('long') / 2
