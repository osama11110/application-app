from .karriere_at import KarriereAt
from .stepstone_at import StepstoneAt
from .jobs_at import JobsAt
from .indeed_at import IndeedAt
from .linkedin import LinkedIn
from .willhaben_at import WillhabenAt
from .hokify_at import HokifyAt
from .xing import Xing
from .monster_at import MonsterAt
from .devjobs_at import DevJobsAt

SITE_MAP = {
    "karriere_at":  KarriereAt,
    "stepstone_at": StepstoneAt,
    "jobs_at":      JobsAt,
    "indeed":       IndeedAt,
    "linkedin":     LinkedIn,
    "willhaben":    WillhabenAt,
    "hokify":       HokifyAt,
    "xing":         Xing,
    "monster":      MonsterAt,
    "devjobs_at":   DevJobsAt,
}
