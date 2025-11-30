"""
Prompt Chain Utility
--------------------
Execute multi-step prompt chains with step-by-step debugging and visualization.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional, Callable
import logging

# Import topological executor for non-linear chains
try:
    from src.app.utils.topological_executor import topological_execute, is_linear_chain
    HAS_TOPOLOGICAL = True
except ImportError:
    HAS_TOPOLOGICAL = False

logger = logging.getLogger(__name__)


class PromptChain:
    """Execute multi-step prompt chains with debugging"""
    
    def __init__(self, chains_dir: str = "./prompts/chains"):
        self.chains_dir = Path(chains_dir)
        self.chains_dir.mkdir(parents=True, exist_ok=True)
    
    def load_chain(self, chain_name: str) -> Optional[Dict]:
        """
        Load chain from YAML file.
        
        Args:
            chain_name: Name of chain (without .yaml extension)
            
        Returns:
            Chain configuration dict or None if not found
        """
        chain_path = self.chains_dir / f"{chain_name}.yaml"
        
        if not chain_path.exists():
            logger.error(f"Chain not found: {chain_name}")
            return None
        
        try:
            chain_data = yaml.safe_load(chain_path.read_text(encoding='utf-8'))
            logger.info(f"Loaded chain: {chain_name}")
            return chain_data
        except Exception as e:
            logger.error(f"Error loading chain {chain_name}: {e}")
            return None
    
    def list_chains(self) -> List[str]:
        """
        List all available chain names.
        
        Returns:
            List of chain names (without .yaml extension)
        """
        chains = list(self.chains_dir.glob("*.yaml"))
        return [c.stem for c in chains]
    
    def execute_chain(
        self,
        chain_config: Dict,
        initial_input: str,
        llm_function: Callable,
        debug_callback: Optional[Callable] = None,
        use_topological: Optional[bool] = None
    ) -> Dict:
        """
        Execute prompt chain with step-by-step debugging.
        Supports both linear and non-linear (topological) execution.
        
        Args:
            chain_config: Chain definition from YAML
            initial_input: Starting input text
            llm_function: Function(prompt: str, temperature: float, rag_k: int) -> str
            debug_callback: Optional function(step_result: Dict) for UI updates
            use_topological: If True, use topological executor. If None, auto-detect.
            
        Returns:
            Dict with:
                - success: bool
                - final_output: str or None
                - steps: List[Dict] with step results
                - error: str or None
        """
        results = {
            'success': False,
            'final_output': None,
            'steps': [],
            'error': None
        }
        
        steps = chain_config.get('steps', [])
        if not steps:
            results['error'] = "Chain has no steps defined"
            return results
        
        # Check if we should use topological execution
        connections = chain_config.get('connections', [])
        should_use_topological = False
        
        if use_topological is True:
            should_use_topological = True
        elif use_topological is None and HAS_TOPOLOGICAL:
            # Auto-detect: use topological if connections exist and chain is non-linear
            if connections:
                should_use_topological = not is_linear_chain(connections, len(steps))
        
        # Use topological executor for non-linear chains
        if should_use_topological and HAS_TOPOLOGICAL:
            # Convert steps list to nodes dict
            nodes_dict = {str(i): step for i, step in enumerate(steps)}
            
            # Convert connections to use string indices if needed
            str_connections = []
            for conn in connections:
                if len(conn) == 2:
                    from_idx = str(conn[0]) if isinstance(conn[0], str) else str(conn[0])
                    to_idx = str(conn[1]) if isinstance(conn[1], str) else str(conn[1])
                    str_connections.append([from_idx, to_idx])
            
            return topological_execute(
                nodes_dict=nodes_dict,
                connections=str_connections,
                initial_context=initial_input,
                llm_function=llm_function,
                debug_callback=debug_callback
            )
        
        # Linear execution (original implementation)
        context = initial_input
        
        for idx, step in enumerate(steps):
            step_result = {
                'step_number': idx + 1,
                'description': step.get('description', f'Step {idx + 1}'),
                'input': context[:200] + '...' if len(context) > 200 else context,
                'output': None,
                'success': False,
                'error': None
            }
            
            try:
                # Build prompt with context placeholder
                prompt_template = step.get('prompt', '')
                if not prompt_template:
                    raise ValueError(f"Step {idx + 1} has no prompt defined")
                
                prompt = prompt_template.format(context=context)
                
                # Get step parameters
                temperature = step.get('temperature', chain_config.get('settings', {}).get('default_temperature', 0.7))
                rag_k = step.get('rag_k', chain_config.get('settings', {}).get('default_rag_k', 8))
                
                # Call LLM function
                output = llm_function(
                    prompt=prompt,
                    temperature=temperature,
                    rag_k=rag_k
                )
                
                if not output:
                    raise ValueError(f"Step {idx + 1} returned empty output")
                
                step_result['output'] = output
                step_result['success'] = True
                
                # Update context for next step
                context = output
                
                # Call debug callback if provided (for UI updates)
                if debug_callback:
                    debug_callback(step_result)
                
            except Exception as e:
                error_msg = str(e)
                step_result['error'] = error_msg
                results['error'] = f"Step {idx + 1} failed: {error_msg}"
                results['steps'].append(step_result)
                logger.error(f"Chain execution failed at step {idx + 1}: {e}")
                return results
            
            results['steps'].append(step_result)
        
        # All steps completed successfully
        results['success'] = True
        results['final_output'] = context
        
        logger.info(f"Chain executed successfully: {len(results['steps'])} steps")
        
        return results
    
    def create_chain_template(self, chain_name: str, description: str, steps: List[Dict]) -> bool:
        """
        Create a new chain template file.
        
        Args:
            chain_name: Name for the chain (SCREAMING_SNAKE_CASE)
            description: Description of what the chain does
            steps: List of step dicts with 'description' and 'prompt'
            
        Returns:
            True if created successfully
        """
        try:
            chain_path = self.chains_dir / f"{chain_name}.yaml"
            
            chain_data = {
                'name': chain_name,
                'description': description,
                'version': '1.0',
                'settings': {
                    'default_temperature': 0.7,
                    'default_rag_k': 8
                },
                'steps': steps,
                'metadata': {
                    'created': str(Path(__file__).stat().st_mtime),  # Will be updated
                    'author': 'powercore',
                    'tags': []
                }
            }
            
            chain_path.write_text(yaml.dump(chain_data, default_flow_style=False, sort_keys=False), encoding='utf-8')
            logger.info(f"Created chain template: {chain_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating chain template: {e}")
            return False


# ============================================================================
# PUBLIC API
# ============================================================================

# Singleton instance
_chain_executor = None

def get_prompt_chain_executor() -> PromptChain:
    """Get or create prompt chain executor singleton"""
    global _chain_executor
    if _chain_executor is None:
        _chain_executor = PromptChain()
    return _chain_executor

def load_chain(chain_name: str) -> Optional[Dict]:
    """Public API: Load chain from YAML"""
    executor = get_prompt_chain_executor()
    return executor.load_chain(chain_name)

def list_chains() -> List[str]:
    """Public API: List available chains"""
    executor = get_prompt_chain_executor()
    return executor.list_chains()

def execute_chain(
    chain_config: Dict,
    initial_input: str,
    llm_function: Callable,
    debug_callback: Optional[Callable] = None
) -> Dict:
    """Public API: Execute prompt chain"""
    executor = get_prompt_chain_executor()
    return executor.execute_chain(chain_config, initial_input, llm_function, debug_callback)

