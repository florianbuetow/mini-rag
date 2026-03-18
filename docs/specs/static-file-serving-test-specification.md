# Static File Serving — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: GET / returns web/index.html | TS-1: Serve index.html at root |
| AC-1.2: GET /css/<file> returns CSS files | TS-2: Serve CSS files |
| AC-1.3: GET /gfx/<file> returns image files | TS-3: Serve image files |
| AC-1.4: Files served from web/ directory | TS-1, TS-2, TS-3 (verified by serving correct content) |
| AC-2.1: GET /nonexistent.html returns 404 | TS-4: Return 404 for non-existent root file |
| AC-2.2: GET /css/nonexistent.css returns 404 | TS-5: Return 404 for non-existent CSS file |
| C: API routes take precedence over static | TS-6: API routes take precedence over static files |
| EC: web/ directory missing | TS-7: Service works without web/ directory |
| EC: Path traversal attempts | TS-8: Reject path traversal attempts |

## Test Scenarios

### Happy Path

**TS-1: Serve index.html at root**

```
Scenario: Serve the main HTML page
  Given the mini-rag service is running
  And web/index.html exists with content "<html>Chat UI</html>"
  When the client sends GET /
  Then the response status is 200
  And the response content type is text/html
  And the response body contains "Chat UI"
```

**TS-2: Serve CSS files**

```
Scenario: Serve a CSS file from web/css/
  Given the mini-rag service is running
  And web/css/style.css exists with content "body { color: red; }"
  When the client sends GET /css/style.css
  Then the response status is 200
  And the response content type includes text/css
  And the response body contains "body { color: red; }"
```

**TS-3: Serve image files**

```
Scenario: Serve an image file from web/gfx/
  Given the mini-rag service is running
  And web/gfx/logo.png exists as a valid PNG file
  When the client sends GET /gfx/logo.png
  Then the response status is 200
  And the response content type includes image/png
```

### Error Scenarios

**TS-4: Return 404 for non-existent root file**

```
Scenario: Non-existent file at root returns 404
  Given the mini-rag service is running
  When the client sends GET /nonexistent.html
  Then the response status is 404
```

**TS-5: Return 404 for non-existent CSS file**

```
Scenario: Non-existent CSS file returns 404
  Given the mini-rag service is running
  When the client sends GET /css/nonexistent.css
  Then the response status is 404
```

### Constraint Scenarios

**TS-6: API routes take precedence over static files**

```
Scenario: API route is not shadowed by static files
  Given the mini-rag service is running and healthy
  When the client sends GET /v1/corpora
  Then the response status is 200
  And the response body contains a JSON object with "corpora" key
```

### Edge Case Scenarios

**TS-7: Service works without web/ directory**

```
Scenario: Service starts when web/ directory is missing
  Given the mini-rag service is running
  And the web/ directory does not exist
  When the client sends GET /
  Then the response status is 404
  And the API endpoints remain functional (GET /v1/health returns 200)
```

**TS-8: Reject path traversal attempts**

```
Scenario: Path traversal is rejected
  Given the mini-rag service is running
  When the client sends GET /../../etc/passwd
  Then the response status is 404 or 400
  And no file content from outside web/ is returned
```

## Traceability

All acceptance criteria (AC-1.1 through AC-2.2), constraints (API precedence), and edge cases (missing web/ directory, path traversal) are covered. No coverage gaps.
