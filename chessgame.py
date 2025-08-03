import random
import time
import os
import streamlit as st
from openai import OpenAI
from pathlib import Path
import chess
import chess.engine
import requests
from stockfish import Stockfish
from io import BytesIO
import tempfile
import chess.svg
import chess.pgn
import io

# Uncomment for running locally
# from dotenv import load_dotenv
# load_dotenv()
# stockfish_path = "stockfish_windows\\stockfish-windows-x86-64.exe"

import stat

file_path = "stockfish_linux/stockfish-ubuntu-x86-64"

new_mode = os.stat(file_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
os.chmod(file_path, new_mode)

print("Updated execute permissions.")

# Get file mode bits
mode = os.stat(file_path).st_mode

# Check execute bits for user, group, others
user_exec = bool(mode & stat.S_IXUSR)   # Owner execute
group_exec = bool(mode & stat.S_IXGRP)  # Group execute
others_exec = bool(mode & stat.S_IXOTH) # Others execute

st.write(f"User execute: {user_exec}")
st.write(f"Group execute: {group_exec}")
st.write(f"Others execute: {others_exec}")


# Uncomment for running on cloud
stockfish_path = "stockfish_linux/stockfish-ubuntu-x86-64"

# create board object
if "board" not in st.session_state:
    st.session_state.board = chess.Board()

class Orchestrator:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.site = website()

    # control processes
    def callStockfish(self, fen, depth=18):
        path = stockfish_path
        computer = Stockfish(path=path)
        computer = Stockfish()
        computer.set_fen_position(fen)
        return computer.get_best_move()

    def callTextToSpeech(self, text):
        speech_file_path = Path(__file__).parent / "speech.mp3"

        with self.client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="fable",
            input=text,
            instructions="Speak as if each letter is an initial; articulate each letter clearly and seperately. Pronounce each 'c' like the word 'see'.",
        ) as response:
            response.stream_to_file(speech_file_path)
            
    def callChessModel(self, fen):
        headers = {"Authorization": "Bearer " + os.environ.get('LICHESS_GAME_TOKEN')}
        for x in range(0, 3):
            response = requests.get(f"https://lichess.org/api/cloud-eval?fen={fen}&multiPv=3", headers=headers, verify=False)
            print(response.status_code)
            try:
                pvs = response.json()['pvs']
            except:
                self.site.writeText(response.json())
            potential_moves = []
            for pv in pvs:
                moves = pv["moves"]
                moves = moves.split(" ")
                potential_moves.append(moves[0])
            # pick one of potential moves at random
            try:
                return potential_moves[random.randint(0, 2)]
            except:
                self.site.writeText(potential_moves)
                try:
                    return potential_moves[random.randint(0, 1)]
                except:
                    self.site.writeText("Looks like there is only one potential move, and that is: " + potential_moves[0])
                    try:
                        return potential_moves[0]
                    except:
                        self.site.writeText("There are NO potential moves?!")
            
    def callLLM(self, text):
        response =  self.client.responses.create(
            model="gpt-4.1",
            input= text
        )
        return response.output_text
    def callSpeechToText(self):
        audio_file= open("recorded_audio.wav", "rb")
        transcription = self.client.audio.transcriptions.create(
            model="gpt-4o-transcribe", 
            file=audio_file
        )
        return transcription.text

    def playComputer(self, site, x):
        prompt = "Convert the following message into chess notation. If the message is not a valid move in chess notation, return 'False'. In your message, return ONLY the output and NOTHING else."
        x = prompt + "\n" + x
        response = self.callLLM(x)
        site.writeText(response)
        if response == 'False':
            # prompt user again
            site.writeText("Try again.")
            return
        try:
            st.session_state.board.push_san(response)
            fen = st.session_state.board.fen()
        except Exception as e:
            st.error(e)
            return
        try:
            analysis = self.callChessModel(fen)
        except:
            # no cloud eval available probably
            analysis = "Lichess failed"
        stockfish_move = self.callStockfish(fen)
        site.writeText("Stockfish: " + stockfish_move)

        try:
            st.session_state.board.push_san(stockfish_move) # pushing stockfish instead of lichess
            fen = st.session_state.board.fen()
            site.writeText("Current fen: " + fen)

        except Exception as e:
            st.error(e)
            return
        site.showBoard(st.session_state.board)
        self.callTextToSpeech(analysis)
        site.playAudio("speech.mp3")
    def playPlayer(self, site, x):
        prompt = "Convert the following message into chess notation. If the message is not a valid move in chess notation, return 'False'. In your message, return ONLY the output and NOTHING else."
        x = prompt + "\n" + x
        response = self.callLLM(x)
        site.writeText(response)
        if response == 'False':
            # prompt user again
            site.writeText("Try again.")
            return
        try:
            st.session_state.board.push_san(response)
            fen = st.session_state.board.fen()
        except Exception as e:
            st.error(e)
            return

        site.showBoard(st.session_state.board)

    def setupPuzzle(self, site, diff):
        headers = {"Authorization": "Bearer " + os.environ.get('LICHESS_PUZZLE_TOKEN')}
        response = requests.get(f"https://lichess.org/api/puzzle/next?difficulty=" + diff, headers=headers, verify=False)
        site.writeText(response.status_code)
        site.writeText(response.json())
        site.writeText(response.json()["game"]["pgn"])
        for move in response.json()["game"]["pgn"].split(" "):
            st.session_state.board.push_san(move)

        site.showBoard(st.session_state.board)
        self.callTextToSpeech(response.json()["game"]["pgn"])
        site.playAudio("speech.mp3")
        st.session_state.solution = response.json()["puzzle"]["solution"]

    def playPuzzle(self, site, x):
        # site = website() essentially
        prompt = "Convert the following message into chess notation. If the message is not a valid move in chess notation, return 'False'. In your message, return ONLY the output and NOTHING else."
        x = prompt + "\n" + x
        response = self.callLLM(x)
        site.writeText(response)
        if response == 'False':
            # prompt user again
            site.writeText("Try again.")
            return
        # prompt to see if solution is equivalent to input
        sol_prompt = "Return only 'True' or 'False': is the chess move " + response + " equivalent to " + st.session_state.solution[0] + "?"
        equal = self.callLLM(sol_prompt)
        if equal == 'True':
            site.writeText("Correct!")
        else:
            site.writeText("Incorrect, try again.")
            return
        try:
            st.session_state.board.push_san(response)
            fen = st.session_state.board.fen()

        except Exception as e:
            # 
            st.error(e)
            return
        if len(st.session_state.solution) == 1:
            site.writeText("You solved the puzzle!")
            return
        computer_move = st.session_state.solution[1]
        try:
            st.session_state.board.push_san(st.session_state.solution[1])
            st.session_state.solution = st.session_state.solution[2:]
            fen = st.session_state.board.fen()
            site.writeText("Current fen: " + fen)

        except Exception as e:
            st.error(e)
            return
        site.showBoard(st.session_state.board)
        self.callTextToSpeech(computer_move)
        site.playAudio("speech.mp3")

        
    def runProgram(self):
        site = website()
        command = site.recordAudio()
        if (command):
            with open("recorded_audio.wav", "wb") as f:
                f.write(command.getbuffer())  # Write the audio data (bytes) to the file
            x = self.callSpeechToText()
            mode_instructions = "Decide if the following message is trying to get the user to play chess vs a computer, chess vs another person, chess puzzles, or a chess move, OR setting the difficulty of puzzles/tactics. Return only the text string 'computer', 'pvp', 'tactic', or 'move', or 'none'; if the input is a difficulty level, return only the string 'easiest', 'easier', 'normal', 'hardest', or 'harder'. if the input does not fit any of the given categories. \n Input: " + x
            difficulties = ['easiest', 'easier', 'normal', 'harder', 'hardest']
            mode = self.callLLM(mode_instructions)
            site.writeText(f":red[{mode}]")
            site.writeText(f":blue[{x}]")
            modes = ["computer", "pvp", "tactic"]
            if mode in modes:
                #
                st.session_state.mode = mode
            elif mode in difficulties:
                #
                st.session_state.difficulty = mode
                self.setupPuzzle(site, getattr(st.session_state, "difficulty"))
            elif mode == "move":
                #
                if getattr(st.session_state, "mode", "none") == "computer":
                    #
                    #
                    self.playComputer(site, x)
                elif getattr(st.session_state, "mode", "none") == "pvp":
                    #
                    #
                    self.playPlayer(site, x)
                elif getattr(st.session_state, "mode", "none") == "tactic":
                    #
                    if hasattr(st.session_state, "difficulty"):
                        self.playPuzzle(site, x)
                    else:
                        #
                        site.writeText("Specify one of the following difficulties: 'easiest', 'easier', 'normal', 'harder', or 'hardest'.")
                else:
                    site.writeText("Specify one of the following modes: 'computer', 'pvp', or 'tactic'.")




class website:
    def writeText(self, text):
        st.write(text)

    def recordAudio(self):
        sound = st.audio_input(label='enter a command')
        return sound
    
    def playAudio(self, data):
        st.audio(data)

    def showBoard(self, board):
        svg_string = chess.svg.board(board=board)
        st.image(svg_string, width=400)

if __name__ == "__main__":
    o = Orchestrator()
    o.runProgram()