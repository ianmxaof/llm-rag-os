"""
Cognitive IDE - Chain Editor Component
Phase 4.1: Visual Graph Editor with Drag-and-Drop Nodes
"""

import streamlit as st
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import logging
import uuid

# Try to import streamlit-agraph for graph visualization
try:
    from streamlit_agraph import agraph, Node, Edge, Config
    HAS_AGRAPH = True
except ImportError:
    HAS_AGRAPH = False
    st.warning("streamlit-agraph not installed. Install with: pip install streamlit-agraph")

logger = logging.getLogger(__name__)

# Directory structure
CHAINS_DIR = Path("prompts/chains")
SACRED_DIR = CHAINS_DIR / "sacred"
CUSTOM_DIR = CHAINS_DIR / "custom"
DATA_DIR = Path("data")
SESSION_FILE = DATA_DIR / "chain_session.json"

# Ensure directories exist
SACRED_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Node templates for auto-population
NODE_TEMPLATES = [
    {
        "description": "Entropy Audit",
        "prompt": """Conduct a ruthless entropy audit on this context.

Identify every:
- Decaying assumption
- Outdated belief  
- Hidden risk
- Cognitive friction point

Rate each 1-10 for "how quietly it's killing the outcome."

Output ONLY the top 3 highest-scoring entropy sources.
One lethal sentence each.""",
        "temperature": 0.05,
        "rag_k": 25
    },
    {
        "description": "Leverage Matrix",
        "prompt": """Using the analysis above, create a 2×2 matrix:

X-axis: Effort (low → high)
Y-axis: Impact (low → high)

Place each item in the correct quadrant.

Then write ONE surgical action that moves the highest-impact item forward.

End with the single move that obsoletes all others.""",
        "temperature": 0.0,
        "rag_k": 30
    },
    {
        "description": "First Principles Decomposition",
        "prompt": """Break down the context to first principles.

For each element, ask:
1. What is the foundational truth?
2. What assumptions can we strip away?
3. What remains when everything removable is removed?

Output the irreducible core in 3 bullet points.""",
        "temperature": 0.1,
        "rag_k": 20
    }
]


def calculate_combo_score(steps: List[Dict], connections: List[List[str]] = None, context: str = "") -> int:
    """
    Calculate combo score (20-100) based on chain quality with context awareness.
    
    Dimensions:
    1. Structural quality (up to 50 points)
    2. Precision rewards (up to 25 points)
    3. Contextual resonance (up to 30 points)
    4. Prompt quality (up to 15 points)
    """
    if not steps:
        return 0
    
    score = 20  # Baseline: any chain starts at 20%
    
    # === 1. STRUCTURAL QUALITY (up to 50 points) ===
    node_count = len(steps)
    
    # Optimal range: 2-5 nodes for focused chains
    if 2 <= node_count <= 5:
        score += 30
    elif node_count == 1:
        score += 15  # Single node is okay
    elif node_count > 5:
        # Gentle penalty for bloat
        score += max(10, 30 - (node_count - 5) * 3)
    
    # Topology bonus (non-linear is sophisticated)
    if connections:
        expected = node_count - 1  # Linear chain
        actual = len(connections)
        if actual > expected:
            # Reward branches/merges
            score += min(20, (actual - expected) * 5)
    
    # === 2. PRECISION REWARDS (up to 25 points) ===
    temps = [s.get("temperature", 0.7) for s in steps]
    rag_ks = [s.get("rag_k", 8) for s in steps]
    
    # Reward temperature extremes (decisive thinking)
    if any(t <= 0.1 for t in temps):
        score += 15  # Has ultra-precise node
    if any(t >= 0.8 for t in temps):
        score += 5   # Has creative node
    
    # Reward deep retrieval
    if any(k >= 20 for k in rag_ks):
        score += 10
    elif any(k >= 15 for k in rag_ks):
        score += 5
    
    # === 3. CONTEXTUAL RESONANCE (up to 30 points) ===
    # This makes the meter "breathe" with the conversation
    if context and steps:
        try:
            # Simple keyword overlap (upgrade to embeddings later)
            context_words = set(context.lower().split())
            
            chain_text = " ".join([
                s.get("description", "") + " " + s.get("prompt", "")
                for s in steps
            ]).lower()
            
            chain_words = set(chain_text.split())
            
            # Jaccard similarity
            overlap = len(context_words & chain_words)
            union = len(context_words | chain_words)
            
            if union > 0:
                similarity = overlap / union
                score += int(similarity * 30)  # Up to +30 for perfect alignment
        except:
            score += 5  # Fallback if context analysis fails
    else:
        score += 5  # No context? Give baseline
    
    # === 4. PROMPT QUALITY (up to 15 points) ===
    # Reward concise, lethal prompts
    total_prompt_length = sum(len(s.get("prompt", "")) for s in steps)
    avg_prompt_length = total_prompt_length / len(steps)
    
    if avg_prompt_length < 250:  # Concise and surgical
        score += 15
    elif avg_prompt_length < 500:
        score += 8
    else:
        score += 3
    
    # Clamp to [20, 100]
    return min(100, max(20, int(score)))


