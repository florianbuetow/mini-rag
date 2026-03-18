#!/bin/bash
SESSION="claude-swarm"
tmux kill-session -t "$SESSION" 2>/dev/null && echo "Session '$SESSION' killed." || echo "No session '$SESSION' found."
