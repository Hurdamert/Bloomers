# Bloomers

Bloomer is a small Windows macro for farming tower XP in the Steam version of Bloons TD 6. It starts Easy Standard games, fills the map with one selected non-hero tower, buys randomized valid two-path builds, and restarts after victory or defeat.

Land towers use Monkey Meadow. Monkey Sub, Monkey Buccaneer, and Mermonkey use Spice Islands. Banana Farm and Monkey Village receive a small Dart/Bomb defense so their games can progress.

## Quick start

1. Install [Python 3.11 or newer](https://www.python.org/downloads/windows/) and enable **Add python.exe to PATH** or **Install launcher for all users** during installation.
2. Clone this repository and enter its directory:

   ```powershell
   git clone https://github.com/Hurdamert/Bloomers.git
   cd Bloomers
   ```

3. In BTD6, open **Settings > Controls** and use **Click & Drop** tower placement. Placement hotkeys do not reliably work with Drag & Drop.
4. Keep the standard tower and upgrade bindings. The macro expects comma, period, and slash for top, middle, and bottom upgrades.
5. BTD6 does not assign default placement keys to Mermonkey or Desperado. If farming either one, open **Settings > Hotkeys** and bind the same key shown in Bloomer. The suggested keys are `P` and `[`, respectively.
6. Double-click `run_bloomer.bat`. It automatically finds `py`, `python`, or `python3`. You can also run `python bloomer.py` from PowerShell.
7. Return to the BTD6 main menu, choose a tower in Bloomer, set **Cycles** to `1` for the first test, and click **Start farming**.

After confirming one cycle works, set **Cycles** to `0` for continuous farming. Press **F8** at any time for an emergency stop.

Bloomer has no third-party runtime dependencies. Keyboard and mouse actions use Windows `SendInput`, so BTD6 receives tower hotkeys, upgrade hotkeys, and explicit left-click placement events reliably.

Bloomer minimizes itself, locates the BTD6 client area, searches for the exact target map by name, and scales normalized coordinates to the actual window. The width and height fields are only a fallback if the window title cannot be found.

## How the loop works

- The selected tower is tried before any helper is purchased.
- If it is initially unaffordable, one cheap Dart Monkey starts the game.
- Farms and Villages can receive a Dart and Bomb helper; target-tower spending remains the priority.
- Every target gets one of six randomly selected builds: `420`, `402`, `240`, `042`, `204`, or `024` by default.
- Curated Monkey Meadow points favor grass close to the road while excluding known road locations. Every placement attempt sends an explicit left click before the macro evaluates whether it succeeded.
- Visual change detection confirms placements and upgrades, so failed purchases caused by insufficient cash are retried later.
- Paired Space presses use a transition delay so a paused round reliably starts and enters fast-forward without changing the speed of a round already in progress.
- A visual detector distinguishes the blue Victory and Defeat dialogs. Defeat uses Restart; victory uses Home and begins the navigation flow again.

The activity log shows every confirmed placement, upgrade, and detected end screen.

## Resolution and calibration

The included profile was measured from the supplied 1920x1200 screenshots and uses normalized positions, so it scales to other 16:9 and 16:10 resolutions. UI layout changes, unusual aspect ratios, and cosmetic themes may still move a control.

Use **Calibrate points...** to record navigation and end-screen buttons for another layout. The map-search button and its top-center text field are separate calibration targets. Select an item, click Capture, then put the mouse over the corresponding BTD6 control within four seconds.

**Command delay** controls the pause between closely related inputs, such as selecting a tower, left-clicking its location, and cancelling the placement cursor. Increase it if BTD6 misses clicks or keys. **Action interval** controls the pause between placement/upgrade decisions during a running round.

Advanced timing, detection thresholds, and placement lists live in [`config.json`](config.json). The application creates or updates that file without discarding newly added defaults.

## Important limits

- Unlock the selected tower and its upgrades before farming it.
- Leave BTD6 on its main menu before starting.
- Do not move the mouse or type while the macro is active.
- The profile deliberately never clicks the paid Continue button on defeat.
- Visual automation can break after a BTD6 UI update. Test one finite cycle before leaving it unattended.
- Use it only for ordinary single-player play where automation is permitted. Do not use it in co-op, races, ranked events, or leaderboards.

## Tests

The pure state/detection helpers have dependency-light unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