def get_llm_function() -> Callable:
    """
    Adapter to connect chain IDE to existing LLM function.
    Returns a function that matches the expected signature: (prompt, temperature, rag_k) -> str
    """
    def llm_wrapper(prompt: str, temperature: float, rag_k: int) -> str:
        """Wrapper to call existing LLM function"""
        try:
            from src import rag_utils
            from scripts.config import config
            
            selected_model = st.session_state.get("selected_model", config.OLLAMA_CHAT_MODEL)
            
            result = rag_utils.answer_question(
                question=prompt,
                k=rag_k,
                raw_mode=False,
                rag_threshold=0.25,
                model=selected_model
            )
            
            return result.get('response', '')
        except Exception as e:
            logger.error(f"LLM call failed in chain editor: {e}")
            raise
    
    return llm_wrapper


def auto_save_session(chain_name: str, steps: List[Dict], connections: List[List[str]] = None):
    """Automatically save current work to temp file"""
    try:
        temp_save = {
            "chain_name": chain_name,
            "steps": steps,
            "connections": connections or [],
            "last_saved": datetime.now().isoformat()
        }
        
        SESSION_FILE.write_text(json.dumps(temp_save, indent=2))
    except Exception as e:
        logger.error(f"Failed to auto-save session: {e}")


def restore_session() -> Optional[Dict]:
    """Restore last session on page load"""
    if not SESSION_FILE.exists():
        return None
    
    try:
        data = json.loads(SESSION_FILE.read_text())
        
        # Only restore if less than 1 hour old
        last_saved = datetime.fromisoformat(data["last_saved"])
        if datetime.now() - last_saved < timedelta(hours=1):
            return data
    except Exception as e:
        logger.error(f"Failed to restore session: {e}")
    
    return None


def load_chains_from_dirs() -> Dict[str, Path]:
    """Load all chains from sacred and custom directories"""
    chains = {}
    
    # Load sacred chains
    if SACRED_DIR.exists():
        for f in SACRED_DIR.glob("*.yaml"):
            chains[f"✨ {f.stem}"] = f
    
    # Also check root chains directory for backward compatibility
    for f in CHAINS_DIR.glob("*.yaml"):
        if f.parent == CHAINS_DIR:  # Only root level files
            chains[f"✨ {f.stem}"] = f
    
    # Load custom chains
    if CUSTOM_DIR.exists():
        for f in CUSTOM_DIR.glob("*.yaml"):
            chains[f.stem] = f
    
    return chains


