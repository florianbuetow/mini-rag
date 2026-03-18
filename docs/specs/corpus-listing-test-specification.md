# Corpus Listing — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: GET /v1/corpora returns 200 with corpora array | TS-1: List corpora successfully |
| AC-1.2: Corpora sorted alphabetically | TS-2: Corpora returned in alphabetical order |
| AC-1.3: Each entry is a non-empty string | TS-1 (verified within) |
| AC-1.4: Unhealthy service returns 503 | TS-3: Reject request when service unhealthy |
| EC: No corpora exist | TS-4: Return empty array when no corpora exist |

## Test Scenarios

### Happy Path

**TS-1: List corpora successfully**

```
Scenario: List available corpora
  Given the mini-rag service is running and healthy
  And corpora "alpha", "beta", "gamma" exist
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the response body contains {"status": "success", "data": {"corpora": ["alpha", "beta", "gamma"]}}
  And each entry in the corpora array is a non-empty string
```

**TS-2: Corpora returned in alphabetical order**

```
Scenario: Corpora are sorted alphabetically
  Given the mini-rag service is running and healthy
  And corpora "gamma", "alpha", "beta" exist (created in non-alphabetical order)
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the corpora array is ["alpha", "beta", "gamma"]
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
  And the response body contains {"status": "success", "data": {"corpora": []}}
```

## Traceability

All acceptance criteria (AC-1.1 through AC-1.4) and the edge case (no corpora) are covered by test scenarios TS-1 through TS-4. No coverage gaps.
