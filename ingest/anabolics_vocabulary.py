"""
Anabolics & Performance Enhancement Vocabulary
Used for Whisper prompts and post-processing corrections
"""

# Comprehensive list for Whisper prompt biasing
WHISPER_PROMPT = """
Fitness and bodybuilding discussion covering anabolic steroids, peptides, and performance enhancement.

STEROIDS & ANDROGENS:
testosterone, test, test e, test c, test prop, testosterone enanthate, testosterone cypionate, testosterone propionate,
trenbolone, tren, tren ace, tren e, trenbolone acetate, trenbolone enanthate,
masteron, mast, drostanolone, drostanolone propionate,
winstrol, winny, stanozolol,
anavar, var, oxandrolone,
dianabol, dbol, methandrostenolone,
anadrol, drol, oxymetholone,
deca, deca durabolin, nandrolone, nandrolone decanoate,
NPP, nandrolone phenylpropionate,
equipoise, EQ, boldenone, boldenone undecylenate,
primobolan, primo, methenolone,
superdrol, methyldrostanolone,
halotestin, halo, fluoxymesterone,
proviron, mesterolone,
turinabol, tbol, oral turinabol,
DHB, dihydroboldenone,
MENT, trestolone,

SARMS:
ostarine, MK-2866, enobosarm,
ligandrol, LGD-4033,
RAD-140, testolone,
andarine, S4,
cardarine, GW-501516,
YK-11, myostatin inhibitor,
MK-677, ibutamoren,
S23,

GROWTH HORMONE & PEPTIDES:
HGH, human growth hormone, growth hormone, somatropin,
IGF-1, insulin-like growth factor,
BPC-157, BPC 157, body protection compound,
TB-500, TB500, thymosin beta-4,
CJC-1295, CJC with DAC, CJC without DAC,
ipamorelin,
GHRP-2, GHRP-6, growth hormone releasing peptide,
tesamorelin,
sermorelin,
hexarelin,
AOD-9604,
PT-141, bremelanotide,
melanotan, MT-2, melanotan II,
semaglutide, ozempic, wegovy,
tirzepatide, mounjaro,
retatrutide,
GLP-1, glucagon-like peptide,

RESEARCH PEPTIDES & EXPERIMENTAL:
epithalon, epitalon, epithalamin, AEDG peptide,
selank,
semax,
dihexa,
cerebrolysin,
P21, P-21,
NA-Selank, NA-Semax,
DSIP, delta sleep inducing peptide,
GHK, GHK-Cu, copper peptide,
LL-37, cathelicidin,
thymalin,
vilon,
pinealon,
KPV, alpha-MSH,
VIP, vasoactive intestinal peptide,
kisspeptin, kisspeptin-10,
gonadorelin, GnRH,
SNAP-8, acetyl octapeptide,
argireline,
matrixyl, palmitoyl pentapeptide,
mots-c, MOTS-c, mitochondrial peptide,
humanin,
SS-31, elamipretide,
FGL, NCAM peptide,
PACAP, pituitary adenylate cyclase,
orexin, orexin-A, orexin-B,
oxytocin,
vasopressin,
insulin-like peptide 3, INSL3,
follistatin, follistatin-344, FS-344,
ACE-031,
YK-11,
myostatin, GDF-8,

RESEARCH CHEMICALS & NOOTROPICS:
phenibut,
tianeptine,
piracetam, aniracetam, oxiracetam, pramiracetam, phenylpiracetam,
noopept,
modafinil, armodafinil, adrafinil,
flmodafinil, CRL-40,940,
NSI-189,
BPC-157, stable BPC, BPC-157 acetate, BPC-157 arginine salt,
9-me-bc, 9-methyl-beta-carboline,
bromantane,
sunifiram, unifiram,
coluracetam,
fasoracetam,
PRL-8-53,
IDRA-21,
memantine,
cyclazodone, N-methyl-cyclazodone,
DMHA, DMAA, DMBA,
higenamine,
synephrine,
hordenine,
gramine,
octopamine,
beta-phenylethylamine, PEA,
4-DHEA, 1-DHEA, 19-nor-DHEA,
7-keto DHEA,
pregnenolone,
GABA, phenyl GABA,
agmatine, agmatine sulfate,
alpha-GPC,
citicoline, CDP-choline,
uridine,
lion's mane, hericenones, erinacines,
cordyceps,
reishi,
ashwagandha, KSM-66, sensoril,
rhodiola, rhodiola rosea,
bacopa, bacopa monnieri,
ginkgo biloba,
phosphatidylserine,
ALCAR, acetyl-L-carnitine,
sulbutiamine,

DRUGS IN DEVELOPMENT & CLINICAL TRIALS:
retatrutide, triple agonist,
survodutide,
cagrilintide, cagrisema,
orforglipron,
pemvidutide,
danuglipron,
ecnoglutide,
bimagrumab, BYM338,
taldefgrobep alfa, anti-myostatin,
domagrozumab,
stamulumab,
trevogrumab,
apitegromab,
SRK-015,
vosoritide,
setmelanotide,
bremelanotide, PT-141,
REGN-4461,
anamorelin, ghrelin agonist,
enobosarm, GTx-024,
VK5211, LGD-4033 clinical,
GSK2881078,
PF-06260414,
RAD-140 clinical,
S-40503,
S-23, S23,
ACP-105,
AC-262536,
LGD-3303,
PF-06412562,
tesamorelin,
somapacitan,
lonapegsomatropin,
somatrogon,
TransCon hGH,
MOD-4023,
NNC0195-0092,
somavaratan,
CJC-1295 clinical, modified GRF,
macimorelin,
pralmorelin,
tabimorelin,
examorelin,
capromorelin,
ibutamoren mesylate, MK-0677,
AOD-9604 clinical,
fragmento 176-191, HGH frag,
terlipressin,
pegvisomant,
pasireotide,
lanreotide,
octreotide,

ESTROGEN & ANTI-ESTROGENS:
aromatase inhibitor, AI,
anastrozole, arimidex,
letrozole, femara,
exemestane, aromasin,
tamoxifen, nolvadex, nolva,
clomid, clomiphene,
raloxifene, evista,
gyno, gynecomastia,

PCT & SUPPORT:
PCT, post cycle therapy,
HCG, human chorionic gonadotropin,
DHEA, dehydroepiandrosterone,
pregnenolone,
TUDCA, tauroursodeoxycholic acid,
NAC, N-acetyl cysteine,
milk thistle, silymarin,
liver support,

INSULIN & METABOLICS:
insulin, slin,
humalog, novolog, lantus,
metformin,
berberine,
GDA, glucose disposal agent,
DNP, dinitrophenol,
clenbuterol, clen,
T3, cytomel, liothyronine,
T4, levothyroxine,
albuterol,
ephedrine,

TERMINOLOGY:
blast, cruise, blast and cruise,
cycle, on cycle, off cycle,
stack, stacking,
ester, half-life,
aromatization, aromatize,
anabolic, androgenic, anabolic androgenic steroid, AAS,
bioavailability,
intramuscular, IM, subcutaneous, subq, sub-q,
pinning, pin, injection site,
pip, post injection pain,
water retention, bloat,
vascularity, vascular,
myostatin, follistatin,
androgen receptor, AR,
free testosterone, total testosterone,
SHBG, sex hormone binding globulin,
E2, estradiol, estrogen,
prolactin,
progesterone,
cortisol,
liver enzymes, AST, ALT,
lipids, HDL, LDL, cholesterol,
hematocrit, hemoglobin, RBC,
blood pressure, BP,
"""