def render_graph_canvas(nodes_dict: Dict[str, Dict], connections: List[List[str]]) -> Optional[str]:
    """
    Render interactive graph using streamlit-agraph.
    Returns the ID of the clicked node, or None.
    """
    if not HAS_AGRAPH:
        return None
    
    if not nodes_dict:
        st.info("Add nodes to see the graph")
        return None
    
    # Convert nodes to agraph format
    graph_nodes = []
    graph_edges = []
    
    # Create nodes
    for node_id, node in nodes_dict.items():
        desc = node.get('description', 'Node')[:30]
        temp = node.get('temperature', 0.7)
        rag_k = node.get('rag_k', 8)
        
        # Color by temperature
        if temp <= 0.15:
            color = "#8b5cf6"  # Purple for precise
        elif temp >= 0.8:
            color = "#06b6d4"  # Cyan for creative
        else:
            color = "#10b981"  # Green for medium
        
        graph_nodes.append(Node(
            id=node_id,
            label=f"{desc}\ntemp={temp}",
            size=25,
            color=color,
            font={"size": 12}
        ))
    
    # Create edges
    if connections:
        for conn in connections:
            if len(conn) == 2 and conn[0] in nodes_dict and conn[1] in nodes_dict:
                graph_edges.append(Edge(
                    source=conn[0],
                    target=conn[1],
                    color="#00ff88",
                    width=2,
                    arrows="to"
                ))
    else:
        # Default linear connections if none specified
        node_ids = sorted(nodes_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0)
        for i in range(len(node_ids) - 1):
            graph_edges.append(Edge(
                source=node_ids[i],
                target=node_ids[i+1],
                color="#00ff88",
                width=2,
                arrows="to"
            ))
    
    # Configure graph
    config = Config(
        width=1200,
        height=700,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#ff0000",
        collapsible=False,
        node={"labelProperty": "label"},
        link={"labelProperty": "label", "renderLabel": False}
    )
    
    # Render graph and get selected node
    selected = agraph(nodes=graph_nodes, edges=graph_edges, config=config)
    return selected


def suggest_connections(nodes_dict: Dict[str, Dict], existing_connections: List[List[str]]) -> List[Dict]:
    """
    Suggest high-leverage connections between nodes based on semantic patterns.
    Returns list of suggestions with from, to, reason, and boost percentage.
    """
    if len(nodes_dict) < 2:
        return []
    
    suggestions = []
    node_list = list(nodes_dict.items())
    
    # Hard-coded sacred synergies (expand forever)
    synergy_map = {
        "entropy": ["leverage", "matrix", "compress", "synthesis"],
        "first principles": ["leverage", "critical path", "compress"],
        "leverage matrix": ["synthesis", "compress", "action"],
        "critical path": ["action", "execute", "compress"],
        "decay": ["renewal", "update", "refresh"],
        "assumption": ["verify", "test", "validate"],
        "extract": ["analyze", "synthesize", "compress"],
        "analyze": ["synthesize", "compress", "action"],
    }
    
    # Check each node pair for synergies
    for i, (from_id, from_node) in enumerate(node_list):
        from_desc = from_node.get("description", "").lower()
        
        for trigger, targets in synergy_map.items():
            if trigger in from_desc:
                for j, (to_id, to_node) in enumerate(node_list):
                    if i != j:
                        to_desc = to_node.get("description", "").lower()
                        
                        # Check if target matches
                        if any(target in to_desc for target in targets):
                            # Check if connection already exists
                            conn_exists = any(
                                conn[0] == from_id and conn[1] == to_id 
                                for conn in existing_connections
                            )
                            
                            if not conn_exists:
                                # Calculate boost
                                boost = 18
                                if "compress" in to_desc or "synthesis" in to_desc:
                                    boost += 12  # Extra boost for compression/synthesis
                                
                                suggestions.append({
                                    "from": from_id,
                                    "to": to_id,
                                    "from_desc": from_node.get("description", ""),
                                    "to_desc": to_node.get("description", ""),
                                    "reason": f"High-leverage flow: {from_node.get('description', '')[:30]} → {to_node.get('description', '')[:30]}",
                                    "boost": boost
                                })
    
    # Sort by boost and return top 3
    suggestions.sort(key=lambda x: x["boost"], reverse=True)
    return suggestions[:3]


