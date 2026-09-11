"""CHP lock errors. None of these imply a send happened."""


class ChpError(ValueError):
    """Base error for the outreach CHP decision lock."""


class ImmutableCommitError(ChpError):
    """R0 or evidence pack was mutated after seal."""


class AdversaryRequiredError(ChpError):
    """Structural adversary cannot be skipped when CHP lock is on."""


class NamedActorRequired(ChpError):
    """Lock requires a named human; automation aliases are rejected."""


class R0GateHalt(ChpError):
    """R0 foundation gate did not PASS; lock is refused."""


class EvidencePackError(ChpError):
    """Evidence pack missing, mutated, or digest mismatch."""
