# Session notes: p01

**user**: The 1.3.2 release failed verification on the deploy target: every single file was reported missing, even though the tarball contents were byte-for-byte fine. The manifest that shipped is preserved at incident/manifest-1.3.2.json, the target's verification log at incident/verify.log, and the generator that produced it at incident/make_manifest_1.3.2.py. Work out why the target could not match a single path, and specify precisely what the path keys in the manifest must look like so that any build machine produces a manifest any deploy target can verify. State the rule and show the three keys as they should have been; no need to write the fixed generator.

**assistant [Read]**: 
> 1	{
2	  "C:\\builds\\agent7\\repo\\release\\app\\main.py": "a3f6c1de9b2a44e7815f0c9d3b6a2e441f7d8c05aa11b23c445d6e778899aabb",
3	  "C:\\builds\\agent7\\repo\\release\\assets\\banner.txt": "0d1e2f3a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9012345678abcd",
4	  "C:\\builds\\agent7\\repo\\release\\VERSION": "5f4e3d2c1b0a99887766554433221100ffeeddccbbaa00112233445566778899"
5	}
6	

**assistant [Read]**: 
> 1	verify: reading manifest-1.3.2.json, 3 entries
2	verify: MISSING C:\builds\agent7\repo\release\app\main.py
3	verify: MISSING C:\builds\agent7\repo\release\assets\banner.txt
4	verify: MISSING C:\builds\agent7\repo\release\VERSION
5	verify: FAILED, 3 of 3 entries unmatched on target (linux host, tree extracted at /srv/deploy/parcel)
6	

**assistant [Read]**: 
> 1	"""Manifest generator as run for the 1.3.2 release. Kept for the failed-verification investigation."""
2	
3	import hashlib
4	import json
5	import os
6	
7	manifest = {}
8	for dirpath, dirnames, filenames in os.walk(os.path.abspath("release")):
9	    for name in sorted(filenames):
10	        path = os.path.join(dirpath, name)
11	        with open(path, "rb") as handle:
12	            manifest[path] = hashlib.sha256(handle.read()).hexdigest()
13	with open("manifest.json", "w", encoding="utf-8") as out:
14	    json.dump(manifest, out, indent=2)
15	

**assistant**: Let me check the actual file structure to confirm the relative

**assistant [Bash]**: 
> release/VERSION
release/app/main.py
release/assets/banner.txt

**assistant**: ## Root Cause

The manifest keys are **absolute paths** captured from the Windows build machine (`C:\builds\agent7\repo\release\...`). The deploy target is a Linux host with the tree extracted at `/srv/deploy/parcel`, so it can never match those machine-specific Windows paths. Every single file is reported "MISSING" because the lookup is literal — there is no `C:` drive on the target.

This is a classic **portability bug**: absolute paths embed the build machine's filesystem layout (OS drive letter, CI agent working directory, path separators), which differs from every deploy target.

## The Rule

**Manifest keys must be relative paths, normalised to forward slashes, rooted at the release tree (i.e. the content root of the tarball).** This guarantees that any build machine (Windows, Linux, macOS) produces a manifest that any deploy target, regardless of where it extracts the tarball, can verify.

## The Three Keys as They Should Have Been

```
app/main.py
assets/banner.txt
VERSION
```

(Forward slashes keep the manifest OS-independent; no leading `./` so they are clean relative paths with no ambiguity.)

**user**: Agreed. Decision: manifest path keys are always relative to the repo root and written with forward slashes, that is POSIX paths like release/app/main.py, never absolute and never OS-native backslashed. That is what makes it a portable manifest: the same tree yields the same keys on any build machine, and any deploy target can resolve them.
