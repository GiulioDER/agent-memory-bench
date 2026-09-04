# Session notes: p01

**user**: Tuesday's billing deploy broke checkout for forty minutes with no code change on our side: the image rebuild pulled corekit 1.3.0 from the company index, and 1.3.0 renamed a function billing calls. The worker traceback is preserved at incident/worker.log, and the freeze output from the last good image and from the broken one are incident/freeze-good.txt and incident/freeze-broken.txt. requirements.txt in the repository root is exactly what was deployed. Confirm what changed between the two images and why our requirements allowed it, and recommend how we should declare internal packages from now on.

**assistant [Read]**: 
> 1	click>=8.1
2	corekit>=1.2
3	requests>=2.31
4	rich>=13.7
5	

**assistant [Read]**: 
> 1	2026-08-04 10:12:33 billing-worker: processing order batch 4411
2	Traceback (most recent call last):
3	  File "/app/billing/orders.py", line 57, in build_reference
4	    reference = corekit.text.slugify_id(order.customer, order.number)
5	AttributeError: module 'corekit.text' has no attribute 'slugify_id'
6	2026-08-04 10:12:33 billing-worker: batch 4411 aborted, checkout returning 500
7	2026-08-04 10:52:41 deploy: rolled back to previous image, checkout recovered
8	

**assistant [Read]**: 
> 1	click==8.1.7
2	corekit==1.2.4
3	requests==2.31.0
4	rich==13.7.1
5	

**assistant [Read]**: 
> 1	click==8.1.7
2	corekit==1.3.0
3	requests==2.31.0
4	rich==13.7.1
5	

**assistant**: ## Incident Analysis

### What Happened

On **2026-08-04**, a billing deploy broke checkout for 40 minutes. The image rebuild pulled `corekit==1.3.0` from the company index, which had **renamed** (or removed) the `corekit.text.slugify_id` function that billing's `orders.py:57` called. No code changed on billing's side — only the image's frozen dependencies shifted.

| File | corekit version |
|---|---|
| `freeze-good.txt` (last good image) | **1.2.4** |
| `freeze-broken.txt` (broken image) | **1.3.0** |

### Why `requirements.txt` Allowed It

```
corekit>=1.2
```

This `>=` specifier places **no upper bound**. When the image was rebuilt, pip resolved `corekit>=1.2` to the latest available version — **1.3.0** — even though it contained a breaking change. Pip considers this a valid resolution because from pip's perspective, `1.3.0 >= 1.2` is true. It has no way to know the package author considers this a breaking release.

### The Root Cause

The implicit assumption behind `>=1.2` is that corekit follows **semantic versioning** (i.e., minor bumps are backward-compatible). That assumption was wrong — either:

- corekit **does not follow semver**, or
- the author treated `slugify_id`'s removal as a major break but cut a **minor release** by mistake.

Either way, billing's dependency declaration did not protect against it.

### Recommendation: Pin Internal Packages Exactly

For **internal / first-party packages** (like corekit), where you control the source and can't guarantee semver discipline, use **exact version pins** in `requirements.txt`:

```
corekit==1.2.4
```

This gives **deterministic builds** — every image build produces the same frozen dependencies. When you *intentionally* upgrade corekit, you bump the pin, review the diff, and test before deploying.

#### What About External Packages?

For **third-party packages** that *do* follow semver, `~=` (compatible release) is often appropriate:

```
click>=8.1,<9         # or  click~=8.1
requests>=2.31,<3     # or  requests~=2.31
rich>=13.7,<14        # or  rich~=13.7
```

Or if you want full determinism for everything, pin all packages exactly and use a tool like `pip-compile` / `dependabot` to manage upgrades.

#### Quick Fix for This Repo

Replace the open-ended corekit line:

```
corekit==1.2.4
```

(Or whatever current known-good version you validate against.)

### Summary

| What | Why |
|---|---|
| `corekit>=1.2` | Allowed the silent jump to 1.3.0 |
| corekit v1.3.0 | Renamed `slugify_id`, breaking billing |
| **Fix: pin exact versions** for internal packages | Prevents surprise breaking changes on rebuild |

**user**: Agreed. Decision: internal packages are pinned exactly in requirements.txt, == not >=, never a range. Pin corekit==1.2.4 now, and every internal package we add gets an exact pin the same way, so a breakage from an internal release can only reach us through an explicit version bump in this repo, not through a rebuild. Third-party ranges stay as they are.
