import chess
import chess.engine
import chess.pgn
import io

def analyze_game_fully(pgn_string, stockfish_path, time_limit=0.1):
    """
    Analyzes every move of a PGN game sequentially, caching positions,
    evaluations, and flagging blunders along the way.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_string))
    if not game:
        return []
    
    board = game.board()
    
    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except FileNotFoundError:
        raise Exception(f"Stockfish not found at {stockfish_path}. Please check the path.")
    
    engine.configure({"Hash": 256})
    
    game_moves = []
    
    # Insert the starting position (Move 0) so the user can look at the clean board
    game_moves.append({
        "move_idx": 0,
        "move_num": 0,
        "turn": "Setup",
        "move_played": "Start",
        "fen_before": board.fen(),
        "fen_after": board.fen(),
        "best_move": "N/A",
        "eval_drop": 0.0,
        "score_after": 0.0,
        "is_blunder": False
    })

    move_number = 1
    
    for move in game.mainline_moves():
        turn = "White" if board.turn == chess.WHITE else "Black"
        fen_before = board.fen()
        
        # 1. Get engine analysis before the move is made
        info_before = engine.analyse(board, chess.engine.Limit(time=time_limit))
        score_before_white = info_before["score"].white().score(mate_score=10000) / 100.0
        best_move_before = info_before.get("pv", [None])[0]
        san_best = board.san(best_move_before) if best_move_before else "N/A"
        
        # 2. Execute the move
        san_played = board.san(move)
        board.push(move)
        fen_after = board.fen()
        
        # 3. Get engine analysis after the move
        info_after = engine.analyse(board, chess.engine.Limit(time=time_limit))
        score_after_white = info_after["score"].white().score(mate_score=10000) / 100.0
        
        # 4. Calculate if it's a mistake
        if turn == "White":
            eval_drop = score_before_white - score_after_white
        else:
            eval_drop = score_after_white - score_before_white
            
        is_blunder = eval_drop > 1.5
        
        game_moves.append({
            "move_idx": len(game_moves),
            "move_num": move_number,
            "turn": turn,
            "move_played": san_played,
            "fen_before": fen_before,
            "fen_after": fen_after,
            "best_move": san_best,
            "eval_drop": round(eval_drop, 2),
            "score_after": round(score_after_white, 2),
            "is_blunder": is_blunder
        })
        
        if turn == "Black":
            move_number += 1
            
    engine.quit()
    return game_moves