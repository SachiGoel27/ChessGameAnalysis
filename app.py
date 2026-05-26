import streamlit as st
import chess
import chess.svg
import base64
from groq import Groq
from engine_utils import analyze_game_fully

# --- CONFIGURATION ---
STOCKFISH_PATH = "./stockfish" 

st.set_page_config(page_title="Local AI Chess Coach", layout="wide")

def render_svg(svg_string):
    b64 = base64.b64encode(svg_string.encode('utf-8')).decode("utf-8")
    html = f'<img src="data:image/svg+xml;base64,{b64}" width="100%"/>'
    st.write(html, unsafe_allow_html=True)

# --- SESSION STATE ---
if "game_moves" not in st.session_state:
    st.session_state.game_moves = []
if "blunders" not in st.session_state:
    st.session_state.blunders = []
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Coach Settings")
    groq_api_key = st.text_input("Groq API Key", type="password")
    pgn_input = st.text_area("Paste Chess.com PGN here:", height=200)
    
    if st.button("Analyze Game", type="primary"):
        if not pgn_input:
            st.warning("Please paste a PGN first.")
        else:
            with st.spinner("Analyzing all game moves..."):
                try:
                    full_game = analyze_game_fully(pgn_input, STOCKFISH_PATH, time_limit=0.1)
                    st.session_state.game_moves = full_game
                    st.session_state.blunders = [m for m in full_game if m["is_blunder"]]
                    st.session_state.current_idx = 0
                    st.session_state.chat_history = []
                    st.success(f"Loaded {len(full_game)-1} moves. Found {len(st.session_state.blunders)} blunders.")
                except Exception as e:
                    st.error(f"Engine Error: {e}")

# --- MAIN INTERFACE ---
st.title("♟️ Move-by-Move Interactive Review")

if not st.session_state.game_moves:
    st.info("Paste a game PGN in the sidebar and click Analyze to begin.")
