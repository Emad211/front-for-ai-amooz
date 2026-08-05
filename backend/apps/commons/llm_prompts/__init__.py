from .prompts import PROMPTS
from .exam_prep_page import EXAM_PREP_PAGE_PROMPTS
from .exam_prep_question_repair import EXAM_PREP_QUESTION_REPAIR_PROMPTS
from .exam_prep_v4 import EXAM_PREP_V4_PROMPTS

PROMPTS.update(EXAM_PREP_PAGE_PROMPTS)
PROMPTS.update(EXAM_PREP_QUESTION_REPAIR_PROMPTS)
PROMPTS.update(EXAM_PREP_V4_PROMPTS)