# Post-processing corrections for common ASR mistakes
# Format: { "misheard": "correct" }
CORRECTIONS = {
    # Masteron variants
    "master on": "masteron",
    "master ron": "masteron",
    "master own": "masteron",
    "mast her on": "masteron",
    "the restaurant": "drostanolone",
    "drost a known": "drostanolone",

    # Trenbolone variants
    "trend": "tren",
    "tran": "tren",
    "train": "tren",
    "tremble own": "trenbolone",
    "trend below": "trenbolone",
    "tremble on": "trenbolone",
    "trend balone": "trenbolone",

    # Winstrol variants
    "when straw": "winstrol",
    "win stroll": "winstrol",
    "when stroll": "winstrol",
    "wind stroll": "winstrol",
    "win strahl": "winstrol",
    "stan ozone all": "stanozolol",
    "stan oh zole all": "stanozolol",

    # Anavar
    "an a var": "anavar",
    "anna var": "anavar",
    "on of our": "anavar",
    "ox and roll own": "oxandrolone",

    # Dianabol
    "die anna ball": "dianabol",
    "diana ball": "dianabol",
    "d ball": "dbol",
    "d bowl": "dbol",

    # Testosterone
    "test e": "test e",
    "test see": "test c",
    "test prop": "test prop",
    "in and fate": "enanthate",
    "sip ion eight": "cypionate",
    "pro p on eight": "propionate",

    # Deca / Nandrolone
    "deck a": "deca",
    "nan draw loan": "nandrolone",
    "nan dro lone": "nandrolone",
    "deca dura bolin": "deca durabolin",

    # Equipoise / Boldenone
    "equip oise": "equipoise",
    "bowl den own": "boldenone",
    "bold a known": "boldenone",
    "e q": "EQ",

    # Primobolan
    "primo bolan": "primobolan",
    "pre mo bolan": "primobolan",
    "pre mobile an": "primobolan",
    "method own": "methenolone",

    # Anadrol
    "anna drawl": "anadrol",
    "oxy meth alone": "oxymetholone",
    "oxy method own": "oxymetholone",

    # HGH / Growth Hormone
    "h g h": "HGH",
    "growth harm own": "growth hormone",
    "so matt row pin": "somatropin",
    "i g f one": "IGF-1",
    "i g f 1": "IGF-1",

    # Peptides
    "b p c one fifty seven": "BPC-157",
    "b p c 157": "BPC-157",
    "bpc one fifty seven": "BPC-157",
    "bpc one five seven": "BPC-157",
    "bpc 157": "BPC-157",
    "bpc157": "BPC-157",
    "t b five hundred": "TB-500",
    "t b 500": "TB-500",
    "tb five hundred": "TB-500",
    "thyme oh sin": "thymosin",
    "thy most in": "thymosin",
    "i pa more lynn": "ipamorelin",
    "ippa more lin": "ipamorelin",
    "c j c": "CJC",
    "cjc twelve ninety five": "CJC-1295",
    "g h r p": "GHRP",
    "sarah more lynn": "sermorelin",
    "hexa rellin": "hexarelin",

    # SARMs
    "oster een": "ostarine",
    "osta reen": "ostarine",
    "m k two eight six six": "MK-2866",
    "lig and roll": "ligandrol",
    "l g d": "LGD",
    "lgd four oh three three": "LGD-4033",
    "rad one forty": "RAD-140",
    "rad one four zero": "RAD-140",
    "card a reen": "cardarine",
    "card uh reen": "cardarine",
    "ibuprofen": "ibutamoren",  # common mistake
    "i boot a more in": "ibutamoren",
    "m k six seventy seven": "MK-677",

    # Anti-estrogens
    "arrow my sin": "aromasin",
    "aroma sin": "aromasin",
    "ex mess tane": "exemestane",
    "anna straw zole": "anastrozole",
    "arimidex": "arimidex",
    "let row zole": "letrozole",
    "femme are a": "femara",
    "nova decks": "nolvadex",
    "nova dex": "nolvadex",
    "ta moxie fin": "tamoxifen",
    "clo mid": "clomid",
    "clo my feen": "clomiphene",

    # HCG / PCT
    "h c g": "HCG",
    "hcg": "HCG",
    "core ee on ick": "chorionic",
    "go nada tro pin": "gonadotropin",
    "p c t": "PCT",
    "post cycle": "post cycle",

    # Insulin
    "insulin": "insulin",
    "human log": "humalog",
    "nova log": "novolog",
    "lawn tis": "lantus",
    "met for men": "metformin",

    # Thyroid
    "t three": "T3",
    "t four": "T4",
    "sigh toe mell": "cytomel",
    "lie oh thy row neen": "liothyronine",
    "levo thigh rocks in": "levothyroxine",

    # Clen / Fat burners
    "clean boot a roll": "clenbuterol",
    "clen brutal": "clenbuterol",
    "clean": "clen",
    "d n p": "DNP",
    "die nitro": "dinitrophenol",
    "al beauty roll": "albuterol",
    "a fed rin": "ephedrine",

    # GLP-1 agonists
    "semi glue tide": "semaglutide",
    "ozempic": "ozempic",
    "we go v": "wegovy",
    "tear zep a tide": "tirzepatide",
    "moon jar oh": "mounjaro",
    "retta true tide": "retatrutide",
    "ret a true tide": "retatrutide",
    "sir vo due tide": "survodutide",
    "cag re lint tide": "cagrilintide",
    "or for glip ron": "orforglipron",

    # Research peptides
    "epi talon": "epithalon",
    "epi thal on": "epithalon",
    "sell ankle": "selank",
    "see max": "semax",
    "die hexa": "dihexa",
    "die hex a": "dihexa",
    "sarah bro lice in": "cerebrolysin",
    "g h k": "GHK",
    "g h k copper": "GHK-Cu",
    "thy may lin": "thymalin",
    "vile on": "vilon",
    "pin eel on": "pinealon",
    "kiss pep tin": "kisspeptin",
    "gonna door elin": "gonadorelin",
    "g n r h": "GnRH",
    "mots see": "MOTS-c",
    "human in": "humanin",
    "follow stat in": "follistatin",
    "myo stat in": "myostatin",
    "ace oh three one": "ACE-031",

    # Research chemicals / nootropics
    "fenny boot": "phenibut",
    "feen a boot": "phenibut",
    "tea anna pep teen": "tianeptine",
    "peer ass a tam": "piracetam",
    "annie rass a tam": "aniracetam",
    "noop ept": "noopept",
    "no a pept": "noopept",
    "moe daf in il": "modafinil",
    "arm oh daf a nil": "armodafinil",
    "bro man tane": "bromantane",
    "soon if a ram": "sunifiram",
    "call you rass a tam": "coluracetam",
    "faso rass a tam": "fasoracetam",
    "mem man teen": "memantine",
    "d m h a": "DMHA",
    "d m a a": "DMAA",
    "high jen a mean": "higenamine",
    "sin a freen": "synephrine",
    "hoard a neen": "hordenine",
    "agma teen": "agmatine",
    "alpha g p c": "alpha-GPC",
    "city coal lean": "citicoline",
    "c d p coal lean": "CDP-choline",
    "your a deen": "uridine",
    "lions main": "lion's mane",
    "lion's main": "lion's mane",
    "cord a seps": "cordyceps",
    "ray she": "reishi",
    "ash wa ganda": "ashwagandha",
    "ash wa gone da": "ashwagandha",
    "road ee ola": "rhodiola",
    "back oh pa": "bacopa",
    "gink go": "ginkgo",
    "phosphate a dill sear een": "phosphatidylserine",
    "al car": "ALCAR",
    "sul boot a mean": "sulbutiamine",

    # Drugs in development
    "by ma grew mab": "bimagrumab",
    "tall def grow bep": "taldefgrobep",
    "anna more lynn": "anamorelin",
    "en oh bo sarm": "enobosarm",
    "tess a more lin": "tesamorelin",
    "soma pack a tan": "somapacitan",
    "massy more lin": "macimorelin",
    "peg viso mant": "pegvisomant",
    "pass ear ee oh tide": "pasireotide",
    "lan ree oh tide": "lanreotide",
    "ocktree oh tide": "octreotide",

    # General terms
    "a a s": "AAS",
    "anabolic androgenic": "anabolic androgenic",
    "arrow mitt eyes": "aromatize",
    "arrow ma taze": "aromatase",
    "andro gin": "androgen",
    "ester": "ester",
    "half life": "half-life",
    "bio availability": "bioavailability",
    "sub q": "subq",
    "sub queue": "subq",
    "i m": "IM",
    "intra muscular": "intramuscular",
    "my oh stat in": "myostatin",
    "follow stat in": "follistatin",
    "s h b g": "SHBG",
    "hema toe crit": "hematocrit",
    "hemo globe in": "hemoglobin",
}