else:
    # Fetch current position details
    current_move = st.session_state.game_moves[st.session_state.current_idx]
    
    # 1. TOP CONTROL BAR: Dropdown + Sequential Toggles
    top_col1, top_col2 = st.columns([2, 1])
    
    with top_col1:
        # Create option list for the Blunder Dropdown
        blunder_options = ["Browse Manually / No Blunder Selected"] + [
            f"Move {b['move_num']} ({b['turn']}): {b['move_played']} (Dropped -{b['eval_drop']})"
            for b in st.session_state.blunders
        ]
        
        # Calculate dynamic index to keep dropdown in sync with sequential arrows
        default_dropdown_idx = 0
        if current_move["is_blunder"]:
            for idx, b in enumerate(st.session_state.blunders):
                if b["move_idx"] == current_move["move_idx"]:
                    default_dropdown_idx = idx + 1
                    break
                    
        selected_blunder = st.selectbox("🎯 Jump straight to a blunder:", options=blunder_options, index=default_dropdown_idx)
        
        # Handle dropdown adjustments
        if selected_blunder != "Browse Manually / No Blunder Selected":
            target_blunder_idx = blunder_options.index(selected_blunder) - 1
            target_move_idx = st.session_state.blunders[target_blunder_idx]["move_idx"]
            if target_move_idx != st.session_state.current_idx:
                st.session_state.current_idx = target_move_idx
                st.session_state.chat_history = []
                st.rerun()

    with top_col2:
        st.write("###") # Structural alignment spacer
        btn_prev, btn_next = st.columns(2)
        with btn_prev:
            if st.button("⬅️ Previous", use_container_width=True, disabled=(st.session_state.current_idx == 0)):
                st.session_state.current_idx -= 1
                st.session_state.chat_history = []
                st.rerun()
        with btn_next:
            if st.button("Next ➡️", use_container_width=True, disabled=(st.session_state.current_idx == len(st.session_state.game_moves) - 1)):
                st.session_state.current_idx += 1
                st.session_state.chat_history = []
                st.rerun()

    st.write("---")

    # 2. SPLIT LAYOUT: Board Presentation vs Chat Coaching
    col1, col2 = st.columns([1, 1.3])

    with col1:
        # Set up board state right before this specific move occurred
        board = chess.Board(current_move["fen_before"])
        arrows = []
        
        if current_move["move_played"] != "Start":
            played_move_obj = board.parse_san(current_move["move_played"])
            
            if current_move["is_blunder"]:
                # Blunder visual styling: Red arrow for what you did, green for what you missed
                arrows.append(chess.svg.Arrow(played_move_obj.from_square, played_move_obj.to_square, color="red"))
                if current_move["best_move"] != "N/A":
                    best_move_obj = board.parse_san(current_move["best_move"])
                    arrows.append(chess.svg.Arrow(best_move_obj.from_square, best_move_obj.to_square, color="green"))
            else:
                # Normal move visual styling: Standard blue path arrow
                arrows.append(chess.svg.Arrow(played_move_obj.from_square, played_move_obj.to_square, color="blue"))

        # Render board frame
        board_svg = chess.svg.board(board, arrows=arrows, size=420)
        render_svg(board_svg)
        
        # Contextual Status Box underneath the board
        if current_move["move_played"] == "Start":
            st.info("**Starting Position** - Click 'Next' to view the game.")
        elif current_move["is_blunder"]:
            st.error(f"⚠️ **Blunder on Move {current_move['move_num']} ({current_move['turn']})**")
            st.write(f"❌ Played: **{current_move['move_played']}** | Engine wanted: **{current_move['best_move']}**")
            st.write(f"📉 Evaluation penalty: **{current_move['eval_drop']}** pawns.")
        else:
            st.success(f"**Move {current_move['move_num']} ({current_move['turn']}): {current_move['move_played']}**")
            st.write(f"🤖 Centipawn Eval: `{current_move['score_after']}` (Positive favors White)")

    with col2:
        st.subheader("💬 Interactive Coach Analysis")
        
        # Print ongoing conversation history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        user_query = st.chat_input("Ask a question about this exact position...")
        
        if user_query:
            if not groq_api_key:
                st.warning("Please input your Groq API key in the sidebar.")
            else:
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                with st.chat_message("user"):
                    st.markdown(user_query)
                    
                # Tailor the system instruction based on whether the position is a blunder or a regular development move
                if current_move["is_blunder"]:
                    scenario_context = f"""
                    The student committed a critical error.
                    - Played move: {current_move['move_played']}
                    - Better alternative: {current_move['best_move']}
                    - Strategic/tactical cost: {current_move['eval_drop']} pawns.
                    Explain the tactical flaw behind their move and why the engine's recommendation improves the position.
                    """
                else:
                    scenario_context = f"""
                    This is a standard game position without severe blunders.
                    - Move executed: {current_move['move_played']}
                    - Current evaluation score: {current_move['score_after']}
                    Help the student understand overall positional strategy, piece development paths, or pawn structures for this layout.
                    """

                system_prompt = f"""
                You are a supportive, high-clarity chess coach helping an intermediate student targeting a 1000 ELO rating.
                Keep explanations intuitive, brief (2-3 paragraphs), and centered on fundamental spatial patterns (hanging pieces, development lines, open files, king coverage).
                
                Position Details:
                - Current FEN string: {current_move['fen_before']}
                {scenario_context}
                
                Strict Guideline: Trust the engine completely. Do not improvise variations that aren't mentioned. Translate the notation patterns into solid conceptual guidance.
                """
                
                # Fetch response from Groq
                client = Groq(api_key=groq_api_key)
                messages_for_api = [{"role": "system", "content": system_prompt}]
                messages_for_api.extend(st.session_state.chat_history)
                
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing board properties..."):
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=messages_for_api,
                            temperature=0.2
                        )
                        coach_reply = response.choices[0].message.content
                        st.markdown(coach_reply)
                        
                st.session_state.chat_history.append({"role": "assistant", "content": coach_reply})