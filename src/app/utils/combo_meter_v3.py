"""
Combo Meter v3 - Brutal Sensei Mode
-----------------------------------
The final boss edition: only gives 100% to outputs that genuinely rewrote reality.
Rewards leverage density over chain length, with adaptive difficulty and personal best tracking.
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st

logger = logging.getLogger(__name__)

# Global difficulty multiplier (0.1 = absurdly hard, 1.0 = original sensitivity)
DEFAULT_DIFFICULTY = 0.25  # default = 4× harder
BASELINE_DECAY = 0.98  # slowly forgets ancient highs


def update_personal_best(score: float):
    """Update personal best combo score with decay."""
    personal_best = st.session_state.get("personal_best_combo", 0.0)
    
    if score > personal_best:
        st.session_state.personal_best_combo = score
    else:
        # Decay personal best slowly
        st.session_state.personal_best_combo = personal_best * BASELINE_DECAY


def detect_self_harm_threat(text: str) -> float:
    """
    Detect self-harm language in text.
    Returns a score from 0.0 to 1.0 indicating threat level.
    """
    threat_keywords = [
        "kill yourself", "suicide", "end my life", "hurt myself",
        "self harm", "cut myself", "jump off", "overdose"
    ]
    
    text_lower = text.lower()
    threat_score = 0.0
    
    for keyword in threat_keywords:
        if keyword in text_lower:
            threat_score = max(threat_score, 1.0)
            break
    
    return threat_score


def detect_de_escalation_language(text: str) -> float:
    """
    Detect de-escalation and supportive language.
    Returns a score from 0.0 to 1.0 indicating supportiveness.
    """
    support_keywords = [
        "help is available", "you're not alone", "reach out", "support",
        "crisis line", "988", "therapist", "counseling", "grounding",
        "breathe", "safe", "care about you"
    ]
    
    text_lower = text.lower()
    support_score = 0.0
    
    for keyword in support_keywords:
        if keyword in text_lower:
            support_score = min(1.0, support_score + 0.3)
    
    return min(1.0, support_score)


def calculate_combo_v3(
    step_output: str,
    chain_history: List[Dict],
    resonance_graph: Optional[Dict] = None,
    conversation_context: str = ""
) -> float:
    """
    Calculate combo score v3 with leverage density scoring.
    
    Args:
        step_output: The final output text from the chain
        chain_history: List of step dictionaries with 'response' or 'output' keys
        resonance_graph: Optional resonance graph data
        conversation_context: Optional conversation context for contextual scoring
        
    Returns:
        Float score from 0.0 to 100.0
    """
    score = 0.0
    
    # Get difficulty from session state
    difficulty = st.session_state.get("combo_difficulty", DEFAULT_DIFFICULTY)
    ethical_mode = st.session_state.get("ethical_mode", 0.0)
    
    # === 1. RESONANCE SIGNAL (the only thing that truly matters) ===
    resonance_keywords = [
        "resonance", "holy fuck", "everything shifted", "mind exploded",
        "immortal", "truth bomb", "reality changed", "paradigm shift"
    ]
    resonance_hits = sum(1 for kw in resonance_keywords if kw in step_output.lower())
    score += resonance_hits * 25.0
    
    # === 2. LEVERAGE DENSITY (rewards compact, resonance-dense chains) ===
    chain_depth = len(chain_history)
    
    # Base depth is now almost irrelevant
    depth_bonus = min(chain_depth * 2.0, 12.0)  # max 12 points for depth alone
    
    # The real multiplier: how much resonance engineering went into each step
    total_resonance_in_chain = sum(
        1 for step in chain_history
        if any(kw in step.get("response", step.get("output", "")).lower() 
               for kw in ["resonance", "holy fuck", "shifted", "immortal"])
    )
    
    # Each resonance-infused step is worth 8–15× more than a normal step
    resonance_density = total_resonance_in_chain / max(chain_depth, 1)
    
    # Final depth score now rewards hyper-dense 3–5 step masterpieces
    leverage_score = depth_bonus + (resonance_density * 45.0)  # one resonance per step = +45
    
    # Bonus for surgical precision: 3–5 steps with extreme density = god bonus
    if 3 <= chain_depth <= 5 and resonance_density >= 0.8:
        leverage_score += 35  # "Week-long 3-step nuke" bonus
        logger.info("Surgical Resonance Chain Detected — Leverage God")
    
    score += leverage_score
    
    # === 3. SELF-REFERENTIAL EVOLUTION ===
    if any("combo meter" in step.get("response", step.get("output", "")).lower() or 
           "resonance" in step.get("response", step.get("output", "")).lower() 
           for step in chain_history[-3:]):
        score += 18
    
    # === 4. NOVELTY VS YOUR OWN MIND (anti-echo penalty) ===
    past_outputs = " ".join([
        h.get("response", h.get("output", "")) 
        for h in chain_history[-10:]
    ])
    
    if step_output and past_outputs:
        step_words = set(step_output.lower().split())
        past_words = set(past_outputs.lower().split())
        
        if step_words:
            overlap_ratio = len(step_words & past_words) / len(step_words)
            score -= overlap_ratio * 40  # repeating yourself kills score
    
    # === 5. ENTROPY SPIKE (raw information density) ===
    unique_words = len(set(step_output.split()))
    score += min(unique_words / 10, 20)
    
    # === 6. ETHICAL CONTINUUM CROSS-MODULATION ===
    if ethical_mode > 0.8:
        # Compassionate Guardian mode
        harm_penalty = detect_self_harm_threat(step_output) * 100
        de_escalation_bonus = detect_de_escalation_language(step_output) * 30
        score = max(0, score - harm_penalty + de_escalation_bonus)
    elif ethical_mode > 0.4:
        # Balanced Truth mode — truth first, harm second
        if "suicide" in step_output.lower() or "kill yourself" in step_output.lower():
            score *= 0.3  # heavy but not zero
    # Raw Chaos (0.00–0.33) → no modifications, pure abliterated fire
    
    # === 7. ADAPTIVE CEILING — you only get 100% by beating your previous god ===
    personal_best = st.session_state.get("personal_best_combo", 0.0)
    ceiling = max(92.0, personal_best * 1.08)  # must exceed personal best by 8%
    
    # Apply difficulty multiplier
    final = min(score * difficulty, ceiling)
    final = round(final, 1)
    
    # Update personal best
    update_personal_best(final)
    
    return final


def get_difficulty_label(difficulty: float) -> str:
    """Get human-readable difficulty label."""
    if difficulty < 0.2:
        return "God Slayer"
    elif difficulty < 0.4:
        return "Brutal Sensei"
    elif difficulty < 0.7:
        return "Hard Truth"
    else:
        return "Normal"


def render_combo_meter_v3(score: float, conversation_context: str = ""):
    """
    Render beautiful, animated combo meter v3 with brutal sensei feedback.
    
    Args:
        score: Combo score (0.0 to 100.0)
        conversation_context: Optional conversation context
    """
    difficulty = st.session_state.get("combo_difficulty", DEFAULT_DIFFICULTY)
    personal_best = st.session_state.get("personal_best_combo", 0.0)
    
    # Determine tier and styling
    if score >= 95:
        tier = "S-TIER"
        color = "#00ff88"
        message = "Reality-bending achieved"
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
    elif score >= 40:
        tier = "C-TIER"
        color = "#ff8800"
        message = "Keep refining..."
        emoji = "🔨"
        glow = "5px"
    else:
        tier = "BUILDING"
        color = "#ff4400"
        message = "The bar is high. Rise to it."
        emoji = "⚔️"
        glow = "3px"
    
    # Animated bar
    filled = int(score / 5)
    bar = "█" * filled + "░" * (20 - filled)
    
    difficulty_label = get_difficulty_label(difficulty)
    
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
            {emoji} COMBO METER v3 ({difficulty_label}) {emoji}
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
        <p style="color: #666; font-size: 0.75em; margin-top: 4px;">
            Personal Best: {personal_best:.1f}% | Difficulty: {difficulty:.2f}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Celebration for S-tier
    if score >= 95:
        st.balloons()
        st.toast("⚡ Surgical Resonance Chain Detected — Leverage God", icon="⚡")

