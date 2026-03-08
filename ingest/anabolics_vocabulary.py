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
blast, cruise, blast and cruise, BnC, B and C,
cycle, on cycle, off cycle, cycling,
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

BODYBUILDING SLANG & STREET NAMES:
gear, juice, sauce, roids, vitamin S, vitamin T,
natty, natural, enhanced, juiced, on the sauce,
TRT, testosterone replacement therapy, hormone replacement, HRT,
blast, cruise, blast and cruise, BnC, permablast,
cycle, on cycle, off cycle, bridging,
frontload, frontloading, kickstart,
pin, pinning, jabbing, shooting, injecting,
pip, post injection pain, virgin muscle,
sides, side effects,
gains, gainz, newbie gains, noob gains,
cutting, cut, shredding, getting lean, getting peeled,
bulking, bulk, mass phase, offseason, off-season,
recomp, recomposition, body recomposition,
dry compound, wet compound, dry gains, wet gains,
19-nor, 19-nors, nandrolone class, tren class,
DHT, DHT derivative, DHT-based,
UGL, underground lab, underground,
pharma, pharma grade, pharmaceutical grade, human grade,
raws, raw powder, raw powders,
homebrew, home brew, brewing,
orals, oral steroids, oral only,
injectables, injectable steroids, oils,
ancillaries, support supps, cycle support,

STEROID SLANG NAMES:
test, testosterone, vitamin T,
tren, trenbolone, tren train, trensomnia,
mast, masteron, the hardener,
winny, winstrol, stanozolol,
var, anavar, oxandrolone, girl steroid,
dbol, d-bol, dianabol, dbol bloat,
drol, anadrol, a-bombs, a-50,
deca, deca dick, nandrolone, nand,
NPP, nandrolone phenylpropionate, fast deca,
EQ, equipoise, boldenone, bold,
primo, primobolan, the gentle giant,
trest, MENT, trestolone, mental trest,
sus, sust, sustanon, sus 250,
TNE, test no ester, test suspension, test base,
prop, propionate, short ester,
ace, acetate, short ester,
enth, enanthate, long ester,
cyp, cypionate, long ester,
undeca, undecanoate, very long ester,
halo, halotestin, the aggression drug,
tbol, turinabol, oral turinabol,
superdrol, sdrol, methyldrostanolone,
cheque drops, mibolerone,
mtren, methyltrienolone, oral tren,

SARM SLANG:
osta, ostarine, MK-2866, enobosarm,
rad, RAD-140, testolone,
lgd, LGD-4033, ligandrol, anabolicum,
card, cardarine, GW-501516, endurobol,
mk, MK-677, ibutamoren, nutrobal,
yk, YK-11, myostine,
s4, andarine, gtx-007,
s23, super andarine,

AI & SERM SLANG:
AI, aromatase inhibitor, estrogen blocker,
adex, arimidex, anastrozole,
aromasin, asin, exemestane, suicide inhibitor,
letro, letrozole, femara,
nolva, nolvadex, tamoxifen, titty pills,
clomid, clomiphene, fertility drug,
ralox, raloxifene, evista,
gyno, gynecomastia, bitch tits, man boobs,
puffy nips, spicy nips, sensitive nipples,
crashed E2, crashed estrogen, low estrogen,
high E2, high estrogen, estrogen rebound,

PEPTIDE SLANG:
GH, growth, growth hormone, HGH,
slin, insulin, slinning,
humalog, humulin, novolog, novalog,
sema, semaglutide, ozempic, wegovy, rybelsus,
tirz, tirzepatide, mounjaro, zepbound,
reta, retatrutide, triple G, triple agonist,
frag, HGH frag, fragment 176-191,
ipa, ipamorelin, the clean GHRP,
mod GRF, modified GRF, CJC no DAC, CJC without DAC,
GHRP, growth hormone releasing peptide,
BPC, BPC-157, body protection compound, wolverine peptide,
TB, TB-500, thymosin beta,
PT, PT-141, bremelanotide, the sex peptide,
MT2, melanotan, melanotan 2, barbie drug,
GHK, GHK-Cu, copper peptide,

