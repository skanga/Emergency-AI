"""Shared bounded observations from compatible user turns, never model claims."""
import re
from .query_planner import normalize
from .safety_patterns import (
    _breathing, _consciousness, _SWALLOW, _UNSAFE_SWALLOW, _CONDITIONAL,
)





def _facts(plan):
    facts = {'consciousness': None, 'breathing': None, 'swallowing': None,
             'age_group': plan.scope.get('age_group')}
    # Planner context contains only compatible prior user turns, never assistant
    # assertions. Current explicit facts override those inherited facts.
    for text in (*plan.context_turns, plan.question):
        for sentence in re.split(r'[.!?\n]+', text):
            t = normalize(sentence)
            if _CONDITIONAL.search(t):
                continue  # A hypothetical condition is not a patient observation.
            facts['consciousness'] = _consciousness(t) or facts['consciousness']
            facts['breathing'] = _breathing(t) or facts['breathing']
            if _UNSAFE_SWALLOW.search(t):
                facts['swallowing'] = 'unsafe'
            elif _SWALLOW.search(t):
                facts['swallowing'] = 'safe'
    return facts
