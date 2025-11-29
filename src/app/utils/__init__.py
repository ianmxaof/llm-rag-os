"""
Powercore Mind utility modules
"""

from .rag_engine import (
    get_rag_context,
    get_rag_context_cached,
    _compute_context_hash,
    adjust_chunk_relevance,
    get_performance_stats,
    export_feedback_summary,
    get_rag_engine
)

from .obsidian_bridge import (
    get_related_notes,
    get_obsidian_bridge,
    inject_note_context,
    crystallize_to_vault,
    open_in_obsidian,
    detect_vault_changes,
    get_vault_structure,
    search_vault
)

from .memory_store import (
    get_memory_streams,
    load_conversation_by_id,
    store_conversation,
    mark_crystallized,
    search_conversations,
    get_memory_statistics,
    get_memory_store
)

__all__ = [
    # RAG Engine
    'get_rag_context',
    'get_rag_context_cached',
    '_compute_context_hash',
    'adjust_chunk_relevance',
    'get_performance_stats',
    'export_feedback_summary',
    'get_rag_engine',
    
    # Obsidian Bridge
    'get_related_notes',
    'get_obsidian_bridge',
    'inject_note_context',
    'crystallize_to_vault',
    'open_in_obsidian',
    'detect_vault_changes',
    'get_vault_structure',
    'search_vault',
    
    # Memory Store
    'get_memory_streams',
    'load_conversation_by_id',
    'store_conversation',
    'mark_crystallized',
    'search_conversations',
    'get_memory_statistics',
    'get_memory_store',
]
