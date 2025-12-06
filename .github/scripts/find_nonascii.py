import unicodedata, re, hashlib, subprocess, pathlib, sys

def sanitize(name, index=None, max_len=200):
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_name = ascii_bytes.decode("ascii")
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', '-', ascii_name).strip('-')
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode('utf-8', 'surrogatepass')).hexdigest()[:12]
    suffix = f'-{index}' if index is not None else ''
    max_name_len = max_len - len(suffix)
    if len(ascii_name) > max_name_len:
        ascii_name = ascii_name[:max_name_len]
    return ascii_name + suffix

proc = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
files = [l for l in proc.stdout.splitlines() if l.strip()]
if not files:
    print("No git-tracked files found.")
    sys.exit(0)

print("=== Git-tracked files containing non-ASCII characters (if any) ===")
found = False
for f in files:
    if any(ord(c) > 127 for c in f):
        print(f)
        found = True
if not found:
    print("(none)")

print("\n=== Generating sanitized ids for all git-tracked files (sample mapping) ===")
bad_sanitized = []
for f in files:
    src_name = pathlib.Path(f).name
    sanitized = sanitize(src_name, index=0)
    bad_flag = any(ord(c) > 127 for c in sanitized)
    note = " [BAD]" if bad_flag else ""
    print(f"{f}  ->  {sanitized}{note}")
    if bad_flag:
        bad_sanitized.append((f, sanitized))

if bad_sanitized:
    print()
    print("Found sanitized IDs that still contain non-ASCII characters (unexpected):")
    for f, s in bad_sanitized:
        print(f"  {f} -> {s}")
    sys.exit(1)
else:
    print()
    print("All sanitized IDs are ASCII-only.")
    sys.exit(0)
