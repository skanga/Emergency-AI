"""Shared bounded action patterns; topical water use is not oral intake."""
import re

WATER_INTAKE = re.compile(
    r'\b(?:offer|give|drink|sip|oferec(?:a|er)|ofrec(?:e|er)|ofrezca(?:le)?|beba|dele)\b'
    r'(?:\s+\w+){0,8}\s+\b(?:water|agua)\b')
