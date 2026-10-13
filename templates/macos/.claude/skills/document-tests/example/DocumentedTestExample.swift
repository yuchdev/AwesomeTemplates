// Reference specimen for /document-tests - the DocC-comment format, one per
// classification. The Swift twin of DocumentedTestExample.cpp.
//
// This is a *teaching example*, not a collected test: it lives under `.claude/`,
// outside any real `Tests/` directory, and its filename does not match any
// pattern `scripts/document_tests.py` discovers (`*Tests.swift`, `*Test.swift`,
// `*IT.swift`), so neither a build tool nor the codemod ever touches it.
//
// Each case below shows two things at once:
//
//   1. the structural signal `scripts/document_tests.py` keys on to classify
//      it, and
//   2. the exact `///` comment the codemod emits, as described in
//      `../references/classification-guide.md`.
//
// Doc-comment contract (enforced by the codemod's title regex
// `^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$`):
//
//   [<Class>] <context>: verifies <one sentence ending in a period>.
//
//   Scenario: ...
//   Boundaries: ...
//   On failure, first check: ...
//
// `WidgetKit` is a deliberately fictional module so nothing here looks like it
// should resolve against your own code. Copy the *shape* - the comments - not
// the names.
//
// Classification is decided by directory/filename first, then body markers. In
// a real project each case would live in its own conventional location
// (`Tests/WidgetKitTests/`, `Tests/WidgetKitIntegrationTests/`,
// `Tests/WidgetKitUITests/`) and the directory signal alone would settle it.

import Testing
import XCTest

@testable import WidgetKit

// ----------------------------------------------------------------------- //
// [Unit] - pure logic, no test doubles, no I/O. Signal: no mock/process markers.
// ----------------------------------------------------------------------- //
final class StreakCalculatorTests: XCTestCase {
    /// [Unit] streak calculator: verifies missed day resets streak to zero.
    ///
    /// Scenario:
    ///   - Given a current streak of 5 and a 2-day gap
    ///   - When StreakCalculator.nextStreak(current: 5, gapDays: 2) executes
    ///   - Then the result is confirmed to be 0
    ///
    /// Boundaries:
    ///   - Focus: the gap-resets-streak branch of nextStreak
    ///   - Fixtures/params: none
    ///   - Scope: pure function, no I/O
    ///
    /// On failure, first check:
    ///   - The gap-day threshold compared against inside StreakCalculator.nextStreak
    func testMissedDayResetsStreakToZero() {
        XCTAssertEqual(StreakCalculator.nextStreak(current: 5, gapDays: 2), 0)
    }
}

// ----------------------------------------------------------------------- //
// [Mock] - unit-scoped, but a collaborator is replaced by a hand-written test
// double. Signal: a `Mock…`/`Fake…`/`Stub…`/`Spy…` type in the test body.
// Swift has no mocking framework in the toolchain, so the codemod keys on
// that naming convention - name your doubles accordingly.
// ----------------------------------------------------------------------- //
private final class MockProofRepository: ProofRepository {
    private(set) var rejectedIDs: [String] = []

    func find(id: String) async throws -> Proof? { Proof.pending(id: id) }
    func markRejected(id: String) async throws { rejectedIDs.append(id) }
}

struct ProofReviewerTests {
    /// [Mock] proof reviewer: verifies rejecting a proof marks it rejected in the repository.
    ///
    /// Scenario:
    ///   - Given a repository double that returns a pending proof for "abc123"
    ///   - When ProofReviewer.reject(id: "abc123") executes
    ///   - Then the result is confirmed by the double recording "abc123" as rejected
    ///
    /// Boundaries:
    ///   - Focus: ProofReviewer.reject's delegation to the repository
    ///   - Fixtures/params: repository (test double)
    ///   - Scope: only ProofReviewer runs for real; the repository is MockProofRepository
    ///
    /// On failure, first check:
    ///   - Whether ProofReviewer.reject still calls markRejected rather than deleting the proof
    @Test func rejectingProofMarksItRejectedInRepository() async throws {
        let repository = MockProofRepository()

        try await ProofReviewer(repository: repository).reject(id: "abc123")

        #expect(repository.rejectedIDs == ["abc123"])
    }
}

// ----------------------------------------------------------------------- //
// [Integration] - two+ real components wired together, external edge
// sandboxed. Signal: lives under `Tests/…IntegrationTests/` (or an
// `integration` directory); no process/network markers in the body.
// ----------------------------------------------------------------------- //
final class GoalStoreIntegrationTests: XCTestCase {
    /// [Integration] goal store: verifies a saved goal reloads by goal id.
    ///
    /// Scenario:
    ///   - Given a real InMemoryGoalStore and a real GoalMapper wired together
    ///   - When a Goal is saved and then reloaded by id "goal-1"
    ///   - Then the reloaded Goal is confirmed to equal the one that was saved
    ///
    /// Boundaries:
    ///   - Focus: GoalStore + GoalMapper round trip
    ///   - Fixtures/params: none
    ///   - Scope: real store and mapper; no test doubles, no filesystem I/O
    ///
    /// On failure, first check:
    ///   - Whether GoalMapper.toRecord / fromRecord round-trip lost a field
    func testRoundTripsByGoalID() async throws {
        let store = InMemoryGoalStore(mapper: GoalMapper())
        let goal = Goal(id: "goal-1", title: "Run 5k")

        try await store.save(goal)
        let reloaded = try await store.find(id: "goal-1")

        XCTAssertEqual(reloaded, goal)
    }
}

// ----------------------------------------------------------------------- //
// [E2E] - a full user-facing journey driven end to end. Signal: lives under
// `Tests/…UITests/` and/or the body drives `XCUIApplication`, spawns a
// `Process`, or opens a real `URLSession.shared` request.
// ----------------------------------------------------------------------- //
final class LaunchUITests: XCTestCase {
    /// [E2E] launch: verifies the main window appears after app launch.
    ///
    /// Scenario:
    ///   - Given the built application bundle
    ///   - When it is launched through XCUIApplication
    ///   - Then the main window is confirmed to exist within the launch timeout
    ///
    /// Boundaries:
    ///   - Focus: application launch and first-window presentation
    ///   - Fixtures/params: none
    ///   - Scope: the whole app runs for real in its own process; nothing is substituted
    ///
    /// On failure, first check:
    ///   - Whether the app crashes in `applicationDidFinishLaunching` or its first scene's `.task`
    func testLaunchShowsMainWindow() {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.windows.firstMatch.waitForExistence(timeout: 10))
    }
}
