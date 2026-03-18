# Integration: Auto-Launch — Test Specification

## Coverage Matrix

| Spec Requirement | Test Scenario(s) |
|-----------------|------------------|
| AC-1.1: just start serves Chat UI on port 9191 | TS-1: Service starts on port 9191 |
| AC-1.2: GET / loads Chat UI | TS-2: Root URL serves Chat UI |
| AC-1.3: API endpoints on same port | TS-3: API endpoints accessible on 9191 |
| AC-1.4: No additional manual steps | TS-1 (verified by start sequence) |
| AC-2.1: Stop shuts down both API and static serving | TS-4: Service stops cleanly |
| AC-2.2: Port 9191 freed after stop | TS-4 (verified within) |
| EC: Port 9191 already in use | TS-5: Port conflict error |
| EC: web/ directory missing | TS-6: Start without web/ directory |

## Test Scenarios

### Happy Path

**TS-1: Service starts on port 9191**

```
Scenario: Mini-rag service starts and listens on port 9191
  Given port 9191 is available
  When the mini-rag service is started
  Then the service is listening on port 9191
  And GET http://localhost:9191/v1/health returns 200
```

**TS-2: Root URL serves Chat UI**

```
Scenario: Browser can access Chat UI at root URL
  Given the mini-rag service is running on port 9191
  When the client sends GET http://localhost:9191/
  Then the response status is 200
  And the response content type is text/html
  And the response body contains the Chat UI page
```

**TS-3: API endpoints accessible on 9191**

```
Scenario: API endpoints work on the same port as the Chat UI
  Given the mini-rag service is running on port 9191
  When the client sends GET http://localhost:9191/v1/corpora
  Then the response status is 200
  And the response body contains a corpora array
```

**TS-4: Service stops cleanly**

```
Scenario: Stopping the service frees port 9191
  Given the mini-rag service is running on port 9191
  When the service is stopped
  Then port 9191 is no longer in use
  And GET http://localhost:9191/ fails to connect
```

### Edge Case Scenarios

**TS-5: Port conflict error**

```
Scenario: Service fails to start when port 9191 is occupied
  Given port 9191 is already in use by another process
  When the mini-rag service attempts to start
  Then the service fails to start
  And an error message indicates port 9191 is occupied
```

**TS-6: Start without web/ directory**

```
Scenario: Service starts without web/ directory, API still works
  Given the web/ directory does not exist
  When the mini-rag service is started
  Then the service starts successfully
  And GET http://localhost:9191/v1/health returns 200
  And GET http://localhost:9191/ returns 404
```

## Traceability

All acceptance criteria (AC-1.1 through AC-2.2) and all edge cases are covered by test scenarios TS-1 through TS-6. No coverage gaps.