def render_enhanced_combo_meter(score: int, conversation_context: str = ""):
    """Render beautiful, animated combo meter with context-aware feedback"""
    
    # Determine tier and styling
    if score >= 95:
        tier = "S-TIER"
        color = "#00ff88"
        message = "Reality-bending expected"
        emoji = "⚡"
        glow = "20px"
    elif score >= 80:
        tier = "A-TIER"
        color = "#06b6d4"
        message = "Professional grade"
        emoji = "🔥"
        glow = "15px"
    elif score >= 60:
        tier = "B-TIER"
        color = "#ffaa00"
        message = "Solid foundation"
        emoji = "💪"
        glow = "10px"
    else:
        tier = "BUILDING"
        color = "#ff4400"
        message = "Keep refining..."
        emoji = "🔨"
        glow = "5px"
    
    # Animated bar
    filled = int(score / 5)
    bar = "█" * filled + "░" * (20 - filled)
    
    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 12px;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
        border: 2px solid {color};
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 0 {glow} {color}40;
        animation: pulse 2s ease-in-out infinite;
    ">
        <style>
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.01); }}
        }}
        </style>
        <h2 style="color: {color}; margin: 0; font-size: 0.9em;">
            {emoji} COMBO METER {emoji}
        </h2>
        <h1 style="
            color: {color};
            font-size: 1.5em;
            margin: 8px 0;
            text-shadow: 0 0 5px {color};
            font-family: monospace;
        ">
            {bar}<br/>{score}%
        </h1>
        <h3 style="color: {color}; margin: 4px 0; font-size: 1em;">
            {tier}
        </h3>
        <p style="color: #999; font-size: 0.85em; margin-top: 4px;">
            {message}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Celebration for S-tier
    if score >= 95:
        st.balloons()


def generate_mermaid_diagram(steps: List[Dict], connections: Optional[List[List[str]]] = None) -> str:
    """Generate Mermaid diagram code from chain steps"""
    if not steps:
        return "graph LR\n    Start[Start]"
    
    mermaid = "graph LR\n"
    
    # Generate nodes
    for i, step in enumerate(steps):
        desc = step.get('description', f'Step {i+1}').replace('"', "'")[:30]
        temp = step.get('temperature', 0.7)
        mermaid += f'    S{i}["{desc}\\n(temp={temp})"]\n'
    
    # Generate edges
    if connections:
        # Use explicit connections
        for conn in connections:
            if len(conn) == 2:
                from_idx = int(conn[0]) if conn[0].isdigit() else 0
                to_idx = int(conn[1]) if conn[1].isdigit() else 0
                if 0 <= from_idx < len(steps) and 0 <= to_idx < len(steps):
                    mermaid += f"    S{from_idx} --> S{to_idx}\n"
    else:
        # Linear chain (default)
        for i in range(len(steps) - 1):
            mermaid += f"    S{i} --> S{i+1}\n"
    
    # Style start node
    if steps:
        mermaid += "    style S0 fill:#f9f,stroke:#333\n"
    
    return mermaid


def render_chain_editor():
    """Main chain editor component"""
    st.markdown("<h1 style='text-align:center; max-width:1200px; margin:0 auto;'>⚡ Cognitive IDE - Chain Editor</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888; max-width:1200px; margin:0 auto;'>Build superhuman reasoning chains visually</p>", unsafe_allow_html=True)
    
    # Initialize session state
    if "chain_editor_nodes" not in st.session_state:
        st.session_state.chain_editor_nodes = {}
        st.session_state.chain_editor_connections = []
        st.session_state.chain_editor_name = "Untitled Chain"
        
        # Try to restore session
        restored = restore_session()
        if restored:
            st.session_state.chain_editor_name = restored.get("chain_name", "Untitled Chain")
            steps = restored.get("steps", [])
            st.session_state.chain_editor_nodes = {str(i): s for i, s in enumerate(steps)}
            st.session_state.chain_editor_connections = restored.get("connections", [])
            st.info("Restored unsaved work from last session")
    
    # Tabs for editor and marketplace
    tab1, tab2 = st.tabs(["Editor", "Marketplace"])
    
    with tab1:
        render_chain_editor_content()
    
    with tab2:
        from src.components.marketplace import render_marketplace
        render_marketplace()


