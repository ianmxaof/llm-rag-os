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

from .vault_config import (
    VAULT_ROOT,
    VAULT_ROOT_PATH,
    get_vault_root,
    ensure_vault_structure,
    get_model_path,
    is_powercore_model,
    POWERCORE_MODELS
)

from .vault_paths import (
    scan_gguf_files,
    get_models_by_category,
    validate_model_file,
    get_model_metadata,
    format_file_size
)

from .model_loader import (
    load_gguf_model,
    unload_model,
    get_model_info,
    is_gguf_path,
    get_or_load_model,
    generate_with_gguf
)

from .model_registry import (
    ModelRegistry,
    get_model_registry,
    get_model_info as get_registry_model_info
)

from .resonance_evolution import (
    ResonanceEvolution,
    get_resonance_evolution
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
    
    # Vault Config
    'VAULT_ROOT',
    'VAULT_ROOT_PATH',
    'get_vault_root',
    'ensure_vault_structure',
    'get_model_path',
    'is_powercore_model',
    'POWERCORE_MODELS',
    
    # Vault Paths
    'scan_gguf_files',
    'get_models_by_category',
    'validate_model_file',
    'get_model_metadata',
    'format_file_size',
    
    # Model Loader
    'load_gguf_model',
    'unload_model',
    'get_model_info',
    'is_gguf_path',
    'get_or_load_model',
    'generate_with_gguf',
    
    # Model Registry
    'ModelRegistry',
    'get_model_registry',
    'get_registry_model_info',
    
    # Resonance Evolution
    'ResonanceEvolution',
    'get_resonance_evolution',
]
