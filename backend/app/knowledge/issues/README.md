# Known-issues knowledge base

One YAML file per model or per engine/powertrain family. Loaded by `app/knowledge/service.py`.

```yaml
id: unique-file-id
title: Human title
summary: Short Dutch summary shown on the model page
applies_to:                      # file-level targets (canonical slugs from normalize/taxonomy.yaml)
  - {make: peugeot, model: "208"}
battery_warranty: {years: 8, km: 160000, min_soh_pct: 70, note: "..."}   # optional (EV/PHEV)
general_checks: ["..."]           # optional extra checks for the viewing checklist
issues:
  - id: unique-issue-id
    title: Dutch title
    applies_to: [...]             # optional, overrides file-level targets for this issue
    generations: [golf-7]         # optional, generation ids from the taxonomy
    years: [2012, 2023]           # optional, first-registration year range (null = open)
    fuels: [benzine]              # optional
    engine:                       # optional; matched against title/trim and engine_cc/power_kw
      keywords: ["1.2", "puretech"]
      exclude_keywords: ["hybrid"]
      cc: [1150, 1250]
      kw: [50, 100]
    severity: low | medium | high | critical
    likelihood: low | medium | high          # how common among affected cars
    category: motor | transmissie | ophanging | elektrisch | accu | carrosserie | ...
    summary: ...
    symptoms: [...]
    repair_cost_eur: [min, max]   # only when a source gives a figure (otherwise severity-based)
    fix:
      type: recall | campaign | revised_part | software | warranty_extension | maintenance | none
      description: ...
      rdw_recall_keywords: [...]  # matched against RDW recall descriptions for "repaired?" status
    verify: [...]                 # how to check whether it was fixed
    questions: [...]              # what to ask the seller (Dutch)
    test_drive: [...]
    sources: [{title: ..., url: ...}]   # at least one, always
    reviewed: 2026-10-27
```

Rules: every issue needs at least one source; say so in `summary` when evidence is thin, anecdotal
or from another market; prefer official sources (RDW, manufacturer, ANWB, consumer organisations).
Quote any string that contains `: ` (`- "Na de rit: geen waarschuwingen?"`); unquoted, YAML turns it into a
mapping. `tests/test_knowledge.py` validates every file and catches this.