SUPPLEMENT SLANG:
pre, pre-workout, PWO, preworkout,
post, post-workout, PWO,
intra, intra-workout,
whey, whey protein, whey isolate, WPI,
casein, slow protein, night protein,
BCAAs, branched chain amino acids, branch chains,
EAAs, essential amino acids, essentials,
creatine, creatine monohydrate, the OG supplement,
beta, beta-alanine, tingles,
cit, citrulline, citrulline malate, L-citrulline,
pump, pumps, skin splitting pumps,
stim, stimulant, high stim,
non-stim, stim-free, no stim,
test booster, testosterone booster, natty test,
fat burner, thermogenic, thermo,
GDA, glucose disposal agent, carb blocker,

BLOOD WORK SLANG:
bloods, blood work, labs, lab work,
total T, total testosterone,
free T, free testosterone,
sensitive E2, sensitive estradiol,
hematocrit, HCT, thick blood,
hemoglobin, HGB,
liver values, liver enzymes, AST, ALT, GGT,
lipids, cholesterol panel, lipid panel, HDL, LDL,
RBC, red blood cells, polycythemia,
kidney function, creatinine, BUN, eGFR, cystatin C,
CBC, complete blood count,
CMP, comprehensive metabolic panel,
prolactin, prolactin gyno, deca dick,

ADVANCED BLOODWORK MARKERS:
hs-CRP, C-reactive protein, homocysteine, BNP, NT-proBNP, troponin,
HbA1c, A1c, fasting glucose, fasting insulin, HOMA-IR, C-peptide,
ferritin, TIBC, transferrin saturation, iron panel,
microalbumin, cystatin C, eGFR, glomerular filtration rate,
coronary calcium score, CIMT, carotid intima-media thickness,
reticulocyte count, blood viscosity,
TSH, free T3, free T4, reverse T3, thyroid antibodies, calcitonin,
IL-6, TNF-alpha, fibrinogen, ESR,

