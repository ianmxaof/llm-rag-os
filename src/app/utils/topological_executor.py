"""
Topological Executor for Non-Linear Prompt Chains
Phase 4.3: Execute chains with branches, merges, and parallel execution
"""

import logging
import time
from typing import Dict, List, Optional, Callable
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


def execute_node_with_retry(
    node: Dict,
    context: str,
    llm_function: Callable,
    max_retries: int = 3
) -> Dict:
    """
    Execute a single node with exponential backoff retry logic.
    
    Returns:
        Dict with keys: success (bool), output (str or None), error (str or None)
    """
    for attempt in range(max_retries):
        try:
            prompt_template = node.get("prompt", "")
            if not prompt_template:
                return {
                    "success": False,
                    "output": None,
                    "error": "Node has no prompt defined"
                }
            
            prompt = prompt_template.format(context=context)
            temperature = node.get("temperature", 0.7)
            rag_k = node.get("rag_k", 8)
            
            output = llm_function(
                prompt=prompt,
                temperature=temperature,
                rag_k=rag_k
            )
            
            if not output:
                raise ValueError("LLM returned empty output")
            
            return {
                "success": True,
                "output": output,
                "error": None
            }
        
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(f"Node '{node.get('description', 'Unknown')}' failed (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                return {
                    "success": False,
                    "output": None,
                    "error": str(e)
                }
    
    return {
        "success": False,
        "output": None,
        "error": "Max retries exceeded"
    }


