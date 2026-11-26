# Answer-quality evaluation design

Approved 2026-11-25. This developer-only suite evaluates the advice a person actually receives, independently of retrieval diagnostics and the application's own release checks.

Keep the 22 original request bodies, including frozen historical follow-ups. Add separately identified live follow-ups and boundary scenarios. Cases carry versioned rubrics with required useful actions, prohibited instructions, conditions, and dated primary references. Historical cases are regression data, not a holdout.

Capture exact requests, displayed answers, source passages, terminal events, timing, and available provenance. Distinguish incomplete generation and transport failures from withholding. Repeated trials never overwrite one another. Import historical captures without inferring missing deployment identity. Git stores compact historical baselines; fresh runs remain local unless explicitly selected as evidence.

Automated checks cover stream completion and citation identity only. Evidence-based assessments cover usefulness, unsafe instructions, semantic citation support/applicability, and unnecessary withholding. Accept safe paraphrases. Missing reviews and uncertain findings are visible and cannot yield a passing gate. Bind reviews to exact captured content and rubric hashes. Hidden drafts cannot establish whether a rejection was justified. Review displayed fallbacks for usefulness even when the draft is withheld.

Reports compare exact matched requests, list unmatched cases, separate each quality dimension, and include evidence excerpts and uncertainty. No blended score offsets serious safety errors. Report coverage and denominators. First-token latency is not time to useful advice. No claim of clinical certification or causal attribution from one stochastic run.

Use Python standard library only. Keep suite, rubrics, baselines, and documentation beneath tests/ so existing export-ignore rules exclude them from ZIP/tar installation downloads. Git clones retain them. No production dependency or answer-policy changes. CI verifies the harness and archive exclusion; live model evaluation is explicit.
