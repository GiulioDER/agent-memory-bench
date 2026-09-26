# Diagrams

`amb-pipeline.graph.json` is the source. It is a
[gitdiagram](https://github.com/ahmedkhaleel2004/gitdiagram) graph, validated and compiled with
gitdiagram's own `validateDiagramGraph` and `compileDiagramGraph` (`src/server/generate/graph.ts`),
so every node `path` was checked against this repository's file tree at compile time.
`amb-pipeline.svg` and `amb-pipeline.png` are Mermaid 11 renders of the compiled output, laid out
top to bottom.

To regenerate: edit the graph JSON, never the render. Compile it against `git ls-files` plus its
directories, then render the Mermaid. The compiler emits `flowchart TD`; the published render keeps
it.