def render_chain_editor_content():
    """Main chain editor content (separated for tab organization)"""
    # Sidebar: Chain Library
    with st.sidebar:
        st.subheader("Chain Library")
        
        # Load available chains
        all_chains = load_chains_from_dirs()
        
        chain_options = ["[New Chain]"] + list(all_chains.keys())
        selected_chain = st.selectbox(
            "Select Chain",
            chain_options,
            key="chain_selector"
        )
        
        if selected_chain != "[New Chain]":
            if st.button("Load Chain", key="load_chain_btn"):
                chain_path = all_chains[selected_chain]
                try:
                    chain_data = yaml.safe_load(chain_path.read_text(encoding='utf-8'))
                    st.session_state.chain_editor_name = chain_data.get("name", chain_path.stem)
                    steps = chain_data.get("steps", [])
                    st.session_state.chain_editor_nodes = {str(i): s for i, s in enumerate(steps)}
                    st.session_state.chain_editor_connections = chain_data.get("connections", [])
                    st.success(f"Loaded {selected_chain}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load chain: {e}")
        
        if st.button("New Chain", key="new_chain_btn"):
            st.session_state.chain_editor_nodes = {}
            st.session_state.chain_editor_connections = []
            st.session_state.chain_editor_name = "Untitled Chain"
            st.rerun()
    
    # View mode toggle
    view_mode = st.radio(
        "View Mode",
        ["Graph View", "List View"],
        horizontal=True,
        key="chain_view_mode"
    )
    
    # Main editor area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chain name editor
        chain_name = st.text_input(
            "Chain Name",
            value=st.session_state.chain_editor_name,
            key="chain_name_input"
        )
        st.session_state.chain_editor_name = chain_name
        
        # Graph or List view
        if view_mode == "Graph View" and HAS_AGRAPH:
            st.markdown("### Visual Graph")
            selected_node_id = render_graph_canvas(
                st.session_state.chain_editor_nodes,
                st.session_state.chain_editor_connections
            )
            
            if selected_node_id and selected_node_id in st.session_state.chain_editor_nodes:
                st.session_state.selected_node_for_edit = selected_node_id
        else:
            if view_mode == "Graph View" and not HAS_AGRAPH:
                st.warning("Install streamlit-agraph for graph view: pip install streamlit-agraph")
            
            # Steps editor (List View)
            st.markdown("### Chain Steps")
        
        # Convert nodes dict to list for editing
        node_list = []
        for node_id in sorted(st.session_state.chain_editor_nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            node_list.append((node_id, st.session_state.chain_editor_nodes[node_id]))
        
        # Display and edit steps
        # If a node is selected from graph, show it first
        selected_for_edit = st.session_state.get("selected_node_for_edit")
        
        for idx, (node_id, step) in enumerate(node_list):
            is_selected = (selected_for_edit == node_id) if selected_for_edit else False
            with st.expander(
                f"Step {idx+1}: {step.get('description', 'No description')}", 
                expanded=is_selected or not selected_for_edit
            ):
                desc = st.text_input(
                    "Description",
                    value=step.get("description", ""),
                    key=f"desc_{node_id}"
                )
                prompt = st.text_area(
                    "Prompt",
                    value=step.get("prompt", ""),
                    height=150,
                    key=f"prompt_{node_id}"
                )
                
                col_temp, col_rag = st.columns(2)
                with col_temp:
                    temp = st.slider(
                        "Temperature",
                        0.0, 1.0,
                        step.get("temperature", 0.7),
                        0.05,
                        key=f"temp_{node_id}"
                    )
                with col_rag:
                    rag_k = st.number_input(
                        "RAG-k",
                        1, 50,
                        step.get("rag_k", 8),
                        key=f"ragk_{node_id}"
                    )
                
                col_refine, col_delete = st.columns(2)
                with col_refine:
                    if st.button("AI Refine", key=f"refine_{node_id}"):
                        with st.spinner("Refining prompt..."):
                            try:
                                llm_fn = get_llm_function()
                                refine_prompt = f"Make this prompt more precise and lethal in <40 words:\n\n{prompt}"
                                refined = llm_fn(refine_prompt, temperature=0.1, rag_k=5)
                                # Update the prompt
                                step["prompt"] = refined
                                st.session_state.chain_editor_nodes[node_id] = step
                                st.success("Refined!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Refinement failed: {e}")
                
                with col_delete:
                    if st.button("Delete", key=f"delete_{node_id}"):
                        del st.session_state.chain_editor_nodes[node_id]
                        # Reindex nodes
                        new_nodes = {}
                        for i, (_, node) in enumerate(sorted(st.session_state.chain_editor_nodes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)):
                            new_nodes[str(i)] = node
                        st.session_state.chain_editor_nodes = new_nodes
                        st.rerun()
                
                # Update step data
                st.session_state.chain_editor_nodes[node_id] = {
                    "description": desc,
                    "prompt": prompt,
                    "temperature": temp,
                    "rag_k": int(rag_k)
                }
        
        # Add step button and connection management
        col_add, col_conn = st.columns(2)
        with col_add:
            if st.button("➕ Add Node", key="add_step_btn"):
                node_count = len(st.session_state.chain_editor_nodes)
                # Alternate between templates
                template = NODE_TEMPLATES[node_count % len(NODE_TEMPLATES)]
                
                new_id = str(uuid.uuid4())[:8]
                st.session_state.chain_editor_nodes[new_id] = {
                    "description": template["description"],
                    "prompt": template["prompt"],
                    "temperature": template["temperature"],
                    "rag_k": template["rag_k"]
                }
                
                # Auto-connect to previous node if exists
                if node_count > 0:
                    prev_ids = sorted(st.session_state.chain_editor_nodes.keys(), 
                                     key=lambda x: int(x) if x.isdigit() else 0)
                    if prev_ids:
                        prev_id = prev_ids[-1]
                        new_conn = [prev_id, new_id]
                        if new_conn not in st.session_state.chain_editor_connections:
                            st.session_state.chain_editor_connections.append(new_conn)
                
                auto_save_session(
                    st.session_state.chain_editor_name,
                    list(st.session_state.chain_editor_nodes.values()),
                    st.session_state.chain_editor_connections
                )
                st.rerun()
        
        with col_conn:
            if st.button("🔗 Manage Connections", key="manage_conn_btn"):
                st.session_state.show_connection_manager = True
        
        # AI Suggestions
        if len(st.session_state.chain_editor_nodes) >= 2:
            suggestions = suggest_connections(
                st.session_state.chain_editor_nodes,
                st.session_state.chain_editor_connections
            )
            
            if suggestions:
                st.markdown("### AI Suggested Connections")
                for sug in suggestions:
                    col_desc, col_apply = st.columns([4, 1])
                    with col_desc:
                        st.markdown(f"**{sug['reason']}** (+{sug['boost']}% combo)")
                    with col_apply:
                        if st.button("Apply", key=f"apply_sug_{sug['from']}_{sug['to']}"):
                            new_conn = [sug['from'], sug['to']]
                            if new_conn not in st.session_state.chain_editor_connections:
                                st.session_state.chain_editor_connections.append(new_conn)
                                st.success(f"Connected: {sug['from_desc'][:20]} → {sug['to_desc'][:20]}")
                                st.rerun()
        
        # Connection manager
        if st.session_state.get("show_connection_manager", False):
            st.markdown("### Manage Connections")
            node_ids = list(st.session_state.chain_editor_nodes.keys())
            if len(node_ids) >= 2:
                col_from, col_to, col_add_conn = st.columns([2, 2, 1])
                with col_from:
                    from_node = st.selectbox("From", node_ids, key="conn_from", format_func=lambda x: st.session_state.chain_editor_nodes[x].get('description', x))
                with col_to:
                    to_node = st.selectbox("To", node_ids, key="conn_to", format_func=lambda x: st.session_state.chain_editor_nodes[x].get('description', x))
                with col_add_conn:
                    if st.button("Add", key="add_conn_btn"):
                        new_conn = [from_node, to_node]
                        if new_conn not in st.session_state.chain_editor_connections:
                            st.session_state.chain_editor_connections.append(new_conn)
                            st.success("Connection added")
                            st.rerun()
                
                # Show existing connections
                st.markdown("**Existing Connections:**")
                for i, conn in enumerate(st.session_state.chain_editor_connections):
                    from_desc = st.session_state.chain_editor_nodes.get(conn[0], {}).get('description', conn[0])
                    to_desc = st.session_state.chain_editor_nodes.get(conn[1], {}).get('description', conn[1])
                    col_display, col_del = st.columns([4, 1])
                    with col_display:
                        st.write(f"{from_desc} → {to_desc}")
                    with col_del:
                        if st.button("Delete", key=f"del_conn_{i}"):
                            st.session_state.chain_editor_connections.remove(conn)
                            st.rerun()
            else:
                st.info("Add at least 2 nodes to create connections")
            
            if st.button("Close", key="close_conn_mgr"):
                st.session_state.show_connection_manager = False
                st.rerun()
        
        # Auto-save
        steps_list = list(st.session_state.chain_editor_nodes.values())
        auto_save_session(
            st.session_state.chain_editor_name,
            steps_list,
            st.session_state.chain_editor_connections
        )
    
    with col2:
        # Combo Meter
        steps_list = list(st.session_state.chain_editor_nodes.values())
        
        # Get conversation context from chat history
        conversation_context = ""
        if hasattr(st.session_state, 'chat_history') and st.session_state.chat_history:
            conversation_context = " ".join([
                msg.get('question', msg.get('content', ''))
                for msg in st.session_state.chat_history[-5:]
            ])
        
        score = calculate_combo_score(
            steps_list, 
            st.session_state.chain_editor_connections,
            conversation_context
        )
        
        render_enhanced_combo_meter(score, conversation_context)
        
        # Mermaid Preview
        if steps_list:
            st.markdown("### Live Diagram")
            mermaid_code = generate_mermaid_diagram(steps_list, st.session_state.chain_editor_connections)
            st.markdown(f"```mermaid\n{mermaid_code}\n```")
        
        # Save and Execute buttons
        st.markdown("---")
        
        col_save, col_exec = st.columns(2)
        with col_save:
            if st.button("💾 Save Chain", type="primary", use_container_width=True):
                try:
                    chain_data = {
                        "name": chain_name,
                        "description": f"Chain created in Cognitive IDE",
                        "version": "1.0",
                        "settings": {
                            "default_temperature": 0.7,
                            "default_rag_k": 8
                        },
                        "steps": steps_list,
                        "connections": st.session_state.chain_editor_connections,
                        "metadata": {
                            "created": datetime.now().isoformat(),
                            "author": "cognitive_ide",
                            "tags": []
                        }
                    }
                    
                    chain_filename = chain_name.replace(" ", "_").replace("/", "_")
                    chain_path = CUSTOM_DIR / f"{chain_filename}.yaml"
                    chain_path.write_text(yaml.dump(chain_data, default_flow_style=False, sort_keys=False), encoding='utf-8')
                    st.success(f"Saved to {chain_path.name}")
                    
                    # Clear session file
                    if SESSION_FILE.exists():
                        SESSION_FILE.unlink()
                except Exception as e:
                    st.error(f"Failed to save chain: {e}")
        
        with col_exec:
            if st.button("🚀 Execute", use_container_width=True, disabled=len(steps_list) == 0):
                st.session_state.chain_execute_mode = True
        
        # Publish to Marketplace button
        if st.button("📤 Publish to Marketplace", use_container_width=True, disabled=len(steps_list) == 0):
            st.session_state.show_publish_dialog = True
        
        # Publish dialog
        if st.session_state.get("show_publish_dialog", False):
            st.markdown("### Publish to Marketplace")
            author_name = st.text_input("Your name", value="Anonymous", key="publish_author")
            
            col_pub, col_cancel = st.columns(2)
            with col_pub:
                if st.button("Publish", type="primary", key="publish_confirm"):
                    try:
                        from src.components.marketplace import publish_to_marketplace
                        
                        chain_data = {
                            "name": chain_name,
                            "description": f"Chain created in Cognitive IDE",
                            "version": "1.0",
                            "settings": {
                                "default_temperature": 0.7,
                                "default_rag_k": 8
                            },
                            "steps": steps_list,
                            "connections": st.session_state.chain_editor_connections,
                            "metadata": {
                                "created": datetime.now().isoformat(),
                                "author": author_name,
                                "tags": []
                            }
                        }
                        
                        combo_score = publish_to_marketplace(chain_data, author_name)
                        if combo_score is not None:
                            st.success(f"Published! Combo score: {combo_score}%")
                            st.balloons()
                            st.session_state.show_publish_dialog = False
                            st.rerun()
                        else:
                            st.error("Failed to publish chain")
                    except Exception as e:
                        st.error(f"Publishing failed: {e}")
            
            with col_cancel:
                if st.button("Cancel", key="publish_cancel"):
                    st.session_state.show_publish_dialog = False
                    st.rerun()
    
    # Execution area
    if st.session_state.get("chain_execute_mode", False):
        st.markdown("---")
        st.markdown("### Execute Chain")
        
        context_input = st.text_area(
            "Input context for execution",
            height=150,
            value="What should I do with my life?",
            key="exec_context_input"
        )
        
        if st.button("Run Chain", type="primary", key="run_chain_btn"):
            try:
                from src.app.utils.prompt_chains import execute_chain
                
                # Filter out hidden nodes for execution
                execution_steps = [s for s in steps_list if not s.get("hidden", False)]
                
                chain_config = {
                    "name": chain_name,
                    "steps": execution_steps,
                    "connections": st.session_state.chain_editor_connections,
                    "settings": {
                        "default_temperature": 0.7,
                        "default_rag_k": 8
                    }
                }
                
                llm_fn = get_llm_function()
                
                # Execute with progress display
                execution_container = st.container()
                with execution_container:
                    st.markdown("### Execution Log")
                    
                    step_placeholders = {}
                    
                    def debug_callback(step_result):
                        """Update UI for each step"""
                        step_num = step_result['step_number']
                        
                        if step_num not in step_placeholders:
                            step_placeholders[step_num] = st.expander(
                                f"Step {step_result['step_number']}: {step_result['description']}",
                                expanded=True
                            )
                        
                        with step_placeholders[step_num]:
                            st.caption("Input:")
                            st.code(step_result['input'][:200] + '...' if len(step_result['input']) > 200 else step_result['input'])
                            
                            if step_result['success']:
                                st.caption("Output:")
                                st.markdown(step_result['output'])
                                st.success("✓ Step completed")
                            else:
                                st.error(f"❌ {step_result['error']}")
                    
                    result = execute_chain(
                        chain_config=chain_config,
                        initial_input=context_input,
                        llm_function=llm_fn,
                        debug_callback=debug_callback
                    )
                    
                    if result['success']:
                        st.markdown("### Final Output")
                        st.markdown(result['final_output'])
                        st.balloons()
                        
                        # Check for resonance tracking (if chain was imported)
                        if st.session_state.get("imported_chain_id"):
                            st.markdown("---")
                            st.markdown("### Resonance")
                            if st.button("✨ This chain changed my thinking (resonance)", 
                                        key="resonance_btn", 
                                        use_container_width=True):
                                from src.components.marketplace import track_resonance_event
                                if track_resonance_event(st.session_state.imported_chain_id):
                                    st.balloons()
                                    st.success("Thank you! Your resonance has been recorded.")
                                else:
                                    st.error("Failed to record resonance")
                    else:
                        st.error(f"Chain failed: {result['error']}")
                
                st.session_state.chain_execute_mode = False
            except Exception as e:
                st.error(f"Execution failed: {e}")
                logger.error(f"Chain execution error: {e}")

