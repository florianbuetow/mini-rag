# Corpus Listing — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: GET /v1/corpora returns 200 with corpora array and descriptions map | TS-1: List corpora successfully |
| AC-1.2: Corpora sorted alphabetically | TS-2: Corpora returned in alphabetical order |
| AC-1.3: Each entry is a non-empty string | TS-1 (verified within) |
| AC-1.4: Unhealthy service returns 503 | TS-3: Reject request when service unhealthy |
| AC-1.5: Descriptions map matches corpora | TS-1, TS-4 |
| AC-1.6: Missing descriptions use placeholder | TS-5: Missing description placeholder |
| AC-2.1: Individual description endpoint returns Markdown | TS-6: Fetch one corpus description |
| AC-2.2: Individual missing description uses placeholder | TS-7: Fetch missing corpus description |
| AC-2.3: Invalid corpus name returns 400 | TS-8: Reject invalid corpus name |
| AC-2.4: Unknown corpus returns 404 | TS-9: Reject unknown corpus |
| AC-2.5: Stored description read failure returns 500 | TS-10: Stored description failure |
| AC-3.1: Just target stores canonical description | TS-11: Ingest corpus description |
| AC-3.2: Source file constraints enforced | TS-12: Reject invalid description sources |
| AC-3.3: Unknown corpora rejected at ingestion | TS-13: Reject unknown corpus during ingestion |
| AC-3.4: Description is not indexed or ledgered | TS-14: Description remains metadata |
| AC-3.5: Re-ingestion atomically replaces old text | TS-15: Replace description |
| AC-3.6: Index deletion/rebuild preserves description | TS-16: Preserve description across rebuild |
| EC: No corpora exist | TS-4: Return empty array when no corpora exist |

## Test Scenarios

### Happy Path

**TS-1: List corpora successfully**

```
Scenario: List available corpora
  Given the mini-rag service is running and healthy
  And corpora "alpha", "beta", "gamma" exist
  And corpus "alpha" has description "# Alpha"
  And corpus "beta" has no description
  And corpus "gamma" has description "Gamma notes"
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the response body contains {"status": 200, "data": {"corpora": ["alpha", "beta", "gamma"], "descriptions": {"alpha": "# Alpha", "beta": "No description available.", "gamma": "Gamma notes"}}}
  And each entry in the corpora array is a non-empty string
  And the description keys exactly match the corpora array values
```

**TS-2: Corpora returned in alphabetical order**

```
Scenario: Corpora are sorted alphabetically
  Given the mini-rag service is running and healthy
  And corpora "gamma", "alpha", "beta" exist (created in non-alphabetical order)
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the corpora array is ["alpha", "beta", "gamma"]
  And the description keys exactly match ["alpha", "beta", "gamma"]
```

### Edge Case Scenarios

**TS-3: Reject request when service unhealthy**

```
Scenario: Return 503 when service is not healthy
  Given the mini-rag service is running but not in "healthy" status
  When the client sends GET /v1/corpora
  Then the response status is 503
```

**TS-4: Return empty array when no corpora exist**

```
Scenario: Empty corpora list
  Given the mini-rag service is running and healthy
  And no corpora exist
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the response body contains {"status": 200, "data": {"corpora": [], "descriptions": {}}}
```

**TS-5: Missing description placeholder**

```
Scenario: Loaded corpus has no description file
  Given the mini-rag service is running and healthy
  And corpus "books" exists
  And corpus "books" has no data/storage/books/description.md file
  When the client sends GET /v1/corpora
  Then the response status is 200
  And data.descriptions.books is "No description available."
```

**TS-6: Fetch one corpus description**

```
Scenario: Individual corpus description is available
  Given the mini-rag service is running and healthy
  And corpus "books" exists
  And data/storage/books/description.md contains "# Books\nReference material."
  When the client sends GET /v1/corpus/books/description
  Then the response status is 200
  And the response body contains {"status": 200, "data": {"corpus": "books", "description": "# Books\nReference material."}}
```

**TS-7: Fetch missing corpus description**

```
Scenario: Individual corpus description is missing
  Given the mini-rag service is running and healthy
  And corpus "books" exists
  And corpus "books" has no data/storage/books/description.md file
  When the client sends GET /v1/corpus/books/description
  Then the response status is 200
  And data.description is "No description available."
```

**TS-8: Reject invalid corpus name**

```
Scenario: Individual description rejects invalid name
  Given the mini-rag service is running and healthy
  When the client sends GET /v1/corpus/invalid.name/description
  Then the response status is 400
```

**TS-9: Reject unknown corpus**

```
Scenario: Individual description rejects unknown loaded corpus
  Given the mini-rag service is running and healthy
  And corpus "books" does not exist
  When the client sends GET /v1/corpus/books/description
  Then the response status is 404
```

**TS-10: Stored description failure**

```
Scenario: Stored description cannot be read safely
  Given the mini-rag service is running and healthy
  And corpus "books" exists
  And data/storage/books/description.md is symlinked or invalid UTF-8
  When the client sends GET /v1/corpus/books/description
  Then the response status is 500
```

### Ingestion Scenarios

**TS-11: Ingest corpus description**

```
Scenario: Store a Markdown corpus description
  Given corpus "books" exists
  And ./corpus-description.md is a regular UTF-8 Markdown file containing "# Books"
  When the operator runs just describe-corpus books ./corpus-description.md
  Then data/storage/books/description.md contains "# Books"
```

**TS-12: Reject invalid description sources**

```
Scenario: Invalid Markdown source is rejected
  Given corpus "books" exists
  When the operator runs just describe-corpus books <invalid-source>
  Then the command exits non-zero
  And the previous data/storage/books/description.md content is unchanged
```

Invalid sources include symlinks, directories, non-`.md` files, invalid UTF-8 files, whitespace-only files, and files larger than 64 KiB.

**TS-13: Reject unknown corpus during ingestion**

```
Scenario: Description ingestion cannot create a corpus
  Given corpus "unknown" does not exist
  And ./corpus-description.md is a valid Markdown file
  When the operator runs just describe-corpus unknown ./corpus-description.md
  Then the command exits non-zero
  And data/storage/unknown/description.md does not exist
```

**TS-14: Description remains metadata**

```
Scenario: Description is not indexed or ledgered
  Given corpus "books" exists
  And a valid description has been ingested
  When the operator searches for text that appears only in data/storage/books/description.md
  Then the text is not returned as a search result
  And data/storage/books/indexed.txt does not contain description.md
```

**TS-15: Replace description**

```
Scenario: Re-ingestion replaces the previous description
  Given corpus "books" exists
  And data/storage/books/description.md contains "Old"
  When the operator runs just describe-corpus books ./new-description.md
  Then data/storage/books/description.md contains the full content of ./new-description.md
```

**TS-16: Preserve description across rebuild**

```
Scenario: Corpus description survives index deletion and rebuild
  Given corpus "books" exists
  And data/storage/books/description.md contains "# Books"
  When the operator deletes or rebuilds the corpus index
  Then data/storage/books/description.md still contains "# Books"
```

**TS-17: Show current description without a file argument**

```
Scenario: Read a corpus description from the operator command
  Given corpus "books" exists
  And data/storage/books/description.md contains "# Books"
  When the operator runs just describe-corpus books
  Then standard output is "# Books"
```

## Traceability

All acceptance criteria (AC-1.1 through AC-3.6) and the edge case (no corpora) are covered by test scenarios TS-1 through TS-17. No coverage gaps.