BLOODWORK PHARMACEUTICALS:
rosuvastatin, atorvastatin, pitavastatin, ezetimibe,
telmisartan, lisinopril, amlodipine,
TUDCA, UDCA, NAC, N-acetyl cysteine,
cabergoline, P5P, pyridoxal-5-phosphate,
metformin, berberine,
citrus bergamot, naringin, niacin,
NAD+, L-carnitine, injectable L-carnitine,
anastrozole, exemestane, aromasin, arimidex,
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
    # NOTE: "trend", "tran", "train" removed — too aggressive as substring matches
    # They corrupt "training" → "trening", "trend" → "tren", "transaction" → etc.
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
    # NOTE: "ibuprofen" → "ibutamoren" removed — ibuprofen is a real drug (NSAID)
    # that users legitimately discuss. This was NOT a safe correction.
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
    # NOTE: "clean" → "clen" removed — corrupts "clean", "cleanest", "cleaner", etc.
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
    # NOTE: "ester" → "ester" removed (no-op that wastes processing)
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

    # ─── BODYBUILDING SLANG CORRECTIONS ───
    # Gear/Juice slang
    "on the sauce": "on the sauce",
    "vitamin t": "vitamin T",
    "vitamin s": "vitamin S",
    "juice head": "juicehead",
    "gear head": "gearhead",
    "natty or not": "natty or not",
    "not natty": "not natty",
    "enhanced athlete": "enhanced athlete",

    # Cycle slang
    "b and c": "blast and cruise",
    "b n c": "BnC",
    "bee and see": "blast and cruise",
    "perma blast": "permablast",
    "perma blasting": "permablasting",
    "front load": "frontload",
    "front loading": "frontloading",
    "kick start": "kickstart",
    "kick starting": "kickstarting",
    "bridging": "bridging",
    "time on time off": "time on time off",

    # Injection slang
    "pinning": "pinning",
    "virgin muscle": "virgin muscle",
    "pip": "PIP",
    "post injection pain": "post injection pain",
    "subcu": "subq",
    "sub cue": "subq",

    # Body comp slang
    "getting peeled": "getting peeled",
    "getting shredded": "getting shredded",
    "cutting phase": "cutting phase",
    "bulking phase": "bulking phase",
    "bulk phase": "bulk phase",
    "off season": "offseason",
    "re comp": "recomp",
    "re comping": "recomping",
    "body recomp": "body recomp",
    "lean bulk": "lean bulk",
    "dirty bulk": "dirty bulk",
    "clean bulk": "clean bulk",
    "mini cut": "mini cut",
    "maintenance": "maintenance",

    # Compound class slang
    "19 nor": "19-nor",
    "19 nors": "19-nors",
    "d h t": "DHT",
    "dht derivative": "DHT derivative",
    "dht based": "DHT-based",
    "wet compound": "wet compound",
    "dry compound": "dry compound",
    "dry gains": "dry gains",
    "wet gains": "wet gains",

    # Source slang
    "u g l": "UGL",
    "underground lab": "underground lab",
    "pharma grade": "pharma grade",
    "human grade": "human grade",
    "home brew": "homebrew",
    "home brewing": "homebrewing",
    "raw powder": "raw powder",
    "raw powders": "raw powders",

    # Steroid nicknames
    "trest": "MENT",
    "mental trest": "mental trest",
    "tren train": "tren train",
    "tren somnia": "trensomnia",
    "tren cough": "tren cough",
    "deca dick": "deca dick",
    "dbol bloat": "dbol bloat",
    "a bombs": "A-bombs",
    "a 50": "A-50",
    "a fifty": "A-50",
    "sus 250": "Sustanon 250",
    "sust 250": "Sustanon 250",
    "sustanon two fifty": "Sustanon 250",
    "test no ester": "TNE",
    "test suspension": "test suspension",
    "test base": "test base",
    "oral tren": "oral tren",
    "methyl tren": "methyltren",
    "check drops": "cheque drops",
    "cheek drops": "cheque drops",
    "superdrawl": "superdrol",
    "s drol": "sdrol",

    # SARM nicknames
    "osta reen": "ostarine",
    "rad one forty": "RAD-140",
    # NOTE: "test alone" → "testolone" removed — matches normal English phrase
    # "testolone" is already in WHISPER_PROMPT for Whisper biasing
    "anna bolic um": "anabolicum",
    "enduro ball": "endurobol",
    "new tro ball": "nutrobal",
    "my oh steen": "myostine",

    # AI/SERM slang
    "a dex": "adex",
    "a sin": "aromasin",
    "suicide inhibitor": "suicide inhibitor",
    "let row": "letro",
    "nova": "nolva",
    "titty pills": "titty pills",
    "bitch tits": "bitch tits",
    "man boobs": "man boobs",
    "puffy nips": "puffy nips",
    "spicy nips": "spicy nips",
    "crashed e2": "crashed E2",
    "crashed estrogen": "crashed estrogen",
    "high e2": "high E2",
    "estrogen rebound": "estrogen rebound",

    # Peptide slang
    # NOTE: "g h" → "GH" removed — too short, matches inside words like "hiGH", "weigHt"
    # NOTE: "growth" → "growth hormone" removed — corrupts "growth" in all contexts
    # These are handled by the REGEX_PATTERNS section with proper word boundaries
    "slinning": "slinning",
    "human log": "humalog",
    "nova log": "novolog",
    "novalog": "novolog",
    "semi glue tide": "semaglutide",
    "sema glue tide": "semaglutide",
    "oh zempic": "ozempic",
    "we go vee": "wegovy",
    "rye bell sus": "rybelsus",
    "tier zep a tide": "tirzepatide",
    "moon jar oh": "mounjaro",
    "zep bound": "zepbound",
    "retta true tide": "retatrutide",
    "triple g": "triple G",
    "triple agonist": "triple agonist",
    "h g h frag": "HGH frag",
    "fragment one seventy six": "fragment 176-191",
    "mod g r f": "mod GRF",
    "modified g r f": "modified GRF",
    "c j c no dac": "CJC no DAC",
    "c j c without dac": "CJC without DAC",
    "wolverine peptide": "wolverine peptide",
    "barbie drug": "barbie drug",
    "sex peptide": "sex peptide",

    # Supplement slang
    "pre workout": "pre-workout",
    "post workout": "post-workout",
    "intra workout": "intra-workout",
    "p w o": "PWO",
    "way protein": "whey protein",
    "way isolate": "whey isolate",
    "w p i": "WPI",
    "b c double a": "BCAAs",
    "b c a a s": "BCAAs",
    "branch chains": "branched chain amino acids",
    "e a a s": "EAAs",
    "essential aminos": "essential amino acids",
    "creatine mono": "creatine monohydrate",
    "the o g supplement": "the OG supplement",
    "beta alanine": "beta-alanine",
    "tingles": "tingles",
    "sit trill een": "citrulline",
    "citrulline mallet": "citrulline malate",
    "l citrulline": "L-citrulline",
    "skin splitting pumps": "skin-splitting pumps",
    "high stim": "high stim",
    "stim free": "stim-free",
    "no stim": "no stim",
    "test booster": "test booster",
    "natty test": "natty test",
    "fat burner": "fat burner",
    "thermo genic": "thermogenic",
    "g d a": "GDA",
    "glucose disposal": "glucose disposal agent",
    "carb blocker": "carb blocker",

    # Blood work slang
    "lab work": "lab work",
    "getting bloods": "getting bloods",
    "pulling bloods": "pulling bloods",
    "total t": "total T",
    "free t": "free T",
    "sensitive e two": "sensitive E2",
    "sensitive estradiol": "sensitive estradiol",
    "h c t": "HCT",
    "thick blood": "thick blood",
    "h g b": "HGB",
    "polly sith emia": "polycythemia",
    "poly cythemia": "polycythemia",
    "create a nine": "creatinine",
    "b u n": "BUN",
    "c b c": "CBC",
    "complete blood count": "complete blood count",
    "c m p": "CMP",
    "metabolic panel": "metabolic panel",
    "prolactin gyno": "prolactin gyno",

    # ThinkBig hosts
    "scott mcnally": "Scott McNally",
    "scott mc nally": "Scott McNally",
    "dave crossland": "Dave Crosland",
    "dave crosland": "Dave Crosland",
    "skip hill": "Skipp Hill",
    "skipp hill": "Skipp Hill",

    # ─── PHARMACEUTICAL CORRECTIONS (bloodwork interventions) ───
    # Statins
    "rosu vast atin": "rosuvastatin",
    "rose ooh vast atin": "rosuvastatin",
    "a tore vast atin": "atorvastatin",
    "at or vast atin": "atorvastatin",
    "pita vast atin": "pitavastatin",
    "eze tim ibe": "ezetimibe",
    "ez it a mibe": "ezetimibe",

    # Blood pressure meds
    "tell me sartan": "telmisartan",
    "tele me sartan": "telmisartan",
    "tell a me sartan": "telmisartan",
    "lice in a pril": "lisinopril",
    "lisin a pril": "lisinopril",
    "lie sin oh pril": "lisinopril",
    "am low dip een": "amlodipine",

    # Liver/kidney support
    "tudka": "TUDCA",
    "tud ca": "TUDCA",
    "you dca": "UDCA",
    "ur so dee oxy": "ursodeoxycholic",

    # Prolactin management
    "cab a go lean": "cabergoline",
    "cab urge oh lean": "cabergoline",
    "cab er go lean": "cabergoline",
    "p five p": "P5P",
    "p 5 p": "P5P",
    "pyridoxal five phosphate": "pyridoxal-5-phosphate",

    # Metabolic drugs
    "berber een": "berberine",
    "burr burr een": "berberine",

    # Supplements for bloodwork
    "citrus berg a mot": "citrus bergamot",
    "berg a mot": "bergamot",
    "nigh a sin": "niacin",
    "narin gin": "naringin",
    "narrow gin": "naringin",
    "n a c": "NAC",
    "n a d plus": "NAD+",
    "l car nah teen": "L-carnitine",
    "l car nih teen": "L-carnitine",
    "injectable l carnitine": "injectable L-carnitine",

    # ─── BLOODWORK MARKER CORRECTIONS ───
    "sis tatin c": "cystatin C",
    "sys tatin c": "cystatin C",
    "cyst a tin c": "cystatin C",
    "homo sis teen": "homocysteine",
    "homo cyst een": "homocysteine",
    "home oh sis teen": "homocysteine",
    "homa ir": "HOMA-IR",
    "homer ir": "HOMA-IR",
    "micro album in": "microalbumin",
    "micro al bumen": "microalbumin",
    "c reactive protein": "C-reactive protein",
    "see reactive protein": "C-reactive protein",
    "trop oh nin": "troponin",
    "trope oh nin": "troponin",
    "ferro tin": "ferritin",
    "fair a tin": "ferritin",
    "transfer in sat": "transferrin sat",
    "retick you low site": "reticulocyte",
    "eh gee fr": "eGFR",
    "glomer you lar": "glomerular",
    "cal see tonin": "calcitonin",
    "corona ree calcium": "coronary calcium",

    # ─── COMMON ASR ERRORS ───
    "natural prediction": "natural production",
    "arrow my taste": "aromatase",
    "aroma taste": "aromatase",
    "enhance ate": "enanthate",
    "in anthem": "enanthate",
    "sip your nate": "cypionate",
    "trend alone": "trenbolone",
    "trend bolo": "trenbolone",
    "nan dra loan": "nandrolone",
    "bold and own": "boldenone",
    "method own own": "methenolone",
    "anna straw sole": "anastrozole",
    "example stain": "exemestane",
    "cab ergo lean": "cabergoline",
}

