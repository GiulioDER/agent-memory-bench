# Hugging Face publication, prepared and not published

Source for two Hugging Face repositories. **Neither has been created or uploaded.**

| file | becomes |
|---|---|
| `dataset-card.md` | `README.md` of the dataset repo `GiulioDER/agent-memory-bench-corpus` |
| `space-card.md` | `README.md` of the static Space `GiulioDER/agent-memory-bench` |
| `PRE-UPLOAD.md` | the gate: two open decisions, then a checklist. Read it first. |

Assemble both payloads under `build/hf/`, which is gitignored:

```bash
python scripts/hf_stage.py --check
```

`--check` writes nothing. Without it the script stages the files and prints the two `hf upload`
commands rather than running them. It **refuses** if an unannounced product name reaches either
payload, which is the site's existing guard extended to cover this second published surface.

Why a dataset and a Space rather than a post: a benchmark spreads by being cited and by being
reachable from where people look for benchmarks, and neither of those needs an audience. The
dataset is the haystack every arm ingests; the Space is `site/` deployed verbatim, whose board is
empty by construction until the first preregistered multi-product run exists.

Task statements, checkers and reference solutions stay on GitHub on purpose. They are the graded
artifacts, and mirroring them onto a platform that is scraped for training data is how a benchmark
stops measuring anything.
