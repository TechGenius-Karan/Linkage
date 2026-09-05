"""Curated word lists used by the vocabulary filter chain.

Domain tier: pure data.

These are hand-maintained on purpose. planning.md 7.9.4 Tier 3 makes the case:
degree-percentile removal punishes a word for being *well-connected*, but the
actual problem is a word being *generic*. `music`, `fire` and `gold` are all
high-degree and all excellent puzzle words. `thing`, `stuff` and `way` are the
poison, and only a person can tell the difference.
"""

from __future__ import annotations

#: Function words and other tokens that can never form an interesting link.
STOPWORDS: frozenset[str] = frozenset(
    """
    the be to of and in that have it for not on with as you do at this but his
    from they we say her she or an will my one all would there their what so up
    out if about who get which go me when make can like time no just him know
    take people into year your good some could them see other than then now
    look only come its over also back after use two how our work first well way
    even new want because any these give day most us is are was were been being
    has had did does am shall should may might must ought need dare
    i he it we you they me him her us them my your his its our
    their mine yours hers ours theirs myself yourself himself herself itself
    ourselves yourselves themselves
    who whom whose what which where when why how
    a an and or but nor for yet so
    very really quite rather too also just still yet already
    """.split()
)

#: Words that are technically nouns and technically well-connected, but carry
#: no conceptual content. Left in, every path routes through them and you get
#: `cat -> animal -> thing -> object -> box` (planning.md 7.3).
GENERIC_HUBS: frozenset[str] = frozenset(
    """
    thing things something anything everything nothing
    object objects item items stuff material
    person people human man woman men women guy folks
    place places area region spot location position
    part parts piece pieces bit section portion segment
    way ways method manner mode means
    kind kinds sort sorts type types form forms
    group groups set sets collection bunch lot
    amount number quantity level degree rate
    time times moment period point instance case
    thought idea concept notion subject topic matter
    fact info information detail details data
    name word term title label
    result effect cause reason purpose
    state condition situation status
    system process activity action event
    example sample instance
    member unit element component
    property feature quality attribute characteristic
    value worth measure size
    end start beginning middle side top bottom front back
    change difference variety
    """.split()
)

#: Shipped to the public. Kept short and unambiguous; slurs and sexual content
#: are excluded outright rather than risked in a puzzle.
PROFANITY: frozenset[str] = frozenset(
    """
    ass arse arsehole asshole bastard bitch bollocks boob boobs
    cock crap cunt damn dick dildo dyke fag faggot fuck fucker fucking
    goddamn hell homo horny jerk jizz kike nigga nigger nipple
    penis piss porn prick pussy queer rape rapist retard retarded
    scrotum semen sex sexy shit slut sperm spic testicle tit tits
    tranny turd twat vagina wank wanker whore
    """.split()
)

#: Proper nouns worth keeping. WordNet classifies many of these as instances
#: rather than common nouns, so they would be lost to a blanket POS filter --
#: but they are exactly where the best "aha" moments live (planning.md 7.1).
PROPER_NOUN_ALLOWLIST: frozenset[str] = frozenset(
    """
    newton einstein darwin galileo tesla edison mozart beethoven shakespeare
    picasso vangogh napoleon caesar cleopatra lincoln gandhi
    rome paris london tokyo egypt greece china india africa europe asia
    america england france germany japan russia spain italy
    everest amazon sahara nile atlantis
    christmas halloween easter
    mars venus jupiter saturn mercury neptune pluto
    """.split()
)