# Case-insensitive regex patterns for trickier replacements
REGEX_PATTERNS = [
    (r'\btest\s+e\b', 'test e'),
    (r'\btest\s+c\b', 'test c'),
    (r'\bd\s*ball?\b', 'dbol'),
    (r'\be\s*q\b', 'EQ'),
    (r'\bn\s*p\s*p\b', 'NPP'),
    (r'\bh\s*g\s*h\b', 'HGH'),
    (r'\bh\s*c\s*g\b', 'HCG'),
    (r'\bp\s*c\s*t\b', 'PCT'),
    (r'\ba\s*i\b', 'AI'),
    (r'\bt\s*3\b', 'T3'),
    (r'\bt\s*4\b', 'T4'),
]


def get_whisper_prompt():
    """Return the full Whisper prompt for domain biasing."""
    return WHISPER_PROMPT.strip()


def correct_transcript(text):
    """Apply corrections to a transcript."""
    import re

    result = text

    # Apply simple replacements (case-insensitive)
    for wrong, right in CORRECTIONS.items():
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        result = pattern.sub(right, result)

    # Apply regex patterns
    for pattern, replacement in REGEX_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


if __name__ == "__main__":
    # Test corrections
    test_cases = [
        "master on trend when straw",
        "I'm taking test e and master on",
        "BPC one fifty seven with t b five hundred",
    ]

    print("Testing corrections:\n")
    for test in test_cases:
        print(f"Original: {test}")
        print(f"Corrected: {correct_transcript(test)}")
        print()
