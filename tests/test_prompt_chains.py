"""
Unit tests for Prompt Chains module
"""
import pytest
import tempfile
import shutil
import yaml
from pathlib import Path
from src.app.utils.prompt_chains import PromptChain, load_chain, list_chains, execute_chain


@pytest.fixture
def temp_chains_dir():
    """Create a temporary chains directory"""
    temp_dir = tempfile.mkdtemp()
    chains_dir = Path(temp_dir) / "chains"
    chains_dir.mkdir(parents=True)
    
    # Create a test chain
    test_chain = {
        'name': 'TEST_CHAIN',
        'description': 'Test chain',
        'version': '1.0',
        'settings': {
            'default_temperature': 0.7,
            'default_rag_k': 8
        },
        'steps': [
            {
                'description': 'Step 1',
                'prompt': 'Process: {context}',
                'temperature': 0.5,
                'rag_k': 5
            }
        ]
    }
    
    chain_file = chains_dir / "test_chain.yaml"
    chain_file.write_text(yaml.dump(test_chain), encoding='utf-8')
    
    yield chains_dir
    
    shutil.rmtree(temp_dir)


def test_load_chain(temp_chains_dir):
    """Test chain loading"""
    executor = PromptChain(chains_dir=str(temp_chains_dir))
    chain = executor.load_chain("test_chain")
    
    assert chain is not None
    assert chain['name'] == 'TEST_CHAIN'
    assert len(chain['steps']) == 1


def test_list_chains(temp_chains_dir):
    """Test chain listing"""
    executor = PromptChain(chains_dir=str(temp_chains_dir))
    chains = executor.list_chains()
    
    assert isinstance(chains, list)
    assert "test_chain" in chains


def test_execute_chain(temp_chains_dir):
    """Test chain execution"""
    executor = PromptChain(chains_dir=str(temp_chains_dir))
    chain = executor.load_chain("test_chain")
    
    # Mock LLM function
    def mock_llm(prompt, temperature, rag_k):
        return f"Processed: {prompt}"
    
    result = executor.execute_chain(
        chain_config=chain,
        initial_input="test input",
        llm_function=mock_llm
    )
    
    assert result['success'] is True
    assert result['final_output'] is not None
    assert len(result['steps']) == 1
    assert result['steps'][0]['success'] is True


def test_execute_chain_error_handling(temp_chains_dir):
    """Test chain error handling"""
    executor = PromptChain(chains_dir=str(temp_chains_dir))
    chain = executor.load_chain("test_chain")
    
    # Mock LLM function that raises error
    def failing_llm(prompt, temperature, rag_k):
        raise ValueError("LLM error")
    
    result = executor.execute_chain(
        chain_config=chain,
        initial_input="test input",
        llm_function=failing_llm
    )
    
    assert result['success'] is False
    assert result['error'] is not None
    assert len(result['steps']) == 1
    assert result['steps'][0]['success'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

