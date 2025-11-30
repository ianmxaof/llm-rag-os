"""
Chain Marketplace Component
Phase 4.4: Browse, import, and publish chains
"""

import streamlit as st
import yaml
import json
import requests
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Marketplace configuration
MARKETPLACE_DIR = Path("prompts")
MARKETPLACE_FILE = MARKETPLACE_DIR / "marketplace.json"
CHAINS_DIR = Path("prompts/chains")
SACRED_DIR = CHAINS_DIR / "sacred"
CUSTOM_DIR = CHAINS_DIR / "custom"

# Remote marketplace URL (optional, for future)
MARKETPLACE_URL = "https://raw.githubusercontent.com/powercore-mind/marketplace/main/chains.json"

# Ensure directories exist
MARKETPLACE_DIR.mkdir(parents=True, exist_ok=True)
SACRED_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)


def calculate_chain_combo_score(chain_data: Dict) -> int:
    """Calculate combo score for a chain"""
    from src.components.chain_editor import calculate_combo_score
    
    steps = chain_data.get("steps", [])
    connections = chain_data.get("connections", [])
    
    return calculate_combo_score(steps, connections)


def fetch_marketplace() -> Dict:
    """Fetch marketplace data (chains and authors) from local or remote"""
    marketplace_data = {
        "chains": [],
        "authors": {}
    }
    
    # Try remote first (if available)
    try:
        resp = requests.get(MARKETPLACE_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            marketplace_data["chains"] = data.get("chains", [])
            marketplace_data["authors"] = data.get("authors", {})
            logger.info(f"Loaded {len(marketplace_data['chains'])} chains from remote marketplace")
            return marketplace_data
    except Exception as e:
        logger.debug(f"Remote marketplace unavailable: {e}")
    
    # Fallback to local marketplace
    if MARKETPLACE_FILE.exists():
        try:
            data = json.loads(MARKETPLACE_FILE.read_text())
            marketplace_data["chains"] = data.get("chains", [])
            marketplace_data["authors"] = data.get("authors", {})
            logger.info(f"Loaded {len(marketplace_data['chains'])} chains from local marketplace")
        except Exception as e:
            logger.error(f"Failed to load local marketplace: {e}")
    
    return marketplace_data


def bootstrap_marketplace() -> List[Dict]:
    """Bootstrap marketplace with existing sacred chains"""
    chains = []
    
    # Load all sacred chains
    for chain_file in SACRED_DIR.glob("*.yaml"):
        try:
            chain_data = yaml.safe_load(chain_file.read_text(encoding='utf-8'))
            if chain_data:
                combo_score = calculate_chain_combo_score(chain_data)
                
                chain_id = get_chain_id(chain_data.get("name", chain_file.stem), str(chain_file))
                chains.append({
                    "id": chain_id,
                    "name": chain_data.get("name", chain_file.stem),
                    "description": chain_data.get("description", "No description"),
                    "author": chain_data.get("metadata", {}).get("author", "powercore"),
                    "uses": 0,
                    "resonance_count": 0,
                    "combo": combo_score,
                    "url": str(chain_file),  # Local path
                    "created": chain_data.get("metadata", {}).get("created", datetime.now().isoformat()),
                    "tags": chain_data.get("metadata", {}).get("tags", []),
                    "steps_count": len(chain_data.get("steps", [])),
                    "local": True,
                    "chain_data": chain_data
                })
        except Exception as e:
            logger.error(f"Failed to load chain {chain_file}: {e}")
    
    # Also check custom chains
    for chain_file in CUSTOM_DIR.glob("*.yaml"):
        try:
            chain_data = yaml.safe_load(chain_file.read_text(encoding='utf-8'))
            if chain_data:
                combo_score = calculate_chain_combo_score(chain_data)
                
                chain_id = get_chain_id(chain_data.get("name", chain_file.stem), str(chain_file))
                chains.append({
                    "id": chain_id,
                    "name": chain_data.get("name", chain_file.stem),
                    "description": chain_data.get("description", "No description"),
                    "author": chain_data.get("metadata", {}).get("author", "Anonymous"),
                    "uses": 0,
                    "resonance_count": 0,
                    "combo": combo_score,
                    "url": str(chain_file),
                    "created": chain_data.get("metadata", {}).get("created", datetime.now().isoformat()),
                    "tags": chain_data.get("metadata", {}).get("tags", []),
                    "steps_count": len(chain_data.get("steps", [])),
                    "local": True,
                    "chain_data": chain_data
                })
        except Exception as e:
            logger.error(f"Failed to load chain {chain_file}: {e}")
    
    return chains


def save_marketplace(chains: List[Dict], authors: Optional[Dict] = None):
    """Save marketplace index to local file"""
    try:
        marketplace_data = {
            "chains": chains,
            "authors": authors or {},
            "last_updated": datetime.now().isoformat()
        }
        MARKETPLACE_FILE.write_text(json.dumps(marketplace_data, indent=2))
        logger.info(f"Saved {len(chains)} chains to marketplace")
    except Exception as e:
        logger.error(f"Failed to save marketplace: {e}")


def import_chain(chain_info: Dict) -> bool:
    """
    Import a chain from marketplace to custom directory.
    Also loads chain into editor session state if available.
    
    Returns:
        True if imported successfully
    """
    try:
        chain_url = chain_info.get("url")
        if not chain_url:
            return False
        
        # Use chain_data if available (from marketplace), otherwise load from file
        chain_data = chain_info.get("chain_data")
        
        # If it's a local path, copy it
        if chain_info.get("local", False):
            source_path = Path(chain_url)
            if source_path.exists():
                # Load chain data if not already provided
                if not chain_data:
                    chain_data = yaml.safe_load(source_path.read_text(encoding='utf-8'))
                
                # Copy to custom directory
                target_path = CUSTOM_DIR / source_path.name
                import shutil
                shutil.copy2(source_path, target_path)
                logger.info(f"Imported chain from {source_path} to {target_path}")
                
                # Load into editor if chain_data is available
                if chain_data and hasattr(st, 'session_state'):
                    # Remove hidden resonance node for editing
                    steps = [s for s in chain_data.get("steps", []) if not s.get("hidden", False)]
                    
                    st.session_state.chain_editor_nodes = {str(i): step for i, step in enumerate(steps)}
                    st.session_state.chain_editor_connections = chain_data.get("connections", [])
                    st.session_state.chain_editor_name = chain_data.get("name", "Imported Chain")
                    
                    # Store chain ID for resonance tracking
                    chain_id = chain_info.get("id")
                    if chain_id:
                        st.session_state.imported_chain_id = chain_id
                
                return True
            else:
                logger.warning(f"Source chain file not found: {source_path}")
                return False
        else:
            # Remote URL - download it
            try:
                resp = requests.get(chain_url, timeout=10)
                if resp.status_code == 200:
                    # Validate it's valid YAML
                    chain_data = yaml.safe_load(resp.text)
                    if chain_data:
                        chain_name = chain_info.get("name", "imported_chain")
                        target_path = CUSTOM_DIR / f"{chain_name.replace(' ', '_').replace('/', '_')}.yaml"
                        target_path.write_text(resp.text, encoding='utf-8')
                        logger.info(f"Imported chain from remote URL to {target_path}")
                        
                        # Load into editor
                        if hasattr(st, 'session_state'):
                            steps = [s for s in chain_data.get("steps", []) if not s.get("hidden", False)]
                            st.session_state.chain_editor_nodes = {str(i): step for i, step in enumerate(steps)}
                            st.session_state.chain_editor_connections = chain_data.get("connections", [])
                            st.session_state.chain_editor_name = chain_data.get("name", "Imported Chain")
                            
                            chain_id = chain_info.get("id")
                            if chain_id:
                                st.session_state.imported_chain_id = chain_id
                        
                        return True
            except requests.RequestException as e:
                logger.error(f"Failed to download chain from URL: {e}")
                return False
        
        return False
    except Exception as e:
        logger.error(f"Failed to import chain: {e}")
        return False


def get_chain_id(chain_name: str, chain_path: str) -> str:
    """Generate a unique chain ID"""
    return hashlib.md5(f"{chain_name}{chain_path}".encode()).hexdigest()[:12]


def track_resonance_event(chain_id: str):
    """Increment resonance counter when user types 'resonance'"""
    try:
        marketplace_data = fetch_marketplace()
        chains = marketplace_data.get("chains", [])
        authors = marketplace_data.get("authors", {})
        
        for chain in chains:
            if chain.get("id") == chain_id:
                chain["resonance_count"] = chain.get("resonance_count", 0) + 1
                
                # Update author reputation
                author = chain.get("author", "Unknown")
                if author not in authors:
                    authors[author] = {
                        "total_chains": 0,
                        "total_resonance": 0,
                        "total_uses": 0,
                        "tier": "Emerging"
                    }
                
                authors[author]["total_resonance"] = authors[author].get("total_resonance", 0) + 1
                
                # Recalculate tier
                total_res = authors[author]["total_resonance"]
                if total_res >= 100:
                    authors[author]["tier"] = "∅ Void Master"
                elif total_res >= 50:
                    authors[author]["tier"] = "S-Tier"
                elif total_res >= 20:
                    authors[author]["tier"] = "A-Tier"
                elif total_res >= 5:
                    authors[author]["tier"] = "B-Tier"
                else:
                    authors[author]["tier"] = "Emerging"
                
                break
        
        save_marketplace(chains, authors)
        return True
    except Exception as e:
        logger.error(f"Failed to track resonance event: {e}")
        return False


def get_author_reputation(author_name: str) -> Dict:
    """Calculate author reputation score"""
    marketplace_data = fetch_marketplace()
    authors = marketplace_data.get("authors", {})
    
    if author_name not in authors:
        return {
            "tier": "Unknown",
            "total_resonance": 0,
            "total_uses": 0,
            "total_chains": 0,
            "resonance_rate": 0.0
        }
    
    author_data = authors[author_name]
    
    # Calculate resonance rate
    total_uses = author_data.get("total_uses", 0)
    total_resonance = author_data.get("total_resonance", 0)
    resonance_rate = total_resonance / max(1, total_uses)
    
    return {
        "tier": author_data.get("tier", "Emerging"),
        "total_resonance": total_resonance,
        "total_uses": total_uses,
        "total_chains": author_data.get("total_chains", 0),
        "resonance_rate": resonance_rate
    }


def publish_to_marketplace(chain_data: Dict, author_name: str = "Anonymous") -> Optional[int]:
    """
    Publish a chain to the marketplace.
    
    Returns:
        Combo score if published successfully, None otherwise
    """
    try:
        # Calculate combo score
        combo_score = calculate_chain_combo_score(chain_data)
        
        # Save chain file if not already saved
        chain_name = chain_data.get("name", "Untitled Chain")
        chain_filename = chain_name.replace(" ", "_").replace("/", "_")
        chain_path = CUSTOM_DIR / f"{chain_filename}.yaml"
        
        if not chain_path.exists():
            chain_path.write_text(yaml.dump(chain_data, default_flow_style=False, sort_keys=False), encoding='utf-8')
        
        # Add hidden resonance mirror node to chain data
        resonance_node = {
            "description": "Resonance Check",
            "prompt": """If this chain delivered an insight that genuinely altered your trajectory, reply with the single word: resonance

If it was merely interesting, say nothing.

The author will never see your response—only the count.""",
            "temperature": 0.0,
            "rag_k": 0,
            "hidden": True
        }
        
        # Add resonance node to steps (for execution tracking)
        chain_data_with_resonance = chain_data.copy()
        chain_data_with_resonance["steps"] = chain_data.get("steps", []) + [resonance_node]
        
        # Save chain with resonance node
        chain_path.write_text(yaml.dump(chain_data_with_resonance, default_flow_style=False, sort_keys=False), encoding='utf-8')
        
        # Load existing marketplace
        marketplace_data = fetch_marketplace()
        marketplace_chains = marketplace_data.get("chains", [])
        authors = marketplace_data.get("authors", {})
        
        # Generate chain ID
        chain_id = get_chain_id(chain_name, str(chain_path))
        
        # Check if chain already exists
        existing_idx = None
        for i, chain in enumerate(marketplace_chains):
            if chain.get("id") == chain_id or (chain.get("name") == chain_name and chain.get("url") == str(chain_path)):
                existing_idx = i
                break
        
        # Create or update chain entry
        chain_entry = {
            "id": chain_id,
            "name": chain_name,
            "description": chain_data.get("description", "No description"),
            "author": author_name,
            "uses": marketplace_chains[existing_idx].get("uses", 0) if existing_idx is not None else 0,
            "resonance_count": marketplace_chains[existing_idx].get("resonance_count", 0) if existing_idx is not None else 0,
            "combo": combo_score,
            "url": str(chain_path),
            "created": chain_data.get("metadata", {}).get("created", datetime.now().isoformat()),
            "tags": chain_data.get("metadata", {}).get("tags", []),
            "steps_count": len(chain_data.get("steps", [])),
            "local": True,
            "chain_data": chain_data_with_resonance  # Store full chain data for import
        }
        
        if existing_idx is not None:
            marketplace_chains[existing_idx] = chain_entry
        else:
            marketplace_chains.append(chain_entry)
        
        # Update author stats
        if author_name not in authors:
            authors[author_name] = {
                "total_chains": 0,
                "total_resonance": 0,
                "total_uses": 0,
                "tier": "Emerging"
            }
        
        authors[author_name]["total_chains"] = authors[author_name].get("total_chains", 0) + 1
        
        # Save marketplace
        save_marketplace(marketplace_chains, authors)
        
        return combo_score
    except Exception as e:
        logger.error(f"Failed to publish chain: {e}")
        return None


def render_marketplace():
    """Render marketplace component"""
    st.markdown("<h1 style='text-align:center; max-width:1200px; margin:0 auto;'>⚡ Chain Marketplace</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888; max-width:1200px; margin:0 auto;'>Discover and import god-tier reasoning chains</p>", unsafe_allow_html=True)
    
    # Load marketplace data
    marketplace_data = fetch_marketplace()
    marketplace_chains = marketplace_data.get("chains", [])
    authors = marketplace_data.get("authors", {})
    
    # Bootstrap if empty
    if not marketplace_chains:
        st.markdown("""
        <div style="
            text-align: center;
            padding: 60px 40px;
            background: linear-gradient(135deg, #1a1a1a 0%, #2a1a2a 100%);
            border-radius: 20px;
            margin: 40px 0;
        ">
            <h2 style="color: #8b5cf6; font-size: 2.5em;">
                Be the first.
            </h2>
            <p style="color: #999; font-size: 1.3em; margin: 20px 0;">
                Publish a chain so sharp that strangers will one day<br/>
                type a single word to thank you.
            </p>
            <p style="color: #666; font-size: 1em;">
                The marketplace remembers who built the first S-tier chain.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Try to bootstrap
        bootstrap_chains = bootstrap_marketplace()
        if bootstrap_chains:
            save_marketplace(bootstrap_chains, {})
            st.rerun()
        return
    
    # Sort by combo score (descending) as default
    marketplace_chains.sort(key=lambda x: x.get("combo", 0), reverse=True)
    
    # Filter and search
    col_search, col_sort = st.columns([3, 1])
    with col_search:
        search_term = st.text_input("Search chains", placeholder="Enter chain name or description...")
    with col_sort:
        sort_by = st.selectbox("Sort by", ["Resonance", "Combo Score", "Uses", "Recent", "Name"], index=0)
        if sort_by == "Resonance":
            marketplace_chains.sort(key=lambda x: x.get("resonance_count", 0), reverse=True)
        elif sort_by == "Uses":
            marketplace_chains.sort(key=lambda x: x.get("uses", 0), reverse=True)
        elif sort_by == "Recent":
            marketplace_chains.sort(key=lambda x: x.get("created", ""), reverse=True)
        elif sort_by == "Name":
            marketplace_chains.sort(key=lambda x: x.get("name", "").lower())
        else:  # Combo Score
            marketplace_chains.sort(key=lambda x: x.get("combo", 0), reverse=True)
    
    # Filter by search term
    if search_term:
        marketplace_chains = [
            c for c in marketplace_chains
            if search_term.lower() in c.get("name", "").lower() 
            or search_term.lower() in c.get("description", "").lower()
        ]
    
    # Display chains
    st.markdown(f"### Found {len(marketplace_chains)} chains")
    
    for chain in marketplace_chains[:50]:  # Limit to top 50
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{chain.get('name', 'Unnamed')}**")
                author = chain.get("author", "Unknown")
                author_rep = get_author_reputation(author)
                st.caption(f"by {author} • {author_rep['tier']}")
                st.caption(chain.get("description", "No description")[:100])
                if chain.get("tags"):
                    tags_str = ", ".join(chain.get("tags", [])[:3])
                    st.caption(f"Tags: {tags_str}")
            
            with col2:
                resonance = chain.get("resonance_count", 0)
                st.metric("Resonance", resonance)
            
            with col3:
                st.metric("Uses", chain.get("uses", 0))
                st.caption(f"{chain.get('steps_count', 0)} steps")
            
            with col4:
                combo = chain.get("combo", 0)
                color = "#00ff88" if combo >= 95 else "#06b6d4" if combo >= 80 else "#ffaa00"
                st.markdown(f"<span style='color:{color}; font-size:1.5em; font-weight:bold;'>{combo}%</span>", unsafe_allow_html=True)
                st.caption("Combo")
                if combo >= 95:
                    st.markdown("⚡ **S-TIER**")
            
            with col5:
                chain_id = chain.get("id")
                if st.button("Import", key=f"import_{chain_id}"):
                    if import_chain(chain):
                        # Store chain ID in session state for resonance tracking
                        st.session_state.imported_chain_id = chain_id
                        st.success(f"Imported {chain.get('name')}")
                        st.balloons()
                        
                        # Update usage count
                        marketplace_data = fetch_marketplace()
                        chains = marketplace_data.get("chains", [])
                        authors = marketplace_data.get("authors", {})
                        
                        for i, c in enumerate(chains):
                            if c.get("id") == chain_id:
                                chains[i]["uses"] = chains[i].get("uses", 0) + 1
                                
                                # Update author stats
                                author = chain.get("author", "Unknown")
                                if author not in authors:
                                    authors[author] = {
                                        "total_chains": 0,
                                        "total_resonance": 0,
                                        "total_uses": 0,
                                        "tier": "Emerging"
                                    }
                                authors[author]["total_uses"] = authors[author].get("total_uses", 0) + 1
                                break
                        
                        save_marketplace(chains, authors)
                        st.rerun()
                    else:
                        st.error("Failed to import chain")
            
            st.markdown("---")

