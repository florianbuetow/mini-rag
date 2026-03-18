#!/bin/bash
# Create .claude/commands directory for slash commands
mkdir -p .claude/commands
echo "Created .claude/commands/"
ls -la .claude/commands/

# Check if project-level settings.json exists
echo ""
echo "=== Checking settings ==="
cat .claude/settings.json 2>/dev/null || echo "No .claude/settings.json found"
cat .claude/settings.local.json 2>/dev/null || echo "No .claude/settings.local.json found"

# Extract user corrections and frustration from the top high-signal sessions
echo "=== DEEP DIVE: High-signal sessions ==="

# Session d27a1d6b - monster session (2838L, 360 corrections, 67 frustration)
echo ""
echo "=== d27a1d6b (THE MONSTER - 2838L, 360 corrections) ==="
FILE="$HOME/.claude/projects/-Users-flo-Developer-github-mini-rag-git-main/d27a1d6b-e73f-42ef-87ed-19c6f6f5c7ce.jsonl"
python3 -c "
import json, sys
corrections = []
frustrations = []
positive = []
topics = []
turn_count = 0
with open('$FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                turn_count += 1
                msg = obj.get('message', {})
                content = msg.get('content', '')
                text = ''
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                elif isinstance(content, str):
                    text = content
                text_lower = text.lower()
                short = text[:300].replace(chr(10), ' ')
                # Detect corrections
                for kw in ['no,', 'no ', 'wrong', 'not that', 'instead', 'revert', 'actually,', 'I already']:
                    if kw in text_lower and len(text) > 5:
                        corrections.append(f'Turn {turn_count}: {short}')
                        break
                # Detect frustration
                for kw in ['never mind', 'forget it', 'whatever', 'frustrat', 'give up', 'I\\'ll do it']:
                    if kw in text_lower:
                        frustrations.append(f'Turn {turn_count}: {short}')
                        break
                # Detect positive
                for kw in ['perfect', 'exactly', 'great', 'thanks', 'awesome', 'looks good', 'nice']:
                    if kw in text_lower and len(text) > 3:
                        positive.append(f'Turn {turn_count}: {short}')
                        break
                # First 5 user messages for topic detection
                if turn_count <= 5 and len(text) > 20:
                    topics.append(f'Turn {turn_count}: {short}')
        except:
            pass
print(f'Total user turns: {turn_count}')
print(f'\\n--- TOPICS (first 5 msgs) ---')
for t in topics[:5]: print(t)
print(f'\\n--- CORRECTIONS ({len(corrections)} total, showing first 15) ---')
for c in corrections[:15]: print(c)
print(f'\\n--- FRUSTRATION ({len(frustrations)} total) ---')
for f in frustrations[:10]: print(f)
print(f'\\n--- POSITIVE ({len(positive)} total) ---')
for p in positive[:10]: print(p)
" 2>/dev/null

# Session 876c44c9 - high frustration (274L, 47 corrections, 29 frustration)
echo ""
echo "=== 876c44c9 (HIGH FRUSTRATION - 274L, 47 corrections, 29 frustration) ==="
FILE="$HOME/.claude/projects/-Users-flo-Developer-github-mini-rag-git-main/876c44c9-3e85-45b7-91de-813b7313d3da.jsonl"
python3 -c "
import json, sys
corrections = []
frustrations = []
positive = []
topics = []
turn_count = 0
with open('$FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                turn_count += 1
                msg = obj.get('message', {})
                content = msg.get('content', '')
                text = ''
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                elif isinstance(content, str):
                    text = content
                text_lower = text.lower()
                short = text[:300].replace(chr(10), ' ')
                for kw in ['no,', 'no ', 'wrong', 'not that', 'instead', 'revert', 'actually,', 'I already']:
                    if kw in text_lower and len(text) > 5:
                        corrections.append(f'Turn {turn_count}: {short}')
                        break
                for kw in ['never mind', 'forget it', 'whatever', 'frustrat', 'give up', 'I\\'ll do it']:
                    if kw in text_lower:
                        frustrations.append(f'Turn {turn_count}: {short}')
                        break
                for kw in ['perfect', 'exactly', 'great', 'thanks', 'awesome', 'looks good', 'nice']:
                    if kw in text_lower and len(text) > 3:
                        positive.append(f'Turn {turn_count}: {short}')
                        break
                if turn_count <= 5 and len(text) > 20:
                    topics.append(f'Turn {turn_count}: {short}')
        except:
            pass
print(f'Total user turns: {turn_count}')
print(f'\\n--- TOPICS (first 5 msgs) ---')
for t in topics[:5]: print(t)
print(f'\\n--- CORRECTIONS ({len(corrections)} total, showing first 15) ---')
for c in corrections[:15]: print(c)
print(f'\\n--- FRUSTRATION ({len(frustrations)} total) ---')
for f in frustrations[:10]: print(f)
print(f'\\n--- POSITIVE ({len(positive)} total) ---')
for p in positive[:10]: print(p)
" 2>/dev/null

# Session bc2a6373 - feature-metadata (1531L, 26 corrections)
echo ""
echo "=== bc2a6373 (feature-metadata main session - 1531L, 26 corrections) ==="
FILE="$HOME/.claude/projects/-Users-flo-Developer-github-mini-rag-git-feature-metadata/bc2a6373-17cb-48d9-a383-ffffc93fac7a.jsonl"
python3 -c "
import json, sys
corrections = []
frustrations = []
topics = []
turn_count = 0
with open('$FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                turn_count += 1
                msg = obj.get('message', {})
                content = msg.get('content', '')
                text = ''
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                elif isinstance(content, str):
                    text = content
                text_lower = text.lower()
                short = text[:300].replace(chr(10), ' ')
                for kw in ['no,', 'no ', 'wrong', 'not that', 'instead', 'revert', 'actually,', 'I already']:
                    if kw in text_lower and len(text) > 5:
                        corrections.append(f'Turn {turn_count}: {short}')
                        break
                for kw in ['never mind', 'forget it', 'whatever', 'frustrat', 'give up', 'I\\'ll do it']:
                    if kw in text_lower:
                        frustrations.append(f'Turn {turn_count}: {short}')
                        break
                if turn_count <= 5 and len(text) > 20:
                    topics.append(f'Turn {turn_count}: {short}')
        except:
            pass
print(f'Total user turns: {turn_count}')
print(f'\\n--- TOPICS (first 5 msgs) ---')
for t in topics[:5]: print(t)
print(f'\\n--- CORRECTIONS ({len(corrections)} total, showing first 10) ---')
for c in corrections[:10]: print(c)
print(f'\\n--- FRUSTRATION ({len(frustrations)} total) ---')
for f_ in frustrations[:10]: print(f_)
" 2>/dev/null

# Session 96b2a4be - chat UI work (331L, 22 corrections, 7 frustration)
echo ""
echo "=== 96b2a4be (chat UI work - 331L, 22 corrections, 7 frustration) ==="
FILE="$HOME/.claude/projects/-Users-flo-Developer-github-mini-rag-git-main/96b2a4be-592d-4564-b8fd-2d8618a9a029.jsonl"
python3 -c "
import json, sys
corrections = []
frustrations = []
topics = []
turn_count = 0
with open('$FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                turn_count += 1
                msg = obj.get('message', {})
                content = msg.get('content', '')
                text = ''
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                elif isinstance(content, str):
                    text = content
                text_lower = text.lower()
                short = text[:300].replace(chr(10), ' ')
                for kw in ['no,', 'no ', 'wrong', 'not that', 'instead', 'revert', 'actually,', 'I already']:
                    if kw in text_lower and len(text) > 5:
                        corrections.append(f'Turn {turn_count}: {short}')
                        break
                for kw in ['never mind', 'forget it', 'whatever', 'frustrat', 'give up', 'I\\'ll do it']:
                    if kw in text_lower:
                        frustrations.append(f'Turn {turn_count}: {short}')
                        break
                if turn_count <= 5 and len(text) > 20:
                    topics.append(f'Turn {turn_count}: {short}')
        except:
            pass
print(f'Total user turns: {turn_count}')
print(f'\\n--- TOPICS (first 5 msgs) ---')
for t in topics[:5]: print(t)
print(f'\\n--- CORRECTIONS ({len(corrections)} total, showing first 10) ---')
for c in corrections[:10]: print(c)
print(f'\\n--- FRUSTRATION ({len(frustrations)} total) ---')
for f_ in frustrations[:10]: print(f_)
" 2>/dev/null

# Successful sessions - clean completions
echo ""
echo "=== SUCCESSFUL PATTERNS ==="
echo "--- Sessions with high positive, low correction ratios ---"

# Session caf9baef - debug mode help (153L, 4 corrections, completed successfully)
echo ""
echo "-- caf9baef (debug mode help - 153L, low friction) --"
FILE="$HOME/.claude/projects/-Users-flo-Developer-github-mini-rag-git-main/caf9baef-e1fa-473b-bf2c-67d8273d0af1.jsonl"
python3 -c "
import json, sys
turn_count = 0
topics = []
with open('$FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                turn_count += 1
                msg = obj.get('message', {})
                content = msg.get('content', '')
                text = ''
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            text = c.get('text', '')
                            break
                elif isinstance(content, str):
                    text = content
                if turn_count <= 10 and len(text) > 10:
                    short = text[:200].replace(chr(10), ' ')
                    topics.append(f'Turn {turn_count}: {short}')
        except:
            pass
print(f'Total user turns: {turn_count}')
for t in topics: print(t)
" 2>/dev/null

# Aggregate stats
echo ""
echo "=== AGGREGATE STATISTICS ==="
python3 -c "
import re
with open('/tmp/retro-28128/summary.txt') as f:
    text = f.read()

sessions = text.split('=== SESSION:')
total_corrections = 0
total_frustration = 0
total_positive = 0
total_turns = 0
total_errors = 0
monitor_count = 0
dev_count = 0
branch_counts = {}

for s in sessions[1:]:
    # Extract metrics
    corr = re.search(r'CORRECTIONS: (\d+)', s)
    frust = re.search(r'FRUSTRATION: (\d+)', s)
    pos = re.search(r'POSITIVE: (\d+)', s)
    user_turns = re.search(r'user=(\d+)', s)
    errors = re.search(r'TOOL_ERRORS: (\d+)', s)
    branch = re.search(r'BRANCH: (.+)', s)
    topic = re.search(r'TOPIC: (.+)', s)

    if corr: total_corrections += int(corr.group(1))
    if frust: total_frustration += int(frust.group(1))
    if pos: total_positive += int(pos.group(1))
    if user_turns: total_turns += int(user_turns.group(1))
    if errors: total_errors += int(errors.group(1))

    if branch:
        b = branch.group(1).strip()
        branch_counts[b] = branch_counts.get(b, 0) + 1

    if topic and 'monitor-pane' in topic.group(1):
        monitor_count += 1
    else:
        dev_count += 1

print(f'Total sessions analyzed: {len(sessions)-1}')
print(f'Monitor/orchestration sessions: {monitor_count}')
print(f'Development sessions: {dev_count}')
print(f'Total user turns: {total_turns}')
print(f'Total corrections: {total_corrections}')
print(f'Total frustration signals: {total_frustration}')
print(f'Total positive signals: {total_positive}')
print(f'Total tool errors: {total_errors}')
print(f'Correction rate: {total_corrections/max(total_turns,1)*100:.1f}%')
print(f'\\nBranch distribution:')
for b, c in sorted(branch_counts.items(), key=lambda x: -x[1]):
    print(f'  {b}: {c} sessions')
" 2>/dev/null
