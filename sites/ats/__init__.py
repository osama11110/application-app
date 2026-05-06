from .detector import detect_ats, is_external
from . import greenhouse, lever, personio, workday, smartrecruiters, erecruiter, softgarden, generic

_HANDLERS = {
    "greenhouse":      greenhouse.apply,
    "lever":           lever.apply,
    "personio":        personio.apply,
    "workday":         workday.apply,
    "smartrecruiters": smartrecruiters.apply,
    "erecruiter":      erecruiter.apply,
    "softgarden":      softgarden.apply,
    # All other detected or unknown portals fall through to generic
    "recruitee":       generic.apply,
    "taleo":           generic.apply,
    "icims":           generic.apply,
    "bamboohr":        generic.apply,
    "successfactors":  generic.apply,
    "breezy":          generic.apply,
    "jobvite":         generic.apply,
    "dvinci":          generic.apply,
    "rexx":            generic.apply,
    "umantis":         generic.apply,
    "talentsuite":     generic.apply,
    "generic":         generic.apply,
}


def get_handler(ats_name: str):
    return _HANDLERS.get(ats_name, generic.apply)