def topological_execute(
    nodes_dict: Dict[str, Dict],
    connections: List[List[str]],
    initial_context: str,
    llm_function: Callable,
    debug_callback: Optional[Callable] = None
) -> Dict:
    """
    Execute a directed graph of reasoning nodes in perfect causal order.
    Handles branches, merges, parallelism, and cycles (with warning).
    
    Args:
        nodes_dict: Dict mapping node_id to node data (description, prompt, temperature, rag_k)
        connections: List of [from_id, to_id] pairs representing edges
        initial_context: Starting input text
        llm_function: Function(prompt: str, temperature: float, rag_k: int) -> str
        debug_callback: Optional function(step_result: Dict) for UI updates
    
    Returns:
        Dict with:
            - success: bool
            - final_output: str or None
            - steps: List[Dict] with step results
            - error: str or None
    """
    if not nodes_dict:
        return {
            "success": False,
            "final_output": None,
            "steps": [],
            "error": "No nodes to execute"
        }
    
    # Build graph structure
    graph = defaultdict(list)  # node_id -> [child_ids]
    incoming = defaultdict(int)  # node_id -> count of incoming edges
    node_map = {}  # node_id -> node data
    
    # Initialize nodes
    for node_id, node in nodes_dict.items():
        node_map[node_id] = node
        incoming[node_id] = 0
    
    # Build edges
    for from_id, to_id in connections:
        if from_id in node_map and to_id in node_map:
            graph[from_id].append(to_id)
            incoming[to_id] += 1
    
    # Find root nodes (no incoming edges)
    queue = deque([nid for nid in nodes_dict if incoming[nid] == 0])
    
    # If no root nodes, try to detect cycle or use first node
    if not queue:
        logger.warning("No root nodes found - possible cycle or disconnected graph")
        # Use first node as root (fallback)
        if nodes_dict:
            first_node_id = list(nodes_dict.keys())[0]
            queue.append(first_node_id)
            logger.info(f"Using first node '{first_node_id}' as root")
        else:
            return {
                "success": False,
                "final_output": None,
                "steps": [],
                "error": "No root nodes found and graph is empty"
            }
    
    # Execution state
    results = {}  # node_id -> output string
    executed = set()  # Track executed nodes
    step_results = []  # For debug callback
    
    # Initialize root nodes with initial context
    for root_id in queue:
        results[root_id] = initial_context
    
    # Kahn's algorithm with execution
    while queue:
        current_id = queue.popleft()
        
        if current_id in executed:
            continue  # Skip if already executed
        
        current_node = node_map[current_id]
        input_text = results.get(current_id, initial_context)
        
        # Execute node
        step_result = {
            "node_id": current_id,
            "step_number": len(step_results) + 1,
            "description": current_node.get("description", f"Node {current_id}"),
            "input": input_text[:200] + "..." if len(input_text) > 200 else input_text,
            "output": None,
            "success": False,
            "error": None
        }
        
        exec_result = execute_node_with_retry(
            node=current_node,
            context=input_text,
            llm_function=llm_function,
            max_retries=3
        )
        
        if not exec_result["success"]:
            step_result["error"] = exec_result["error"]
            step_results.append(step_result)
            
            if debug_callback:
                debug_callback(step_result)
            
            # Option: Continue with error message or halt
            # For now, halt on error
            return {
                "success": False,
                "final_output": None,
                "steps": step_results,
                "error": f"Node '{current_node.get('description', current_id)}' failed: {exec_result['error']}"
            }
        
        output = exec_result["output"]
        results[current_id] = output
        executed.add(current_id)
        
        step_result["output"] = output
        step_result["success"] = True
        step_results.append(step_result)
        
        if debug_callback:
            debug_callback(step_result)
        
        # Propagate to children
        for child_id in graph[current_id]:
            # Merge strategy: concatenate all parent outputs
            parent_outputs = []
            for parent_id in nodes_dict:
                if (parent_id, child_id) in [(c[0], c[1]) for c in connections]:
                    if parent_id in results:
                        parent_outputs.append(results[parent_id])
            
            # Merge parent outputs
            if parent_outputs:
                merged = "\n\n---\n\n".join(parent_outputs)
                if child_id not in results:
                    results[child_id] = merged
                else:
                    # Append if already has content
                    results[child_id] = results[child_id] + "\n\n---\n\n" + merged
            
            # Decrement incoming count
            incoming[child_id] -= 1
            
            # Add to queue if all parents executed
            if incoming[child_id] == 0:
                queue.append(child_id)
    
    # Check if all nodes executed
    if len(executed) < len(nodes_dict):
        missing = set(nodes_dict.keys()) - executed
        logger.warning(f"Some nodes were not executed (possible cycle or disconnected): {missing}")
        return {
            "success": False,
            "final_output": None,
            "steps": step_results,
            "error": f"Cycle detected or disconnected nodes — some thoughts were lost: {missing}"
        }
    
    # Final merge of all terminal nodes (nodes with no children)
    terminal_outputs = []
    for node_id in nodes_dict:
        if node_id not in graph or not graph[node_id]:  # No children
            if node_id in results:
                terminal_outputs.append(results[node_id])
    
    if terminal_outputs:
        final_output = "\n\n=== FINAL SYNTHESIS ===\n\n".join(terminal_outputs)
    else:
        # Fallback: use last executed node's output
        if step_results:
            final_output = step_results[-1]["output"]
        else:
            final_output = initial_context
    
    return {
        "success": True,
        "final_output": final_output,
        "steps": step_results,
        "error": None
    }


def is_linear_chain(connections: List[List[str]], node_count: int) -> bool:
    """
    Check if a chain is linear (no branches/merges).
    
    Args:
        connections: List of [from_id, to_id] pairs
        node_count: Total number of nodes
    
    Returns:
        True if chain is linear, False otherwise
    """
    if not connections:
        return True  # Empty connections = linear by default
    
    if len(connections) != node_count - 1:
        return False  # Non-linear if not exactly n-1 edges
    
    # Check for branches (multiple edges from same node)
    from_counts = {}
    for from_id, _ in connections:
        from_counts[from_id] = from_counts.get(from_id, 0) + 1
        if from_counts[from_id] > 1:
            return False  # Branch detected
    
    # Check for merges (multiple edges to same node)
    to_counts = {}
    for _, to_id in connections:
        to_counts[to_id] = to_counts.get(to_id, 0) + 1
        if to_counts[to_id] > 1:
            return False  # Merge detected
    
    return True

