/**
 * Reference specimen for /document-tests - the Javadoc format, one per class.
 *
 * <p>This is a <em>teaching example</em>, not a collected test (it lives under
 * {@code .claude/}, outside any real {@code src/test/java} or
 * {@code src/androidTest/java} source set, so no build tool ever compiles or
 * runs it). Each method below shows two things at once:
 *
 * <ol>
 *   <li>the structural signal {@code scripts/document_tests.py} keys on to classify it, and
 *   <li>the exact Javadoc the codemod emits and that
 *       {@code ../references/classification-guide.md} describes.
 * </ol>
 *
 * <p>Javadoc contract (enforced by the codemod's title regex
 * {@code ^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$}):
 *
 * <pre>
 * [&lt;Class&gt;] &lt;context&gt;: verifies &lt;one sentence ending in a period&gt;.
 *
 * Scenario: ...
 * Boundaries: ...
 * On failure, first check: ...
 * </pre>
 *
 * <p>The package below, {@code com.example.habittracker}, is a deliberately
 * fictional habit-tracking app so nothing here looks like it should resolve
 * against your own code. Read the <em>shape</em> - a real test importing the
 * class under test, asserting on real behavior - and copy the Javadocs, not
 * the package name.
 *
 * <p>Note on classification: the codemod decides by <b>source-set directory
 * first, then body markers</b>. This file sits in an unrecognised directory, so
 * the codemod would tag every method below {@code ambiguous} and fall back to
 * the body signal alone - exactly the situation where a human uses the
 * semantic definitions in the classification guide. In a real project each of
 * these four methods would instead live in its own conventional source set
 * ({@code src/test/java}, {@code src/integrationTest/java}, or
 * {@code src/androidTest/java}) and the directory signal alone would settle it.
 */
package com.example.habittracker;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;

import androidx.test.core.app.ActivityScenario;
import org.junit.Test;

public class DocumentedTestExample {

    // ----------------------------------------------------------------- //
    // [Unit] - pure logic, no mocks, no I/O. Signal: no mock/instrumentation markers.
    // ----------------------------------------------------------------- //
    /**
     * [Unit] streak calculator: verifies a missed day resets the streak to zero.
     *
     * <p>Scenario:
     * <ul>
     *   <li>Given a StreakCalculator with a current streak of 5 and a 2-day gap
     *   <li>When StreakCalculator.nextStreak(5, gapDays = 2) executes
     *   <li>Then the result is confirmed to be 0
     * </ul>
     *
     * <p>Boundaries:
     * <ul>
     *   <li>Focus: the gap-resets-streak branch of nextStreak
     *   <li>Fixtures/params: none
     *   <li>Scope: pure function, no I/O
     * </ul>
     *
     * <p>On failure, first check:
     * <ul>
     *   <li>The gap-day threshold compared against inside StreakCalculator.nextStreak
     * </ul>
     */
    @Test
    public void testMissedDayResetsStreakToZero() {
        assertEquals(0, StreakCalculator.nextStreak(5, 2));
    }

    // ----------------------------------------------------------------- //
    // [Mock] - unit-scoped, but a collaborator is mocked. Signal: Mockito markers.
    // ----------------------------------------------------------------- //
    /**
     * [Mock] proof review: verifies rejecting a proof calls the repository's reject method.
     *
     * <p>Scenario:
     * <ul>
     *   <li>Given a ProofRepository mocked to return a pending proof for "abc123"
     *   <li>When ProofReviewer.reject(repository, "abc123") executes
     *   <li>Then the result is confirmed by verifying repository.markRejected("abc123") was called
     * </ul>
     *
     * <p>Boundaries:
     * <ul>
     *   <li>Focus: ProofReviewer.reject's delegation to the repository
     *   <li>Fixtures/params: repository (mocked)
     *   <li>Scope: only ProofReviewer runs for real; the repository it calls is a Mockito mock
     * </ul>
     *
     * <p>On failure, first check:
     * <ul>
     *   <li>Whether ProofReviewer.reject still calls markRejected rather than delete
     * </ul>
     */
    @Test
    public void testRejectingProofCallsRepositoryMarkRejected() {
        ProofRepository repository = mock(ProofRepository.class);
        when(repository.findById("abc123")).thenReturn(Proof.pending("abc123"));

        new ProofReviewer(repository).reject("abc123");

        org.mockito.Mockito.verify(repository).markRejected("abc123");
    }

    // ----------------------------------------------------------------- //
    // [Integration] - two+ real components wired together, external edge sandboxed.
    // Signal: filename would end "IT.java" in a real project; no mock/instrumentation markers.
    // ----------------------------------------------------------------- //
    /**
     * [Integration] goal store: verifies a saved goal reloads by goal id.
     *
     * <p>Scenario:
     * <ul>
     *   <li>Given a real InMemoryGoalStore and a real GoalMapper wired together
     *   <li>When a Goal is saved and then reloaded by id "goal-1"
     *   <li>Then the reloaded Goal is confirmed to equal the one that was saved
     * </ul>
     *
     * <p>Boundaries:
     * <ul>
     *   <li>Focus: GoalStore + GoalMapper round trip
     *   <li>Fixtures/params: none
     *   <li>Scope: real store and mapper; no repository mocks, no device I/O
     * </ul>
     *
     * <p>On failure, first check:
     * <ul>
     *   <li>Whether GoalMapper.toEntity / fromEntity round-trip lost a field
     * </ul>
     */
    @Test
    public void testGoalStoreRoundTripByGoalId() {
        InMemoryGoalStore store = new InMemoryGoalStore(new GoalMapper());
        Goal goal = new Goal("goal-1", "Run 5k");

        store.save(goal);
        Goal reloaded = store.findById("goal-1");

        assertEquals(goal, reloaded);
    }

    // ----------------------------------------------------------------- //
    // [E2E] - a full user-facing journey driven end to end. Signal: Espresso/ActivityScenario.
    // ----------------------------------------------------------------- //
    /**
     * [E2E] goal creation flow: verifies creating a goal shows it in the activity list.
     *
     * <p>Scenario:
     * <ul>
     *   <li>Given GoalCreationActivity launched via ActivityScenario
     *   <li>When the user fills the goal name field and taps save via Espresso
     *   <li>Then the activity list view is confirmed to display the new goal
     * </ul>
     *
     * <p>Boundaries:
     * <ul>
     *   <li>Focus: goal creation UI flow through to the activity list
     *   <li>Fixtures/params: none
     *   <li>Scope: the whole screen-to-screen journey runs for real on-device/emulator
     * </ul>
     *
     * <p>On failure, first check:
     * <ul>
     *   <li>Whether the save button's onClick still navigates to the activity list
     * </ul>
     */
    @Test
    public void testCreatingGoalShowsItInActivityList() {
        try (ActivityScenario<GoalCreationActivity> scenario =
                ActivityScenario.launch(GoalCreationActivity.class)) {
            onView(withId(R.id.goalNameField)).perform(click());
            onView(withId(R.id.saveButton)).perform(click());
            onView(withId(R.id.activityListItem)).check(matches(isDisplayed()));
        }
    }
}
