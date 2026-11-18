import sys
import tarfile
import zipfile

whl = sys.argv[1]
sdist = sys.argv[2]

needles = [
    b"C:\\Users",
    b"P:\\GithubRepos",
    b"/p/GithubRepos",
    b"marcosudau-vps",
    b"api_key",
    b"apikey",
    b"secret",
    b"BEGIN RSA PRIVATE KEY",
    b"BEGIN OPENSSH PRIVATE KEY",
]


def scan_zip(path):
    hits = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        for n in names:
            data = zf.read(n)
            for needle in needles:
                if needle.lower() in data.lower():
                    hits.append((n, needle.decode()))
    return names, hits


def scan_tar(path):
    hits = []
    with tarfile.open(path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        for m in members:
            data = tf.extractfile(m).read()
            for needle in needles:
                if needle.lower() in data.lower():
                    hits.append((m.name, needle.decode()))
    return members, hits


names, hits = scan_zip(whl)
print("wheel files scanned:", len(names))
print("wheel hits:", hits if hits else "none")

members, hits2 = scan_tar(sdist)
print("sdist files scanned:", len(members))
print("sdist hits:", hits2 if hits2 else "none")

big = [(m.name, m.size) for m in members if m.size > 3_000_000 and "wakeword_models" not in m.name]
print("unexpectedly large sdist files (>3MB, not a wake asset):", big if big else "none")
