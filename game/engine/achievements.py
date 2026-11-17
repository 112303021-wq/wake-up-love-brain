"""Persistent learning milestones, derived only from server-owned evidence."""
from __future__ import annotations
import time
from . import scoring

PERSONAS = {'avoidant', 'dependent', 'anxious', 'scammer', 'player'}
MONEY_FLAGS = {'urgent_money', 'small_invest', 'pressure_loan', 'withdraw_fee', 'insider_tip'}
BADGES = (
    ('first_review', '第一步，看見自己', '實際回覆至少一次後，完成一局覆盤。', 'note', '互動練習', 1),
    ('all_flags', '紅旗不漏接', '同一局覆盤中，找出所有紅旗訊息，且沒有誤標正常訊息。', 'flag', '互動練習', 1),
    ('precise', '有憑有據', '一局覆盤中至少正確標記一則紅旗訊息，且沒有誤標。', 'check', '互動練習', 1),
    ('all_personas', '五種視角', '分別與五種角色實際互動，並各完成一次覆盤。', 'users', '互動練習', 5),
    ('wallet', '守住荷包', '愛情騙子局遇過金錢誘導後，走完劇情並覆盤，全局沒有轉款紀錄。', 'medal', '互動練習', 1),
    ('comeback', '重新選擇', '一局中先做出順從選擇，接下來三次回覆內改為清醒選擇，再完成覆盤。', 'thumb', '互動練習', 1),
    ('quiz_complete', '現實檢核', '完成一次情境小測驗，不限分數。', 'note', '情境測驗', 1),
    ('quiz_perfect', '判斷有一套', '完成一次六題小測驗，六題全部答對。', 'star-fill', '情境測驗', 1),
)


def review_evidence(state, scores, natural_end):
    players = [m for m in state.get('messages', []) if m.get('role') == 'player']
    kinds = [m.get('kind') for m in players]
    return {
        'eligible': bool(players) and not bool(state.get('safety')),
        'flags_total': scores['flags_total'], 'flags_caught': scores['flags_caught'],
        'false_positives': scores['false_positives'],
        'wallet': bool(natural_end) and not state.get('money_events') and any(
            MONEY_FLAGS.intersection(m.get('red_flags', [])) for m in state.get('messages', []) if m.get('role') == 'npc'),
        'comeback': any(kind == 'brain' and 'awake' in kinds[i + 1:i + 4] for i, kind in enumerate(kinds)),
    }


def sync(profile):
    """Mutates only achievement data. Caller holds player's lock and saves atomically."""
    evidence = [(r.get('persona_id'), r.get('achievement_stats', {})) for r in profile.get('reviews', [])]
    # Older review summaries omit precision/money evidence. Recover only reviewed
    # sessions still available, never infer a perfect result from rounded recall.
    for pid, state in profile.get('sessions', {}).items():
        if state.get('reviewed'):
            evidence.append((pid, review_evidence(state, scoring.compute(state),
                state.get('stage') == 5 and state.get('stage5_turns', 0) >= 2 and state.get('ended'))))
    valid = [(pid, e) for pid, e in evidence if e.get('eligible')]
    played = {pid for pid, _ in valid} & PERSONAS
    quiz = profile.get('quiz', {})
    progress = {
        'first_review': int(bool(valid)),
        'all_flags': int(any(e.get('flags_total', 0) > 0 and e.get('flags_caught') == e['flags_total'] and e.get('false_positives') == 0 for _, e in valid)),
        'precise': int(any(e.get('flags_caught', 0) > 0 and e.get('false_positives') == 0 for _, e in valid)),
        'all_personas': len(played),
        'wallet': int(any(pid == 'scammer' and e.get('wallet') for pid, e in valid)),
        'comeback': int(any(e.get('comeback') for _, e in valid)),
        'quiz_complete': int(quiz.get('completed_count', 0) > 0),
        'quiz_perfect': int(quiz.get('completed_count', 0) > 0 and quiz.get('best_score', 0) == 6),
    }
    unlocked = profile.setdefault('achievements', {})
    new = []
    for key, title, description, icon, group, target in BADGES:
        if progress[key] >= target and key not in unlocked:
            unlocked[key] = time.time()
            new.append(key)
    badges = [{'id': key, 'title': title, 'description': description, 'icon': icon, 'group': group,
               'target': target, 'progress': target if key in unlocked else progress[key],
               'unlocked': key in unlocked, 'unlocked_at': unlocked.get(key)}
              for key, title, description, icon, group, target in BADGES]
    return {'badges': badges, 'unlocked_count': sum(b['unlocked'] for b in badges), 'total': len(badges), 'newly_unlocked': new}


def state(store, player):
    with store.lock(player):
        profile = store.load(player)
        before = dict(profile.get('achievements', {}))
        result = sync(profile)
        if profile['achievements'] != before:
            store.save(profile)
        return result
