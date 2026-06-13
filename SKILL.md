---
name: literature-rename
description: Batch rename local literature, paper, article, book, PDF, and DOCX files so filenames contain the document title. Use when Codex is asked to rename academic references, English/Chinese literature folders, cryptic DOI/SSRN/download filenames, translated or bilingual copies, or to generate and apply a safe rename ledger with logs.
---

# Literature Rename

## Workflow

Use a ledger-first, action-second process unless the user explicitly says to directly modify files. Even with direct permission, build a final plan and run a dry-run before executing.

1. Inventory the target folder recursively, excluding work/output folders such as `rename_work`, `.git`, `.codex`, and `.agents`.
2. Generate a rename plan for `.pdf` and `.docx` files. Use `scripts/build_rename_plan.py` when helpful.
3. Prefer stable titles in this order:
   - Explicit overrides supplied or created by Codex.
   - A reliable title in PDF/DOCX metadata.
   - A clearly readable existing filename after cleaning punctuation and suffixes.
   - A first-page title block only when the filename is cryptic and the extracted line is not a header, citation, author list, abstract sentence, table of contents, or OCR boilerplate.
4. For translated or bilingual files, copy the base title from the matching original file and append one of:
   - `（翻译结果）` for names containing `翻译结果`
   - `（译文）` for names containing `translated`
   - `（双语）` for names containing `billingual` or `bilingual`
   - `（中文版）` for Chinese editions
5. Inspect all plan rows marked `needs_review=true`, plus any final names containing suspicious fragments such as `Citation`, `QR Code`, `Columbia Law School`, `Preliminary`, `Abstract`, `Keywords`, `unknown Seq`, or a complete sentence.
6. Create or update an override CSV for every doubtful row. Do not let body text, footnotes, author affiliations, journal volume strings, or table-of-contents entries become filenames.
7. Run a dry-run execution. Continue only when target count matches source count and there are zero errors.
8. Execute the final plan with `scripts/apply_rename_plan.py --execute`.
9. Verify:
   - original literature file count equals final literature file count
   - every planned target exists
   - there are no extra unexpected PDF/DOCX filenames
   - the action log contains no `error` rows

## Scripts

Use the bundled scripts from this skill directory:

```powershell
python scripts/build_rename_plan.py --root "C:\path\to\folder"
python scripts/build_rename_plan.py --root "C:\path\to\folder" --overrides "C:\path\to\overrides.csv"
python scripts/apply_rename_plan.py --plan "C:\path\to\rename_work\literature_rename_plan.csv"
python scripts/apply_rename_plan.py --plan "C:\path\to\rename_work\literature_rename_plan.csv" --execute
```

Override CSV columns:

- `original_name`: exact current filename, or leave blank when using `key`
- `key`: normalized base key such as `ssrn 1143343`
- `title`: title stem without extension or variant tag
- `final_name`: optional full filename; when present it wins over `title`

## Title Rules

Treat these as high-risk and review or override:

- filenames made only from DOI, SSRN, arXiv, database IDs, journal page citations, or short author abbreviations
- PDF text extraction lines from HeinOnline, SSRN, JSTOR, journal headers, OCR warnings, or downloaded-print pages
- lines beginning with article body text, such as `This paper`, `This article`, `We develop`, `A half century`, or quoted abstract text
- titles truncated by line breaks; join the full title manually
- near-duplicates where one file is original and another is translated or bilingual

When in doubt, keep a conservative cleaned filename instead of inventing a title. If the user has authorized direct modification, Codex should resolve doubtful titles itself from document text/metadata and the surrounding corpus rather than stopping for confirmation.

## Safety Rules

- Never delete source documents as part of this skill.
- Never overwrite an existing target. Add numeric suffixes for genuine duplicate titles.
- Handle Windows case-only renames with a temporary filename.
- Keep generated ledgers and logs in `rename_work` or an equivalent work folder under the target root.
- Preserve exact file extensions, using lowercase `.pdf` and `.docx` only when renaming.
