"""Server-scored practice using existing per-player locking and save lifecycle."""
from __future__ import annotations
import copy
import json
import secrets
import time
from pathlib import Path
from . import achievements

QUESTIONS = json.loads((Path(__file__).resolve().parent.parent / 'data/quiz.json').read_text(encoding='utf-8'))
HISTORY_LIMIT = 20


def _view(data):
    out = copy.deepcopy(data)
    attempt = out.get('active')
    if attempt:
        attempt['questions'] = [{k: q[k] for k in ('id', 'prompt', 'options')} for q in attempt['questions']]
    return out


def state(store, player):
    with store.lock(player):
        return _view(store.load(player).get('quiz', {'active': None, 'history': [], 'completed_count': 0, 'best_score': 0}))


def start(store, player):
    with store.lock(player):
        profile = store.load(player)
        data = profile.setdefault('quiz', {'active': None, 'history': [], 'completed_count': 0, 'best_score': 0})
        if data['active'] and not data['active']['completed']:
            return _view(data)
        rng = secrets.SystemRandom()
        selected = rng.sample([q for q in QUESTIONS if q['red_flag']], 5) + rng.sample([q for q in QUESTIONS if not q['red_flag']], 1)
        rng.shuffle(selected)
        data['active'] = {'id': secrets.token_urlsafe(18), 'questions': copy.deepcopy(selected),
                          'answers': [], 'completed': False, 'started_at': time.time()}
        store.save(profile)
        return _view(data)


def answer(store, player, attempt_id, question_id, choice, confidence):
    if not isinstance(attempt_id, str) or not isinstance(question_id, str):
        raise ValueError('attempt_id and question_id must be strings')
    if type(choice) is not int or type(confidence) is not int or confidence not in (1, 2, 3):
        raise ValueError('choice and confidence must be integers; confidence must be 1, 2 or 3')
    with store.lock(player):
        profile = store.load(player)
        data = profile.get('quiz', {})
        attempt = data.get('active')
        if not attempt or attempt['id'] != attempt_id:
            raise ValueError('測驗已更新，請關閉並重新開啟小測驗。')
        for saved in attempt['answers']:
            if saved['question_id'] == question_id:
                if saved['choice'] == choice and saved['confidence'] == confidence:
                    return _view(data)
                raise ValueError('這題已確認答案，不能更改。')
        if attempt['completed']:
            raise ValueError('這份測驗已完成。')
        q = attempt['questions'][len(attempt['answers'])]
        if q['id'] != question_id or not 0 <= choice < len(q['options']):
            raise ValueError('題目或選項無效，請重新開啟小測驗。')
        attempt['answers'].append({'question_id': q['id'], 'choice': choice, 'confidence': confidence,
                                   'correct': choice == q['answer'], 'correct_choice': q['answer'],
                                   'explanation': q['explanation'], 'red_flag': q['red_flag']})
        if len(attempt['answers']) == len(attempt['questions']):
            attempt['completed'] = True
            attempt['score'] = sum(a['correct'] for a in attempt['answers'])
            attempt['completed_at'] = time.time()
            data['completed_count'] += 1
            data['best_score'] = max(data['best_score'], attempt['score'])
            data['history'].append({'id': attempt['id'], 'score': attempt['score'], 'total': len(attempt['questions']),
                                    'completed_at': attempt['completed_at']})
            data['history'] = data['history'][-HISTORY_LIMIT:]
            achievements.sync(profile)
        store.save(profile)
        return _view(data)