# Case-insensitive regex patterns for trickier replacements
REGEX_PATTERNS = [
    # Testosterone esters
    (r'\btest\s+e\b', 'test e'),
    (r'\btest\s+c\b', 'test c'),
    (r'\btest\s+prop\b', 'test prop'),
    (r'\btest\s+u\b', 'test u'),
    (r'\btest\s+base\b', 'test base'),

    # Common compound abbreviations
    (r'\bd\s*ball?\b', 'dbol'),
    (r'\bd\s*bol\b', 'dbol'),
    (r'\be\s*q\b', 'EQ'),
    (r'\bn\s*p\s*p\b', 'NPP'),
    (r'\bt\s*n\s*e\b', 'TNE'),
    (r'\bs\s*drol\b', 'sdrol'),
    (r'\bt\s*bol\b', 'tbol'),

    # Hormones
    (r'\bh\s*g\s*h\b', 'HGH'),
    (r'\bh\s*c\s*g\b', 'HCG'),
    (r'\bi\s*g\s*f\s*[-]?\s*1\b', 'IGF-1'),
    (r'\bt\s*3\b', 'T3'),
    (r'\bt\s*4\b', 'T4'),

    # PCT/Support
    (r'\bp\s*c\s*t\b', 'PCT'),
    (r'\ba\s*i\b', 'AI'),
    (r'\bs\s*e\s*r\s*m\b', 'SERM'),
    (r'\be\s*2\b', 'E2'),

    # SARMs
    (r'\bl\s*g\s*d\b', 'LGD'),
    (r'\bm\s*k\s*[-]?\s*677\b', 'MK-677'),
    (r'\bm\s*k\s*[-]?\s*2866\b', 'MK-2866'),
    (r'\br\s*a\s*d\s*[-]?\s*140\b', 'RAD-140'),
    (r'\bg\s*w\s*[-]?\s*501516\b', 'GW-501516'),
    (r'\by\s*k\s*[-]?\s*11\b', 'YK-11'),
    (r'\bs\s*[-]?\s*4\b', 'S4'),
    (r'\bs\s*[-]?\s*23\b', 'S-23'),

    # Peptides
    (r'\bb\s*p\s*c\s*[-]?\s*157\b', 'BPC-157'),
    (r'\bt\s*b\s*[-]?\s*500\b', 'TB-500'),
    (r'\bp\s*t\s*[-]?\s*141\b', 'PT-141'),
    (r'\bm\s*t\s*[-]?\s*2\b', 'MT-2'),
    (r'\bc\s*j\s*c\s*[-]?\s*1295\b', 'CJC-1295'),
    (r'\bg\s*h\s*r\s*p\s*[-]?\s*[26]\b', 'GHRP'),
    (r'\bg\s*h\s*k\s*[-]?\s*cu\b', 'GHK-Cu'),
    (r'\ba\s*o\s*d\s*[-]?\s*9604\b', 'AOD-9604'),

    # GLP-1 drugs
    (r'\bg\s*l\s*p\s*[-]?\s*1\b', 'GLP-1'),
    (r'\bg\s*i\s*p\b', 'GIP'),

    # Cycle terminology
    (r'\bb\s*[&n]\s*c\b', 'BnC'),
    (r'\bb\s+and\s+c\b', 'blast and cruise'),
    (r'\bt\s*r\s*t\b', 'TRT'),
    (r'\bh\s*r\s*t\b', 'HRT'),
    (r'\bu\s*g\s*l\b', 'UGL'),

    # Blood work
    (r'\bc\s*b\s*c\b', 'CBC'),
    (r'\bc\s*m\s*p\b', 'CMP'),
    (r'\bh\s*c\s*t\b', 'HCT'),
    (r'\bh\s*g\s*b\b', 'HGB'),
    (r'\br\s*b\s*c\b', 'RBC'),
    (r'\ba\s*s\s*t\b', 'AST'),
    (r'\ba\s*l\s*t\b', 'ALT'),
    (r'\bb\s*u\s*n\b', 'BUN'),
    (r'\bs\s*h\s*b\s*g\b', 'SHBG'),
    (r'\bh\s*d\s*l\b', 'HDL'),
    (r'\bl\s*d\s*l\b', 'LDL'),

    # Supplements
    (r'\bp\s*w\s*o\b', 'PWO'),
    (r'\bb\s*c\s*a\s*a\s*s?\b', 'BCAAs'),
    (r'\be\s*a\s*a\s*s?\b', 'EAAs'),
    (r'\bg\s*d\s*a\b', 'GDA'),
    (r'\bw\s*p\s*i\b', 'WPI'),

    # Research chemicals
    (r'\bd\s*m\s*a\s*a\b', 'DMAA'),
    (r'\bd\s*m\s*h\s*a\b', 'DMHA'),
    (r'\bd\s*n\s*p\b', 'DNP'),

    # 19-nor class
    (r'\b19\s*[-]?\s*nor\b', '19-nor'),
    (r'\bd\s*h\s*t\b', 'DHT'),
    (r'\bd\s*h\s*b\b', 'DHB'),

    # Bloodwork markers
    (r'\bg\s*g\s*t\b', 'GGT'),
    (r'\be\s*g\s*f\s*r\b', 'eGFR'),
    (r'\bh\s*s\s*[-]?\s*c\s*r\s*p\b', 'hs-CRP'),
    (r'\bc\s*r\s*p\b', 'CRP'),
    (r'\bb\s*n\s*p\b', 'BNP'),
    (r'\bh\s*b\s*a\s*1\s*c\b', 'HbA1c'),
    (r'\ba\s*1\s*c\b', 'A1c'),
    (r'\bn\s*t\s*[-]?\s*pro\s*b\s*n\s*p\b', 'NT-proBNP'),
    (r'\bc\s*i\s*m\s*t\b', 'CIMT'),
    (r'\bt\s*u\s*d\s*c\s*a\b', 'TUDCA'),
    (r'\bu\s*d\s*c\s*a\b', 'UDCA'),
    (r'\bn\s*a\s*c\b', 'NAC'),
]


def get_whisper_prompt():
    """Return the full Whisper prompt for domain biasing."""
    return WHISPER_PROMPT.strip()


def correct_transcript(text):
    """Apply corrections to a transcript."""
    import re

    result = text

    # Apply simple replacements (case-insensitive) with WORD BOUNDARIES
    # to prevent substring corruption (e.g., "train" inside "training")
    for wrong, right in CORRECTIONS.items():
        # Skip comment-only entries (values starting with #)
        if wrong.startswith('#') or wrong.startswith('//'):
            continue
        escaped = re.escape(wrong)
        pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
        result = pattern.sub(right, result)

    # Apply regex patterns (these already have their own boundary handling)
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
